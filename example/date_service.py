#!/usr/bin/env python3
"""Using the cellaserv module to implement a service answering to the
"epoch" command.
"""
import time

from cellaserv.client import AsynClient

class DateService(AsynClient):

    def __init__(self, sock, identification=None):
        super().__init__(sock)

        self.identification = identification

    def connect(self):
        self.register_service('date', self.identification)

    def query_recieved(self, message):
        response = {}
        response['command'] = 'ack'
        response['id'] = message['id']

        if message['action'] == 'time':
            response['data'] = {'epoch': int(time.time())}

        else:
            response['data'] = {'error':
                    "unknown action: '{}'".format(message['action'])}

        self.send_message(response)

def main():
    import asyncore
    import socket

    import cellaserv.settings

    HOST, PORT = cellaserv.settings.HOST, cellaserv.settings.PORT

    with socket.create_connection((HOST, PORT)) as sock:
        service = DateService(sock)
        service.connect()

        asyncore.loop()

if __name__ == "__main__":
    main()
