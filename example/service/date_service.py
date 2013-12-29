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

    @Service.event
    def kill(self):
        import sys
        sys.exit(0)

def main():
    date_service = Date()
    date_service.run()

if __name__ == "__main__":
    main()
