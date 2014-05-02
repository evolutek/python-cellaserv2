"""
Service
=======

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
import sys
import inspect
import json
import logging
import os
import threading

from google.protobuf.text_format import MessageToString

import cellaserv.settings
from cellaserv.client import AsynClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG if cellaserv.settings.DEBUG >= 1 else logging.INFO)

def _request_to_string(req):
    """Dump request to a shorter representation"""
    strfmt = "{r.service_name}[{r.service_identification}].{r.method}({data}) #id={r.id}"
    return strfmt.format(r=req, data=req.data if req.data != b"" else "")


# Keeping the script compatible between python 3.1 and above
Event = None
if sys.version_info[1] < 2:
    Event = threading._Event
else:
    Event = threading.Event

class Variable(Event):
    """
    Variables help you share data and states between services.

    The value of the variable can be set by cellaserv publish messages. When a
    service publishs the event associated with this variable, the underlying
    threding.Event will be set() and any thread wait()ing for it will we
    awaken.

    The events associated with this Variable can be set in the constructor, but
    must be subscribed by another client, eg. a Service subclass.

    This is believed to be thread-safe. That is mutliple threads can wait()
    this varible and each of then will be woken up when the variable is set().

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

        self.name = "?" # set by Service to the name of the declared field
        self.data = {}

        self._event_set = set
        self._event_clear = clear

    def __call__(self):
        """Handy syntactic sugar for accessing the variable value."""
        return self.data

class ConfigVariable:
    """
    ConfigVariable setup a variable using the 'config' service. It will always
    have the latest value.

    Event that update the value of this variable: 'config.<section>.<option>'

    Example::

        >>> from cellaserv.service import Service, ConfigVariable
        >>> class Match(Service):
        ...     color = ConfigVariable("match", "color")
        ...     ...

    You can also add callbacks to get notified when the variable is updated::

        >>> from cellaserv.service import Service, ConfigVariable
        >>> class Match(Service):
        ...     color = ConfigVariable("match", "color")
        ...     def __init__(self):
        ...         self.on_color_update() # set the self.color_coef
        ...         self.color.add_update_cb(self.on_color_update)
        ...     def on_color_update(self, value):
        ...         self.color_coef = 1 if value == "red" else -1
    """

    def __init__(self, section, option):
        """
        Define a new config variable using the 'config service'.

        :param section str: The section of this variable (eg. match, robot,
            etc.)
        :param option str: The option corresponding to this variable in the
            section.
        """
        self.section = section
        self.option = option
        self.update_cb = []

    def add_update_cb(self, cb):
        """
        add_update_cb(cb) adds callback function that will be called when the
        value of the variable is updated.

        :param cb function: a function compatible with the prototype f(value)
        """
        self.update_cb.append(cb)

    def update(self, value):
        """
        update(value) is called when the value of the variable changes.
        """
        logger.debug("Variable %s.%s updated: %s",
                self.section, self.option, value)
        self.value = value
        for cb in self.update_cb:
            cb(value)

    def __call__(self):
        """
        Returns the current value of the variable.

        Handy syntactic sugar.
        """
        return self.value

class Service(AsynClient):

    service_name = None
    identification = None

    # Meta

    def __new__(cls, *args, **kwargs):
        """
        This method setup the list of actions (_actions) and subscribed events
        (_event). It is called when a new subclass of Service is declared.

        Basic level of metaprogramming magic.
        """

        # Wrappers

        def _var_wrap_set(variable):
            def _variable_set(self, **kwargs):
                logger.debug("Variable %s set, data=%s", variable.name, kwargs)
                variable.set()
                variable.data = kwargs
            return _variable_set

        def _var_wrap_clear(variable):
            def _variable_clear(self, **kwargs):
                logger.debug("Variable %s cleared, data=%s", variable.name,
                             kwargs)
                variable.clear()
                variable.data = kwargs
            return _variable_clear

        def _config_var_wrap_event(variable):
            def _variable_update(self, value):
                variable.update(value=value)
            return _variable_update

        _actions = {}
        _events = {}
        _config_variables = []

        for name, member in inspect.getmembers(cls):
            if hasattr(member, "_actions"):
                for action in member._actions:
                    _actions[action] = member
            if hasattr(member, "_events"):
                for event in member._events:
                    _events[event] = member

            if isinstance(member, ConfigVariable):
                event_name = 'config.{section}.{option}'.format(
                        section=member.section,
                        option=member.option)
                _events[event_name] = _config_var_wrap_event(member)
                _config_variables.append(member)

            elif isinstance(member, Variable):
                member.name = name
                event_set = member._event_set or name
                event_clear = member._event_clear or name + "_clear"
                _events[event_set] = _var_wrap_set(member)
                _events[event_clear] = _var_wrap_clear(member)

        cls._actions = _actions
        cls._events = _events
        cls._config_variables = _config_variables

        return super(Service, cls).__new__(cls)

    # Meta decorators

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

        if hasattr(method_or_name, '__call__'):
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

    # Instanciated class land

    def __init__(self, identification=None, sock=None):
        self._reply_cb = {}

        if not sock:
            sock = cellaserv.settings.get_socket()

        self.identification = identification or self.identification

        super().__init__(sock)

    def __call__(self, event, **kwargs):
        """
        Send a publish message.

        :param event str: Event name
        :param **kwargs: Data sent along the publish message, encoded in json.
        """
        self.publish(event, data=json.dumps(kwargs).encode())

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


    # Override methods of cellaserv.client.AsynClient

    def on_reply(self, rep):
        """
        on_reply is called when a reply is received by the service.
        """
        logger.debug("Reply received: %s", MessageToString(rep).decode())
        if rep.HasField('error'):
            logger.error("Reply is error: %s", MessageToString(rep).decode())

        try:
            self._reply_cb[rep.id](rep.data)
            del self._reply_cb[rep.id]
        except KeyError as e:
            logger.error("Dropping reply for unknown request: %s", e)
        except Exception as e:
            logger.error("Error on reply: %s", e)

    def on_request(self, req):
        """
        on_request(req) is called when a request is received by the service.
        """
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

    def help(self) -> dict:
        """Help about this service.

        TODO: refactor all help functions, compute help dicts when creating the
        class using metaprogramming.
        """
        docs = {}
        docs["doc"] = inspect.getdoc(self)
        docs["actions"] = self.help_actions()
        docs["events"] = self.help_events()
        return docs

    help._actions = ['help']

    def help_actions(self) -> dict:
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

    def help_events(self) -> dict:
        """List subscribed events of this service."""
        doc = {}
        for event, f in self._events.items():
            # Here we try to get a bound method just to get the right
            # signature in the end. It is overly complicated for what it is
            # meant, but at least it was a fun exercice. -- halfr
            if not hasattr(f, '__self__') or f.__self__ != None:
                bound_f = f
            else: # f is not bound
                # try to get bound version of this method
                bound_f = getattr(self, f.__name__)
            doc[event] = (inspect.getdoc(bound_f) or
                    str(inspect.signature(bound_f)))

        return doc

    help_events._actions = ['help_events']

    def kill(self) -> "Does not return.":
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
        setup() will use the socket connected to cellaserv to initialize the
        service.

        Use this if you want to setup multiple service before running
        ``Service.loop()``.
        """

        def _event_wrap(fun):
            """Convert event data (raw bytes) to arguments for methods."""
            def _wrap(data=None):
                """called by cellaserv.client.AsynClient"""
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

        def _config_variable_wrap(update_fun):
            """Adapter for data received for ConfigVariable."""
            def _wrap(data):
                try:
                    args = json.loads(data.decode())
                except (UnicodeDecodeError, ValueError):
                    args = data
                update_fun(value=args)

            return _wrap

        if not self.service_name:
            # service name is class name in lower case
            self.service_name = self.__class__.__name__.lower()

        # Register the service
        self.register(self.service_name, self.identification)

        # Subsribe to all events
        for event_name, callback in self._events.items():
            self.add_subscribe_cb(event_name, _event_wrap(callback))

        # Request base values for ConfigVariables
        for variable in self._config_variables:
            req_data = {
                'section': variable.section,
                'option': variable.option
            }
            req_data_bytes = json.dumps(req_data).encode()
            req_id = self.request('get', 'config', data=req_data_bytes)
            self._reply_cb[req_id] = _config_variable_wrap(variable.update)

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
