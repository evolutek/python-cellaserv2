"""
Service
=======

Service allows you to write cellaserv services with high-level decorators:
Service.action and Service.event.

The @Service.action make a method exported to cellaserv. When matching request
is received, the method is called. The return value of the method is sent in
the reply. The return value must be json-encodable. The method must not take
too long to execute or it will cause cellaserv to send a RequestTimeout error
instead of your reply.

The @Service.event make the service listen for an event from cellaserv.

Only one @Service.action or @Service.event method can run at the same time
because there is only one service thread. If you want to have a background job,
use the @Service.thread decorator.

If you want to send requests to cellaserv, you should use a CellaservProxy
object, see ``cellaserv.proxy.CellaservProxy``.

You can use ``self('foo')`` to send an event, for more information see the
documentation for ``Service.__call__``.

You can use ``self.log()`` to produce logs.

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

Dependencies
------------

You can specify that your service depends on another service using the
@Service.require('my_other_service') class decorator.

    >>> from cellaserv.service import Service
    >>> @Service.require('hokuyo')
    ... class WithDep(Service):
    ...     pass

When the service is ``setup()``, it will wait for all the dependencies to be
registered on cellaserv.

Threads
-------

Service can have multiple threads running at the same time. You can use the
@Service.thread decorator to register a method to be run in another thread.

TODO
----

- implement service state notification

Disclaimer
----------

Don't be afraid by this code, theses classes leverage the power of a simple
pub/sub req/rep protocol to implement useful features. It is absolutly not
necessary to implement all this features in your version of the cellaserv
client. They serve a showcase of what can be done with the protocol, plus they
are pretty useful and simplify writing of services for the user.

"""

from collections import defaultdict
import asyncore
import inspect
import json
import logging
import os
import sys
import threading
import traceback

from google.protobuf.text_format import MessageToString

from cellaserv.protobuf.cellaserv_pb2 import (
    Message,
    Publish,
)

import cellaserv.settings
from cellaserv.client import AsynClient, SynClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG if cellaserv.settings.DEBUG >= 1
                else logging.INFO)


def _request_to_string(req):
    """Dump request to a short string representation."""
    strfmt = "{r.service_name}[{r.service_identification}].{r.method}({data}) #id={r.id}"
    return strfmt.format(r=req, data=req.data if req.data != b"" else "")


# Keeping the script compatible between python 3.1 and above
Event = None
if sys.version_info[1] < 2:
    Event = threading._Event
else:
    Event = threading.Event

if 'callable' not in dir(__builtins__):
    def callable(f):
        return hasattr(f, '__call__')

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

    TODO: Rename this class to Event, because that is what it really is. Plus
    we now have ConfigVariable that are better implementation of the "variable"
    concept.
    """

    def __init__(self, set=None, clear=None):
        """
        Define a new cellaserv Variable.

        :param set str: Event that sets the variable
        :param clear str: Event that clears the variable
        """
        super().__init__()

        self.name = "?"  # set by Service to the name of the declared field
        # Optional data held by the variable
        self.data = {}

        # Events that set/clear the variable, if they are different from the
        # name
        self._event_set = set
        self._event_clear = clear

    def __call__(self):
        """
        Returns the current value of the variable.

        Handy syntactic sugar.
        """
        return self.data


class ConfigVariable:
    """
    ConfigVariable setup a variable using the 'config' service. It will always
    have the most up-to-date value.

    The value of this variable can be updated with the following event:
    'config.<section>.<option>'. The message must be a valid json object of the
    form: {'value': NEW VALUE}.

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
        self.value = None

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

        NB. It is not called when the value is first set.
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

    # Mandatory name of the service as it will appeared for cellaserv.
    service_name = None
    # Optional identification string used to register multiple instances of the
    # same service.
    identification = None

    # Meta

    def __new__(cls, *args, **kwargs):
        """
        ``__new__`` is called when a new instance of Service is created.

        This method setup the list of actions (cls._actions) and subscribed
        events (cls._event) in the new class.

        Basic level of metaprogramming magic.
        """

        # XXX: Why do we use wrappers, doesn't simple class methods work?
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
        _config_variables = []
        _events = {}
        _threads = []

        for name, member in inspect.getmembers(cls):
            if hasattr(member, "_actions"):
                for action in member._actions:
                    _actions[action] = member
            if hasattr(member, "_events"):
                for event in member._events:
                    _events[event] = member
            if hasattr(member, "_thread"):
                _threads.append(member)

            if isinstance(member, ConfigVariable):
                event_name = 'config.{section}.{option}'.format(
                    section=member.section, option=member.option)
                _events[event_name] = _config_var_wrap_event(member)
                _config_variables.append(member)

            elif isinstance(member, Variable):
                member.name = name
                event_set = member._event_set or name
                event_clear = member._event_clear or name + "_clear"
                _events[event_set] = _var_wrap_set(member)
                _events[event_clear] = _var_wrap_clear(member)

        cls._actions = _actions
        cls._config_variables = _config_variables
        cls._events = _events
        cls._threads = _threads

        if not hasattr(cls, '_service_dependencies'):
            # Force existence of _service_dependencies
            cls._service_dependencies = defaultdict(list)

        return super(Service, cls).__new__(cls)

    # Meta class decorator

    @classmethod
    def require(cls, depend, cb=None):
        """
        Use the ``Service.require`` class decorator to specify a dependency
        between this service and ``depend``. This service will not start before
        the ``depend`` service is registered on cellaserv. Optionally you can
        specify a callback ``cb`` that will be called when the dependency is
        satisfied.

        This operation may delay the start of service, because it must wait for
        all services to be registered. When state.<service>

        The service setup() will not return until all services are registered.
        """


        def class_builder(cls):
            # 'cls' is being created so the first time require() is called we
            # must create this field
            if not hasattr(cls, '_service_dependencies'):
                cls._service_dependencies = defaultdict(list)
            cls._service_dependencies[depend].append(cb)

            return cls

        return class_builder

    # Meta methods decorators

    @classmethod
    def action(cls, method_or_name):
        """
        Use the ``Service.action`` decorator on a method to declare it as
        exported to cellaserv. If a parameter is given, change the name of the
        method to that name.

        :param name str: Change the name of that metod to ``name``.
        """

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

    @classmethod
    def thread(cls, method):
        """
        The method decorated with ``Service.thread`` will run in another
        thread, aside from the main service thread. The thread is automatically
        started when the service is ready to use.

        Example::

            >>> from cellaserv.service import Service
            >>> from time import sleep
            >>> class Foo(Service):
            ...     @Service.thread
            ...     def loop(self):
            ...         while not sleep(1):
            ...             print("hello!")
        """

        method._thread = True
        return method

    # Instanciated class land

    def __init__(self, identification=None, sock=None):
        self._reply_cb = {}
        self.identification = identification or self.identification

        if not sock:
            # Get a socket from cellaserv configuration mechanism
            sock = cellaserv.settings.get_socket()
        self._socket = sock

    # Protocol helpers

    @classmethod
    def _decode_msg_data(cls, msg):
        """Return the data contained in a message."""
        if msg.HasField('data'):
            return cls._decode_data(msg.data)
        else:
            return {}

    @classmethod
    def _decode_data(cls, data):
        """Returns the data contained in a message."""
        try:
            obj = data.decode()
            return json.loads(obj)
        except (UnicodeDecodeError, ValueError):
            # In case the data cannot be decoded, return raw data.
            # This "feature" can be used to communicate with services that
            # don't handle json data, but only raw bytes.
            return data

    # Override methods of cellaserv.client.AsynClient

    def on_request(self, req):
        """
        on_request(req) is called when a request is received by the service.
        """
        if (req.HasField('service_identification')
                and req.service_identification != self.identification):
            logger.error("Dropping request for wrong identification")
            return

        method = req.method

        try:
            callback = self._actions[method]
        except KeyError:
            logger.error("No such method: %s.%s", self, method)
            self.reply_error_to(req, cellaserv.client.Reply.Error.NoSuchMethod,
                                method)
            return

        try:
            data = self._decode_msg_data(req)
        except Exception as e:
            logger.error("Bad arguments formatting: %s",
                         _request_to_string(req), exc_info=True)
            self.reply_error_to(req, cellaserv.client.Reply.Error.BadArguments,
                                req.data)
            return

        try:
            logger.debug("Calling %s/%s.%s(%s)...",
                         self.service_name, self.identification, method, data)
            reply_data = callback(self, **data)
            logger.debug("Called  %s/%s.%s(%s) = %s",
                         self.service_name, self.identification, method, data,
                         reply_data)
            # Method may, or may not return something. If it returns some data,
            # it must be encoded in json.
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
        """
        Help about this service.

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
            try:
                sig = action_name + str(inspect.signature(bound_f))
            except AttributeError:  # because python 3.1 fuck you
                sig = action_name + \
                      inspect.formatargspec(*inspect.getfullargspec(foo))
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
            if not hasattr(f, '__self__') or f.__self__ is not None:
                bound_f = f
            else:  # f is not bound
                # try to get bound version of this method
                bound_f = getattr(self, f.__name__)
            doc[event] = (inspect.getdoc(bound_f)
                          or str(inspect.signature(bound_f)))

        return doc

    help_events._actions = ['help_events']

    def kill(self) -> "Does not return.":
        """Kill the service."""
        os.kill(os.getpid(), 9)

    kill._actions = ['kill']

    def stacktraces(self) -> dict:
        """Return a stacktrace for each thread running."""
        ret = {}
        for thread_id, stack in sys._current_frames().items():
            ret[thread_id] = '\n'.join(traceback.format_stack(stack))
        return ret

    stacktraces._actions = ['stacktraces']

    # Convenience methods

    def __call__(self, event, **kwargs):
        """
        Send a publish message.

        :param event str: Event name
        :param **kwargs: Data sent along the publish message, will be encoded
                         in json.
        """
        self.publish(event, data=json.dumps(kwargs).encode())

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

        # Publish log message to cellaserv
        self.publish(log_name, data=json.dumps(kwargs).encode())

        # Also log to stdout
        logger.Info("[Log] %s", kwargs)

    # Main setup of the service

    def setup(self):
        """
        setup() will use the socket connected to cellaserv to initialize the
        service.

        Use this if you want to setup multiple service before running
        ``Service.loop()``.
        """

        if not self.service_name:
            # service name is class name in lower case
            self.service_name = self.__class__.__name__.lower()

        self._setup_synchronous()
        self._setup_asynchronous()

        logger.info("[Dependencies] Service ready!")

    def _setup_synchronous(self):
        """
        setup_synchronous manages the static initialization of the service.
        When this methods return, the service should be fully functionnal.

        What needs to be synchronously setup:

        - dependencies, that is we have to wait for them to be online,
        - configuration variables should have the default value.
        """

        # Reuse our socket to create a synchronous client
        syn_client = SynClient(self._socket)

        # Setup for ConfigVariable, get base value using the synchronous client
        def _on_config_registered_wrap(variable):
            """Whis wrapper create a scope for 'variable'"""
            def on_config_registered():
                """
                on_config_registered is called when the 'config' service is
                available. It sends a request to 'config' to get de default
                value of the variable.
                """
                # Get the value of the configuration variable
                req_data = {
                    'section': variable.section,
                    'option': variable.option
                }
                req_data_bytes = json.dumps(req_data).encode()
                # Send the request
                data = syn_client.request('get', 'config', data=req_data_bytes)
                # Data is json encoded
                args = self._decode_data(data)
                logger.info("[ConfigVariable] %s.%s is %s", variable.section,
                            variable.option, args)
                # we don't use update() because the context of the service is
                # not yet initialized, and it is not an update of a previous
                # value (because there isn't)
                variable.value = args
            return on_config_registered

        # When the service 'config' is available, request base values for
        # ConfigVariables, using syn_client
        for variable in self._config_variables:
            self._service_dependencies['config'].append(
                _on_config_registered_wrap(variable))

        self._setup_dependencies(syn_client)

    def _setup_dependencies(self, syn_client):
        """
        Wait for all dependencies, synchronously.

        TODO
        ----

        - Add dependency to a service with a specific identification.

        Implementation
        --------------

        In the class, we setup a dictionary of services names that maps to a
        list of functions that will be called when the service is available.

        When the service setup() method is called a SynClient is used to:

        - for each dependency 'S', subscribe to 'new-service.S'
        - request the service 'cellaserv' for the list of currently connected
          services, using the 'list-services' method. Dependencies already
          registered are removed from the list of waited depencies
        - wait for publish messages 'new-service.<service>' for each
          dependency.
        - when all services are registered, call callbacks
        """

        if not self._service_dependencies:
            # No dependencies, return early
            return

        # First register for new services, so that we don't loose a service if
        # it register just after the 'list-services' call.
        for service in self._service_dependencies:
            syn_client.subscribe('log.cellaserv.new-service.' + service)

        # The set of services we are waiting.
        services_unregistered = set(self._service_dependencies.keys())

        # Get the list of already registered service.
        data = syn_client.request('list-services', 'cellaserv')
        # Go JSON's implementation sends null for the empty slice
        services_registered = self._decode_data(data) or []
        for service in services_registered:
            services_unregistered.remove(service['Name'])

        # Wait for all service to have registered
        while services_unregistered:
            logger.debug("[Dependencies] Waiting for %s",
                         services_unregistered)
            msg = syn_client.read_message()
            if msg.type == Message.Publish:
                # We are waiting for a pubish or form:
                # 'new-service.<service>'
                # It is sent automatically by cellaserv when a new service is
                # registered
                pub = Publish()
                pub.ParseFromString(msg.content)
                if pub.event.startswith('log.cellaserv.new-service.'):
                    service = pub.event.split('.')[3]
                    try:
                        services_unregistered.remove(service)
                        logger.debug("[Dependencies] Waited for %s", service)
                    except KeyError:
                        logger.error("Received a 'new-service' event for"
                                     "the wrong service: %s",
                                     MessageToString(msg))
                        continue
                else:
                    logger.error("Dropping non 'new-service' publish: %s",
                                 MessageToString(pub))
            else:
                logger.error("Dropping unknown message: %s",
                             MessageToString(msg))

        for callbacks in self._service_dependencies.values():
            for callback in callbacks:
                callback()

    def _setup_asynchronous(self):
        """
        Setup the asynchronous part of the service, that is implemented by its
        superclass.

        When this method returns, the service is ready to be managed by an
        event loop, and have requests, events, etc. dispatched to it.
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

        super().__init__(self._socket)

        # Subsribe to all events
        for event_name, callback in self._events.items():
            self.add_subscribe_cb(event_name, _event_wrap(callback))

        # Register the service last
        self.register(self.service_name, self.identification)

        # Start threads
        for method in self._threads:
            threading.Thread(target=method, args=(self,)).start()

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
