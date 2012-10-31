#!/usr/bin/env python3
import time

import cellaserv.client

class EpochDelta(cellaserv.client.AsynClientDebug):
    def __init__(self, sock):
        super().__init__(sock=sock)

        self.subscribe_event('epoch')
        self.connect_event('epoch', self.on_epoch)

    def on_epoch(self, message):
        epoch = float(message['data'])
        print('{:3.3} msec'.format((time.time() - epoch) * 1000))

if __name__ == "__main__":
    import asyncore
    import socket

    import local_settings
    HOST, PORT = local_settings.HOST, local_settings.PORT

    service = EpochDelta(socket.create_connection((HOST, PORT)))
    asyncore.loop()
