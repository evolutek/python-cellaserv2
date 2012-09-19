#!/usr/bin/env python3
"""Sample client, query date from the date service through cellaserv
"""

import asyncore
import socket
import time

import sys
sys.path.append("..")
import cellaserv

import local_settings

HOST, PORT = local_settings.HOST, local_settings.PORT

class DateQueryClient(cellaserv.DebugClient):
    def __init__(self, sock):
        super().__init__(sock)

        self.set_ack_cb(self.print_time)

    def print_time(self, message):
        print("Time: {}".format(time.ctime(message['ack-data']['epoch'])))

def main():
    with socket.create_connection((HOST, PORT)) as sock:
        client = DateQueryClient(sock)
        #client.register_service("test")
        #client.notify({'hello': 'world'}, "test")
        for i in range(10):
            client.query('epoch', 'date') # request command `epoch` to
                                          # service `date`
        asyncore.loop()

if __name__ == "__main__":
    main()
