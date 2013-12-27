"""
Python base class for writing clients for cellaserv.

These classes only manipulates protobuf *messages*. If you are looking for a
high level API you should use ``cellaserv.service.Service``.

Sample usage is provided in the ``example/`` folder of the source distribution.
"""

import asynchat
import logging
import struct

from collections import defaultdict

from protobuf.cellaserv_pb2 import (
        Message,
        Register,
        Request,
        Reply,
        Publish,
        Subscribe
)

from google.protobuf.text_format import MessageToString

class MessageTimeout(Exception):
    pass

class ErrorMessage(Exception):
    pass

class BadMessage(Exception):
    pass

class AbstractClient:
    """Abstract client. Send protobuf messages."""

    def __init__(self):
        # Nonce used to identify requests
        self._request_seq_id = 0

    def send_message(self, msg, *args, **kwargs):
        self._send_message(msg.SerializeToString(), *args, **kwargs)

    def _send_message(self, *args, **kwargs):
        """Implementation specific method for sending messages."""
        raise NotImplementedError

    ### Actions

    def register(self, name, identification=None, *args, **kwargs):
        """Send a ``register`` message.

        :param str name: Name of the new service
        :param str identification: Optional identification for the service
        :rtype: None"""


        register = Register(name=name)
        if identification:
            register.identification = identification

        message = Message(type=Message.Register,
                          content=register.SerializeToString())

        self.send_message(message, *args, **kwargs)

    def request(self, method, service, identification=None, data=None,
            *args, **kwargs):
        """Send a ``request`` message.

        :return: The message id
        :rtype: int"""

        request = Request(service_name=service, method=method)
        if identification:
            request.service_identification = identification
        if data:
            request.data = data
        request.id = self._request_seq_id
        self._request_seq_id += 1

        message = Message(type=Message.Request,
                          content=request.SerializeToString())

        self.send_message(message, *args, **kwargs)

        return request.id

    def publish(self, event, data=None, *args, **kwargs):
        """Send a ``publish`` message"""

        publish = Publish(event=event)
        if data:
            publish.data = data

        message = Message(type=Message.Publish,
                          content=publish.SerializeToString())

        self.send_message(message, *args, **kwargs)

    def subscribe(self, event, *args, **kwargs):
        """Send a ``subscribe`` message."""

        subscribe = Subscribe(event=event)

        message = Message(type=Message.Subscribe,
                          content=subscribe.SerializeToString())

        self.send_message(message, *args, **kwargs)

class SynClient(AbstractClient):
    """Synchronous cellaserv client.

    Wait for ``response`` after every ``request`` message."""

    def __init__(self, sock):
        super().__init__()

        self._socket = sock

    def _send_message(self, msg, *args, **kwargs):
        self._socket.send(struct.pack("!I", len(msg)))
        self._socket.send(msg)

    ### Actions

    def request(self, *args, **kwargs):
        """Blocking ``request``."""
        req_id = super().request(*args, **kwargs)

        while True:
            # Receive message header
            hdr = bytearray()
            hdr_remaining = 4 # == struct.calcsize("I") == sizeof (uint32)
            while hdr_remaining != 0:
                recv_len = self._socket.recv_into(hdr, hdr_remaining)
                hdr_remaining -= recv_len
            # Header is the size of the message as a uint32 in network byte order
            msg_len = struct.unpack("!I", hdr)

            # Receive message
            msg = bytearray()
            msg_remaining = msg_len
            while msg_remaining != 0:
                recv_len = self._socket.recv_into(msg, msg_remaining)
                msg_remaining -= recv_len

            # Parse message
            message = Message()
            message.ParseFromString(msg)
            if message.type != Message.Reply:
                logging.warning("Received a non Reply message, dropping:")
                logging.warning(MessageToString(message))
                continue

            reply = Reply
            reply.ParseFromString(message.content)
            if reply.id != req_id:
                logging.warning(
                    "Received a Reply for the wrong Request, dropping:")
                logging.warning(MessageToString(reply))
                continue

            return reply.data

class AsynClient(asynchat.async_chat, AbstractClient):
    """Asynchronous cellaserv client."""

    def __init__(self, sock):
        # Init base classes
        async_chat.async_chat().__init__(sock=sock)
        AbstractClient.__init__(self)

        # setup asynchat
        self.set_terminator(4) # first, we are looking for a message header
        # hold incoming data
        self._ibuffer = bytearray()
        self._read_header = True

        # map events to a list of callbacks
        self._events_cb = defaultdict(list)

    def _send_message(self, message, *args, **kwargs):
        # 'push' is asynchat version of socket.send
        self.push(struct.pack("!I", len(msg)))
        self.push(msg)

    # Asyncore methods

    def collect_incoming_data(self, data):
        """Store incoming data in the buffer."""
        self._ibuffer.extend(data)

    def found_terminator(self):
        """Process an incoming header or message."""

        if self._read_header:
            self._read_header = False

            msg_len = struct.unpack("!I", self._ibuffer)
            self.set_terminator(msg_len)

            self._ibuffer.clear()
        else:
            self._read_header = True
            self.set_terminator(4)

            msg = Message()
            msg.ParseFromString(self._ibuffer)

            self._ibuffer.clear()

            self._message_recieved(msg)

    # Methods called by subclasses

    def add_subscribe_cb(self, event, event_cb):
        """On event ``event`` recieved, call ``event_cb``"""
        self._events_cb[event].append(event_cb)

    # Callbacks

    def on_message_recieved(self, msg):
        """Called on incoming message from cellaserv."""
        if msg.type == Message.Request:
            req = Request()
            req.ParseFromString(msg.content)
            self.recieved_request(req)
        elif msg.type == Message.Reply:
            rep = Reply()
            rep.ParseFromString(msg.content)
            self.received_reply(rep)
        elif msg.type == Message.Publish:
            pub = Publish()
            pub.ParseFromString(msg.content)
            for cb in self._events_cb[pub.event]:
                if pub.HasField('data'):
                    cb(pub.data)
                else:
                    cb()
        else:
            logging.warning("Invalid message:")
            logging.warning(MessageToString(msg))

    def on_request(self, req):
        pass

    def on_reply(self, rep):
        pass
