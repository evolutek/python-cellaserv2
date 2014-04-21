#!/usr/bin/env python3
"""
Sample client, synchronous time request to the date service through cellaserv.
"""

import time

from cellaserv.client import SynClient
from cellaserv.settings import get_socket

def run_client(n):
    with get_socket() as sock:
        client = SynClient(sock)
        for _ in range(n):
            client.request('time', 'date')

def main():
    from multiprocessing import Pool
    p = Pool(20)
    begin = time.perf_counter()
    p.map(run_client, [100] * 5)
    end = time.perf_counter()
    print((end - begin) * 1000)

if __name__ == "__main__":
    main()
