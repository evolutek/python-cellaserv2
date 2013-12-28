import socket
import asyncore

from cellaserv.settings import HOST, PORT
from cellaserv.client import AsynClient

def main():
    with socket.create_connection((HOST, PORT)) as sock:
        client = AsynClient(sock)
        client.register("test_client")
        asyncore.loop()

if __name__ == "__main__":
    main()
