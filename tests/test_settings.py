import json
from pathlib import Path

import pytest
from adalove.config.settings import load_config, save_config, CONFIG_PATH


@pytest.fixture(autouse=True)
def clean_config(tmp_path, monkeypatch):
    fake_path = tmp_path / "config.json"
    monkeypatch.setattr("adalove.config.settings.CONFIG_PATH", fake_path)
    yield fake_path


def test_load_config_raises_when_missing(clean_config):
    with pytest.raises(FileNotFoundError, match="adalove setup"):
        load_config()


def test_load_config_raises_on_malformed_json(clean_config):
    clean_config.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="malformed"):
        load_config()


def test_save_and_load_roundtrip(clean_config):
    data = {"api_url": "https://example.com", "token": "Bearer abc", "teacher_subjects": {}}
    save_config(data)
    loaded = load_config()
    assert loaded == data


def test_save_config_preserves_unicode(clean_config):
    data = {"subject": "Não presente no módulo"}
    save_config(data)
    raw = clean_config.read_text(encoding="utf-8")
    assert "Não presente no módulo" in raw
