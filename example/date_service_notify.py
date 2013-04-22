#!/usr/bin/env python3
"""Use the cellaserv module to send notify every second"""

import time

from cellaserv.client import SynClient

class DateNotifier(SynClient):
    def __init__(self, sock):
        super().__init__(sock=sock)

    def broadcast_time(self):
        self.notify('epoch', str(time.time()))

    def run(self):
        while not time.sleep(1):
            self.broadcast_time()

def main():
    import socket

    import cellaserv.settings

    HOST, PORT = cellaserv.settings.HOST, cellaserv.settings.PORT

    service = DateNotifier(socket.create_connection((HOST, PORT)))
    service.run()

if __name__ == '__main__':
    main()
