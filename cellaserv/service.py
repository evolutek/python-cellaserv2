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

Starting more than one service
------------------------------

It is sometime preferable to start multiple services at the same time, for
example the same service but with different identifications. In this case you
will instanciate multiple services, call setup() on each of this services and
then give control to the async loop with Service.loop().

Example usage:

    >>> from cellaserv.service import Service
    >>> class Bar(Service):
    ...     def __init__(self, id):
    ...         super().__init__(identification=id)
    ...
    ...     @Service.action
    ...     def bar(self):
    ...         print(self.identification)
    ...
    >>> services = [Bar(i) for i in range(10)]
    >>> for s in services:
    ...    s.setup()
    ...
    >>> Service.loop()

"""

import asyncore
import configparser
import inspect
import json
import logging
import os
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
    strfmt = "{r.service_name}[{r.service_identification}].{r.method}({data}) #id={r.id}"
    return strfmt.format(r=req, data=req.data if req.data != b"" else "")

class Variable(threading.Event):
    """
    Variables help you share data and states between services.

    The value of the variable can be set by cellaserv publish messages. When a
    service publishs the event associated with this variable, the underlying
    threding.Event will be set() and any thread wait()ing for it will we
    awaken.

    The events associated with this Variable can be set in the constructor, but
    must be subscribed by another client, eg. a Service subclass.

    Example::

        >>> from cellaserv.service import Service, Variable
        >>> class Timer(Service):
        ...     t = Variable()
        ...     ...
    """

    def __init__(self, set=None, clear=None):
        """
        Define a new cellaserv Variable.

        :param set str: Event that sets the variable
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
        """
        This method setup the list of actions (_actions) and subscribed events
        (_event). It is called when a new subclass of Service is declared.

        Basic level of metaprogramming magic.
        """

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

    def __init__(self, identification=None, sock=None):
        if not sock:
            sock = cellaserv.settings.get_socket()

        self.identification = identification or self.identification
        super().__init__(sock)

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
        """
        The method decorated with ``Service.event`` will be called when a event
        matching its name (or argument passed to ``Service.event``) will be
        received.
        """

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
        """Returns the data contained in a message."""
        if msg.HasField('data'):
            # We expect json formatted data
            try:
                obj = msg.data.decode()
                return json.loads(obj)
            except (UnicodeDecodeError, ValueError):
                # In case the data cannot be decoded, return raw data
                # Can be used to communicate with services that does not handle
                # json data, but only raw bytes.
                return msg.data
        else:
            return {}


    # Regular methods

    def on_request(self, req):
        """on_request is called when a request is received by the service."""
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
                reply_data = json.dumps(reply_data).encode()
        except Exception as e:
            logger.error("Exception during %s", _request_to_string(req),
                         exc_info=True)
            self.reply_error_to(req, cellaserv.client.Reply.Error.Custom,
                                json.dumps(str(e)))
            return

        self.reply_to(req, reply_data)

    # Default actions

    def help(self):
        """Help about this service."""
        docs = {}
        docs["doc"] = inspect.getdoc(self)
        docs["actions"] = self.help_actions()
        docs["events"] = self.help_events()
        return docs

    help._actions = ['help']

    def help_actions(self):
        """List available actions for this service."""
        docs = {}
        for action_name, unbound_f in self._actions.items():
            # The name of the method can be != action_action
            f_name = unbound_f.__name__
            # Get the function from self to get a bound method in order to
            # remove the first parameter (class name).
            bound_f = getattr(self, f_name)
            doc = inspect.getdoc(bound_f)
            sig = action_name + str(inspect.signature(bound_f))
            docs[action_name] = {'doc': doc, 'sig': sig}
        return docs

    help_actions._actions = ['help_actions']

    def help_events(self):
        """List subscribed events of this service."""
        doc = {}
        for event, unbound_f in self._events.items():
            bound_f = getattr(self, unbound_f.__name__)
            doc[event] = (inspect.getdoc(bound_f) or
                    str(inspect.signature(bound_f)))

        return doc

    help_events._actions = ['help_events']

    def kill(self):
        """Kill the service."""
        os.kill(os.getpid(), 9)

    kill._actions = ['kill']

    # Convenience methods

    def log(self, **kwargs):
        """
        Send a log message to cellaserv using the service's name and
        identification if any.

        Logs in cellaserv are implemented using event with the form
        ``log.<what>``.
        """
        log_name = 'log.' + self.service_name
        if self.identification:
            log_name += self.service_name + '/' + self.identification

        self.publish(log_name, data=json.dumps(kwargs).encode())

    def setup(self):
        """
        Use this if you want to setup multiple service before running
        ``Service.loop()``.
        """

        def _event_wrap(fun):
            """Convert event data to arguments for methods."""
            def _wrap(data=None):
                if data:
                    kwargs = json.loads(data.decode())
                else:
                    kwargs = {}
                logger.debug("Publish callback: %s(%s)", fun.__name__, kwargs)
                try:
                    fun(self, **kwargs)
                except TypeError:
                    log_msg_fmt = "Bad publish data for function {0}: {1}"
                    log_msg = log_msg_fmt.format(fun.__name__, kwargs)
                    self.log(msg=log_msg)
            return _wrap

        if not self.service_name:
            self.service_name = self.__class__.__name__.lower()

        # Register the service
        self.register(self.service_name, self.identification)

        # Subsribe to all events
        for event_name, callback in self._events.items():
            self.add_subscribe_cb(event_name, _event_wrap(callback))

    def run(self):
        """
        One-shot method to setup and start the service at the same time. This
        is the method you will use 90% of the time to start your service.
        """
        self.setup()
        Service.loop()

    @classmethod
    def loop(cls):
        """
        loop() will start the asyncore engine therefore, if you have not
        started another thread, only callbacks (eg. actions, events) will be
        called.
        """
        asyncore.loop()
