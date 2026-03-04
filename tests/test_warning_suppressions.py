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
