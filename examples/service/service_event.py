#!/usr/bin/env python

"""Asynchronous event setting.

.. warning::

    You must setup a custom thread in order to let network thread read incoming
    events.

Set::

    $ cellaservctl publish some-event
    $ cellaservctl publish my-set

Clear::

    # No clearing event have been declared for some_event
    $ cellaservctl publish my-clear

Passing data::

    $ cellaservctl publish my-set foo=bar

Will display::

    Set! self.variable.data = {'foo': 'bar'}
"""

from time import sleep

from cellaserv.service import Service, Event


class Foo(Service):

    some_event = Event()  # set event is 'some_event'
    event = Event(set='my-set', clear='my-clear')

    # Threads

    @Service.thread
    def thread_loop(self):
        while not sleep(1):
            # Do someting
            # ...

            print("self.some_event = {}".format(self.some_event.is_set()))

            # Check variable state
            if self.event.is_set():
                print("Set! self.event.data = {}".format(self.event.data))
            else:
                print("Unset. self.event.data = {}".format(self.event.data))


def main():
    foo = Foo()
    foo.run()

if __name__ == '__main__':
    main()
