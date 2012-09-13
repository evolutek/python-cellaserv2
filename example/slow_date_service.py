#!/usr/bin/env python3
# testing cellasserv(server) timeout

import sys
sys.path.append("..")
import cellaserv_client

import time

class DateService(cellaserv_client.Client):

    def __init__(self, sock):
        cellaserv_client.Client.__init__(self, sock)
        self.register_service('date')

    def message_recieved(self, message):
        cellaserv_client.Client.message_recieved(self, message)

        time.sleep(3) # timeout test

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

        asyncore.loop()

if __name__ == "__main__":
    main()
