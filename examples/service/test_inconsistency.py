#!/usr/bin/env python3

import time

from cellaserv.settings import get_socket
from cellaserv.service import Service

def test_with_then_without():
    with get_socket() as sock:
        s1 = Service("A", sock=sock)
        s1.setup()
        s2 = Service("B", sock=sock)
        s2.setup()
        s0 = Service("", sock=sock)
        s0.setup()

def test_without_then_with():
    with get_socket() as sock:
        s0 = Service("", sock=sock)
        s0.setup()
        s1 = Service("A", sock=sock)
        s1.setup()
        s2 = Service("B", sock=sock)
        s2.setup()

def main():
    test_without_then_with()
    test_with_then_without()

if __name__ == "__main__":
    main()
