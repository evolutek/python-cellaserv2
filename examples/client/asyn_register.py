#!/usr/bin/env python3
import socket
import asyncore

from cellaserv.settings import get_socket
from cellaserv.client import AsynClient

def main():
    with get_socket() as sock:
        client = AsynClient(sock)
        client.register("test_client")
        asyncore.loop()

if __name__ == "__main__":
    main()
