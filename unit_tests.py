#!/usr/bin/env python3
import asyncore
import json
import multiprocessing
import socket
import time
import unittest

import cellaserv_client
import local_settings
import example.date_service as date_service

HOST, PORT = local_settings.HOST, local_settings.PORT

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
        self.assertIn("ack", resp_dict)
        self.assertEqual(resp_dict["ack"], command)

        return resp_dict

class BasicTests(TestCellaserv):
    # Todo:
    # test ill formed query (ints, lists, & other things)

    def test_complete_gibberish(self):
        self.socket.send(b'\n\n{"foo"} 314231234\n{""}\n{"aaa": "foo"}\n')
        resp = self.readline()
        self.assertEqual(json.loads(resp), {"error":
            "message does not contain 'command' component"})

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
        self.assertIn("service_count", resp)

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
                "message does not contain 'command' component"})

    def test_command_register_service(self):
        command = {"command": "register",
                   "service": "test"}
        self.check_ack(command)

    def test_command_register_service_fuzz(self):
        command = {"command": "register",
                   "service": "A"*2**16}
        self.check_ack(command)

    def test_command_register_service_with_ident(self):
        command = {"command": "register",
                   "service": "test",
                   "identification": "foobarlol"}
        self.check_ack(command)

    def test_register_many_services(self):
        command = {"command": "register",
                "service": "test"}

        for i in range(1000):
            command["identification"] = str(i)

            sock = self.new_socket()
            sock.send(json.dumps(command).encode("ascii") + b'\n')

        import time
        time.sleep(0.06) # time to process connections (qt is async)

        command = {}
        command["command"] = "status"

        self.send_command(command)
        resp = self.readline()
        self.assertEqual(json.loads(resp)["service_count"], 1000)

def start_date_service(ident="test"):
    with socket.create_connection((HOST, PORT)) as sock:
        service = date_service.DateService(sock)
        service.connect()

        asyncore.loop()

class TestClientService(TestCellaserv):

    def test_query(self):
        date_serv = multiprocessing.Process(target=start_date_service)
        date_serv.start()

        import time
        time.sleep(0.3) # time for child process to start

        command = {"command": "query",
                   "service": "date",
                   "action": "epoch"}
        self.send_command(command)
        resp = self.check_ack(command)

        self.assertIn("ack-data", resp)

        date_serv.terminate()

    def test_many_query(self):
        date_serv = multiprocessing.Process(target=start_date_service)
        date_serv.start()

        import time
        time.sleep(0.5) # time for child process to start

        command = {"command": "query",
                   "service": "date",
                   "action": "epoch"}

        for i in range(100):
            self.send_command(command)

        for i in range(100):
            resp = self.check_ack(command)
            self.assertIn("ack-data", resp)

        date_serv.terminate()

if __name__ == "__main__":
    unittest.main()
