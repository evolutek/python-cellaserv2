#!/usr/bin/env python3
import asyncore
import time

from cellaserv.client import AsynClient
from cellaserv.settings import get_socket

class EpochDelta(AsynClient):
    def __init__(self, sock):
        super().__init__(sock)

        self.add_subscribe_cb('time', self.on_time)

    def on_time(self, pub):
        epoch = float(pub.decode("utf8"))
        print('{:3.3} msec'.format((time.time() - epoch) * 1000))

def main():
    with get_socket() as sock:
        service = EpochDelta(sock)
        asyncore.loop()

if __name__ == "__main__":
    main()
