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
import pydoc
import socket
import sys
import threading
import traceback

import cellaserv.settings
import cellaserv.client

DEBUG = os.environ.get("CS_DEBUG", False)

if DEBUG:
    AsynClient = cellaserv.client.AsynClientDebug
else:
    AsynClient = cellaserv.client.AsynClient

class Variable(threading.Event):
    def __init__(self, set, clear):
        super().__init__()

        self._event_set = set
        self._event_clear = clear

        self.data = {}

class Service(AsynClient):

    service_name = None
    identification = None

    def __new__(cls, *args, **kwargs):
        def _wrap_set(variable):
            def _variable_set(self, **kwargs):
                variable.set()
                variable.data = kwargs
            return _variable_set

        def _wrap_clear(variable):
            def _variable_clear(self, **kwargs):
                variable.clear()
                variable.data = kwargs
            return _variable_clear

        _actions = {}
        _events = {}

        for name, member in inspect.getmembers(cls):
            if hasattr(member, "_actions"):
                for action in member._actions:
                    _actions[action] = member
            if hasattr(member, "_events"):
                for event in member._events:
                    _events[event] = member
            if isinstance(member, Variable):
                _events[member._event_set or name.replace('_', '-')] = _wrap_set(member)
                if member._event_clear:
                    _events[member._event_clear] = _wrap_clear(member)

        cls._actions = _actions
        cls._events = _events

        return super(Service, cls).__new__(cls)

    def __init__(self, identification=None):
        HOST, PORT = cellaserv.settings.HOST, cellaserv.settings.PORT

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

    @classmethod
    def variable(cls, set=None, clear=None):
        x = Variable(set=set, clear=clear)
        return x

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

    def help(self):
        doc = []
        for name, f in self._actions.items():
            doc.append(f.__doc__ or ''.join(pydoc.render_doc(f,
                title='%s').splitlines()[2:]))

        return '\n'.join(doc)
    help._actions = ['help']

    def help_action(self, action):
        try:
            f = self._actions[action]
            return f.__doc__ or ''.join(pydoc.render_doc(f,
                title="%s").splitlines()[2:])
        except KeyError:
            return "No such action"
    help_action._actions = ['help-action']

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
