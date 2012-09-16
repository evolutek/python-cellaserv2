#!/usr/bin/env python3
"""Sample client, query date from the date service through cellaserv
"""

import asyncore
import socket

import sys
sys.path.append("..")
import cellaserv_client

import local_settings

HOST, PORT = local_settings.HOST, local_settings.PORT

def main():
    with socket.create_connection((HOST, PORT)) as sock:
        client = cellaserv_client.Client(sock)
        #client.register_service("test")
        #client.notify({'hello': 'world'}, "test")
        for i in range(10):
            client.query('epoch', 'date') # request command `epoch` to
                                          # service `date`

        asyncore.loop()

if __name__ == "__main__":
    main()
