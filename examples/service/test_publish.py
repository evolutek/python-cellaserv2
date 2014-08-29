#!/usr/bin/env python3

import multiprocessing
import time

from cellaserv.client import SynClient
from cellaserv.protobuf.cellaserv_pb2 import Message
from cellaserv.proxy import CellaservProxy
from cellaserv.service import Service


class Publisher(Service):

    @Service.action
    def do_publish(self):
        self.publish(event='test_pub')
        # Publish with kwargs
        self.publish('test_pub', time=time.time(), ok=True)
        # Publish with args
        self.publish('test_pub', 'time', 'is', time.time(), {'42': 42})
        # Publish with args and kwargs
        self.publish('test_pub', 'time', 'is', time=time.time())


def main():
    pub = Publisher()
    pub.run()


def test_publisher():
    # Start our test service
    p = multiprocessing.Process(target=main)
    p.start()
    time.sleep(.2)  # Give it time to start

    c = SynClient()
    c.subscribe('test_pub')

    cs = CellaservProxy()
    cs.publisher.do_publish()  # Send request
    time.sleep(.2)  # Give it time to crash

    # Ensure that we have our 4 log messages
    for _ in range(4):
        assert c.read_message().type == Message.Publish

    p.terminate()


if __name__ == "__main__":
    main()
