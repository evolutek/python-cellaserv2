#!/usr/bin/env python3
import time

import cellaserv.client

class EpochDelta(cellaserv.client.AsynClientDebug):
    def __init__(self, sock):
        super().__init__(sock=sock)
        self.listen_notification('epoch')
        self.connect_notify('epoch', self.on_epoch)

    def on_epoch(self, message):
        epoch = float(message['notify-data'])
        print('{:3.3} msec'.format((time.time() - epoch) * 1000))

if __name__ == "__main__":
    import asyncore
    import socket

    import local_settings
    HOST, PORT = local_settings.HOST, local_settings.PORT

    service = EpochDelta(socket.create_connection((HOST, PORT)))
    asyncore.loop()
