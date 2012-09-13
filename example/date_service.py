#!/usr/bin/env python3
# example featuring cellaserv usage

import sys
sys.path.append("..")
import cellaserv_client

import time



class DateService(cellaserv_client.Client):

    def __init__(self, sock, identification=None):
        super(DateService, self).__init__(sock)
        self.identification = identification

    def connect(self):
        self.register_service('date', self.identification)

    def message_recieved(self, message):
        cellaserv_client.Client.message_recieved(self, message) # debug message

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
