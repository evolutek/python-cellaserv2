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

You can use ``self.publish('event_name')`` to send an event.

You can use ``self.log()`` to produce log entries for your service.

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
will instanciate multiple services, then give control to the async loop with
Service.loop().

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
    >>> Service.loop()

Dependencies
------------

You can specify that your service depends on another service using the
@Service.require('my_other_service') class decorator.

    >>> from cellaserv.service import Service
    >>> @Service.require('hokuyo')
    ... class WithDep(Service):
    ...     pass
    >>> # You can also specify a identification
    >>> @Service.require('hokuyo', identification='table')
    ... class WithDep2(Service):
    ...     pass

When the service is instanciated, it will wait for all the dependencies to be
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
import io
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
    ThreadingEvent = threading._Event
else:
    ThreadingEvent = threading.Event

if 'callable' not in dir(__builtins__):
    def callable(f):
        return hasattr(f, '__call__')


class Event(ThreadingEvent):
    """
    Events help you share states between services.

    Events can also contain data, set by cellaserv publish messages. When a
    service publishs the event associated with this Event, the underlying
    threading.Event will be set() and any thread wait()ing for it will we
    awaken.

    Events are thread-safe. That is mutliple threads can wait() this varible
    and each of then will be woken up when the variable is set().

    Example::

        >>> from cellaserv.service import Service, Event
        >>> class Timer(Service):
        ...     t = Event()
        ...     ...
    """

    def __init__(self, set=None, clear=None):
        """
        Define a new cellaserv Event.

        :param set str: Event that sets the variable
        :param clear str: Event that clears the variable
        """
        super().__init__()

        self.name = "?"  # set by Service to the name of the declared field
        # Optional data held by the event
        self.data = {}

        # Events that set/clear the event, if they are different from the name
        self._event_set = set
        self._event_clear = clear

    def __call__(self):
        """
        Returns the current value of the event.

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

    def __init__(self, section, option, coerc=str):
        """
        Define a new config variable using the 'config service'.

        :param section str: The section of this variable (eg. match, robot,
            etc.)
        :param option str: The option corresponding to this variable in the
            section.
        :param coerc function: The value will by passed to this function and
            the result will be the final value.
        """
        self.section = section
        self.option = option
        self.update_cb = []
        self.value = None
        self.coerc = coerc

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
        self.value = self.coerc(value)
        for cb in self.update_cb:
            cb(self.value)

    def set(self, value):
        """set(value) is called when setting the value, not updating it."""
        self.value = self.coerc(value)

    def __call__(self):
        """
        Returns the current value of the variable.

        Handy syntactic sugar.
        """
        return self.value


class ServiceMeta(type):

    def __init__(cls, name, bases, nmspc):
        """
        ``__init__()`` is called when a new type of Service is needed.

        This method setups the list of actions (cls._actions) and subscribed
        events (cls._event) in the new class.

        Basic level of metaprogramming magic.
        """

        def _event_wrap_set(event):
            def _event_set(self, **kwargs):
                logger.debug("Event %s set, data=%s", event.name, kwargs)
                event.data = kwargs
                event.set()
            return _event_set

        def _event_wrap_clear(event):
            def _event_clear(self, **kwargs):
                logger.debug("Event %s cleared, data=%s", event.name,
                             kwargs)
                event.data = kwargs
                event.clear()
            return _event_clear

        def _config_var_wrap_event(variable):
            def _variable_update(self, value):
                variable.update(value=value)
            return _variable_update

        _actions = {}
        _config_variables = []
        _events = {}
        _threads = []

        # Go through all the members of the class, check if they are tagged as
        # action, events, etc. Wrap them if necessary then store them in lists.
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

            elif isinstance(member, Event):
                member.name = name
                event_set = member._event_set or name
                event_clear = member._event_clear or name + "_clear"
                _events[event_set] = _event_wrap_set(member)
                _events[event_clear] = _event_wrap_clear(member)

        cls._actions = _actions
        cls._config_variables = _config_variables
        cls._events = _events
        cls._threads = _threads

        cls._service_dependencies = defaultdict(list)

        return super().__init__(cls)


class Service(AsynClient, metaclass=ServiceMeta):

    # Mandatory name of the service as it will appeared for cellaserv.
    service_name = None
    # Optional identification string used to register multiple instances of the
    # same service.
    identification = None

    # Protocol helpers

    @staticmethod
    def _decode_msg_data(msg):
        """Returns the data contained in a message."""
        if msg.HasField('data'):
            return Service._decode_data(msg.data)
        else:
            return {}

    @staticmethod
    def _decode_data(data):
        """Returns the data contained in a message."""
        try:
            obj = data.decode()
            return json.loads(obj)
        except (UnicodeDecodeError, ValueError):
            # In case the data cannot be decoded, return raw data.
            # This "feature" can be used to communicate with services that
            # don't handle json data, but only raw bytes.
            return data

    # Class decorators

    @classmethod
    def require(cls, service, identification="", cb=None):
        """
        Use the ``Service.require`` class decorator to specify a dependency
        between this service and ``service``. This service will not start
        before the ``service`` service is registered on cellaserv. Optionally
        you can specify a callback ``cb`` that will be called when the service
        dependency is satisfied.

        This operation may delay the start of service, because it must wait for
        all dependencies to be registered.
        """

        depend = (service, identification)

        def class_builder(cls):
            if cb:
                cls._service_dependencies[depend].append(cb)
            else:
                # this will create an entry in the dict if it does not exists
                cls._service_dependencies[depend]

            return cls

        return class_builder

    # Methods decorators

    @staticmethod
    def action(method_or_name):
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

    @staticmethod
    def event(method_or_name):
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

    @staticmethod
    def thread(method):
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

        if not self.service_name:
            # service name is class name in lower case
            self.service_name = self.__class__.__name__.lower()

        self.identification = identification or self.identification

        if not sock:
            # Get a socket from cellaserv configuration mechanism
            sock = cellaserv.settings.get_socket()
        self._socket = sock

        self._setup()

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

            # Guess type of arguments passing
            if type(data) is list:
                args = data
                kwargs = {}
            elif type(data) is dict:
                args = []
                kwargs = data
            else:
                args = [data]
                kwargs = {}

            # We use the desciptor's __get__ because we don't know if the
            # callback should be bound to this instance.
            bound_cb = callback.__get__(self, type(self))
            reply_data = bound_cb(*args, **kwargs)
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
                                str(e))
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

    def _get_help(self, methods) -> dict:
        """
        Helper function that create a dict with the signature and the
        documentation of a mapping of methods.
        """
        docs = {}
        for name, unbound_f in methods.items():
            # Get the function from self to get a bound method in order to
            # remove the first parameter (class name).
            bound_f = unbound_f.__get__(self, type(self))
            doc = inspect.getdoc(bound_f) or ""

            # Get signature of this method, ie. how the use must call it
            if sys.version_info.minor < 3:
                sig = (name +
                       inspect.formatargspec(*inspect.getfullargspec(bound_f)))
            else:
                sig = name + str(inspect.signature(bound_f))

            docs[name] = {'doc': doc, 'sig': sig}
        return docs

    def help_actions(self) -> dict:
        """List available actions for this service."""
        return self._get_help(self._actions)

    help_actions._actions = ['help_actions']

    def help_events(self) -> dict:
        """List subscribed events of this service."""
        return self._get_help(self._events)

    help_events._actions = ['help_events']

    # Note: we cannot use @staticmethod here because the descriptor it creates
    # is shadowing the attribute we add to the method.
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

    def publish(self, event, *args, **kwargs):
        """
        Send a publish message.

        :param event str: Event name
        :param **kwargs: Data sent along the publish message, will be encoded
                         in json.
        """

        if args and kwargs:
            logging.error("Cannot publish with both args and kwargs")
            traceback.print_stack()
            kwargs['args'] = repr(args)
            pub_data = kwargs
        elif args:
            pub_data = args
        else:
            pub_data = kwargs

        try:
            data = json.dumps(pub_data)
        except:
            self.log_exc()
            logging.error("Could not serialize publish data: %s", pub_data)
            data = repr(pub_data)

        super().publish(event=event, data=data.encode())

    def log(self, *args, what=None, **log_data):
        """
        Send a log message to cellaserv using the service's name and
        identification, if any. ``what`` is an optional topic for the log. If
        provided, it will we appened to the log name.

        Logs in cellaserv are implemented using event with the form
        ``log.<service_name>.<optional service_ident>.<optional what>``.
        """
        log_name = 'log.' + self.service_name

        if self.identification:
            log_name += '.' + self.identification

        if what:
            log_name += '.' + what

        if args:
            # Emulate a call to print()
            out = io.StringIO()
            print(*args, end='', file=out)
            out.seek(0)
            log_data['msg'] = out.read()

        # Publish log message to cellaserv
        self.publish(event=log_name, **log_data)

    def log_exc(self):
        """Log the current exception."""

        str_stack = ''.join(traceback.format_exc())
        super().publish(event='log.coding-error', data=str_stack.encode())

    # Main setup of the service

    def _setup(self):
        """
        _setup() will use the socket connected to cellaserv to initialize the
        service.
        """

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
                variable.set(args)
            return on_config_registered

        # When the service 'config' is available, request base values for
        # ConfigVariables, using syn_client
        for variable in self._config_variables:
            self._service_dependencies[('config', '')].append(
                _on_config_registered_wrap(variable))

        self._setup_dependencies(syn_client)

    def _setup_dependencies(self, syn_client):
        """
        Wait for all dependencies, synchronously.

        Implementation
        --------------

        In the class, we setup a dictionary of services names that maps to a
        list of functions that will be called when the service is available.

        When the service _setup() method is called a SynClient is used to:

        - subscribe to 'log.cellaserv.new-service' to get notified of new
          services.
        - request the service 'cellaserv' for the list of currently connected
          services, using the 'list-services' method. Dependencies already
          registered are removed from the list of waited depencies
        - wait for publish messages 'log.cellaserv.new-service' for each
          dependency.
        - when all services are registered, call callbacks
        """

        if not self._service_dependencies:
            # No dependencies, return early
            return

        # We use a set for easier removal
        services_unregistered = set(self._service_dependencies.keys())

        # First register for new services, so that we don't miss a service
        # if it registers just after the 'list-services' call.
        syn_client.subscribe('log.cellaserv.new-service')

        # Get the list of already registered service.
        data = syn_client.request('list-services', 'cellaserv')
        services_registered = self._decode_data(data)

        for service in services_registered:
            service_ident = (service['Name'], service['Identification'])
            try:
                services_unregistered.remove(service_ident)
            except KeyError:
                pass  # We were not waiting for this service.

        # Wait for all service to have registered.
        while services_unregistered:
            logger.info("[Dependencies] Waiting for %s",
                        services_unregistered)
            msg = syn_client.read_message()
            if msg.type == Message.Publish:
                # We are waiting for a pubish or form:
                # 'log.cellaserv.new-service'
                # It is sent automatically by cellaserv when a new service is
                # registered
                pub = Publish()
                pub.ParseFromString(msg.content)
                if pub.event == 'log.cellaserv.new-service':
                    data = json.loads(pub.data.decode())
                    name_ident = (data['Name'], data['Identification'])
                    try:
                        services_unregistered.remove(name_ident)
                        logger.info("[Dependencies] Waited for %s", name_ident)
                    except KeyError:
                        pass  # It was not a service we were waiting for.
                else:
                    logger.error("Dropping non 'new-service' publish: %s",
                                 MessageToString(pub))
            else:
                logger.error("Dropping unknown message: %s",
                             MessageToString(msg))

        # We have waited for all the dependencies to register.
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
                    fun(**kwargs)
                except:
                    self.log_exc()

            return _wrap

        super().__init__(self._socket)

        # Subsribe to all events
        for event_name, callback in self._events.items():
            callback_bound = callback.__get__(self, type(self))
            self.add_subscribe_cb(event_name, _event_wrap(callback_bound))

        # Register the service last
        self.register(self.service_name, self.identification)

        # Start threads
        for method in self._threads:
            method_bound = method.__get__(self, type(self))
            t = threading.Thread(target=method_bound)
            t.daemon = True
            t.start()

    def run(self):
        """
        Sugar for starting the service.
        """
        Service.loop()

    @staticmethod
    def loop():
        """
        loop() will start the asyncore engine therefore, if you have not
        started another thread, only callbacks (eg. actions, events) will be
        called.
        """
        asyncore.loop()
