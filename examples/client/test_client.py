from multiprocessing import Process
from pytest import raises
import time

from cellaserv.settings import get_socket
from cellaserv.client import SynClient
from evolutek.services.cs_date import Date


class TestSynClient:

    def setup_method(self, method):
        self.client = SynClient(get_socket())

    def test_register(self):
        self.client.register('test_service')

    def test_register_bad_bytes(self):
        raises(AttributeError, self.client.register, b'test_service')

    def test_register_ident(self):
        self.client.register('test_service', 'ident')

    def test_register_ident_bad_int(self):
        raises(TypeError, self.client.register, 'test_service', 42)

    def test_register_ident_bad_bytes(self):
        raises(AttributeError, self.client.register, 'test_service', b'ident')

    def test_register(self):
        self.client.register('test_service')

    def test_register_bad_bytes(self):
        raises(AttributeError, self.client.register, b'test_service')

    def test_register_ident(self):
        self.client.register('test_service', 'ident')

    def test_register_ident_bad_int(self):
        raises(TypeError, self.client.register, 'test_service', 42)

    def test_register_ident_bad_bytes(self):
        raises(AttributeError, self.client.register, 'test_service', b'ident')

class TestSynClientWithDate:

    def setup_method(self, method):
        self.slave_service = Date()
        self.slave_process = Process(target=self.slave_service.run)
        self.slave_process.start()
        time.sleep(.2)

    def teardown_method(self, method):
        if self.slave_process.is_alive():
            self.slave_process.terminate()

