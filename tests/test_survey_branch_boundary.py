"""Verify the optional survey distribution retains portable CLI entry points."""

from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
COMMANDS = (
    "analyze", "describe", "render-report", "render-descriptive-report",
    "export-update-plan", "export-eus-form-json", "export-descriptive-upset-r",
    "merge-mucp",
)


@pytest.mark.parametrize("command", COMMANDS)
def test_all_survey_cli_commands_are_retained(command):
    """Exercise every peer command without credentials, inputs or live Directory data.

    Args:
        command: Existing survey subcommand whose public help must remain runnable.

    Returns:
        None. Every public parser exits successfully and prints its usage contract.
    """
    result = subprocess.run(
        [sys.executable, str(ROOT / "survey-so2-directory.py"), command, "--help"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout


def test_survey_reference_defaults_exist():
    """Require tracked data-free configurations and dedicated survey documentation.

    Returns:
        None. A clone contains both its runnable defaults and its documentation index.
    """
    required = (
        "survey-mappings/so2_2025_form.json",
        "survey-mappings/so2_2025_descriptive_report.json",
        "survey-mappings/so2_2025_directory_mapping.json",
        "survey-mappings/so2_2025_upsets.json",
        "survey-mappings/so2_2025_readiness_scores.json",
        "survey-mappings/mucp_answer_states_v1.json",
        "survey-mappings/mucp_reporting_policy.json",
        "survey-mappings/so2_mucp_combined.schema.json",
        "docs/surveys/README.md",
    )
    tracked = set(subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0"))
    assert set(required) <= tracked
    assert all((ROOT / name).is_file() for name in required)


def test_survey_dependencies_include_core_requirements():
    """Keep analysis extras separate without duplicating the shared dependency list.

    Returns:
        None. Installing survey requirements also installs the exact core requirements.
    """
    lines = (ROOT / "requirements-surveys.txt").read_text().splitlines()
    assert "-r requirements.txt" in lines
    assert {"javaobj-py3==0.6.1", "defusedxml~=0.7.1", "jsonschema>=4.17.3,<5"} <= set(lines)
    assert not any(line.startswith(("Yapsy", "networkx", "pandas")) for line in lines)
