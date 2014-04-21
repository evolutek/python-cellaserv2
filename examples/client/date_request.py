#!/usr/bin/env python3
"""
Sample client, (a)synchronous time request to the date service through
cellaserv.
"""

import asyncore
import time

from cellaserv.settings import get_socket
from cellaserv.client import AsynClient, SynClient

class TimeRequestClient:
    def time(self):
        return self.request('time', 'date')

class AsynDateRequestClient(AsynClient, TimeRequestClient):
    def __init__(self, sock):
        super().__init__(sock=sock)

    def on_reply(self, rep):
        print("Time: {}".format(time.ctime(int(float(rep.data.decode("utf8"))))))

class SynDateRequestClient(SynClient, TimeRequestClient):
    def __init__(self, sock):
        super().__init__(sock=sock)

def main():
    print("[+] Testing synchronous client")
    with get_socket() as sock:
        client = SynDateRequestClient(sock)
        for i in range(10):
            print(client.time())

    print("[+] Testing asynchronous client")
    with get_socket() as sock:
        client = AsynDateRequestClient(sock)
        for i in range(10):
            client.time()
        print("===> Kill me after 10 replies. <===")
        asyncore.loop()

if __name__ == "__main__":
    main()
