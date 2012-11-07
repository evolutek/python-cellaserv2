#!/usr/bin/env python3
"""Unit tests for cellaserv using the cellaserv_client library
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
from tests import local_settings
import example.date_service as date_service

HOST, PORT = local_settings.HOST, local_settings.PORT

ERRORS = {
        "missing_command": "Message missing 'command' component",
}

class TestCellaserv(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._sockets = []

    def setUp(self):
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

class VersionTest(TestCellaserv):

    def test_version(self):
        client = cellaserv.client.SynClient(self.new_socket())
        resp = client.server_status()
        self.assertEqual(resp['data']['protocol-version'],
                cellaserv.client.__protocol_version__)

class BasicTests(TestCellaserv):

    def test_complete_gibberish(self):
        self.socket.send(b'\n\n{"foo"} 314231234\n{""}\n{"aaa": "foo"}\n')
        resp = self.readline()
        self.assertEqual(json.loads(resp), {"error":
            ERRORS['missing_command']})

    def test_qjson_bug(self):
        self.socket.send(b'{""}\n{"command":"unknown"}\n')
        resp = self.readline()
        self.assertEqual(json.loads(resp), {'error':
            "unknown command: 'unknown'"})

    def test_partial_packet(self):
        self.socket.send(b'{"command"')
        time.sleep(0)
        self.socket.send(b': "status"}')
        time.sleep(0)
        self.socket.send(b'\n')

        resp = self.readline()
        self.assertIn("service-count", resp)

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
            self.assertEqual(json.loads(resp), {"error":
                ERRORS['missing_command']})

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

        for i in range(100):
            command["identification"] = str(i)
            command['id'] = str(uuid.uuid4())

            sock = self.new_socket()
            sock.send(json.dumps(command).encode("ascii") + b'\n')

        time.sleep(0.1) # time to process connections (qt is async)

        command = {}
        command["command"] = "status"

        self.send_command(command)
        resp = self.readline()
        self.assertEqual(json.loads(resp)['data']["service-count"], 100)

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

        resp = client.query("epoch", "date")

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

        client0 = cellaserv.client.SynClient(self.socket)
        client0.register_service("notify-test")
        client0.notify('foobar', 'test')

        notify = client1.read_message()

        self.assertEqual({ "command" : "notify", "event" : "foobar",
            "data" : "test" }, notify)

    def test_notify_no_emitter(self):
        client = cellaserv.client.SynClient(self.socket)
        client.notify("test")
        client.notify("test", [1, 2, "a"])

if __name__ == "__main__":
    unittest.main()

try:
    sock = socket.create_connection((HOST, PORT))
except socket.error:
    print("Cound not connect to cellaserv", file=sys.stderr)
    sys.exit(1)
