#!/usr/bin/env python3
"""Using the cellaserv_client module to implement a service answering to the
"epoch" command.
"""

import sys
sys.path.append("..")
import cellaserv

import time

class DateService(cellaserv.AsynClient):

    def __init__(self, sock, identification=None):
        super(DateService, self).__init__(sock)
        self.identification = identification

    def connect(self):
        self.register_service('date', self.identification)

    def message_recieved(self, message):
        super().message_recieved(message)

        if message['command'] == 'query' and message['action'] == 'epoch':
            response = {}
            response['command'] = 'ack'
            response['ack'] = message
            response['ack-data'] = {'epoch': int(time.time())}

            self.send_message(response)

def main():
    import asyncore
    import socket

    import local_settings

    HOST, PORT = local_settings.HOST, local_settings.PORT

    with socket.create_connection((HOST, PORT)) as sock:
        service = DateService(sock)
        service.connect()

        asyncore.loop()

if __name__ == "__main__":
    main()
