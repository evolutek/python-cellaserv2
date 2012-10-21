#!/usr/bin/env python3
"""Use the cellaserv module to send notify every second"""

import sys
import time

sys.path.append("..")
import cellaserv.client

class DateNotifier(cellaserv.client.SynClientDebug):
    def __init__(self, sock):
        super().__init__(sock=sock)

    def broadcast_time(self):
        self.notify('epoch', str(time.time()))

    def run(self):
        while not time.sleep(1):
            self.broadcast_time()

if __name__ == '__main__':
    import socket

    import local_settings
    HOST, PORT = local_settings.HOST, local_settings.PORT

    service = DateNotifier(socket.create_connection((HOST, PORT)))
    service.run()
