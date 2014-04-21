#!/usr/bin/env python3
"""
Sample client, synchronous time request to the date service through cellaserv.
"""
import time

from cellaserv.client import SynClient
from cellaserv.settings import get_socket

def main():
    with get_socket() as sock:
        client = SynClient(sock)
        for _ in range(10000):
            begin = time.perf_counter()
            client.request('time', 'date')
            end = time.perf_counter()
            print((end - begin) * 1000)

if __name__ == "__main__":
    main()
