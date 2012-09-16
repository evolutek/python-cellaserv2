#!/usr/bin/env python3
"""Python client for cellaserv and the Evo13 protocol

require:
 - a running cellaserv instance to connect to

Sample usage is provided in the example folder.
"""

__version__ = "0.1"

import asynchat
import json

class Client(asynchat.async_chat):
    """Python implementation of the Evo13 protocol"""

    def __init__(self, sock):
        super(Client, self).__init__(sock=sock)

        self.ibuffer = []
        self.set_terminator(b'\n')

        self.n = 0

    def collect_incoming_data(self, data):
        """Buffer the data"""
        self.ibuffer.append(data)

    def found_terminator(self):
        """Process incoming message"""
        byte_data = b''.join(self.ibuffer)
        self.ibuffer = []
        json_message = byte_data.decode('ascii')
        message = json.loads(json_message)

        self.message_recieved(message)

    def send_message(self, message):
        """Serialize and send a message (python dict) to the server"""
        self.message_sent(message)

        json_message = json.dumps(message).encode('ascii')
        self.push(json_message + b'\n')

    def register_service(self, name, identification=None):
        """Send a register command"""
        message = {}
        message['command'] = 'register'
        message['service'] = name
        if identification:
            message['identification'] = identification

        self.send_message(message)

    def query(self, action, to_service=None, to_identification=None):
        """Send a query command"""
        message = {}
        message['command'] = 'query'
        if to_service:
            message['service'] = to_service
        if to_identification:
            message['identification'] = to_identification
        message['action'] = action

        message['id'] = self.n
        self.n += 1

        self.send_message(message)

    def notify(self, message_content, from_service, from_identification=None):
        """Send a notify command"""
        message = {}
        message['command'] = 'notify'
        message['service'] = from_service
        if from_identification:
            message['identification'] = from_identification
        message['data'] = message_content

        self.send_message(message)

    def message_recieved(self, message):
        print("<< " + str(message))

    def message_sent(self, message):
        print(">> " + str(message))
