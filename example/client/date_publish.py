#!/usr/bin/env python3
"""Use the cellaserv client to send publish every second."""

import time

from cellaserv.client import SynClient

class DatePublisher(SynClient):
    def __init__(self, sock):
        super().__init__(sock=sock)

    def broadcast_time(self):
        self.publish('time', str(time.time()).encode("utf8"))

    def run(self):
        while not time.sleep(1):
            self.broadcast_time()

def main():
    import socket

    import cellaserv.settings

    HOST, PORT = cellaserv.settings.HOST, cellaserv.settings.PORT

    with socket.create_connection((HOST, PORT)) as sock:
        service = DatePublisher(sock)
        service.run()

if __name__ == '__main__':
    main()
