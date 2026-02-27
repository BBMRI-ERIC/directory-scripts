from pathlib import Path
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent

CLI_SCRIPTS = [
    "data-check.py",
    "directory-stats.py",
    "full-text-search.py",
    "get-contacts.py",
    "geocoding_2022.py",
    "COVID19DataPortal_XMLFromBBMRIDirectory.py",
    "exporter-all.py",
    "exporter-bbmri-cohorts.py",
    "exporter-cohorts.py",
    "exporter-country.py",
    "exporter-covid.py",
    "exporter-diagnosis.py",
    "exporter-ecraid.py",
    "exporter-institutions.py",
    "exporter-mission-cancer.py",
    "exporter-negotiator-orphans.py",
    "exporter-obesity.py",
    "exporter-pediatric.py",
    "exporter-quality-label.py",
]


@pytest.mark.parametrize("script_name", CLI_SCRIPTS)
def test_cli_help_runs(script_name):
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / script_name), "-h"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()
