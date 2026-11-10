"""Exercise reviewed migration guidance without a live Directory connection."""

import copy
import json
from pathlib import Path

import pytest


def document():
    """Build a minimal guidance document with one conditional migration.

    Returns:
        Independently owned local-artifact payload with valid source references.
    """
    return {
        "schema_version": 1,
        "sources": {"new": {
            "repository": "https://github.com/molgenis/molgenis-emx2",
            "revision": "a" * 40, "path": "data/DataCategories.csv",
            "sha256": "b" * 64, "locator": "IMAGING_DATA definition",
        }},
        "production_checks": {},
        "expectations": {},
        "manual_sections": {"datasets": {
            "label": "migration-dataset-types", "title": "Dataset types",
            "publication": "unpublished",
        }},
        "migrations": [{
            "id": "datasets.imaging", "table": "DataCategories",
            "entity_fields": ["Collections.data_categories"],
            "previous_terms": ["IMAGING_DATA"], "status": "deprecated",
            "applicability": {"reviewed_reference_ids": ["new"]},
            "history": {"before_source_ids": [], "after_source_ids": ["new"],
                        "production_check_ids": []},
            "replacement_options": [{
                "terms": ["Body image"], "relationship": "target_narrower",
                "basis": "reviewed_recommendation", "conditions": ["Body images are held."],
                "explanation": "Select only when present.", "evidence_ids": ["new"],
            }],
            "actions": [{"kind": "inspect_existing_information", "text": "Check image types."}],
            "information_needed": ["Which image types are held?"],
            "explanation": "Generic imaging does not establish the specific image type.",
            "evidence_ids": ["new"], "review": {
                "state": "accepted", "reviewed_on": "2026-11-05", "note": "Reviewed conditional advice."
            }, "manual_section_ids": ["datasets"],
        }],
        "miabis_bindings": [], "structural_changes": [],
    }


@pytest.mark.parametrize("revision", ["master", "573baa460", "z" * 40, None])
def test_software_development_revision_must_be_immutable(revision):
    """Reject branch names and incomplete or malformed software commit references.

    Args:
        revision: Invalid explicitly supplied software baseline revision.

    Returns:
        None. Absence remains backward-compatible, but a supplied revision must
        identify one full immutable Git commit.
    """
    from vocabulary_guidance import validate_guidance
    payload = document()
    payload["expectations"]["software"] = {"release": "v13.209.1", "revision": revision}
    with pytest.raises(ValueError):
        validate_guidance(payload)


def test_valid_conditional_advice_is_preserved():
    """Keep a narrower alternative conditional rather than an executable update.

    Returns:
        None.
    """
    from vocabulary_guidance import find_guidance, validate_guidance
    payload = validate_guidance(document())
    found = find_guidance(payload, "DataCategories", "IMAGING_DATA")
    assert found[0]["replacement_options"][0]["conditions"] == ["Body images are held."]
    assert "fix_proposals" not in found[0]


@pytest.mark.parametrize("fault", ["duplicate", "dangling", "mutable_revision", "wrong_direction", "missing_action", "conflict"])
def test_invalid_guidance_is_rejected(fault):
    """Reject malformed contracts instead of silently offering unsafe advice.

    Args:
        fault: Mutation selecting the invalid identity, evidence or advice shape.

    Returns:
        None.
    """
    from vocabulary_guidance import validate_guidance
    payload = document()
    entry = payload["migrations"][0]
    if fault == "duplicate":
        payload["migrations"].append(copy.deepcopy(entry))
    elif fault == "dangling":
        entry["evidence_ids"] = ["absent"]
    elif fault == "mutable_revision":
        payload["sources"]["new"]["revision"] = "master"
    elif fault == "wrong_direction":
        entry["replacement_options"][0]["relationship"] = "directory_narrower"
    elif fault == "missing_action":
        entry["actions"][0].pop("text")
    else:
        other = copy.deepcopy(entry)
        other["id"] = "conflicting"
        payload["migrations"].append(other)
    with pytest.raises(ValueError):
        validate_guidance(payload)


def test_review_required_entries_do_not_supply_replacement_advice():
    """Keep unaccepted proposals available for maintenance but not QC advice.

    Returns:
        None.
    """
    from vocabulary_guidance import find_guidance, validate_guidance
    payload = document()
    payload["migrations"][0]["review"]["state"] = "needs_review"
    assert find_guidance(validate_guidance(payload), "DataCategories", "IMAGING_DATA") == []


def test_accepted_unresolved_entry_is_valid():
    """Allow explicit no-safe-replacement guidance without inventing a target.

    Returns:
        None.
    """
    from vocabulary_guidance import validate_guidance
    payload = document()
    payload["migrations"][0]["replacement_options"] = []
    payload["migrations"][0]["actions"] = [{"kind": "no_safe_replacement", "text": "Ask what data are held."}]
    assert validate_guidance(payload)["migrations"][0]["replacement_options"] == []


def test_loading_uses_explicit_path_and_rejects_missing_file(tmp_path):
    """Read a local reviewed document and explain an unavailable input.

    Args:
        tmp_path: Isolated directory for the JSON input artifact.

    Returns:
        None.
    """
    from vocabulary_guidance import load_guidance
    path = tmp_path / "guidance.json"
    path.write_text(json.dumps(document()), encoding="utf-8")
    assert load_guidance(path)["schema_version"] == 1
    with pytest.raises(ValueError, match="guidance"):
        load_guidance(tmp_path / "missing.json")


def test_default_location_is_module_relative():
    """Keep the default artifact independent of the invocation directory.

    Returns:
        None.
    """
    import vocabulary_guidance
    assert vocabulary_guidance.DEFAULT_GUIDANCE_PATH == Path(vocabulary_guidance.__file__).with_name("vocabulary-guidance.json")


@pytest.mark.parametrize("fault", ["expectation", "production", "binding", "blank_explanation", "missing_review_date"])
def test_all_cross_references_and_review_contracts_are_checked(fault):
    """Reject incomplete version context and unsupported comparison evidence.

    Args:
        fault: Invalid cross-reference or review shape inserted into valid guidance.

    Returns:
        None.
    """
    from vocabulary_guidance import validate_guidance
    payload = document()
    if fault == "expectation":
        payload["expectations"] = {"model": {"expected_reference_id": "absent", "older_reference_ids": [], "newer_reference_ids": []}}
    elif fault == "production":
        payload["production_checks"] = {"current": {"checked_at": "yesterday"}}
    elif fault == "binding":
        payload["miabis_bindings"] = [{
            "id": "binding", "explanation": "Unresolved comparison", "evidence_ids": ["new"],
            "review": payload["migrations"][0]["review"], "manual_section_ids": [],
            "miabis_concept": {"source_id": "absent", "name": "X", "locator": "table row", "definition_hash": "a" * 64},
            "directory_terms": [], "relationship": "missing_in_directory",
        }]
    elif fault == "blank_explanation":
        payload["migrations"][0]["explanation"] = ""
    else:
        payload["migrations"][0]["review"]["reviewed_on"] = None
    with pytest.raises(ValueError):
        validate_guidance(payload)


def test_bundled_guidance_covers_every_historical_and_compared_term():
    """Prevent convenient examples from standing in for complete reviewed coverage.

    Returns:
        None.
    """
    from vocabulary_guidance import load_guidance
    payload = load_guidance()
    expected = json.loads((Path(__file__).parent / "fixtures" / "vocabulary-reference-coverage.json").read_text())
    for table in ("DataCategories", "ServiceTypes"):
        old = [name for entry in payload["migrations"] if entry["table"] == table for name in entry["previous_terms"]]
        assert len(old) == len(set(old))
        assert set(old) == set(expected["previous_terms"][table])
        represented = {target["name"] for binding in payload["miabis_bindings"]
                       for target in binding["directory_terms"] if target["table"] == table}
        assert represented == set(expected["directory_terms"][table])
        reference = {binding["miabis_concept"]["name"] for binding in payload["miabis_bindings"]
                     if binding["miabis_concept"] is not None
                     and any(target["table"] == table for target in binding["directory_terms"])}
        assert reference == set(expected["miabis_terms"][table])


@pytest.mark.parametrize("fingerprints", [None, [], {"IMAGING_DATA": None}, {"IMAGING_DATA": "not-a-hash"}])
def test_malformed_optional_fingerprints_are_rejected_at_load(fingerprints):
    """Keep corrupt optional advice from reaching runtime replacement selection.

    Args:
        fingerprints: Invalid term_hashes shape or digest inserted into source evidence.

    Returns:
        None.
    """
    from vocabulary_guidance import validate_guidance
    payload = document()
    payload["sources"]["new"]["term_hashes"] = fingerprints
    with pytest.raises(ValueError):
        validate_guidance(payload)
