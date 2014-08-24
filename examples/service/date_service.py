#!/usr/bin/env python3

import time

from cellaserv.service import Service


class Date(Service):

    @Service.action
    def time(self):
        return {'time': int(time.time())}

    @Service.action("print_time")
    def print(self):
        print(time.time())

    @Service.event("hello")
    def say(self, what="world"):
        print("hello", what)

    @Service.thread
    def loop(self):
        while not time.sleep(3):
            self.log(time=time.time())


def main():
    date_service = Date()
    date_service.run()

if __name__ == "__main__":
    main()
