#!/usr/bin/env python3
"""Sample client, (a)synchronous time time from the date service through
cellaserv.
"""

import time

from cellaserv.client import AsynClientDebug, SynClientDebug

class AsynDateQueryClient(AsynClientDebug):
    def __init__(self, sock):
        super().__init__(sock=sock)

        self.set_ack_cb(self.print_time)

    def print_time(self, message):
        print("Time: {}".format(time.ctime(message['data']['epoch'])))

class SynDateQueryClient(SynClientDebug):
    def __init__(self, sock):
        super().__init__(sock=sock)

    def epoch(self):
        return self.query('time', 'date')

def main():
    import asyncore
    import socket

    import cellaserv.settings

    HOST, PORT = cellaserv.settings.HOST, cellaserv.settings.PORT

    with socket.create_connection((HOST, PORT)) as sock:
        client = SynDateQueryClient(sock)
        for i in range(10):
            print(client.epoch())

    with socket.create_connection((HOST, PORT)) as sock:
        client = AsynDateQueryClient(sock)
        #client.register_service("test")
        #client.notify({'hello': 'world'}, "test")
        for i in range(10):
            client.query('time', 'date') # request command `time` to
                                         # service `date`
        print("===> Kill me when you're done. <===")
        asyncore.loop()

if __name__ == "__main__":
    main()
