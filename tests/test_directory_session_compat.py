from molgenis_emx2_pyclient import Client

from directory_session_compat import DirectorySession


def test_directory_session_compat_uses_client_context_manager_flag(monkeypatch):
    monkeypatch.setattr(Client, "_validate_url", lambda self: None)
    monkeypatch.setattr(Client, "get_schemas", lambda self: [{"name": "ERIC"}])
    monkeypatch.setattr(Client, "set_schema", lambda self, name: name)
    session = DirectorySession("https://example.invalid", schema="ERIC")
    assert session._as_context_manager is False
    with session as active_session:
        assert active_session is session
        assert session._as_context_manager is True
