"""Validate immutable, source-labelled combined-survey evidence contracts."""

import importlib

import pytest


def test_provenance_is_required_and_false_is_not_null():
    """Reject incomplete provenance while preserving negative and unknown answers.

    Returns:
        None. Required provenance and three-valued answer semantics are checked.
    """
    module = importlib.import_module("survey_evidence")
    with pytest.raises(ValueError, match="survey"):
        module.EvidenceItem({"question_id": "B.test"})
    base = {"evidence_id": "e1", "survey": "MuCP", "source_record_id": "RESP-001",
            "question_id": "B.test", "question_label": "Test", "scope_id": "s1",
            "source_refs": [{"path": "redacted.json", "locator": "/responses/0/answers/B.test"}]}
    negative = module.EvidenceItem({**base, "normalized_value": False})
    unknown = module.EvidenceItem({**base, "normalized_value": None})
    assert negative.data["normalized_value"] is False
    assert unknown.data["normalized_value"] is None
    with pytest.raises(TypeError):
        negative.data["survey"] = "SO2"


def test_derived_contributions_and_serialization():
    """Require valid source links and serialize frozen nested structures deterministically.

    Returns:
        None. Dangling derived evidence is rejected without conflating source values.
    """
    module = importlib.import_module("survey_evidence")
    bb = module.CombinedBiobank({"biobank_id": "bbmri-eric:ID:AT_TEST", "evidence": [],
                                "observations": [{"contribution_ids": ["missing"]}]})
    with pytest.raises(ValueError, match="contribution"):
        module.validate_evidence_links(bb)
    assert module.canonical_json({"b": 2, "a": 1}) == module.canonical_json({"a": 1, "b": 2})


def test_answer_scope_must_belong_to_contributing_source():
    """Reject invented scopes even when an answer has superficially complete provenance.

    Returns:
        None. Evidence must reference a retained source record and a known local scope.
    """
    module = importlib.import_module("survey_evidence")
    item = {"evidence_id": "e1", "survey": "MuCP", "source_record_id": "RESP-001",
            "question_id": "C.test", "question_label": "Test", "scope_id": "invented",
            "source_refs": [{"path": "redacted.json", "locator": "/responses/0/answers/C.test"}]}
    bb = module.CombinedBiobank({"mucp_source_records": [{"record_id": "RESP-001"}],
                                "so2_source_records": [], "scopes": {"s1": {}},
                                "evidence": [item], "observations": []})
    with pytest.raises(ValueError, match="scope"):
        module.validate_evidence_links(bb)


def test_cross_question_contributions_and_foreign_scope_are_rejected():
    """Prevent superficially valid IDs from linking another survey or another source.

    Returns:
        None. Both analytical lineage and source/scope ownership are enforced.
    """
    module = importlib.import_module("survey_evidence")
    item = {"evidence_id": "e1", "survey": "MuCP", "source_record_id": "R1", "question_id": "C.test",
            "question_label": "Test", "scope_id": "s1",
            "source_refs": [{"path": "redacted.json", "locator": "/responses/0/answers/C.test"}]}
    data = {"mucp_source_records": [{"record_id": "R1"}, {"record_id": "R2"}], "so2_source_records": [],
            "scopes": {"s1": {"source_record_id": "R1"}}, "evidence": [item],
            "observations": [{"survey": "SO2", "question_id": "q1", "contribution_ids": ["e1"]}]}
    with pytest.raises(ValueError, match="contribution"):
        module.validate_evidence_links(module.CombinedBiobank(data))
    data["observations"] = []
    data["scopes"]["s1"]["source_record_id"] = "R2"
    with pytest.raises(ValueError, match="scope"):
        module.validate_evidence_links(module.CombinedBiobank(data))


def test_source_records_and_item_locators_are_required():
    """Complete-looking answers cannot bypass retained-record and locator invariants.

    Returns:
        None. Missing source records or missing source references are rejected.
    """
    module = importlib.import_module("survey_evidence")
    item = {"evidence_id": "e1", "survey": "MuCP", "source_record_id": "R1", "question_id": "C.test",
            "question_label": "Test", "scope_id": "s1", "source_refs": [{"path": "redacted.json", "locator": "/responses/0"}]}
    with pytest.raises(ValueError, match="source|scope"):
        module.validate_evidence_links(module.CombinedBiobank({"evidence": [item], "scopes": {"s1": {}},
                                                              "so2_source_records": [], "mucp_source_records": []}))
    item["source_refs"] = []
    with pytest.raises(ValueError, match="source_refs"):
        module.EvidenceItem(item)


def test_scope_owner_and_reference_types_are_required():
    """Reject unverifiable scope ownership and superficially nonempty malformed locators.

    Returns:
        None. Ownership is mandatory and input path/source identifiers must be strings.
    """
    module = importlib.import_module("survey_evidence")
    item = {"evidence_id": "e1", "survey": "MuCP", "source_record_id": "R1", "question_id": "C.test",
            "question_label": "Test", "scope_id": "s1", "source_refs": [{"path": "redacted.json", "locator": "/responses/0"}]}
    data = {"evidence": [item], "scopes": {"s1": {}}, "so2_source_records": [],
            "mucp_source_records": [{"record_id": "R1"}]}
    with pytest.raises(ValueError, match="scope"):
        module.validate_evidence_links(module.CombinedBiobank(data))
    item["source_refs"][0]["path"] = ["not", "a", "path"]
    with pytest.raises(ValueError, match="source_refs"):
        module.EvidenceItem(item)
    import json
    from pathlib import Path
    from jsonschema import Draft202012Validator
    schema = json.loads(Path("survey-mappings/so2_mucp_combined.schema.json").read_text())
    assert not Draft202012Validator(schema["$defs"]["evidence"]).is_valid(item)
