#!/usr/bin/env python3
import time

from cellaserv.client import AsynClient

class EpochDelta(AsynClient):
    def __init__(self, sock):
        super().__init__(sock)

        self.add_subscribe_cb('time', self.on_time)

    def on_time(self, pub):
        epoch = float(pub.decode("utf8"))
        print('{:3.3} msec'.format((time.time() - epoch) * 1000))

if __name__ == "__main__":
    import asyncore
    import socket

    import cellaserv.settings

    HOST, PORT = cellaserv.settings.HOST, cellaserv.settings.PORT

    with socket.create_connection((HOST, PORT)) as sock:
        service = EpochDelta(sock)
        asyncore.loop()
