#!/usr/bin/env python3

from multiprocessing import Process
from time import sleep

from cellaserv.proxy import CellaservProxy
from cellaserv.service import Service


class Test(Service):

    @Service.action
    def foo(self):
        return "bar"

    @Service.action
    def echo(self, str):
        return str


def setup_function(f):
    f.p = Process(target=main)
    f.p.start()
    sleep(.2)


def teardown_function(f):
    f.p.terminate()


def test_basic():
    cs = CellaservProxy()

    srvcs = cs.cellaserv.list_services()

    # Check for presence
    foo = False
    bar = False
    for srvc in srvcs:
        if srvc["Name"] == "test":
            if srvc["Identification"] == "foo":
                assert not foo
                foo = True
            if srvc["Identification"] == "bar":
                assert not bar
                bar = True
    assert foo
    assert bar

    assert cs.test["foo"].foo() == "bar"
    assert cs.test["bar"].foo() == "bar"
    assert cs.test["foo"].echo("a") == "a"
    assert cs.test["bar"].echo("b") == "b"


def main():
    tf = Test("foo")
    tb = Test("bar")

    Service.loop()


if __name__ == '__main__':
    main()
