import ast
from pathlib import Path
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent

CLI_SCRIPTS = [
    "data-check.py",
    "qcheck-updater.py",
    "collection-factsheet-descriptor-updater.py",
    "directory-stats.py",
    "full-text-search.py",
    "get-contacts.py",
    "geocoding_2022.py",
    "COVID19DataPortal_XMLFromBBMRIDirectory.py",
    "exporter-all.py",
    "exporter-bbmri-cohorts.py",
    "exporter-cMDR.py",
    "exporter-cohorts.py",
    "exporter-country.py",
    "exporter-covid.py",
    "exporter-ecraid.py",
    "exporter-institutions.py",
    "exporter-mission-cancer.py",
    "exporter-negotiator-orphans.py",
    "exporter-obesity.py",
    "exporter-pediatric.py",
    "exporter-quality-label.py",
]

EXPORTER_SCRIPTS = sorted(path.name for path in REPO_ROOT.glob("exporter-*.py"))
PRODUCTION_PYTHON_FILES = sorted(
    [
        *REPO_ROOT.glob("*.py"),
        *REPO_ROOT.glob("checks/*.py"),
        *REPO_ROOT.glob("R-maps/*.py"),
    ]
)

FACT_SHEET_EXPORTERS = [
    "exporter-all.py",
    "exporter-bbmri-cohorts.py",
    "exporter-cMDR.py",
    "exporter-cohorts.py",
    "exporter-country.py",
    "exporter-covid.py",
    "exporter-ecraid.py",
    "exporter-mission-cancer.py",
    "exporter-obesity.py",
    "exporter-pediatric.py",
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


@pytest.mark.parametrize(
    "module_path",
    PRODUCTION_PYTHON_FILES,
    ids=lambda path: str(path.relative_to(REPO_ROOT)),
)
def test_production_python_file_has_module_purpose_docstring(module_path):
    source = module_path.read_text(encoding="utf-8")

    assert ast.get_docstring(ast.parse(source)), (
        f"{module_path.relative_to(REPO_ROOT)} must have a module docstring "
        "describing its purpose"
    )


def test_each_exporter_has_a_documentation_section():
    documentation = (REPO_ROOT / "docs" / "exporters.md").read_text(encoding="utf-8")

    for script_name in EXPORTER_SCRIPTS:
        assert f"| `{script_name}` |" in documentation
        assert f"### `{script_name}`" in documentation


@pytest.mark.parametrize("script_name", FACT_SHEET_EXPORTERS)
def test_fact_sheet_exporter_help_exposes_no_star_fallback(script_name):
    source = (REPO_ROOT / script_name).read_text(encoding="utf-8")

    assert "add_fact_sheet_summary_arguments(parser)" in source
    assert "warn_if_no_star_fact_sums_enabled(args)" in source
    assert "allow_no_star_fact_sums=args.allow_no_star_fact_sums" in source


def test_data_check_non_eric_schema_requires_auth():
    env = dict(**__import__("os").environ)
    env["DIRECTORYUSERNAME"] = ""
    env["DIRECTORYPASSWORD"] = ""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "data-check.py"), "--schema", "BBMRI-EU", "-N", "-r"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode != 0
    assert "requires -t/--token or -u/--username and -p/--password" in result.stderr
