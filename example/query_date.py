#!/usr/bin/env python3
"""Sample client, (a)synchronous time time from the date service through
cellaserv
"""

import asyncore
import socket
import time

import sys
sys.path.append("..")
import cellaserv

import local_settings

HOST, PORT = local_settings.HOST, local_settings.PORT

class AsynDateQueryClient(cellaserv.AsynClientDebug):
    def __init__(self, sock):
        super().__init__(sock=sock)

        self.set_ack_cb(self.print_time)

    def print_time(self, message):
        print("Time: {}".format(time.ctime(message['ack-data']['epoch'])))

class SyncDateQueryClient(cellaserv.SynClientDebug):
    def __init__(self, sock):
        super().__init__(sock=sock)

def main():
    with socket.create_connection((HOST, PORT)) as sock:
        client = SyncDateQueryClient(sock)
        for i in range(10):
            client.query('epoch', 'date')
            print(client.read_message())

    with socket.create_connection((HOST, PORT)) as sock:
        client = AsynDateQueryClient(sock)
        #client.register_service("test")
        #client.notify({'hello': 'world'}, "test")
        for i in range(10):
            client.query('epoch', 'date') # request command `epoch` to
                                          # service `date`
        asyncore.loop()

if __name__ == "__main__":
    main()
