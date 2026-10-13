"""Verify SO2 physical-row evidence and frozen-findings source binding."""

import json
from types import SimpleNamespace

import pandas as pd
import pytest

from so2_descriptive_report import QuestionDefinition
from survey_identity import MatchOverrides
from survey_combined import so2_source_records, load_bound_so2_resolutions, resolve_so2_records
from survey_identity import identity_fingerprint


def test_physical_row_and_raw_answer_are_preserved():
    """Adapt the real source-row column without inventing observation identifiers.

    Returns:
        None. Raw semicolon text and canonical selections retain worksheet-row provenance.
    """
    workbook = SimpleNamespace(responses=pd.DataFrame([{"source_row": 5, "Q": "DNA;Serum", "Country": "AT",
                                                        "Name of Institution": "Alpha"}]), worksheet="Content",
                               source_path="redacted.xlsx", source_sha256="a" * 64)
    q = QuestionDefinition("q_001", "Q", "multi_choice", "Specimens", ("DNA", "Serum"), ";", (), None)
    result = so2_source_records(workbook, [q], {"questions": {}})[0]
    item = result.data["evidence"][0]
    assert item["survey_row"] == 5
    assert item["raw_answer"] == "DNA;Serum"
    assert item["normalized_value"] == ("DNA", "Serum")


def test_legacy_findings_require_hash_binding(tmp_path):
    """Block accidental freeze of findings whose filename alone matches the workbook.

    Args:
        tmp_path: Isolated directory containing a redacted unbound findings file.

    Returns:
        None. The failure reports both hashes needed for an explicit review binding.
    """
    path = tmp_path / "findings.json"
    path.write_text(json.dumps({"survey_metadata": {"survey_file": "redacted.xlsx"}, "row_resolutions": []}))
    workbook = SimpleNamespace(source_sha256="a" * 64)
    with pytest.raises(ValueError, match="reviewed input binding"):
        load_bound_so2_resolutions(path, workbook, MatchOverrides({}, ()))


def test_frozen_legacy_certain_name_status_does_not_accept_aliases(tmp_path):
    """An input hash proves content provenance, not the correctness of legacy fuzzy matching.

    Args:
        tmp_path: Isolated directory for a hash-bound but alias-derived resolution.

    Returns:
        None. Legacy name certainty still requires a reviewed record override.
    """
    workbook = SimpleNamespace(source_sha256="a" * 64, source_path="redacted.xlsx", worksheet="Content",
                               responses=pd.DataFrame([{"source_row": 5, "Name of Institution": "Alias"}]))
    report = {"survey_metadata": {"survey_sha256": workbook.source_sha256}, "row_resolutions": [{
        "survey_row": 5, "institution_name": "Alias", "matched_biobank_ids": ["bbmri-eric:ID:AT_A"],
        "resolution_status": "resolved_by_institution_name_certain"}]}
    path = tmp_path / "findings.json"
    path.write_text(json.dumps(report))
    frozen = load_bound_so2_resolutions(path, workbook, MatchOverrides({}, ()))
    assert frozen["so2:Content:row:5"].data["status"] == "review"
    records = so2_source_records(workbook, [], {"questions": {}})
    decisions = resolve_so2_records(records, SimpleNamespace(biobanks={}, eligible_ids=set()), frozen, MatchOverrides({}, ()))
    assert decisions[0].data["identity_fingerprint"] == identity_fingerprint(records[0])


def test_frozen_id_cannot_bypass_current_conflicting_identity():
    """Hash-bound findings do not waive contradictory source identity checks.

    Returns:
        None. Conflicting full email ownership requires review despite a frozen ID.
    """
    from survey_evidence import SourceRecord, ResolutionRecord
    from survey_identity import IdentityCatalogue
    a, b = "bbmri-eric:ID:AT_A", "bbmri-eric:ID:AT_B"
    record = SourceRecord({"survey": "SO2", "record_id": "row5", "country": "AT",
        "identity": {"explicit_biobank_id": a, "email_addresses": ["other@example.org"]}})
    catalogue = IdentityCatalogue({a: {"country": "AT"}, b: {"country": "AT"}}, frozenset({a, b}), {"other@example.org": {b}})
    frozen = {"row5": ResolutionRecord({"source_record_id": "row5", "status": "accepted", "biobank_id": a, "method": "frozen:exact_id"})}
    result = resolve_so2_records([record], catalogue, frozen, MatchOverrides({}, ()))[0]
    assert result.data["status"] == "review"
    unmatched = SourceRecord({"survey": "SO2", "record_id": "row5", "country": "AT", "identity": {}})
    result = resolve_so2_records([unmatched], catalogue, frozen, MatchOverrides({}, ()))[0]
    assert result.data["status"] == "review"
