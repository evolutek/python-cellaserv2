"""Proxy object for cellaserv.

Data for requests and events is encoded as JSON objects.

Example usage::

    >>> from cellaserv.proxy import CellaservProxy
    >>> robot = CellaservProxy()
    >>> robot.date.time()
    1353714592
    >>> # Send event 'match-start'
    >>> robot('match-start')
    >>> # Send event 'wait' with data
    >>> robot('wait', seconds=2)
"""

import json
import socket

import cellaserv.client
import cellaserv.settings

class ActionProxy:
    """Action proxy for cellaserv."""

    def __init__(self, action, service, identification, client):
        self.action = action
        self.service = service
        self.identification = identification
        self.client = client

    def __call__(self, **data):
        raw_data = self.client.request(self.action,
                                       service=self.service,
                                       identification=self.identification,
                                       data=json.dumps(data).encode("utf8"))
        if raw_data is not None:
            ret = json.loads(raw_data.decode("utf8"))
        else:
            ret = None
        return ret

    # IPython

    def getdoc(self):
        raw_data = self.client.request('help_action',
                                       service=self.service,
                                       data=json.dumps(
                                           {'action': self.action}))
        return raw_data.decode("utf8")

class ServiceProxy:
    """Service proxy for cellaserv."""

    def __init__(self, service_name, client):
        self.service_name = service_name
        self.client = client
        self.identification = None

    def __getattr__(self, action):
        if action.startswith('__') or action in ['getdoc']:
            return super().__getattr__(action)

        action = ActionProxy(action, self.service_name, self.identification,
                self.client)
        return action

    def __getitem__(self, identification):
        self.identification = identification
        return self

    # IPython

    def getdoc(self):
        raw_data = self.client.request('help', service=self.service_name)
        return raw_data.decode("utf8")

class CellaservProxy():
    """Proxy class for cellaserv."""

    def __init__(self, client=None, host=None, port=None):
        self.socket = None

        if client:
            self.client = client
        else:
            self.socket = cellaserv.settings.get_socket()
            self.client = cellaserv.client.SynClient(self.socket)

    def __getattr__(self, service_name):
        return ServiceProxy(service_name, self.client)

    def __del__(self):
        if self.socket:
            self.socket.close()

    def __call__(self, event, **kwargs):
        """Send a publish message.

        :param event string: The event name.
        :param kwargs dict: Optional data sent with the event.
        """
        self.client.publish(event=event,
                            data=json.dumps(kwargs).encode("utf8"))
