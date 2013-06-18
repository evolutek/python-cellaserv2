#!/usr/bin/env python3
"""Unit tests for cellaserv using the cellaserv_client library.
"""

import asyncore
import json
import multiprocessing
import socket
import sys
import time
import unittest
import uuid

import cellaserv.client
from cellaserv.proxy import CellaservProxy
from tests import local_settings

from example import date_service
from example import date_service_notify

HOST, PORT = local_settings.HOST, local_settings.PORT

class TestCellaserv(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._sockets = []

    def new_socket(self):
        sock = socket.create_connection((HOST, PORT))
        self._sockets.append(sock)

        return sock

    def tearDown(self):
        for sock in self._sockets:
            sock.close()

        self._sockets[:] = []

class BasicTests(TestCellaserv):

    def setUp(self):
        super().setUp()

        self.socket = self.new_socket()
        self.buffer = self.socket.makefile()

    def new_socket(self):
        sock = socket.create_connection((HOST, PORT))
        self._sockets.append(sock)

        return sock

    def tearDown(self):
        self.buffer.close()

        for sock in self._sockets:
            sock.close()

        self._sockets = []

    def readline(self):
        resp = ""
        while not resp:
            resp = self.buffer.readline()

        return resp

    def send_command(self, command):
        self.socket.send(json.dumps(command).encode("ascii") + b'\n')

    def check_ack(self, command):
        self.send_command(command)
        resp = self.readline()
        resp_dict = json.loads(resp)

        self.assertIn("command", resp_dict)
        self.assertEqual(resp_dict["command"], "ack")
        self.assertIn("id", resp_dict)
        self.assertEqual(resp_dict["id"], command["id"])

        return resp_dict

    def test_complete_gibberish(self):
        self.socket.send(b'\n')
        resp = self.readline()
        self.assertEqual(json.loads(resp),
                {'command': 'error', 'error': 'command', 'error-id': 'missing-field'})

        self.socket.send(b'\n\n')
        for i in range(2):
            resp = self.readline()
            self.assertEqual(json.loads(resp),
                {'command': 'error', 'error': 'command', 'error-id': 'missing-field'})

        self.socket.send(b'\n\n{"foo"} 314231234\n')
        for i in range(2): # last message does not parse, no error triggered
            resp = self.readline()
            self.assertEqual(json.loads(resp),
                {'command': 'error', 'error': 'command', 'error-id': 'missing-field'})

        resp = self.readline()
        self.assertEqual(json.loads(resp),
            {'command': 'error', 'error': '', 'error-id': 'bad-json'})

        self.socket.send(b'\n\n{"foo"} 314231234\n{""}\n{"aaa": "foo"}\n')

        for i in range(2):
            resp = self.readline()
            self.assertEqual(json.loads(resp),
                {'command': 'error', 'error': 'command', 'error-id': 'missing-field'})

        for i in range(2):
            resp = self.readline()
            self.assertEqual(json.loads(resp),
                {'command': 'error', 'error': '', 'error-id': 'bad-json'})

        resp = self.readline()
        self.assertEqual(json.loads(resp),
            {'command': 'error', 'error': 'command', 'error-id': 'missing-field'})

    def test_qjson_bug(self):
        self.socket.send(b'{""}\n{"command":"unknown"}\n')

        resp = self.readline()
        self.assertEqual(json.loads(resp),
            {'command': 'error', 'error': '', 'error-id': 'bad-json'})

        resp = self.readline()
        self.assertEqual(json.loads(resp),
                {'command': 'error', 'error': 'unknown', 'error-id': 'no-such-command'})

    def test_partial_packet(self):
        self.socket.send(b'{"command"')
        time.sleep(0)
        self.socket.send(b': "server", "action": "list-services", "id": "42"}')
        time.sleep(0)
        self.socket.send(b'\n')

        resp = self.readline()
        self.assertIn("services", resp)

    def test_big_packet(self):
        self.socket.send(b'{"command": "server", "action": "' + b'A'*123456 +
                b'"}\n')
        resp = self.readline()

        self.assertEqual(json.loads(resp),
                {'command': 'error', 'error-id': 'no-such-action', 'error': 'A'*123456})

    def test_command_register_service(self):
        command = {"command": "register",
                   "service": "test",
                   "id": str(uuid.uuid4())}
        self.check_ack(command)

    def test_command_register_service_fuzz(self):
        command = {"command": "register",
                   "service": "A"*2**16,
                   "id": str(uuid.uuid4())}
        self.check_ack(command)

    def test_command_register_service_with_ident(self):
        command = {"command": "register",
                   "service": "test",
                   "identification": "foobarlol",
                   "id": str(uuid.uuid4())}
        self.check_ack(command)

    def test_register_many_services(self):
        command = {"command": "register",
                "service": "test"}

        client = cellaserv.client.SynClient(self.new_socket())
        status = client.server('list-services')
        before = len(status['data']['services'])

        for i in range(100):
            command["identification"] = str(i)
            command['id'] = str(uuid.uuid4())

            sock = self.new_socket()
            sock.send(json.dumps(command).encode("ascii") + b'\n')

        time.sleep(0.1) # time to process connections (qt is async)

        status = client.server('list-services')
        self.assertEqual(len(status['data']['services']), before+100)

    # Basic errors

    def test_command_unknwon(self):
        commands = [
                {},
                {"lol": 1},
                {"foo": "bar"},
                {"foo": {"hello": "bite"}},
                ["hello", "test"],
        ]

        for command in commands:
            self.send_command(command)
            resp = self.readline()
            self.assertEqual(json.loads(resp),
                    {'command': 'error', 'error': 'command', 'error-id': 'missing-field'})

    def test_command_register(self):
        self.send_command({'command': 'register'})
        self.assertEqual(json.loads(self.readline()),
                {'command': 'error', 'error': 'id', 'error-id': 'missing-field'})

        self.send_command({'command': 'register', 'id': '42'})
        self.assertEqual(json.loads(self.readline()),
                {'command': 'error', 'error': 'service', 'error-id': 'missing-field'})

        self.send_command(
                {'command': 'register', 'id': '42', 'service': [1, 2, 3]})
        self.assertEqual(json.loads(self.readline()),
                {'command': 'error', 'error': 'service', 'error-id': 'invalid-field'})

        # XXX: Should fail
        #self.send_command(
        #        {'command': 'register', 'id': '42', 'service': 42})
        #self.assertEqual(json.loads(self.readline()),
        #        {'command': 'error', 'error': 'service', 'error-id': 'invalid-field'})

        #self.send_command(
        #        {'command': 'register', 'id': '42', 'service': False})
        #self.assertEqual(json.loads(self.readline()),
        #        {'command': 'error', 'error': 'service', 'error-id': 'invalid-field'})

        self.send_command(
                {'command': 'register', 'id': '42', 'service':
                    {'hello': 'world'}})
        self.assertEqual(json.loads(self.readline()),
                {'command': 'error', 'error': 'service', 'error-id': 'invalid-field'})

    def test_command_action(self):
        self.send_command({'command': 'query'})
        self.assertEqual(json.loads(self.readline()),
                {'command': 'error', 'error': 'id', 'error-id': 'missing-field'})

        self.send_command({'command': 'query', 'id': '42'})
        self.assertEqual(json.loads(self.readline()),
                {'command': 'error', 'error': 'service', 'error-id': 'missing-field'})

        self.send_command(
                {'command': 'query', 'id': '42', 'service': [1, 2, 3]})
        self.assertEqual(json.loads(self.readline()),
                {'command': 'error', 'error': 'action', 'error-id': 'missing-field'})

        self.send_command(
                {'command': 'query', 'id': '42', 'action': 'foo', 'service': [1, 2, 3]})
        self.assertEqual(json.loads(self.readline()),
                {'command': 'error', 'error': 'service', 'error-id': 'invalid-field'})

        self.send_command(
                {'command': 'query', 'id': '42', 'action': [1, 2, 3], 'service': [1, 2, 3]})
        self.assertEqual(json.loads(self.readline()),
                {'command': 'error', 'error': 'service', 'error-id': 'invalid-field'})

        self.send_command(
                {'command': 'query', 'id': '42', 'action': {'h': 'w'}, 'service': [1, 2, 3]})
        self.assertEqual(json.loads(self.readline()),
                {'command': 'error', 'error': 'service', 'error-id': 'invalid-field'})

        self.send_command(
                {'command': 'query', 'id': '42', 'service': {'hello':
                    'world'}, 'action': {'h': 'w'}})
        self.assertEqual(json.loads(self.readline()),
                {'command': 'error', 'error': 'service', 'error-id': 'invalid-field'})

    def test_command_subscribe(self):
        self.send_command({'command': 'subscribe'})
        self.assertEqual(json.loads(self.readline()),
                {'command': 'error', 'error': 'event', 'error-id': 'missing-field'})

        self.send_command({'command': 'subscribe', 'id': '42'})
        self.assertEqual(json.loads(self.readline()),
                {'command': 'error', 'error': 'event', 'error-id': 'missing-field'})

        self.send_command(
                {'command': 'subscribe', 'id': '42', 'event': [1, 2, 3]})
        self.assertEqual(json.loads(self.readline()),
                {'command': 'error', 'error': 'event', 'error-id': 'invalid-field'})

    def test_command_notify(self):
        self.send_command({'command': 'notify'})
        self.assertEqual(json.loads(self.readline()),
                {'command': 'error', 'error': 'event', 'error-id': 'missing-field'})

        self.send_command({'command': 'notify', 'event': [1, 2, 3]})
        self.assertEqual(json.loads(self.readline()),
                {'command': 'error', 'error': 'event', 'error-id': 'invalid-field'})

    def test_command_ack(self):
        self.send_command({'command': 'ack'})
        self.assertEqual(json.loads(self.readline()),
                {'command': 'error', 'error': 'id', 'error-id': 'missing-field'})

    def test_command_server(self):
        self.send_command({'command': 'server'})
        self.assertEqual(json.loads(self.readline()),
                {'command': 'error', 'error': 'action', 'error-id': 'missing-field'})

        self.send_command({'command': 'server', 'action': [1, 2, 3]})
        self.assertEqual(json.loads(self.readline()),
                {'command': 'error', 'error': 'action', 'error-id': 'invalid-field'})

        self.send_command({'command': 'server', 'action': 'foobarlol'})
        self.assertEqual(json.loads(self.readline()),
                {'command': 'error', 'error': 'foobarlol', 'error-id': 'no-such-action'})

class TestTimeout(TestCellaserv):

    def test_query_timeout(self):
        slow_client = cellaserv.client.SynClient(self.new_socket())
        slow_client.register_service("slow")

        client = cellaserv.client.SynClient(self.new_socket())
        with self.assertRaises(cellaserv.client.MessageTimeout):
            client.query("nothing", "slow")

def start_date_service(ident="test"):
    with socket.create_connection((HOST, PORT)) as sock:
        service = date_service.DateService(sock)
        service.connect()

        asyncore.loop()

class TestSynClientService(TestCellaserv):

    def test_query(self):
        date_serv = multiprocessing.Process(target=start_date_service)
        date_serv.start()
        time.sleep(0.5) # time for child process to start

        client = cellaserv.client.SynClient(self.new_socket())

        resp = client.query("time", "date")

        self.assertEqual(resp["command"], "ack")
        self.assertIn("id", resp)
        self.assertIn("data", resp)
        self.assertIn("epoch", resp["data"])

        date_serv.terminate()

    def test_query_unknown_action(self):
        date_serv = multiprocessing.Process(target=start_date_service)
        date_serv.start()
        time.sleep(0.5) # time for child process to start

        client = cellaserv.client.SynClient(self.new_socket())

        resp = client.query("foobarlol", "date")

        self.assertEqual(resp["command"], "ack")
        self.assertIn("id", resp)
        self.assertIn("data", resp)
        self.assertEqual(resp["data"],
            {'error': "unknown action: 'foobarlol'"})

        date_serv.terminate()

    def test_many_query(self):
        date_serv = multiprocessing.Process(target=start_date_service)
        date_serv.start()
        time.sleep(0.5) # time for child process to start

        client = cellaserv.client.SynClient(self.new_socket())

        for i in range(100):
            client.query("epoch", "date")

        date_serv.terminate()

class TestNotify(TestCellaserv):

    def test_notify(self):
        client1 = cellaserv.client.SynClient(self.new_socket())
        client1.subscribe_event('foobar')

        time.sleep(0)

        client0 = cellaserv.client.SynClient(self.new_socket())
        client0.register_service("notify-test")
        client0.notify('foobar', 'test')

        notify = client1.read_message()

        self.assertEqual(notify['data'], 'test')

        ack = {}
        ack['command'] = 'ack'
        ack['id'] = notify['id']
        client1.send_message(ack)

    def test_notify_no_emitter(self):
        client = cellaserv.client.SynClient(self.new_socket())
        client.notify("test")
        client.notify("test", [1, 2, "a"])

    def test_notify_many(self):
        client = cellaserv.client.SynClient(self.new_socket())
        client.subscribe_event("test")

        test = cellaserv.client.SynClient(self.new_socket())
        for i in range(1000):
            test.notify("test")

        for i in range(1000):
            client.read_message()

    def test_subscribe_twice(self):
        client = cellaserv.client.SynClient(self.new_socket())
        client.subscribe_event("test")
        client.subscribe_event("test")

        test = cellaserv.client.SynClient(self.new_socket())
        test.notify("test")

        # Only one message is sent.
        client.read_message()

def start_date_notifier():
    with socket.create_connection((HOST, PORT)) as sock:
        service = date_service_notify.DateNotifier(sock)
        service.run()

class TestClientNotify(TestCellaserv):

    def test_notify(self):
        date_serv = multiprocessing.Process(target=start_date_notifier)
        date_serv.start()

        client = cellaserv.client.SynClient(self.new_socket())
        client.subscribe_event('epoch')

        notify = client.read_message()

        self.assertEqual(notify['command'], 'notify')
        ack = {}
        ack['command'] = 'ack'
        ack['id'] = notify['id']
        client.send_message(ack)

        date_serv.terminate()

class TestServer(TestCellaserv):

    def test_list_services(self):
        client = cellaserv.client.SynClient(self.new_socket())
        resp = client.server('list-services')

        self.assertEqual(type(resp['data']['services']), type([]))

        client.register_service("foobar")

        resp2 = client.server('list-services')

        self.assertEqual(len(resp['data']['services']) + 1,
                len(resp2['data']['services']))

    def test_connections_open(self):
        client = cellaserv.client.SynClient(self.new_socket())
        resp = client.server('connections-open')

        self.assertEqual(type(resp['data']['connections-open']), int)

        client2 = cellaserv.client.SynClient(self.new_socket())
        resp2 = client.server('connections-open')

        self.assertEqual(resp['data']['connections-open'] + 1,
                resp2['data']['connections-open'])

    def test_cellaserv_version(self):
        client = cellaserv.client.SynClient(self.new_socket())
        resp = client.server('cellaserv-version')

        self.assertEqual(type(resp['data']['cellaserv-version']), str)

    def test_version(self):
        client = cellaserv.client.SynClient(self.new_socket())
        resp = client.server('protocol-version')
        self.assertEqual(resp['data']['protocol-version'],
                cellaserv.client.__protocol_version__)

class TestProxy(TestCellaserv):

    def test_notify(self):
        cs = CellaservProxy()
        client = cellaserv.client.SynClient(self.new_socket())
        client.subscribe_event("test")
        cs("test")
        msg = client.read_message()
        self.assertEqual('test', msg['event'])

if __name__ == "__main__":
    unittest.main()

try:
    sock = socket.create_connection((HOST, PORT))
except socket.error:
    print("Cound not connect to cellaserv", file=sys.stderr)
    sys.exit(1)
