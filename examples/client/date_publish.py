#!/usr/bin/env python3
"""Use the cellaserv client to send publish every second."""

import time

from cellaserv.client import SynClient


class DatePublisher(SynClient):
    def broadcast_time(self):
        self.publish('time', str(time.time()).encode())

    def run(self):
        while not time.sleep(1):
            self.broadcast_time()


def main():
    date = DatePublisher()
    date.run()

if __name__ == '__main__':
    main()
