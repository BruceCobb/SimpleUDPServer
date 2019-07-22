# -*- coding:utf-8 -*-

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import cgi
import io
from urllib.parse import urlparse
# import threading
import json


class RequestHandler(BaseHTTPRequestHandler):

    with open('demomessage', 'r', encoding='utf-8') as f:
        Page = f.read()

    def do_GET(self):
        parsed_path = urlparse(self.path)
        self.send_response(200)
        self.send_header("Content-Type", "text/html;charset=utf-8")
        # self.send_header("Content-Length", str(len(message)))
        self.end_headers()

        message = {'address': self.client_address, "query": parsed_path.query, "data": self.Page}

        self.wfile.write(json.dumps(message, ensure_ascii=False).encode('utf-8'))

    def do_POST(self):
        parsed_path = urlparse(self.path)

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                'REQUEST_METHOD': 'POST',
                'CONTENT_TYPE': self.headers['Content-Type'],
            }
        )

        # Begin the response
        self.send_response(200)
        self.send_header("Content-Type", "text/json; charset=utf-8")
        self.send_header("Content-Length", str(len(self.Page)))
        self.end_headers()

        out = io.TextIOWrapper(
            self.wfile,
            encoding='utf-8',
            line_buffering=False,
            write_through=True,
        )
        # message = {'address': self.client_address, "query": parsed_path.query, "data": self.Page}
        # out.write(json.dumps(message, ensure_ascii=False).encode('utf-8'))

        message = {'address': self.client_address, "query": parsed_path.query, "data": self.Page}
        self.wfile.write(json.dumps(message, ensure_ascii=False).encode('utf-8'))

        # message = {'address': self.client_address, "query": parsed_path.query}
        # self.wfile.write(json.dumps(message).encode())

        # Echo back information about what was posted in the form
        for field in form.keys():
            field_item = form[field]
            if field_item.filename:
                # The field contains an uploaded file
                file_data = field_item.file.read()
                file_len = len(file_data)
                del file_data
                out.write(
                    '\tUploaded {} as {!r} ({} bytes)\n'.format(
                        field, field_item.filename, file_len)
                )
            else:
                # Regular form value
                out.write('\t{}={}\n'.format(
                    field, form[field].value))

        out.detach()


if __name__ == '__main__':
    serverAddress = ('0.0.0.0', 8001)
    server = ThreadingHTTPServer(serverAddress, RequestHandler)
    server.serve_forever()


