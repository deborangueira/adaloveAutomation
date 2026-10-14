from unittest.mock import MagicMock, patch

import pytest
from adalove.models.section_info import SectionInfo
from cli.main import _extract_section_uuid, _sort_sections, escolher_turma


def test_extract_section_uuid():
    url = "https://apiv2.inteli.edu.br/sections/0aaf5f08fd1de128220ef7673e1ceb2d/userdata"
    assert _extract_section_uuid(url) == "0aaf5f08fd1de128220ef7673e1ceb2d"
    assert _extract_section_uuid("https://example.com/other") is None


def test_sort_sections_orders_open_first_then_newest_date():
    secs = [
        {"uuid": "1", "status": "closed", "date": "2026-08-01"},
        {"uuid": "2", "status": "open", "date": "2025-05-14"},
        {"uuid": "3", "status": "open", "date": "2026-10-14"},
        {"uuid": "4", "status": "closed", "date": "2026-09-01"},
    ]
    sorted_secs = _sort_sections(secs)
    assert [s["uuid"] for s in sorted_secs] == ["3", "2", "4", "1"]


def test_escolher_turma_updates_config(tmp_path, monkeypatch):
    from adalove.config.settings import load_config, save_config

    fake_config = tmp_path / "config.json"
    monkeypatch.setattr("adalove.config.settings.CONFIG_PATH", fake_config)

    save_config({
        "api_url": "https://apiv2.inteli.edu.br/sections/old_uuid/userdata",
        "token": "Bearer test_token",
        "teacher_subjects": {},
    })

    fake_sections = [
        {"uuid": "sec_new", "caption": "2026-2B-T17", "status": "open", "projectCaption": "Módulo 8", "date": "2026-10-14"},
        {"uuid": "old_uuid", "caption": "2026-2A-T17", "status": "closed", "projectCaption": "Módulo 7", "date": "2026-08-01"},
    ]

    mock_client = MagicMock()
    mock_client.fetch_sections.return_value = fake_sections
    mock_client.fetch_section_overview.return_value = (
        SectionInfo("2026-2B-T17", "Módulo 8", "", "Prof", "G1", "2026-10-14"),
        [],
    )

    monkeypatch.setattr("cli.main.AdaloveClient", lambda *args, **kwargs: mock_client)
    monkeypatch.setattr("cli.main._ensure_fresh_token", lambda cfg: cfg)

    # Mock user selection of the new turma
    mock_select = MagicMock()
    mock_select.ask.return_value = fake_sections[0]
    monkeypatch.setattr("cli.main.questionary.select", lambda *args, **kwargs: mock_select)

    escolher_turma()

    saved = load_config()
    assert "sec_new" in saved["api_url"]
    assert saved["section_caption"] == "2026-2B-T17"
