#!/usr/bin/env python3
"""Using the cellaserv module to implement a service that does nothing. Used to
test timeouts.
"""
from cellaserv.client import AsynClient

class DateService(AsynClient):

    def __init__(self, sock):
        super().__init__(sock)
        self.register('date')

    def on_request(self, req):
        pass

def main():
    import asyncore
    import socket

    import cellaserv.settings

    HOST, PORT = cellaserv.settings.HOST, cellaserv.settings.PORT

    with socket.create_connection((HOST, PORT)) as sock:
        service = DateService(sock)

        asyncore.loop()

if __name__ == "__main__":
    main()