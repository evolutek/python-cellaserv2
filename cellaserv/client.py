#!/usr/bin/env python3
"""Python client for cellaserv and the Evo13 protocol

require:
 - a running cellaserv instance to connect to

Sample usage is provided in the example folder.
"""

__version__ = "0.3"

DEBUG = True

import asynchat
import json
import copy

from collections import defaultdict

class AbstractClient:
    """Python implementation of the Evo13 protocol"""

    def __init__(self, sock, *args, **kwargs):
        if DEBUG:
            self._n = 0 # debug

    def send_message(self, message, *args, **kwargs):
        self._message_sent(message)

        return self._send_message(message, *args, **kwargs)

    def _send_message(self, *args, **kwargs):
        raise NotImplementedError

    def _message_sent(self, message):
        """Client may define this method, for debugging purposes for example"""
        self.message_sent(message)

    def message_sent(self, message):
        pass

    def register_service(self, name, identification=None, *args, **kwargs):
        """Send a register command"""
        message = {}
        message['command'] = 'register'
        message['service'] = name
        if identification:
            message['identification'] = identification

        return self.send_message(message, *args, **kwargs)

    def query(self, action, to_service=None, to_identification=None, data=None,
            *args, **kwargs):
        """Send a query command"""
        message = {}
        message['command'] = 'query'
        if to_service:
            message['service'] = to_service
        if to_identification:
            message['identification'] = to_identification
        if data:
            message.update(data)
        message['action'] = action

        if DEBUG:
            message['id'] = self._n
            self._n += 1

        return self.send_message(message, *args, **kwargs)

    def notify(self, notification, message_content=None, *args, **kwargs):
        """Send a notify command"""
        message = {}
        message['command'] = 'notify'
        message['notify'] = notification
        if message_content:
            message['notify-data'] = message_content

        return self.send_message(message, *args, **kwargs)

    def listen_notification(self, notification, *args, **kwargs):
        """Send a listen command to register to a notification"""
        message = {}
        message['command'] = 'listen'
        message['listen'] = notification

        return self.send_message(message, *args, **kwargs)

    def server_status(self, *args, **kwargs):
        message = {}
        message['command'] = 'status'

        return self.send_message(message, *args, **kwargs)

    def _message_recieved(self, message):
        self.message_recieved(message)

    def message_recieved(self, message):
        pass

class SynClient(AbstractClient):
    """Sync. client"""

    def __init__(self, sock):
        super().__init__(sock=sock)

        self._socket = sock
        self._buffer = sock.makefile()

    def _send_message(self, message, *args, **kwargs):
        data = json.dumps(message).encode('ascii')
        self._socket.send(data + b'\n')

    def read_message(self):
        resp = ""
        while not resp:
            resp = self._buffer.readline()

        message = json.loads(resp)

        self._message_recieved(message)

        return message

class AsynClient(asynchat.async_chat, AbstractClient):
    """Async. client"""

    def __init__(self, sock):
        super().__init__(sock=sock)
        AbstractClient.__init__(self, sock=sock)

        self._ibuffer = []
        self.set_terminator(b'\n')

        self._ack_cb = None
        self._notify_cb = defaultdict(list)

    def set_ack_cb(self, f):
        self._ack_cb = f

    def collect_incoming_data(self, data):
        """Buffer the data"""
        self._ibuffer.append(data)

    def connect_notify(self, notify, notify_cb):
        """On notify 'notify' recieve, call `notify_cb`"""
        self._notify_cb[notify].append(notify_cb)

    def found_terminator(self):
        """Process incoming message"""
        byte_data = b''.join(self._ibuffer)
        self._ibuffer = []
        json_message = byte_data.decode('ascii')
        message = json.loads(json_message)

        self._message_recieved(message)

    def message_recieved(self, message):
        """Called on incoming message from cellaserv"""
        if 'ack' in message and self._ack_cb:
            self._ack_cb(message)
        elif 'command' in message:
            if message['command'] == 'query':
                self.query_recieved(message)
            elif message['command'] == 'notify':
                for cb in self._notify_cb[message['notify']]:
                    cb(message)

    def query_recieved(self, query):
        pass

    def _send_message(self, message, *args, **kwargs):
        """Serialize and send a message (python dict) to the server"""
        json_message = json.dumps(message).encode('ascii')
        self.push(json_message + b'\n')


class SynClientDebug(SynClient):
    def _message_recieved(self, message):
        print("<< " + str(message))

        super()._message_recieved(message)

    def _message_sent(self, message):
        print(">> " + str(message))

        super()._message_sent(message)


class AsynClientDebug(AsynClient):
    def _message_recieved(self, message):
        print("<< " + str(message))

        super()._message_recieved(message)

    def _message_sent(self, message):
        print(">> " + str(message))

        super()._message_sent(message)
