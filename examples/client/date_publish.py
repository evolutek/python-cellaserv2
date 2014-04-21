#!/usr/bin/env python3
"""Use the cellaserv client to send publish every second."""

import time

from cellaserv.client import SynClient
from cellaserv.settings import get_socket

class DatePublisher(SynClient):
    def __init__(self, sock):
        super().__init__(sock=sock)

    def broadcast_time(self):
        self.publish('time', str(time.time()).encode())

    def run(self):
        while not time.sleep(1):
            self.broadcast_time()

def main():
    with get_socket() as sock:
        date = DatePublisher(sock)
        date.run()

if __name__ == '__main__':
    main()
