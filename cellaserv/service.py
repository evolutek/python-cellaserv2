"""
Service allows you to write cellaserv services with high-level decorators:
Service.action and Service.event.

Example usage:

    >>> from cellaserv.service import Service
    >>> class Foo(Service):
    ...     @Service.action
    ...     def bar(self):
    ...         print("bar")
    ...
    ...     @Service.event
    ...     def on_foo(self):
    ...         print("foo")
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
import json
import logging
import pydoc
import socket
import sys
import threading
import traceback

import cellaserv.settings
from cellaserv.client import AsynClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG if cellaserv.settings.DEBUG >= 1 else logging.INFO)

def _request_to_string(req):
    return "{r.service_name}[{r.service_identification}].{r.method}({r.data}) #{r.id}".format(r=req)

class Variable(threading.Event):
    """Variables help you share data and states between services.

    Example::

        >>> from cellaserv.service import Service, Variable
        >>> class Timer(Service):
        ...     t = Variable()
        ...     ...
    """

    def __init__(self, set, clear):
        """:param set str: Event that sets the variable
        :param clear str: Event that clears the variable
        """
        super().__init__()

        self.name = "?"
        self.data = {}

        self._event_set = set
        self._event_clear = clear

class Service(AsynClient):

    service_name = None
    identification = None

    def __new__(cls, *args, **kwargs):
        """Metaprogramming magic."""

        def _var_wrap_set(variable):
            def _variable_set(self, **kwargs):
                logger.debug("Varable %s set, data=%s", variable.name, kwargs)
                variable.set()
                variable.data = kwargs
            return _variable_set

        def _var_wrap_clear(variable):
            def _variable_clear(self, **kwargs):
                logger.debug("Varable %s cleared, data=%s", variable.name,
                             kwargs)
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
                member.name = name
                _events[member._event_set or name] = _var_wrap_set(member)
                _events[member._event_clear or name + "_clear"] = _var_wrap_clear(member)

        cls._actions = _actions
        cls._events = _events

        return super(Service, cls).__new__(cls)

    def __init__(self, identification=None):
        HOST, PORT = cellaserv.settings.HOST, cellaserv.settings.PORT

        sock = socket.create_connection((HOST, PORT))

        super().__init__(sock)

        self.identification = identification or self.identification

    # Decorators

    @classmethod
    def action(cls, method_or_name):
        """Use the ``Service.action`` decorator to declare the method as
        exported to cellaserv."""

        def _set_action(method, action):
            try:
                method._actions.append(action)
            except AttributeError:
                method._actions = [action]

            return method

        def _wrapper(method):
            return _set_action(method, method_or_name)

        if callable(method_or_name):
            return _set_action(method_or_name, method_or_name.__name__)
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
            return _set_event(method_or_name, method_or_name.__name__)
        else:
            return _wrapper

    # Protocol helpers

    @classmethod
    def _decode_data(cls, msg):
        if msg.HasField('data'):
            # We assume json formatted data
            txt = msg.data.decode('utf8')
            return json.loads(txt)
        else:
            return {}


    # Regular methods

    def on_request(self, req):
        if (req.HasField('service_identification')
            and req.service_identification != self.identification):
            logger.warning("Dropping request for wrong identification")
            return

        method = req.method

        try:
            callback = self._actions[method]
        except KeyError:
            logger.error("No such method: %s.%s", method, self)
            self.reply_error_to(req, cellaserv.client.Reply.Error.NoSuchMethod,
                                method)
            return

        try:
            data = self._decode_data(req)
        except Exception as e:
            logger.error("Bad arguments formatting: %s",
                         _request_to_string(req), exc_info=True)
            self.reply_error_to(req,
                cellaserv.client.Reply.Error.BadArguments, req.data)
            return


        try:
            reply_data = callback(self, **data)
            logger.debug("%s[%s].%s(%s) = %s",
                    self.service_name, self.identification, method, data,
                    reply_data)
            if reply_data is not None:
                reply_data = json.dumps(reply_data).encode("utf8")
        except Exception as e:
            logger.error("Exception during %s", _request_to_string(req),
                         exc_info=True)
            self.reply_error_to(req, cellaserv.client.Reply.Error.Custom,
                                json.dumps(str(e)))
            return

        self.reply_to(req, reply_data)

    # Default actions

    def help(self):
        """List exported actions."""
        doc = []
        for name, f in self._actions.items():
            doc.append(f.__doc__ or ''.join(pydoc.render_doc(f,
                title='%s').splitlines()[2:]))

        return '\n'.join(doc).encode("utf8")
    help._actions = ['help']

    def help_action(self, action):
        """Returns the docstring of the method ``action``."""
        try:
            f = self._actions[action]
        except KeyError:
            return b"No such action"
        return f.__doc__ or ''.join(pydoc.render_doc(f,
            title="%s").splitlines()[2:])
    help_action._actions = ['help_action']

    # Convenience methods

    def setup(self):
        """Use this if you want to setup multiple service before running
        ``Service.loop()``."""

        def _event_wrap(fun):
            def _wrap(data=None):
                if data:
                    kwargs = json.loads(data.decode("utf8"))
                else:
                    kwargs = {}
                logger.debug("Publish calls: %s(%s)", fun, kwargs)
                # FIXME: Handle bad kwargs format
                fun(self, **kwargs)
            return _wrap

        if not self.service_name:
            self.service_name = self.__class__.__name__.lower()

        self.register(self.service_name, self.identification)

        for event_name, callback in self._events.items():
            self.add_subscribe_cb(event_name, _event_wrap(callback))

    def run(self):
        """One-shot to setup and start the service."""
        self.setup()
        Service.loop()

    @classmethod
    def loop(cls):
        asyncore.loop()
