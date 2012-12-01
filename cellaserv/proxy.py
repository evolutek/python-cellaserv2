"""
Proxy object for cellaserv.

Example usage::

    >>> from cellaserv.proxy import CellaservProxy
    >>> robot = CellaservProxy()
    >>> robot.date.time()
    1353714592
"""

import socket

import cellaserv.client

class ActionProxy:

    def __init__(self, action, service, identification, client):
        self.action = action
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

class CellaservProxy(cellaserv.client.SynClient):

    def __init__(self, client=None, host="evolutek.org", port=4200):
        if client:
            self.client = client
        else:
            self.socket = socket.create_connection((host, port))
            self.client = cellaserv.client.SynClient(self.socket)

    def __getattr__(self, service_name):
        return ServiceProxy(service_name, self.client)
