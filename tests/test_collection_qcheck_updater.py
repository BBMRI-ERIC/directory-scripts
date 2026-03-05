from argparse import Namespace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import logging
import warnings

import pandas as pd

from fix_proposals import compute_checksum

MODULE_PATH = Path(__file__).resolve().parents[1] / "qcheck-updater.py"


def load_module():
    spec = spec_from_file_location("collection_qcheck_updater", MODULE_PATH)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def build_plan(tmp_path: Path) -> Path:
    update = {
        "update_id": "access.duo.collaboration_required",
        "module": "AP",
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
    assert "add: DUO:0000020" in captured.out


def test_collection_qcheck_updater_dry_run_checks_live_mismatch_and_does_not_save(tmp_path, monkeypatch):
    module = load_module()
    path = build_plan(tmp_path)
    saved = []
    review_prompts = []
    confirm_prompts = []

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
    monkeypatch.setattr(module, "confirm_action", lambda prompt, **kwargs: confirm_prompts.append(prompt))
    monkeypatch.setattr(module, "prompt_yes_no", lambda prompt, **kwargs: review_prompts.append(prompt) or True)

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
    assert review_prompts
    assert any("simulated apply" in prompt for prompt in confirm_prompts)


def test_collection_qcheck_updater_module_filter_accepts_check_prefix(tmp_path):
    module = load_module()
    path = build_plan(tmp_path)
    payload = module.load_fix_plan(path).payload

    updates = module._filter_updates(
        Namespace(
            entity_id=None,
            root_id=None,
            staging_area=None,
            check_id=[],
            update_id=[],
            module=["AP"],
            confidence=None,
            list=True,
        ),
        payload,
        directory=None,
    )

    assert len(updates) == 1


def test_collection_qcheck_updater_ignores_multi_value_order_only_mismatches(tmp_path, monkeypatch, caplog):
    module = load_module()
    path = build_plan(tmp_path)
    saved = []

    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["updates"][0]["field"] = "sex"
    payload["updates"][0]["current_value_at_export"] = ["MALE", "FEMALE"]
    payload["updates"][0]["expected_current_value"] = ["MALE", "FEMALE"]
    payload["updates"][0]["proposed_value"] = ["MALE", "FEMALE"]
    payload["updates"][0]["update_checksum"] = compute_checksum(
        {key: value for key, value in payload["updates"][0].items() if key != "update_checksum"}
    )
    payload["file_checksum"] = compute_checksum({key: value for key, value in payload.items() if key != "file_checksum"})
    path.write_text(json.dumps(payload), encoding="utf-8")

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
                    "sex": "FEMALE,MALE",
                }
            ])

        def save_table(self, **kwargs):
            saved.append(kwargs)

    monkeypatch.setattr(module, "DirectorySession", SessionStub)
    monkeypatch.setattr(module, "confirm_action", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "prompt_yes_no", lambda *args, **kwargs: True)

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

    with caplog.at_level(logging.WARNING):
        result = module.run_updater(args)

    assert result == module.EXIT_OK
    assert saved == []
    assert "Live value mismatch" not in caplog.text


def test_collection_qcheck_updater_review_display_normalizes_multi_value_order(tmp_path, monkeypatch, capsys):
    module = load_module()
    path = build_plan(tmp_path)

    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["updates"][0]["field"] = "data_use"
    payload["updates"][0]["current_value_at_export"] = ["DUO_0000007", "DUO_0000029", "DUO_0000006"]
    payload["updates"][0]["expected_current_value"] = ["DUO_0000007", "DUO_0000029", "DUO_0000006"]
    payload["updates"][0]["proposed_value"] = ["DUO:0000007"]
    payload["updates"][0]["update_checksum"] = compute_checksum(
        {key: value for key, value in payload["updates"][0].items() if key != "update_checksum"}
    )
    payload["file_checksum"] = compute_checksum({key: value for key, value in payload.items() if key != "file_checksum"})
    path.write_text(json.dumps(payload), encoding="utf-8")

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
                    "data_use": "DUO_0000007,DUO_0000006,DUO_0000029",
                }
            ])

        def save_table(self, **kwargs):
            raise AssertionError("dry-run must not save")

    monkeypatch.setattr(module, "DirectorySession", SessionStub)
    monkeypatch.setattr(module, "prompt_yes_no", lambda *args, **kwargs: True)
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
    captured = capsys.readouterr()

    assert result == module.EXIT_OK
    assert "live: DUO:0000006, DUO:0000007, DUO:0000029" in captured.err
    assert "expected at export: DUO:0000006, DUO:0000007, DUO:0000029" in captured.err
    assert "target after update: DUO:0000006, DUO:0000007, DUO:0000029" in captured.err


def test_collection_qcheck_updater_does_not_append_duplicate_duo_with_different_separator(tmp_path, monkeypatch):
    module = load_module()
    path = build_plan(tmp_path)
    saved = []

    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["updates"][0]["field"] = "data_use"
    payload["updates"][0]["expected_current_value"] = ["DUO:0000020"]
    payload["updates"][0]["proposed_value"] = ["DUO:0000020"]
    payload["updates"][0]["update_checksum"] = compute_checksum(
        {key: value for key, value in payload["updates"][0].items() if key != "update_checksum"}
    )
    payload["file_checksum"] = compute_checksum({key: value for key, value in payload.items() if key != "file_checksum"})
    path.write_text(json.dumps(payload), encoding="utf-8")

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
                    "data_use": "DUO_0000020",
                }
            ])

        def save_table(self, **kwargs):
            saved.append(kwargs)

    monkeypatch.setattr(module, "DirectorySession", SessionStub)
    monkeypatch.setattr(module, "prompt_yes_no", lambda *args, **kwargs: True)
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

    assert result == module.EXIT_OK
    assert saved == []


def test_collection_qcheck_updater_saves_changed_rows_without_dtype_assignment_futurewarnings(tmp_path, monkeypatch):
    module = load_module()
    path = build_plan(tmp_path)
    saved = []

    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["updates"][0]["field"] = "data_use"
    payload["updates"][0]["expected_current_value"] = []
    payload["updates"][0]["proposed_value"] = ["DUO:0000007"]
    payload["updates"][0]["update_checksum"] = compute_checksum(
        {key: value for key, value in payload["updates"][0].items() if key != "update_checksum"}
    )
    payload["file_checksum"] = compute_checksum({key: value for key, value in payload.items() if key != "file_checksum"})
    path.write_text(json.dumps(payload), encoding="utf-8")

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
            return pd.DataFrame(
                [
                    {
                        "id": "bbmri-eric:ID:CZ_demo:collection:col1",
                        "data_use": "",
                        "some_bool": True,
                        "some_int": 7,
                    }
                ]
            )

        def save_table(self, **kwargs):
            saved.append(kwargs)

    monkeypatch.setattr(module, "DirectorySession", SessionStub)
    monkeypatch.setattr(module, "prompt_yes_no", lambda *args, **kwargs: True)
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

    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        result = module.run_updater(args)

    assert result == module.EXIT_OK
    assert len(saved) == 1
    saved_df = saved[0]["data"]
    assert list(saved_df.columns) == ["id", "data_use", "some_bool", "some_int"]
    assert saved_df.iloc[0]["some_bool"] == True
    assert saved_df.iloc[0]["some_int"] == 7


def test_collection_qcheck_updater_handles_live_mismatch_per_update_in_interactive_mode(tmp_path, monkeypatch, caplog):
    module = load_module()
    path = build_plan(tmp_path)
    saved = []
    confirm_prompts = []
    review_prompts = []

    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    first = payload["updates"][0]
    second = dict(first)
    second["entity_id"] = "bbmri-eric:ID:CZ_demo:collection:col2"
    second["update_id"] = "access.duo.data_return_required"
    second["expected_current_value"] = []
    first["expected_current_value"] = []
    for update in payload["updates"]:
        update["update_checksum"] = compute_checksum({key: value for key, value in update.items() if key != "update_checksum"})
    second["update_checksum"] = compute_checksum({key: value for key, value in second.items() if key != "update_checksum"})
    payload["updates"].append(second)
    payload["file_checksum"] = compute_checksum({key: value for key, value in payload.items() if key != "file_checksum"})
    path.write_text(json.dumps(payload), encoding="utf-8")

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
            return pd.DataFrame(
                [
                    {
                        "id": "bbmri-eric:ID:CZ_demo:collection:col1",
                        "data_use": "DUO:0000020",
                    },
                    {
                        "id": "bbmri-eric:ID:CZ_demo:collection:col2",
                        "data_use": "",
                    },
                ]
            )

        def save_table(self, **kwargs):
            saved.append(kwargs)

    prompt_answers = iter([False, True])

    monkeypatch.setattr(module, "DirectorySession", SessionStub)
    monkeypatch.setattr(module, "confirm_action", lambda prompt, **kwargs: confirm_prompts.append(prompt))
    monkeypatch.setattr(
        module,
        "prompt_yes_no",
        lambda prompt, **kwargs: review_prompts.append(prompt) or next(prompt_answers),
    )

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

    with caplog.at_level(logging.WARNING):
        result = module.run_updater(args)

    assert result == module.EXIT_OK
    assert len(saved) == 1
    saved_ids = list(saved[0]["data"]["id"])
    assert saved_ids == ["bbmri-eric:ID:CZ_demo:collection:col2"]
    assert len(review_prompts) == 2
    assert review_prompts[0] == "  Select this update despite the live mismatch?"
    assert review_prompts[1] == "  Select this update?"
    assert not any("Proceed even though" in prompt for prompt in confirm_prompts)
    assert "Live value mismatch" in caplog.text


def test_collection_qcheck_updater_applies_fact_row_delete_updates(tmp_path, monkeypatch):
    module = load_module()
    path = build_plan(tmp_path)
    deleted = []

    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    update = payload["updates"][0]
    update["update_id"] = "facts.k_anonymity.drop_rows_k5"
    update["field"] = "facts"
    update["mode"] = "delete_rows"
    update["current_value_at_export"] = ["fact1", "fact2"]
    update["expected_current_value"] = ["fact1", "fact2"]
    update["proposed_value"] = ["fact1", "fact2"]
    update["human_explanation"] = "Drop fact rows that violate k-anonymity."
    update["rationale"] = "Rows below donor threshold k=5 are unsafe to expose."
    update["source_check_ids"] = ["FT:KAnonViolation"]
    update["term_explanations"] = []
    update["update_checksum"] = compute_checksum(
        {key: value for key, value in update.items() if key != "update_checksum"}
    )
    payload["file_checksum"] = compute_checksum({key: value for key, value in payload.items() if key != "file_checksum"})
    path.write_text(json.dumps(payload), encoding="utf-8")

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
            assert schema == "BBMRI-CZ"
            assert as_df is True
            if table == "Collections":
                return pd.DataFrame(
                    [{"id": "bbmri-eric:ID:CZ_demo:collection:col1", "data_use": ""}]
                )
            if table == "CollectionFacts":
                return pd.DataFrame(
                    [
                        {"id": "fact1", "collection": "bbmri-eric:ID:CZ_demo:collection:col1"},
                        {"id": "fact2", "collection": "bbmri-eric:ID:CZ_demo:collection:col1"},
                        {"id": "fact3", "collection": "bbmri-eric:ID:CZ_demo:collection:col1"},
                    ]
                )
            raise AssertionError(f"unexpected table {table}")

        def save_table(self, **kwargs):
            raise AssertionError("Fact-row delete update should not write Collections.")

        def delete_records(self, *, table, schema, data):
            assert table == "CollectionFacts"
            assert schema == "BBMRI-CZ"
            deleted.append(data.copy())

    monkeypatch.setattr(module, "DirectorySession", SessionStub)
    monkeypatch.setattr(module, "prompt_yes_no", lambda *args, **kwargs: True)
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

    assert result == module.EXIT_OK
    assert len(deleted) == 1
    assert sorted(deleted[0]["id"].astype(str).tolist()) == ["fact1", "fact2"]
