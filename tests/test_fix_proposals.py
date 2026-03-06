from pathlib import Path

from customwarnings import DataCheckEntityType, DataCheckWarning, DataCheckWarningLevel
from fix_proposals import (
    build_fix_plan_payload,
    load_fix_plan,
    make_fix_proposal,
    write_fix_plan,
)


def test_fix_plan_payload_merges_duplicate_fix_proposals(tmp_path: Path):
    fix = make_fix_proposal(
        update_id="access.duo.collaboration_required",
        module="AP",
        entity_type="COLLECTION",
        entity_id="bbmri-eric:ID:CZ_demo:collection:col1",
        field="data_use",
        mode="append",
        confidence="certain",
        current_value_at_export=[],
        proposed_value=["DUO:0000020"],
        human_explanation="Add collaboration-required DUO term.",
    )
    warning1 = DataCheckWarning(
        "AP:JointDuo",
        "",
        "CZ",
        DataCheckWarningLevel.WARNING,
        "bbmri-eric:ID:CZ_demo:collection:col1",
        DataCheckEntityType.COLLECTION,
        "False",
        "Joint project implies DUO term.",
        fix_proposals=[fix],
    )
    warning2 = DataCheckWarning(
        "AP:JointDuo",
        "",
        "CZ",
        DataCheckWarningLevel.WARNING,
        "bbmri-eric:ID:CZ_demo:collection:col1",
        DataCheckEntityType.COLLECTION,
        "False",
        "Joint project still implies DUO term.",
        fix_proposals=[fix],
    )

    payload = build_fix_plan_payload([warning1, warning2], schema="ERIC", include_withdrawn=False, only_withdrawn=False)

    assert len(payload["updates"]) == 1
    assert payload["updates"][0]["source_check_ids"] == ["AP:JointDuo"]
    assert len(payload["updates"][0]["source_warning_messages"]) == 2

    path = tmp_path / "updates.json"
    write_fix_plan(path, [warning1, warning2], schema="ERIC", include_withdrawn=False, only_withdrawn=False)
    loaded = load_fix_plan(path)
    assert loaded.issues == []
    assert len(loaded.payload["updates"]) == 1


def test_load_fix_plan_reports_checksum_mismatch(tmp_path: Path):
    path = tmp_path / "updates.json"
    path.write_text(
        '{"format_version":1,"generated_at":"2026-03-04T00:00:00+00:00","generated_by":{"tool":"data-check.py","schema":"ERIC","withdrawn_scope":"active-only"},"updates":[{"update_id":"u1","module":"AP","entity_type":"COLLECTION","entity_id":"col1","field":"data_use","mode":"append","confidence":"certain","current_value_at_export":[],"expected_current_value":[],"proposed_value":["DUO:0000020"],"human_explanation":"x","rationale":"","term_explanations":[],"source_check_ids":["AP:JointDuo"],"source_warning_messages":[],"source_warning_actions":[],"replace_required":false,"blocking_reason":"","exclusive_group":"","staging_area":"CZ","update_checksum":"broken"}],"file_checksum":"broken"}',
        encoding="utf-8",
    )
    loaded = load_fix_plan(path)
    assert any("file checksum mismatch" in issue.lower() for issue in loaded.issues)
    assert any("update checksum mismatch" in issue.lower() for issue in loaded.issues)


def test_fix_plan_payload_skips_suppressed_update_ids():
    fix = make_fix_proposal(
        update_id="FT/facts.k_anonymity.drop_rows_k10",
        module="FT",
        entity_type="COLLECTION",
        entity_id="bbmri-eric:ID:EU_demo:collection:demo",
        field="facts",
        mode="delete_rows",
        confidence="certain",
        current_value_at_export=[],
        proposed_value=[{"id": "row1"}],
        human_explanation="Drop rows violating k-anonymity.",
    )
    warning = DataCheckWarning(
        "FT:KAnonViolation",
        "",
        "EU",
        DataCheckWarningLevel.WARNING,
        "bbmri-eric:ID:EU_demo:collection:demo",
        DataCheckEntityType.COLLECTION,
        "False",
        "Rows violate donor k-anonymity.",
        fix_proposals=[fix],
    )
    payload = build_fix_plan_payload(
        [warning],
        schema="ERIC",
        include_withdrawn=False,
        only_withdrawn=False,
        suppressions={
            "FT/facts.k_anonymity.drop_rows_k10": {
                "bbmri-eric:ID:EU_demo:collection:demo": "Reviewed false positive"
            }
        },
    )
    assert payload["updates"] == []


def test_fix_plan_payload_skips_suppressed_module_prefixed_update_id():
    fix = make_fix_proposal(
        update_id="facts.k_anonymity.drop_rows_k10",
        module="FT",
        entity_type="COLLECTION",
        entity_id="bbmri-eric:ID:EU_demo:collection:demo",
        field="facts",
        mode="delete_rows",
        confidence="certain",
        current_value_at_export=[],
        proposed_value=[{"id": "row1"}],
        human_explanation="Drop rows violating k-anonymity.",
    )
    warning = DataCheckWarning(
        "FT:KAnonViolation",
        "",
        "EU",
        DataCheckWarningLevel.WARNING,
        "bbmri-eric:ID:EU_demo:collection:demo",
        DataCheckEntityType.COLLECTION,
        "False",
        "Rows violate donor k-anonymity.",
        fix_proposals=[fix],
    )
    payload = build_fix_plan_payload(
        [warning],
        schema="ERIC",
        include_withdrawn=False,
        only_withdrawn=False,
        suppressions={
            "FT/facts.k_anonymity.drop_rows_k10": {
                "bbmri-eric:ID:EU_demo:collection:demo": "Reviewed false positive"
            }
        },
    )
    assert payload["updates"] == []


def test_fix_plan_payload_skips_fixes_when_source_warning_id_is_suppressed():
    fix = make_fix_proposal(
        update_id="facts.k_anonymity.drop_rows_k10",
        module="FT",
        entity_type="COLLECTION",
        entity_id="bbmri-eric:ID:EU_demo:collection:demo",
        field="facts",
        mode="delete_rows",
        confidence="certain",
        current_value_at_export=[],
        proposed_value=[{"id": "row1"}],
        human_explanation="Drop rows violating k-anonymity.",
    )
    warning = DataCheckWarning(
        "FT:KAnonViolation",
        "",
        "EU",
        DataCheckWarningLevel.WARNING,
        "bbmri-eric:ID:EU_demo:collection:demo",
        DataCheckEntityType.COLLECTION,
        "False",
        "Rows violate donor k-anonymity.",
        fix_proposals=[fix],
    )
    payload = build_fix_plan_payload(
        [warning],
        schema="ERIC",
        include_withdrawn=False,
        only_withdrawn=False,
        suppressions={
            "FT:KAnonViolation": {
                "bbmri-eric:ID:EU_demo:collection:demo": "Suppress warning and attached fixes"
            }
        },
    )
    assert payload["updates"] == []
