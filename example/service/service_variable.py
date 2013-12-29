#!/usr/bin/env python
# encoding: utf-8

"""Asynchronous variable setting.

.. warning::

    You must setup a custom thread in order to let network thread read incoming
    events.

Set::

    $ cellasend command=notify event=some-event
    $ cellasend command=notify event=my-set

Clear::

    # No clearing event have been declared for some_event
    $ cellasend command=notify event=my-clear

Passing data::

    $ cellasend command=notify event=my-set .foo=bar

Will display::

    Set! self.variable.data = {'foo': 'bar'}
"""

from time import sleep
from threading import Thread

from cellaserv.service import Service

class Foo(Service):

    def __init__(self):
        super().__init__()

        self.t = Thread(target=self.thread_loop)
        self.t.start()

    some_event = Service.variable() # set event is 'some-event'
    variable = Service.variable(set='my-set', clear='my-clear')

    # Threads

    def thread_loop(self):
        while not sleep(1):
            # Do someting
            # ...

            print("self.some_event = {}".format(self.some_event.is_set()))

            # Check variable state
            if self.variable.is_set():
                print("Set! self.variable.data = {}".format(self.variable.data))
            else:
                print("Unset... self.variable.data = {}".format(self.variable.data))

def main():
    foo = Foo()
    foo.run()

if __name__ == '__main__':
    main()
