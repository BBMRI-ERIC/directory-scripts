"""Keep core and optional survey branch distributions independently runnable."""

import ast
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
CORE_PATHS = {
    "directory.py", "cli_common.py", "data-check.py", "exporter-all.py",
    "eosc-organisation-matcher.py", "R-maps/README.md", "requirements.txt",
}
SURVEY_REQUIRED = {
    "survey-so2-directory.py", "so2_descriptive_report.py", "survey_combined.py",
    "survey-mappings/so2_2025_form.json", "survey-mappings/so2_2025_directory_mapping.json",
    "survey-mappings/so2_mucp_combined.schema.json", "requirements-surveys.txt",
    "docs/surveys/README.md",
}


def validate_distribution(paths: set[str]) -> None:
    """Validate a tracked file inventory without relying on a branch name.

    Args:
        paths: Repository-relative POSIX paths in a Git index or invented layout.

    Returns:
        None. Accepts either a core-only layout or the complete survey entry points.

    Raises:
        AssertionError: If shared entry points or distribution boundaries are broken.
    """
    assert CORE_PATHS <= paths, f"Missing shared files: {CORE_PATHS - paths}"
    if "docs/surveys/README.md" in paths:
        assert SURVEY_REQUIRED <= paths, f"Missing survey files: {SURVEY_REQUIRED - paths}"
        return
    unexpected = {
        p for p in paths
        if p == "survey-so2-directory.py"
        or ("/" not in p and p.startswith(("so2_", "survey_")) and p.endswith(".py"))
        or p.startswith(("survey-mappings/", "tests/fixtures/so2_mucp/", "docs/surveys/"))
        or p.startswith(("tests/test_so2_", "tests/test_survey_", "tests/test_mucp_"))
        or p in {"tests/test_quantity_reporting_audit.py", "docs/so2-descriptive-upsets.md", "requirements-surveys.txt"}
    }
    assert not unexpected, f"Survey files remain in core distribution: {sorted(unexpected)}"


def test_distribution_inventory_contract():
    """Check the actual tracked checkout, including detached verification worktrees.

    Returns:
        None. Shared and branch-specific inventories satisfy the same layout contract.
    """
    paths = set(subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")) - {""}
    validate_distribution(paths)
    if "docs/surveys/README.md" not in paths:
        for name in sorted(p for p in paths if p.endswith(".py")):
            for node in ast.walk(ast.parse((ROOT / name).read_text(encoding="utf-8"))):
                imports = []
                if isinstance(node, ast.Import):
                    imports = [item.name for item in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports = [node.module]
                assert not any(item.startswith(("so2_", "survey_")) for item in imports), name


def test_distribution_contract_accepts_both_supported_layouts():
    """Exercise both distributions and reject partial surveys and hidden consumers.

    Returns:
        None. Partial restorations and non-prefixed survey tests cannot pass as core.
    """
    validate_distribution(CORE_PATHS)
    validate_distribution(CORE_PATHS | SURVEY_REQUIRED)
    with pytest.raises(AssertionError, match="Survey files remain"):
        validate_distribution(CORE_PATHS | {"tests/test_quantity_reporting_audit.py"})
    with pytest.raises(AssertionError, match="Missing survey files"):
        validate_distribution(CORE_PATHS | {"docs/surveys/README.md"})
    with pytest.raises(AssertionError, match="Missing shared files"):
        validate_distribution(SURVEY_REQUIRED)
