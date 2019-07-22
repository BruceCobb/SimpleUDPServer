# -*- coding：utf-8 -*-

from bitarray import bitarray
from threading import Timer
import requests
import socketserver
import queue
import logging
import os
import datetime
import time

ti = datetime.datetime.now()
logging.basicConfig(format='%(asctime)s - %(levelname)s: %(message)s', level=logging.DEBUG,
                    filename='meshserver-{}-{}-{}.log'.format(ti.year, ti.month, ti.day))

# 回复队列
response_queue = queue.Queue()

# 存储回复分包数据
response_packs = dict()

# 存储请求分包数据
requests_packs = dict()


def demo_message():
    """return the messages of testing"""
    with open('demomessage', 'r', encoding='utf-8') as f:
        mes = f.read()
    return bytes(mes, 'utf-8')


def remove_log():
    """remove expire logs"""
    for parent, dirnames, filenames in os.walk(os.getcwd()):
        for filename in filenames:
            if '.log' in filename:
                fullname = parent + "/" + filename
                createTime = int(os.path.getctime(fullname))
                nDayAgo = (datetime.datetime.now() - datetime.timedelta(days=7))
                timeStamp = int(time.mktime(nDayAgo.timetuple()))
                if createTime < timeStamp:
                    os.remove(os.path.join(parent, filename))


def response_message_task():
    """server sends message to client ever 0.05 second"""
    # logging.debug("当前线程数量：{}".format(len(threading.enumerate())))

    pack = response_queue.get()
    pack[0].sendto(pack[2], pack[1])
    logging.debug("回复的信息为：{}".format(pack[2]))

    global response_timer
    response_timer = Timer(0.05, response_message_task)
    response_timer.start()


def remove_packs_task():
    """server deletes packs when over 2 minutes"""
    # logging.debug("当前线程数量：{}".format(len(threading.enumerate())))

    for i in list(response_packs.keys()):
        if time.time() - response_packs[i][0] > 120:
            # response_packs.pop(bytes(i))
            logging.info("全部的值：{}".format(response_packs.keys()))
            logging.info("超时删除设备ID：{}".format(i))
            del response_packs[bytes(i)]

    for j in list(requests_packs.keys()):
        if time.time() - requests_packs[j][0] > 120:
            # response_packs.pop(bytes(j))
            logging.info("全部的值：{}".format(requests_packs.keys()))
            logging.info("超时删除设备ID：{}".format(j))
            del requests_packs[bytes(j)]

    try:
        logging.WARNING("删除过期日志")
        remove_log()
    except OSError as o:
        logging.WARNING(o)

    global remove_timer
    remove_timer = Timer(120, remove_packs_task)
    remove_timer.start()


def requests_split_pack(socket, address, message):
    """The Threading solve split requests message"""
    identifying_code = message[0:2]
    frame_length = message[2:4]
    frame_type = message[4:8]
    message_id = message[8:12]
    identifying_bit = message[12:14]
    message_data_id = message[14:15]
    message_data_count = message[15:16]
    message_data_index = message[16:17]
    # message_data_content = message[17:]

    start_time = time.time()
    while True:
        if 0 not in requests_packs[bytes(message_id)][2]:
            # 组合请求数据内容
            content = bytearray()
            for one_pack in requests_packs[bytes(message_id)][2]:
                content += one_pack

            # 组合内容数据
            re_content = message_data_id + message_data_count + message_data_index + content

            # 组合请求数据（注意这里的帧长是不对的，但接下来处理中并不使用）
            re_message = identifying_code + frame_length + frame_type + message_id + identifying_bit + re_content

            # 正常处理数据
            analysis_message(socket, address, re_message)

            # 完成请求后删除请求的分包数据
            requests_packs.pop(bytes(message_id))
            return

        elif time.time() - start_time > 60:
            return
        else:
            continue


def judge_message_data(socket, address, message):
    """The message judgement of receiver"""
    logging.debug("收到原生信息:{}".format(bytearray(message).hex()))

    # 判断是否短报文业务
    short_message = message[6]
    if short_message != 5 and short_message != 6:
        logging.debug("非短报文业务")
        return

    # 获取请求目的位信息
    message_data_count = bitarray(endian='big')
    message_data_count.frombytes(message[15: 16])

    if message_data_count[0] == 0:
        pack_count = int.from_bytes(message[15: 16], "big")
        if pack_count > 1:
            logging.debug("请求网址分包")
            analysis_split_message(socket, address, message, pack_count)
        else:
            logging.debug("请求网址单次")
            analysis_message(socket, address, message)
    elif message_data_count[0] == 1:
        logging.debug("请求取包")
        analysis_get_packs(socket, address, message)


def analysis_split_message(socket, address, message, pack_count):
    """service to split requests message"""
    message = bytearray(message)
    # identifying_code = message[0:2]
    # frame_length = message[2:4]
    # frame_type = message[4:8]
    message_id = message[8:12]
    # identifying_bit = message[12:14]
    # message_data_id = message[14:15]
    message_data_index = message[16:17]
    message_data_content = message[17:]

    logging.debug("请求网址分包数量:{}".format(pack_count))

    # 判断是否有分包请求任务
    if not bytes(message_id) in requests_packs.keys():
        # 添加到请求分包数据字典
        requests_packs[bytes(message_id)][2][int.from_bytes(message_data_index, "big")] = message_data_content
        requests_split_pack(socket, address, message)
    else:
        # 添加到请求分包数据字典
        requests_packs[bytes(message_id)][2][int.from_bytes(message_data_index, "big")] = message_data_content


def analysis_message(socket, address, message):
    """service to requests message"""
    message = bytearray(message)
    identifying_code = message[0:2]
    # frame_length = message[2:4]
    frame_type = message[4:8]
    message_id = message[8:12]
    identifying_bit = message[12:14]
    message_data_id = message[14:15]
    # message_data_index = message[16:17]
    message_data_content = message[17:]

    # 提取返回信息
    re_identifying_code = identifying_code
    re_frame_type = frame_type
    re_id = message[10:12] + message[8:10]
    re_identify_bit = identifying_bit
    re_message_data_id = message_data_id

    logging.debug("解析的信息是:{}".format(message_data_content.decode()))

    res = request_url(message_data_content.decode())
    request_content = bytearray(res)

    # 创建数据包字典(创建时间，内容)
    response_packs[bytes(message_id)] = [time.time(), list()]

    if len(request_content) > 68:
        # 把数据每 68 字节平分
        res_content = [request_content[i:i + 68] for i in range(0, len(request_content), 68)]
        pack_count = len(res_content)

        logging.debug("分包长度为是:{}".format(pack_count))

        if pack_count < 128:
            # 数据包个数只有 7 位所以必须小于 128
            re_message_data_pack = bitarray([1]) + bitarray(
                [0] * (7 - len(bitarray(bin(pack_count).replace('0b', ''))))) + bitarray(
                bin(pack_count).replace('0b', ''))

            for index, message_data_pack in enumerate(res_content):
                # 数据包的编号
                message_data_pack_index = bytearray([index])

                # 组合包的内容
                re_content = re_message_data_id + re_message_data_pack + message_data_pack_index + message_data_pack

                # 添加分包字典
                response_packs[bytes(message_id)][1].insert(index, re_content)

                # 计算帧长
                re_frame_length_int = (len(re_id + re_identify_bit + re_content))
                re_frame_length = re_frame_length_int.to_bytes(2, byteorder='little')

                # 组合返回数据
                re_pack = re_identifying_code + re_frame_length + re_frame_type + re_id + re_identify_bit + re_content

                response_queue.put([socket, address, re_pack])

    else:
        # 数据包个数
        re_message_data_pack = bytearray(bitarray('10000001'))

        # 数据包索引
        re_message_data_pack_index = bytearray([1])

        # 组合包的内容
        re_content = re_message_data_id + re_message_data_pack + re_message_data_pack_index + request_content

        # 添加数据字典
        response_packs[bytes(message_id)][1].insert(0, re_content)

        # 计算帧长
        re_frame_length_int = (len(re_id + re_identify_bit + re_content))
        re_frame_length = re_frame_length_int.to_bytes(2, byteorder='little')

        # 组合回复内容
        re_all = re_identifying_code + re_frame_length + re_frame_type + re_id + re_identify_bit + re_content

        response_queue.put([socket, address, re_all])


def analysis_get_packs(socket, address, message):
    """service to requests packs"""
    identifying_code = message[0:2]
    # frame_length = message[2:4]
    frame_type = message[4:8]
    message_id = message[8:12]
    identifying_bit = message[12:14]

    if bytes(message_id) in response_packs.keys():

        re_identifying_code = bytearray(identifying_code)
        re_frame_type = bytearray(frame_type)
        re_id = bytearray(message[10:12] + message[8:10])
        re_identifying_bit = bytearray(identifying_bit)
        # re_message_data_id = bytearray(message[14])
        # pack_bytes_count = len(message[17:])

        # 请求包的数量
        pack_bytes = bytearray(message[17:])

        for index, pack_index in enumerate(pack_bytes):

            try:
                re_content = response_packs[bytes(message_id)][1][int(pack_index)]
            except IndexError as err:
                index += 1
                logging.warning(err)
                continue

            # 计算帧长
            re_frame_length_int = (len(re_id + re_identifying_bit + re_content))
            re_frame_length = re_frame_length_int.to_bytes(2, byteorder='little')

            # 组合回复内容
            re_all = re_identifying_code + re_frame_length + re_frame_type + re_id + re_identifying_bit + re_content

            response_queue.put([socket, address, re_all])


def request_url(message):
    """request analysis url"""

    # 解析数据中的具体内容
    message_data = dict(eval(message))
    url = message_data['u']
    method = message_data['r']
    if method == 'post':
        params = message_data['p']
    else:
        params = ''

    # 返回测试数据
    if '127' in url:
        logging.debug("返回测试数据:{}".format(demo_message()))
        return demo_message()

    try:
        logging.debug("访问链接:{}".format(url))
        if method is "get":
            res = requests.get(url)
        elif method is "post":
            res = requests.post(url, data=params)
        else:
            return bytearray(0)

        res.encoding = 'utf-8'
        return res.content
    except ConnectionRefusedError as err:
        logging.warning(err)
        return bytearray(0)


class MyUDPHandler(socketserver.BaseRequestHandler):

    def handle(self):
        message = self.request[0]
        socket = self.request[1]
        address = self.client_address

        logging.debug("来自IP/PORT:{}".format(self.client_address))

        judge_message_data(socket, address, message)


if __name__ == '__main__':
    logging.debug("response time task is running...")
    response_timer = Timer(5, response_message_task)
    response_timer.start()

    logging.debug("remove time task is running...")
    remove_timer = Timer(5, remove_packs_task)
    remove_timer.start()

    logging.debug("UDP server is listening...")
    server = socketserver.ThreadingUDPServer(('0.0.0.0', 60001), MyUDPHandler)
    server.serve_forever()
