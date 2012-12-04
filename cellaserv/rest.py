#!/usr/bin/env python3
"""
Cellaserv HTTP Rest interface

Example use::

    $ python3 rest.py
    $ wget -O - -o /dev/null --post-data 'goal=500' "cellaserv.evolutek.org/ax/5/move"
    $ wget -O - -o /dev/null cellaserv.evolutek.org/webcam/porte
"""
import json
import os
import re
import subprocess
import urllib.parse

from http.server import HTTPServer, CGIHTTPRequestHandler

from cellaserv.proxy import CellaservProxy

HOST, PORT = '', 4280

SERVICE = re.compile('/(?P<service>.*?)/(?:(?P<identification>[^/]*)/)?(?P<action>.*)$')

class RestAPI(CGIHTTPRequestHandler):
    def send_query(self, params):
        match = SERVICE.match(self.path)
        if not match:
            return

        self.cs = CellaservProxy()

        d = match.groupdict()

        service = self.cs.__getattr__(d['service'])
        if d['identification']:
            service = service.__getitem__(d['identification'])

        ret = service.__getattr__(d['action'])(**params)

        self.wfile.write(str(ret).encode("utf8"))

    def do_GET(self):
        self.send_response(200)
        self.end_headers()

        self.send_query({})

    def do_POST(self):
        self.send_response(200)
        self.end_headers()

        length = int(self.headers['Content-Length'])
        post_data = urllib.parse.parse_qs(self.rfile.read(length).decode('utf-8'))

        params = {k: v[0] for k, v in post_data.items()}

        self.send_query(params)

def main():
    try:
        server = HTTPServer((HOST, PORT), RestAPI)
        server.serve_forever()
    except KeyboardInterrupt:
        server.socket.close()

if __name__=='__main__':
    main()
