"""
Proxy object for cellaserv.

Default server: ``evolutek.org`` port ``4200``.

Example usage::

    >>> from cellaserv.proxy import CellaservProxy
    >>> robot = CellaservProxy()
    >>> robot.date.time()
    1353714592
"""

import socket

import cellaserv.client
import cellaserv.settings

class ActionProxy:
    """Action proxy for cellaserv."""

    def __init__(self, action, service, identification, client):
        self.action = action.replace('_', '-')
        self.service = service
        self.identification = identification
        self.client = client

    def __call__(self, **data):
        if self.identification:
            resp = self.client.query(self.action, to_service=self.service,
                    to_identification=self.identification, data=data)
        else:
            resp = self.client.query(self.action, to_service=self.service,
                    data=data)

        try:
            return resp['data']
        except:
            return resp

class ServiceProxy:
    """Service proxy for cellaserv."""

    def __init__(self, service_name, client):
        self.service_name = service_name
        self.client = client
        self.identification = None

    def __getattr__(self, action):
        action = ActionProxy(action, self.service_name, self.identification,
                self.client)
        return action

    def __getitem__(self, identification):
        self.identification = identification
        return self

class CellaservProxy():
    """Proxy class for cellaserv."""

    def __init__(self, client=None, host=None, port=None):
        if client:
            self.client = client
        else:
            host = host if host else cellaserv.settings.HOST
            port = port if port else cellaserv.settings.PORT

            self.socket = socket.create_connection((host, port))
            self.client = cellaserv.client.SynClient(self.socket)

    def __getattr__(self, service_name):
        return ServiceProxy(service_name, self.client)
