#!/usr/bin/env python3
# get date from date_service through cellaserv(server)

import sys
sys.path.append("..")
import cellaserv_client

def main():
    import asyncore
    import socket

    import local_settings

    HOST, PORT = local_settings.HOST, local_settings.PORT

    with socket.create_connection((HOST, PORT)) as sock:
        client = cellaserv_client.Client(sock)
        #client.register_service("test")
        #client.notify({'hello': 'world'}, "test")
        for i in range(1000):
            client.query('epoch', 'date') # request cammand `epoch` to
                                          # date_service

        asyncore.loop()

if __name__ == "__main__":
    main()
