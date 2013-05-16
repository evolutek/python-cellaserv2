"""
Proxy object for cellaserv.

Default server: ``evolutek.org`` port ``4200``.

Example usage::

    >>> from cellaserv.proxy import CellaservProxy
    >>> robot = CellaservProxy()
    >>> robot.date.time()
    1353714592

From within a Service::

    >>> from cellaserv.service import Service
    >>> from cellaserv.proxy import CellaservProxy
    >>> class Foo(Service):
    ...     def __init__(self):
    ...         super().__init__()
    ...         self.cs = CellaservProxy(client=self)

.. warning::

    Using the Service as client for the proxy can be misleading.

    Service is a subclass of AsynClient, call to cs.service.action() will
    return the ``ack`` id of the message, not the actual response. If you want
    to have it, you must use a SynClient (wich is what is used if
    CellaservProxy is not created with a ``client`` argument).
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

    # IPython

    def getdoc(self):
        #import pdb; pdb.set_trace()
        resp = self.client.query('help-action', to_service=self.service,
                data={'action': self.action})
        try:
            return resp['data']
        except KeyError:
            return "No documentation"

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
        resp = self.client.query('help', to_service=self.service_name)
        try:
            return resp['data']
        except KeyError:
            return "No documentation"

class CellaservProxy():
    """Proxy class for cellaserv."""

    def __init__(self, client=None, host=None, port=None):
        self.socket = None

        if client:
            self.client = client
        else:
            host = host if host else cellaserv.settings.HOST
            port = port if port else cellaserv.settings.PORT

            self.socket = socket.create_connection((host, port))
            self.client = cellaserv.client.SynClient(self.socket)

    def __getattr__(self, service_name):
        return ServiceProxy(service_name, self.client)

    def __del__(self):
        if self.socket:
            self.socket.close()

    def __call__(self, event, **kwargs):
        """Send a notify message.

        :param event string: The event name.
        :param kwargs dict: Optional data sent with the event.
        """

        self.client.notify(event=event, event_data=kwargs)
