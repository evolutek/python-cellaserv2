#!/usr/bin/env python3

import json
import socket
from multiprocessing import Process
from time import sleep

from cellaserv.client import SynClient
from cellaserv.service import Service


class Test(Service):

    @Service.event
    def foo(self, a):
        assert int(a) == 0


def setup_function(f):
    f.p = Process(target=main)
    f.p.start()
    sleep(.2)


def teardown_function(f):
    f.p.terminate()


def recv(c):
    try:
        msg = c.read_message()
        return msg
    except socket.timeout:
        return False


def test_basic():
    c = SynClient()

    c.subscribe('log.coding-error')

    # Setup our client to timeout when there no message is recv
    c._socket.settimeout(.1)

    # Send good publish
    c.publish(event='foo', data=json.dumps({'a': '0'}).encode())
    assert not recv(c)

    # Internal error
    c.publish(event='foo', data=json.dumps({'a': 'hello'}).encode())
    assert recv(c)

    # Bad publish args
    c.publish(event='foo', data=json.dumps({'b': '0'}).encode())
    assert recv(c)


def main():
    t = Test()
    t.run()


if __name__ == '__main__':
    main()
