#!/usr/bin/env python3
"""Using the cellaserv module to implement a service answering to the
"time" command.
"""
import time

from cellaserv.protobuf.cellaserv_pb2 import Reply
from cellaserv.client import AsynClient

class DateService(AsynClient):

    def __init__(self, sock):
        super().__init__(sock)
        self.register('date')

    def on_request(self, req):
        if req.method == 'time':
            self.reply_to(req, str(time.time()).encode("utf8"))
        else:
            self.reply_error_to(req, Reply.Error.NoSuchMethod)

def main():
    import asyncore
    import socket

    import cellaserv.settings

    HOST, PORT = cellaserv.settings.HOST, cellaserv.settings.PORT

    with socket.create_connection((HOST, PORT)) as sock:
        service = DateService(sock)

        asyncore.loop()

if __name__ == "__main__":
    main()
