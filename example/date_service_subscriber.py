#!/usr/bin/env python3
import time

from cellaserv.client import AsynClientDebug

class EpochDelta(AsynClientDebug):
    def __init__(self, sock):
        super().__init__(sock=sock)

        self.subscribe_event('epoch')
        self.connect_event('epoch', self.on_epoch)

    def on_epoch(self, message):
        epoch = float(message['data'])
        print('{:3.3} msec'.format((time.time() - epoch) * 1000))

        ack = {}
        ack['command'] = 'ack'
        ack['id'] = message['id']
        self.send_message(ack)

if __name__ == "__main__":
    import asyncore
    import socket

    import cellaserv.settings

    HOST, PORT = cellaserv.settings.HOST, cellaserv.settings.PORT

    service = EpochDelta(socket.create_connection((HOST, PORT)))
    asyncore.loop()
