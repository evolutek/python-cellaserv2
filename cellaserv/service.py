"""
Service allows you to write cellaserv services with high-level decorators :
Service.action and Service.event.

Example usage:

    >>> from cellaserv.service import Service
    >>> class Foo(Service):
    ...     @Service.action
    ...     def bar(self):
    ...         print("bar")
    ...
    ...     @Service.event
    ...     def bar(self):
    ...         print("bar")
    ...
    >>> s = Foo()
    >>> s.run()

It tries to read the `(HOST, PORT)` configuration from the file called
`local_settings.py`.

If this file does not exist it tries to read `/etc/conf.d/cellaserv` which as
the following format::

    [client]
    host = evolutek.org
    port = 4200

If this file is not found it defaults to HOST = evolutek.org and PORT = 4200.
"""

import asyncore
import configparser
import inspect
import os
import socket
import sys
import traceback

import cellaserv.client

DEBUG = os.environ.get("CS_DEBUG", False)

if DEBUG:
    AsynClient = cellaserv.client.AsynClientDebug
else:
    AsynClient = cellaserv.client.AsynClient

class Service(AsynClient):

    service_name = None
    identification = None
    variant = "python"
    version = None

    def __new__(cls, *args, **kwargs):
        _actions = {'version': cls.version}
        _events = {}

        for name, method in inspect.getmembers(cls):
            if hasattr(method, "_actions"):
                for action in method._actions:
                    _actions[action] = method
            if hasattr(method, "_events"):
                for event in method._events:
                    _events[event] = method

        cls._actions = _actions
        cls._events = _events

        return super(Service, cls).__new__(cls)

    def __init__(self, identification=None):
        try:
            import local_settings
            HOST, PORT = local_settings.HOST, local_settings.PORT
        except:
            config = configparser.ConfigParser()
            config.read(['/etc/conf.d/cellaserv'])

            HOST = os.environ.get("CS_HOST",
                    config.get("client", "host", fallback="evolutek.org"))
            PORT = int(os.environ.get("CS_PORT",
                config.get("client", "port", fallback="4200")))

        sock = socket.create_connection((HOST, PORT))

        super().__init__(sock)

        if not self.identification:
            self.identification = identification

    # Decorators

    @classmethod
    def action(cls, method_or_name):
        """Use the ``Service.action`` decorator to declare the method as
        callable from cellaserv."""

        def _set_action(method, action):
            try:
                method._actions.append(action)
            except AttributeError:
                method._actions = [action]

            return method

        def _wrapper(method):
            return _set_action(method, method_or_name)

        if callable(method_or_name):
            action = method_or_name.__name__.replace("_", "-")
            return _set_action(method_or_name, action)
        else:
            return _wrapper

    @classmethod
    def event(cls, method_or_name):
        """The method decorated with ``Service.event`` will be called when a
        event matching its name (or argument passed to ``Service.event``) will
        be received."""

        def _set_event(method, event):
            try:
                method._events.append(event)
            except AttributeError:
                method._events = [event]

            return method

        def _wrapper(method):
            return _set_event(method, method_or_name)

        if callable(method_or_name):
            event = method_or_name.__name__.replace("_", "-")
            return _set_event(method_or_name, event)
        else:
            return _wrapper

    # Regular methods

    def query_recieved(self, query):
        action = query['action']

        if 'identification' in query and \
                query['identification'] != self.identification:
                    return

        ack = {}
        ack['command'] = 'ack'
        ack['id'] = query['id']

        try:
            callback = self._actions[action]
        except KeyError:
            ack['data'] = {'error': "unknown action: '{}'".format(action)}
            self.send_message(ack)
            return
        except TypeError:
            ack['data'] = {'error': "bad action type: '{}' of type {}".format(
                action,
                type(action))}
            self.send_message(ack)
            return

        try:
            if 'data' in query:
                ack_data = callback(self, **query['data'])
            else:
                ack_data = callback(self)

            if ack_data is not None:
                ack['data'] = ack_data
        except Exception as e:
            traceback.print_exc(file=sys.stderr)

            ack['data'] = str(e)
            self.send_message(ack)
            return

        self.send_message(ack)

    # Default actions

    def version(self):
        ret = {}
        if self.version:
            ret['version'] = self.version
        if self.variant:
            ret['variant'] = self.variant
        return ret or None

    # Convenience methods

    def setup(self):
        """Use this if you want to setup multiple service before running
        ``Service.loop()``."""

        def _wrap(fun):
            def wrap(msg):
                if 'data' in msg:
                    fun(self, **msg['data'])
                else:
                    fun(self)
            return wrap

        if self.service_name:
            service_name = self.service_name
        else:
            service_name = self.__class__.__name__.lower()

        self.register_service(service_name, self.identification)

        for event_name, callback in self._events.items():
            self.subscribe_event(event_name)
            self.connect_event(event_name, _wrap(callback))

    def run(self):
        """One-shot to setup and start the service."""
        self.setup()
        Service.loop()

    @classmethod
    def loop(cls):
        asyncore.loop()
