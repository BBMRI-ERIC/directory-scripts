"""Tests for the EUSurvey active-form manifest helper."""

from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest

import so2_eusurvey as module


def _write_archive(tmp_path: Path, members: dict[str, bytes]) -> Path:
    """Write a minimal EUS archive with the supplied serialized members.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        members: Archive members serialized into the temporary EUSurvey file.

    Returns:
        Path to the saved form.eus ZIP archive beneath tmp_path.
    """
    path = tmp_path / "form.eus"
    with zipfile.ZipFile(path, "w") as archive:
        for name, value in members.items():
            archive.writestr(name, value)
    return path


def test_load_active_form_uses_active_member_and_maps_optional_to_mandatory(tmp_path, monkeypatch):
    """The decoder reads only the active member and preserves EUS optional semantics.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. The decoder reads only the active member and preserves EUS optional semantics.
    """
    archive = _write_archive(tmp_path, {"survey-active.eus": b"serialized"})
    monkeypatch.setattr(module, "_decode_active_member", lambda _data: {
        "uid": "survey-1", "alias": "SO2_2025", "elements": [{
            "class": "SingleChoiceQuestion", "uid": "q1", "title": "Question",
            "optional": False, "position": 1, "answers": [],
        }],
    })

    form = module.load_active_form(archive)

    assert form.fields_by_uid["q1"].mandatory is True


def test_manifest_serialization_is_byte_stable_and_loadable(tmp_path, monkeypatch):
    """A decoded form has a deterministic, self-contained JSON runtime representation.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. A decoded form has a deterministic, self-contained JSON runtime representation.
    """
    archive = _write_archive(tmp_path, {"survey-active.eus": b"serialized"})
    monkeypatch.setattr(module, "_decode_active_member", lambda _data: {
        "uid": "survey-1", "alias": "SO2_2025", "elements": [{
            "class": "FreeTextQuestion", "uid": "q1", "title": "Question",
            "optional": True, "position": 1, "answers": [],
        }],
    })
    form = module.load_active_form(archive)
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    module.write_form_manifest(form, first)
    module.write_form_manifest(form, second)

    assert first.read_bytes() == second.read_bytes()
    assert module.load_form_manifest(first) == form


def test_load_form_manifest_rejects_unknown_schema_version(tmp_path):
    """Runtime report paths reject a manifest outside the supported schema contract.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Runtime report paths reject a manifest outside the supported schema contract.
    """
    path = tmp_path / "form.json"
    path.write_text(json.dumps({"schema_version": 999}))

    with pytest.raises(module.FormInputError, match="schema_version"):
        module.load_form_manifest(path)


def test_committed_so2_manifest_loads_without_java_decoder():
    """The checked-in runtime manifest preserves the SO2 form shape without Java decoding.

    Returns:
        None. The checked-in runtime manifest preserves the SO2 form shape without Java decoding.
    """
    manifest = Path(__file__).parents[1] / "survey-mappings" / "so2_2025_form.json"

    form = module.load_form_manifest(manifest)

    assert form.survey_alias == "SO2_2025"
    assert len(form.fields_by_uid) == 103
    assert sum(field.field_type == "matrix" for field in form.fields_by_uid.values()) == 3


def test_committed_manifest_retains_matrix_row_and_column_labels():
    """Flat EUS matrix grids retain both response axes in the runtime manifest.

    Returns:
        None. Flat EUS matrix grids retain both response axes in the runtime manifest.
    """
    manifest = Path(__file__).parents[1] / "survey-mappings" / "so2_2025_form.json"
    form = module.load_form_manifest(manifest)
    matrix = next(field for field in form.fields_by_uid.values() if field.field_type == "matrix")

    assert matrix.matrix_rows
    assert matrix.matrix_columns


def test_load_form_manifest_rejects_non_object_root(tmp_path):
    """Malformed JSON roots raise the public manifest input error.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Malformed JSON roots raise the public manifest input error.
    """
    path = tmp_path / "form.json"
    path.write_text("[]")
    with pytest.raises(module.FormInputError, match="root"):
        module.load_form_manifest(path)


def test_committed_manifest_records_other_choice_dependency():
    """EUS choice dependencies become a structured child visibility condition.

    Returns:
        None. EUS choice dependencies become a structured child visibility condition.
    """
    manifest = Path(__file__).parents[1] / "survey-mappings" / "so2_2025_form.json"
    form = module.load_form_manifest(manifest)
    child = next(field for field in form.fields_by_uid.values() if field.title == "Type of Institution")

    assert child.shown_when is not None
    assert child.shown_when.atoms
