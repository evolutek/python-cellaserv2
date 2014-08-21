#!/usr/bin/env python3

import multiprocessing
import time

from cellaserv.client import SynClient
from cellaserv.protobuf.cellaserv_pb2 import Message
from cellaserv.proxy import CellaservProxy
from cellaserv.service import Service


class Logger(Service):

    @Service.action
    def do_log(self):
        # Log with nogthing
        self.log()
        # Log with kwargs
        self.log(time=time.time(), ok=True)
        # Log without kwargs
        self.log('time', 'is', time.time(), {'42': 42})
        # Log with args and kwargs
        self.log('time', 'is', time=time.time())


def main():
    logger = Logger()
    logger.run()


def test_logger():
    # Start our test service
    p = multiprocessing.Process(target=main)
    p.start()
    time.sleep(.2)  # Give it time to start

    c = SynClient()
    c.subscribe('log.logger*')

    cs = CellaservProxy()
    cs.logger.do_log()  # Send request
    time.sleep(.2)  # Give it time to crash

    # Ensure that we have our 4 log messages
    for _ in range(4):
        assert c.read_message().type == Message.Publish

    p.terminate()


if __name__ == "__main__":
    main()
