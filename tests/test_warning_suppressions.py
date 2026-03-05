import json
import os
from pathlib import Path

from customwarnings import (
    DataCheckEntityType,
    DataCheckWarning,
    DataCheckWarningLevel,
)
import warning_suppressions
from warning_suppressions import load_warning_suppressions
from warning_suppressions import (
    load_warning_suppressions_detailed,
    serialize_suppression_entries,
    summarize_suppression_diagnostics,
)
from warningscontainer import WarningsContainer


def test_warning_suppressions_loads_entity_mapping_and_suppresses_output(tmp_path, capsys):
    config_path = tmp_path / "warning-suppressions.json"
    config_path.write_text(
        json.dumps(
            {
                "VID:BBExtPrefix": {
                    "entities": {
                        "bbmri-eric:ID:EU_BBMRI-ERIC": "EU is a permitted non-country prefix."
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    suppressions = load_warning_suppressions(config_path)
    container = WarningsContainer(suppressions)
    container.newWarning(
        DataCheckWarning(
            "VID:BBExtPrefix",
            "",
            "EU",
            DataCheckWarningLevel.ERROR,
            "bbmri-eric:ID:EU_BBMRI-ERIC",
            DataCheckEntityType.BIOBANK,
            "False",
            "Suppressed false positive",
        )
    )
    container.newWarning(
        DataCheckWarning(
            "VID:BBExtPrefix",
            "",
            "EU",
            DataCheckWarningLevel.ERROR,
            "bbmri-eric:ID:EU_OTHER",
            DataCheckEntityType.BIOBANK,
            "False",
            "Real warning",
        )
    )

    container.dumpWarnings()
    captured = capsys.readouterr()

    assert "bbmri-eric:ID:EU_BBMRI-ERIC" not in captured.out
    assert "bbmri-eric:ID:EU_OTHER" in captured.out


def test_warning_suppressions_skips_invalid_entries_with_warning(tmp_path):
    config_path = tmp_path / "warning-suppressions.json"
    config_path.write_text(
        json.dumps(
            {
                "VID:BBExtPrefix": {
                    "entities": {
                        "bbmri-eric:ID:EU_BBMRI-ERIC": "valid",
                        "": "invalid empty entity id",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    warnings = []
    suppressions = load_warning_suppressions(config_path, warn=warnings.append)

    assert suppressions == {
        "VID:BBExtPrefix": {
            "bbmri-eric:ID:EU_BBMRI-ERIC": "valid",
        }
    }
    assert warnings
    assert "entity_id" in warnings[0]


def test_warning_suppressions_keeps_valid_entries_when_one_top_level_entry_is_invalid(tmp_path):
    config_path = tmp_path / "warning-suppressions.json"
    config_path.write_text(
        json.dumps(
            {
                "VID:BBExtPrefix": {
                    "entities": {
                        "bbmri-eric:ID:EU_BBMRI-ERIC": "valid",
                    }
                },
                "VID:CtExtPrefix": "broken",
            }
        ),
        encoding="utf-8",
    )

    warnings = []
    suppressions = load_warning_suppressions(config_path, warn=warnings.append)

    assert suppressions == {
        "VID:BBExtPrefix": {
            "bbmri-eric:ID:EU_BBMRI-ERIC": "valid",
        }
    }
    assert warnings
    assert "unsupported suppression entry" in warnings[0]


def test_warning_suppressions_default_path_is_repo_relative(tmp_path, monkeypatch):
    config_path = tmp_path / "warning-suppressions.json"
    config_path.write_text(
        json.dumps(
            {
                "VID:BBExtPrefix": {
                    "entities": {
                        "bbmri-eric:ID:EU_BBMRI-ERIC": "repo-relative default",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        warning_suppressions,
        "DEFAULT_WARNING_SUPPRESSIONS_PATH",
        config_path,
    )

    cwd = os.getcwd()
    other_dir = tmp_path / "other-cwd"
    other_dir.mkdir()
    os.chdir(other_dir)
    try:
        suppressions = load_warning_suppressions(
            warning_suppressions.DEFAULT_WARNING_SUPPRESSIONS_PATH
        )
    finally:
        os.chdir(cwd)

    assert suppressions == {
        "VID:BBExtPrefix": {
            "bbmri-eric:ID:EU_BBMRI-ERIC": "repo-relative default",
        }
    }


def test_warning_suppressions_detailed_loader_parses_metadata_fields(tmp_path):
    config_path = tmp_path / "warning-suppressions.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 2,
                "suppressions": [
                    {
                        "check_id": "FT:KAnonViolation",
                        "entity_id": "bbmri-eric:ID:EU_BBMRI-ERIC:collection:CRC-Cohort",
                        "entity_type": "COLLECTION",
                        "reason": "Reviewed false positive",
                        "added_by": "tester@example.org",
                        "added_on": "2026-03-05",
                        "expires_on": "2026-12-31",
                        "ticket": "DM-1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = load_warning_suppressions_detailed(config_path)
    assert result.issues == []
    assert len(result.entries) == 1
    entry = result.entries[0]
    assert entry.entity_type == "COLLECTION"
    assert entry.expires_on == "2026-12-31"
    assert result.suppressions == {
        "FT:KAnonViolation": {
            "bbmri-eric:ID:EU_BBMRI-ERIC:collection:CRC-Cohort": "Reviewed false positive"
        }
    }


def test_warning_suppression_diagnostics_report_unknown_expired_and_stale():
    entry_result = load_warning_suppressions_detailed(
        path=None
    )
    assert entry_result.entries == []
    diagnostics = summarize_suppression_diagnostics(
        [
            warning_suppressions.WarningSuppressionEntryModel.parse_obj(
                {
                    "check_id": "UNK:Nope",
                    "entity_id": "missing-id",
                    "entity_type": "COLLECTION",
                    "expires_on": "2020-01-01",
                }
            )
        ],
        known_check_ids={"FT:KAnonViolation"},
        known_check_prefixes={"FT", "AP"},
        known_entities={"COLLECTION": {"existing-id"}},
    )
    assert any("unknown check_id" in item for item in diagnostics)
    assert any("expired" in item for item in diagnostics)
    assert any("entity_id not found" in item for item in diagnostics)


def test_serialize_suppression_entries_emits_v2_payload():
    entry = warning_suppressions.WarningSuppressionEntryModel.parse_obj(
        {
            "check_id": "AP:BioDuoMissing",
            "entity_id": "bbmri-eric:ID:EU_demo:collection:x",
            "entity_type": "COLLECTION",
            "reason": "known exception",
            "ticket": "DM-42",
        }
    )
    payload = serialize_suppression_entries([entry])
    assert payload["version"] == 2
    assert payload["suppressions"][0]["check_id"] == "AP:BioDuoMissing"
    assert payload["suppressions"][0]["ticket"] == "DM-42"


def test_warning_suppression_diagnostics_accept_module_prefixed_update_ids():
    diagnostics = summarize_suppression_diagnostics(
        [
            warning_suppressions.WarningSuppressionEntryModel.parse_obj(
                {
                    "check_id": "FT/facts.k_anonymity.drop_rows_k10",
                    "entity_id": "bbmri-eric:ID:EU_BBMRI-ERIC:collection:MICAN",
                    "entity_type": "COLLECTION",
                }
            )
        ],
        known_check_ids={"FT:KAnonViolation"},
        known_check_prefixes={"FT", "AP"},
        known_entities={"COLLECTION": {"bbmri-eric:ID:EU_BBMRI-ERIC:collection:MICAN"}},
    )
    assert not any("unknown check_id" in item for item in diagnostics)
