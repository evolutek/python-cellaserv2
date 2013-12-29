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
    return the ``request`` id of the message, not the actual response. If you
    want to have it, you must use a SynClient (wich is what is used if
    CellaservProxy is not created with a ``client`` argument).
"""

import json
import logging
import socket

import cellaserv.client
import cellaserv.settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG if cellaserv.settings.DEBUG >= 1 else logging.INFO)

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
        logger.debug("%s[%s].%s(%s) = %s", self.service, self.identification,
                self.action, data, ret)
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
        """Send a publish message.

        :param event string: The event name.
        :param kwargs dict: Optional data sent with the event.
        """
        logger.debug("Publish %s(%s)", event, kwargs)
        self.client.publish(event=event,
                            data=json.dumps(kwargs).encode("utf8"))
