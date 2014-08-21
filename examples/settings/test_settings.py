import importlib
import cellaserv.settings


class TestSettings:

    def fix_monkeypatch(self, monkeypatch):
        # monkeypatching only works if we reload the module
        importlib.reload(cellaserv.settings)

    def teardown_monkeypatch(self, monkeypatch):
        # we have to reload the module to really undo monkeypatching
        monkeypatch.undo()
        importlib.reload(cellaserv.settings)

    def test_env(self, monkeypatch):
        monkeypatch.setenv('CS_HOST', 'TESTHOST')
        monkeypatch.setenv('CS_PORT', '1243')
        monkeypatch.setenv('CS_DEBUG', 42)

        self.fix_monkeypatch(monkeypatch)
        assert 'TESTHOST' == cellaserv.settings.HOST
        assert 1243 == cellaserv.settings.PORT
        assert 42 == cellaserv.settings.DEBUG
        self.teardown_monkeypatch(monkeypatch)

    def test_get_socket(self):
        assert cellaserv.settings.get_socket(), "Could not connect to cellaserv"
