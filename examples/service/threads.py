#!/usr/bin/env python3

import time

from cellaserv.service import Service, ConfigVariable


class Date(Service):

    coef = ConfigVariable('test', 'coef')

    def __init__(self):
        super().__init__()
        self._time = time.time()

    @Service.action
    def time(self):
        return self._time

    @Service.thread
    def update(self):
        print("Thread 1 started")
        while not time.sleep(1):
            self._time = time.time() * float(self.coef())

    @Service.thread
    def log(self):
        print("Thread 2 started")
        while not time.sleep(1):
            print(self.coef())


def main():
    date_service = Date()
    date_service.run()

if __name__ == "__main__":
    main()
