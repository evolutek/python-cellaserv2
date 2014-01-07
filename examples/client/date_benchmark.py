#!/usr/bin/env python3
"""Sample client, synchronous time request to the date service through
cellaserv.
"""

from cellaserv.client import SynClient
from cellaserv.settings import get_socket
import time

def run_client(n):
    client = SynClient(get_socket())
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
