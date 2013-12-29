#!/usr/bin/env python3
"""How to use cellaserv.proxy.CellaservProxy"""

from cellaserv.proxy import CellaservProxy

def main():
    cs = CellaservProxy()

    print(cs.date.time())
    cs.date.print_time()
    cs("hello")
    cs("hello", what="you")
    cs("kill")

if __name__ == "__main__":
    main()
