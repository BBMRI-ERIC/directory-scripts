from argparse import Namespace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pandas as pd

from fix_proposals import compute_checksum

MODULE_PATH = Path(__file__).resolve().parents[1] / "collection-qcheck-updater.py"


def load_module():
    spec = spec_from_file_location("collection_qcheck_updater", MODULE_PATH)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def build_plan(tmp_path: Path) -> Path:
    update = {
        "update_id": "access.duo.collaboration_required",
        "module": "access",
        "entity_type": "COLLECTION",
        "entity_id": "bbmri-eric:ID:CZ_demo:collection:col1",
        "field": "data_use",
        "mode": "append",
        "confidence": "certain",
        "current_value_at_export": [],
        "expected_current_value": [],
        "proposed_value": ["DUO:0000020"],
        "human_explanation": "Add DUO collaboration-required term.",
        "rationale": "Joint-project policy already exists.",
        "term_explanations": [
            {
                "term_id": "DUO:0000020",
                "label": "collaboration required",
                "definition": "The requestor must agree to collaboration with the primary study investigator or investigators.",
                "source_name": "DUO",
                "source_url": "https://example.org/duo.owl",
                "source_checked_at": "2026-03-04",
            }
        ],
        "source_check_ids": ["AP:JointDuo"],
        "source_warning_messages": ["Joint project implies DUO term."],
        "source_warning_actions": ["Review data_use."],
        "replace_required": False,
        "blocking_reason": "",
        "exclusive_group": "",
        "staging_area": "CZ",
    }
    update["update_checksum"] = compute_checksum(update)
    payload = {
        "format_version": 1,
        "generated_at": "2026-03-04T00:00:00+00:00",
        "generated_by": {"tool": "data-check.py", "schema": "ERIC", "withdrawn_scope": "active-only"},
        "updates": [update],
    }
    payload["file_checksum"] = compute_checksum(payload)
    path = tmp_path / "updates.json"
    import json
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_collection_qcheck_updater_list_mode_outputs_human_readable_plan(tmp_path, capsys):
    module = load_module()
    path = build_plan(tmp_path)
    args = Namespace(
        input=str(path),
        schema="BBMRI-CZ",
        entity_id=None,
        root_id=None,
        staging_area=None,
        check_id=[],
        update_id=[],
        module=[],
        confidence=None,
        list=True,
        dry_run=False,
        force=False,
        replace_existing=False,
        verbose=False,
        debug=False,
        quiet=False,
        directory_target="https://directory.example.org",
        directory_username="user",
        directory_password="secret",
    )

    result = module.run_updater(args)
    captured = capsys.readouterr()

    assert result == module.EXIT_OK
    assert "bbmri-eric:ID:CZ_demo:collection:col1" in captured.out
    assert "DUO:0000020 = collaboration required" in captured.out


def test_collection_qcheck_updater_dry_run_checks_live_mismatch_and_does_not_save(tmp_path, monkeypatch):
    module = load_module()
    path = build_plan(tmp_path)
    saved = []

    class SessionStub:
        def __init__(self, url):
            self.url = url

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def signin(self, username, password):
            assert username == "user"
            assert password == "secret"

        def get(self, *, table, schema, as_df):
            assert table == "Collections"
            assert schema == "BBMRI-CZ"
            assert as_df is True
            return pd.DataFrame([
                {
                    "id": "bbmri-eric:ID:CZ_demo:collection:col1",
                    "data_use": "DUO:0000042",
                }
            ])

        def save_table(self, **kwargs):
            saved.append(kwargs)

    monkeypatch.setattr(module, "DirectorySession", SessionStub)
    monkeypatch.setattr(module, "confirm_action", lambda *args, **kwargs: None)

    args = Namespace(
        input=str(path),
        schema="BBMRI-CZ",
        entity_id=None,
        root_id=None,
        staging_area=None,
        check_id=[],
        update_id=[],
        module=[],
        confidence=None,
        list=False,
        dry_run=True,
        force=False,
        replace_existing=False,
        verbose=False,
        debug=False,
        quiet=False,
        directory_target="https://directory.example.org",
        directory_username="user",
        directory_password="secret",
    )

    result = module.run_updater(args)

    assert result == module.EXIT_OK
    assert saved == []
