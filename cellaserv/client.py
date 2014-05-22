"""
Python base class for writing clients for cellaserv.

These classes only manipulates protobuf *messages*. If you are looking for a
high level API you should use ``cellaserv.service.Service``.

Sample usage is provided in the ``example/`` folder of the source distribution.
"""

import asynchat
import fnmatch
import logging
import random
import struct

from collections import defaultdict

from google.protobuf.text_format import MessageToString

from cellaserv.protobuf.cellaserv_pb2 import (
    Message,
    Register,
    Request,
    Reply,
    Publish,
    Subscribe
)

from cellaserv.settings import DEBUG

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG if DEBUG >= 2
                else logging.INFO if DEBUG == 1
                else logging.WARNING)

# Exceptions


class ReplyError(Exception):
    def __init__(self, rep):
        self.rep = rep

    def __str__(self):
        return MessageToString(self.rep).decode()


class RequestTimeout(ReplyError):
    pass


class BadArguments(ReplyError):
    pass


class NoSuchService(Exception):
    def __init__(self, service):
        self.service = service

    def __str__(self):
        return "No such service: {0}".format(self.service)


class NoSuchMethod(Exception):
    def __init__(self, service, method):
        self.service = service
        self.method = method

    def __str__(self):
        return "No such method: {0}.{1}".format(self.service, self.method)

# Clients


class AbstractClient:
    """Abstract client. Send protobuf messages."""

    def __init__(self):
        # Nonce used to identify requests
        self._request_seq_id = random.randrange(0, 2**32)

    def send_message(self, msg):
        logger.debug("Sending:\n%s", msg)

        self._send_message(msg=msg.SerializeToString())

    def _send_message(self, *args, **kwargs):
        """Implementation specific method for sending messages."""
        raise NotImplementedError

    def reply_to(self, req, data=None):
        reply = Reply()
        reply.id = req.id
        if data:
            reply.data = data
        msg = Message()
        msg.type = Message.Reply
        msg.content = reply.SerializeToString()
        self.send_message(msg)

    def reply_error_to(self, req, error_type, what=None):
        error = Reply.Error()
        error.type = error_type
        if what is not None:
            error.what = what

        reply = Reply(id=req.id, error=error)

        msg = Message()
        msg.type = Message.Reply
        msg.content = reply.SerializeToString()
        self.send_message(msg)

    # Actions

    def register(self, name, identification=None):
        """Send a ``register`` message.

        :param str name: Name of the new service
        :param str identification: Optional identification for the service
        :rtype: None"""

        register = Register(name=name)
        if identification:
            register.identification = identification

        message = Message(type=Message.Register,
                          content=register.SerializeToString())

        self.send_message(message)

    def request(self, method, service, identification=None, data=None):
        """
        Send a ``request`` message.

        :return: The message id
        :rtype: int"""

        logger.info("[Request] %s/%s.%s(%s)", service, identification, method,
                    data)

        request = Request(service_name=service, method=method)
        if identification:
            request.service_identification = identification
        if data:
            request.data = data
        request.id = self._request_seq_id
        self._request_seq_id += 1

        message = Message(type=Message.Request,
                          content=request.SerializeToString())

        self.send_message(message)

        return request.id

    def publish(self, event, data=None):
        """Send a ``publish`` message.

        :param event str: The event name
        :param data bytes: Optional data sent with the event"""

        logger.info("[Publish] %s(%s)", event, data)

        publish = Publish(event=event)
        if data:
            publish.data = data

        message = Message(type=Message.Publish,
                          content=publish.SerializeToString())

        self.send_message(message)

    def subscribe(self, event):
        """Send a ``subscribe`` message."""

        logger.info("[Subscribe] %s", event)

        subscribe = Subscribe(event=event)

        message = Message(type=Message.Subscribe,
                          content=subscribe.SerializeToString())

        self.send_message(message)


class SynClient(AbstractClient):
    """
    Synchronous (aka. blocking) cellaserv client.

    Wait for ``reply`` after every ``request`` message.
    """

    def __init__(self, sock):
        super().__init__()

        self._socket = sock

    def _send_message(self, msg):
        self._socket.send(struct.pack("!I", len(msg)) + msg)

    ### Actions

    def request(self, method, service, identification=None, data=None):
        """
        Blocking ``request``.

        Send the ``request`` message, then wait for the reply.
        """
        # Send the request
        req_id = super().request(method=method, service=service,
                                 identification=identification, data=data)

        # Wait for response
        while True:
            # Receive message header
            hdr = self._socket.recv(4)
            # Header is the size of the message as a uint32 in network byte order
            msg_len = struct.unpack("!I", hdr)[0]

            # Receive message, which may be in multiple packets so use a loop
            msg = b""
            while msg_len != 0:
                buf = self._socket.recv(msg_len)
                msg_len -= len(buf)
                msg += buf

            # Parse message
            message = Message()
            message.ParseFromString(msg)

            if message.type != Message.Reply:
                # Currentyle Dropping non-reply is not an issue as the
                # SynClient is only used to send queries
                logger.warning("[Request] Dropping non Reply: "
                               + MessageToString(message).decode())
                continue

            # Parse reply
            reply = Reply()
            reply.ParseFromString(message.content)

            if reply.id != req_id:
                logger.warning("[Request] Dropping Reply for the wrong "
                               "request: " + MessageToString(reply).decode())
                continue

            # Check if reply is an error
            if reply.HasField('error'):
                logger.error("[Reply] Received error")
                if reply.error.type == Reply.Error.Timeout:
                    raise RequestTimeout(reply)
                elif reply.error.type == Reply.Error.NoSuchService:
                    raise NoSuchService(service)
                elif reply.error.type == Reply.Error.NoSuchMethod:
                    raise NoSuchMethod(service, method)
                elif reply.error.type == Reply.Error.BadArguments:
                    raise BadArguments(reply)
                else:
                    raise ReplyError(reply)

            logger.debug("Received:\n%s", MessageToString(reply).decode())

            return reply.data if reply.HasField('data') else None


class AsynClient(asynchat.async_chat, AbstractClient):
    """Asynchronous cellaserv client."""

    def __init__(self, sock):
        # Init base classes
        asynchat.async_chat.__init__(self, sock=sock)
        AbstractClient.__init__(self)

        # setup asynchat
        self.set_terminator(4) # first, we are looking for a message header
        # hold incoming data
        self._ibuffer = bytearray()
        self._read_header = True

        # map events to a list of callbacks
        self._events_cb = defaultdict(list)
        self._events_pattern_cb = defaultdict(list)

    def _send_message(self, msg):
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

            msg_len = struct.unpack("!I", self._ibuffer)[0]
            self.set_terminator(msg_len)

            self._ibuffer = bytearray()
        else:
            self._read_header = True
            self.set_terminator(4)

            msg = Message()
            msg.ParseFromString(bytes(self._ibuffer))

            self._ibuffer = bytearray()

            self.on_message_recieved(msg)

    # Methods called by subclasses

    def add_subscribe_cb(self, event, event_cb):
        """On event ``event`` recieved, call ``event_cb``"""
        self._events_cb[event].append(event_cb)
        self.subscribe(event)

    def add_subscribe_pattern_cb(self, pattern, event_cb):
        """On event ``event`` recieved, call ``event_cb``"""
        self._events_pattern_cb[pattern].append(event_cb)
        self.subscribe(pattern)

    # Callbacks

    def on_message_recieved(self, msg):
        """Called on incoming message from cellaserv."""
        if msg.type == Message.Request:
            req = Request()
            req.ParseFromString(msg.content)
            self.on_request(req)
        elif msg.type == Message.Reply:
            rep = Reply()
            rep.ParseFromString(msg.content)
            self.on_reply(rep)
        elif msg.type == Message.Publish:
            pub = Publish()
            pub.ParseFromString(msg.content)

            # Basic subscriptions
            for cb in self._events_cb[pub.event]:
                if pub.HasField('data'):
                    cb(pub.data)
                else:
                    cb()

            # Pattern subscriptions
            for pattern, cb_list in self._events_pattern_cb.items():
                if fnmatch.fnmatch(pub.event, pattern):
                    for cb in cb_list:
                        if pub.HasField('data'):
                            cb(pub.data, event=pub.event)
                        else:
                            cb(event=pub.event)

        else:
            logger.warning("Invalid message:\n%s",
                           MessageToString(msg).decode())

    def on_request(self, req):
        pass

    def on_reply(self, rep):
        pass
