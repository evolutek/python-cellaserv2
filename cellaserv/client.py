"""
Python base class for writing clients for cellaserv.

Sample usage is provided in the ``example/`` folder of the source distribution.
"""

__version__ = "0.5"
__protocol_version__ = "0.5"

import asynchat
import json
import uuid

from collections import defaultdict

class AbstractClient:
    """Abstract client"""

    def __init__(self, sock, *args, **kwargs):
        pass

    def send_message(self, message, *args, **kwargs):
        self._message_sent(message)

        return self._send_message(message, *args, **kwargs)

    def _send_message(self, *args, **kwargs):
        raise NotImplementedError

    def _message_sent(self, message):
        """Method call when a message is sent from the client.

        Clients may redefine this method, for example for debugging purposes"""
        self.message_sent(message)

    def message_sent(self, message):
        pass

    def _message_recieved(self, message):
        self.message_recieved(message)

    def message_recieved(self, message):
        pass

    ### Commands

    def register_service(self, name, identification=None, *args, **kwargs):
        """Send a ``register`` command."""
        message = {}
        message['command'] = 'register'
        message['service'] = name
        if identification:
            message['identification'] = identification
        message['id'] = str(uuid.uuid4())

        self.send_message(message, *args, **kwargs)

        return message['id']

    def query(self, action, to_service=None, to_identification=None,
            data=None, *args, **kwargs):
        """Send a ``query`` command.

        Action comes first because every other argument is optional, eg.
        you can broadcast a ping with ``client.query('ping')``."""

        message = {}
        message['command'] = 'query'
        if to_service:
            message['service'] = to_service
        if to_identification:
            message['identification'] = to_identification
        if data:
            message['data'] = data
        message['action'] = action
        message['id'] = str(uuid.uuid4())

        self.send_message(message, *args, **kwargs)

        return message['id']

    def notify(self, event, event_data=None, *args, **kwargs):
        """Send a ``notify`` command"""
        message = {}
        message['command'] = 'notify'
        message['event'] = event
        if event_data:
            message['data'] = event_data

        self.send_message(message, *args, **kwargs)

    def subscribe_event(self, event, *args, **kwargs):
        """Send a ``subscribe`` command to register to an event"""
        message = {}
        message['command'] = 'subscribe'
        message['event'] = event

        self.send_message(message, *args, **kwargs)

    def server(self, action, *args, **kwargs):
        message = {}
        message['command'] = 'server'
        message['action'] = action
        message['id'] = str(uuid.uuid4())

        self.send_message(message, *args, **kwargs)

        return message['id']

class SynClient(AbstractClient):
    """Synchronous cellaserv client.

    Checks server version on __init__()."""

    def __init__(self, sock):
        super().__init__(sock=sock)

        self._socket = sock
        self._buffer = sock.makefile()
        self._messages_waiting = {}

        resp = self.server('protocol-version')
        if resp['data']['protocol-version'] != __protocol_version__:
            print("Warning: Version mismatch between client and server.")

    def _send_message(self, message, *args, **kwargs):
        data = json.dumps(message).encode('ascii')
        self._socket.send(data + b'\n')

    def _read_single_message(self):
        resp = ""
        while not resp:
            resp = self._buffer.readline()

        message = json.loads(resp)

        self._message_recieved(message)

        return message

    def read_message(self, message_id=None):
        if message_id:
            while message_id not in self._messages_waiting:
                new_message = self._read_single_message()
                self._messages_waiting[new_message['id']] = new_message

            message = self._messages_waiting[message_id]
            del self._messages_waiting[message_id]
            return message

        elif self._messages_waiting:
            return self._messages_waiting.popitem()[1]

        else:
            return self._read_single_message()

    ### Commands

    def register_service(self, *args, **kwargs):
        message_id = super().register_service(*args, **kwargs)

        return self.read_message(message_id)

    def query(self, *args, **kwargs):
        message_id = super().query(*args, **kwargs)

        return self.read_message(message_id)

    def server(self, action, *args, **kwargs):
        message_id = super().server(action, *args, **kwargs)

        return self.read_message(message_id)


class SynClientDebug(SynClient):
    """Synchronous debug client.

    Prints mesages sent/recieved"""

    def _message_recieved(self, message):
        print("<< " + str(message).replace("'", '"'))

        super()._message_recieved(message)

    def _message_sent(self, message):
        print(">> " + str(message).replace("'", '"'))

        super()._message_sent(message)


class AsynClient(asynchat.async_chat, AbstractClient):
    """Asynchronous cellaserv client."""

    def __init__(self, sock):
        super().__init__(sock=sock)
        AbstractClient.__init__(self, sock=sock)

        # asyncore specific
        self._ibuffer = []
        self.set_terminator(b'\n')

        self._ack_cb = None
        self._event_cb = defaultdict(list)

    def _send_message(self, message, *args, **kwargs):
        """Serialize and send a message (python dict) to the server"""
        json_message = json.dumps(message).encode('ascii')
        self.push(json_message + b'\n')

    # Asyncore methods

    def collect_incoming_data(self, data):
        """Buffer the data"""
        self._ibuffer.append(data)

    def found_terminator(self):
        """Process incoming message"""
        byte_data = b''.join(self._ibuffer)
        self._ibuffer = []
        json_message = byte_data.decode('ascii')
        message = json.loads(json_message)

        self._message_recieved(message)

    # Methods called by subclasses

    def set_ack_cb(self, f):
        """Method called when a ``ack`` message is recieved"""
        self._ack_cb = f

    def connect_event(self, event, event_cb):
        """On event ``event`` recieved, call ``event_cb``"""
        self._event_cb[event].append(event_cb)

    # Callbacks

    def message_recieved(self, message):
        """Called on incoming message from cellaserv"""
        if 'ack' in message and self._ack_cb:
            self._ack_cb(message)
        elif 'command' in message:
            if message['command'] == 'query':
                self.query_recieved(message)
            elif message['command'] == 'notify':
                for cb in self._event_cb[message['event']]:
                    cb(message)

    def query_recieved(self, query):
        pass


class AsynClientDebug(AsynClient):
    """Asynchronous debug client.

    Prints mesages sent/recieved."""

    def _message_recieved(self, message):
        print("<< " + str(message).replace("'", '"'))

        super()._message_recieved(message)

    def _message_sent(self, message):
        print(">> " + str(message).replace("'", '"'))

        super()._message_sent(message)
