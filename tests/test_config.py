import importlib


def test_credentials_are_loaded_from_environment(monkeypatch):
    monkeypatch.setenv("USERNAME", "student-id-from-env")
    monkeypatch.setenv("PASSWORD", "password-from-env")

    import config

    config = importlib.reload(config)

    assert config.USERNAME == "student-id-from-env"
    assert config.PASSWORD == "password-from-env"
