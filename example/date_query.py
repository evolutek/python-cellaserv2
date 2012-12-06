#!/usr/bin/env python3
"""Sample client, (a)synchronous time time from the date service through
cellaserv
"""

import time

import cellaserv.client

class AsynDateQueryClient(cellaserv.client.AsynClientDebug):
    def __init__(self, sock):
        super().__init__(sock=sock)

        self.set_ack_cb(self.print_time)

    def print_time(self, message):
        print("Time: {}".format(time.ctime(message['data']['epoch'])))

class SynDateQueryClient(cellaserv.client.SynClientDebug):
    def __init__(self, sock):
        super().__init__(sock=sock)

    def epoch(self):
        return self.query('time', 'date')

def main():
    import asyncore
    import socket

    import local_settings

    HOST, PORT = local_settings.HOST, local_settings.PORT

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
        asyncore.loop()

if __name__ == "__main__":
    main()
