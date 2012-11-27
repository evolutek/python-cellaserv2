import asyncore
import socket
import sys
import traceback

import cellaserv.client

class Service(cellaserv.client.AsynClient):

    # Default actions

    def version(self):
        ret = {}
        if self.version:
            ret['version'] = self.version
        if self.variant:
            ret['variant'] = self.variant
        return ret

    _actions = {'version': version}
    _events = {}

    service_name = None
    identification = None
    variant = "python"
    version = None

    # Decorators

    @classmethod
    def action(cls, method, action=None):
        if action:
            cls._actions[action] = method
        else:
            cls._actions[method.__name__.replace("_", "-")] = method

        return method

    @classmethod
    def event(cls, method, event=None):
        if event:
            cls._events[event] = method
        else:
            cls._events[method.__name__.replace("_", "-")] = method

        return method

    # Regular methods

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

    # TODO: Check identification
    def query_recieved(self, query):
        action = query['action']

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

    # Convenience methods

    def setup(self):
        """Use this if you want to setup multiple service before running
        ``Service.loop()``."""
        if self.service_name:
            service_name = self.service_name
        else:
            service_name = self.__class__.__name__.lower()

        self.register_service(service_name, self.identification)

        for event_name, callback in self._events.items():
            self.subscribe_event(event_name)
            self.connect_event(event_name, callback)

    def run(self):
        """One-shot to setup and start the service."""
        self.setup()
        Service.loop()

    @classmethod
    def loop(cls):
        asyncore.loop()
