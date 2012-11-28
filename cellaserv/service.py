import asyncore
import inspect
import socket
import sys
import traceback

import cellaserv.client

class Service(cellaserv.client.AsynClient):

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

    # TODO: Allow using already connected client
    def __init__(self, identification=None):
        # setup socket
        try:
            import local_settings
            HOST, PORT = local_settings.HOST, local_settings.PORT
        except:
            print("Could not find 'local_settings.py', "
                    "using default host:port (evolutek.org:4200)",
                    file=sys.stderr)
            HOST, PORT = "evolutek.org", 4200

        if not self.identification:
            self.identification = identification

        sock = socket.create_connection((HOST, PORT))
        super().__init__(sock)

    # Decorators

    @classmethod
    def action(cls, method, action=None):
        if not action:
            action = method.__name__.replace("_", "-")

        try:
            method._actions.append(action)
        except AttributeError:
            method._actions = [action]

        return method

    @classmethod
    def event(cls, method, event=None):
        if not event:
            event = method.__name__.replace("_", "-")

        try:
            method._events.append(event)
        except AttributeError:
            method._events = [event]

        return method

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
            ack['data'] = "Unknown action: " + action
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
