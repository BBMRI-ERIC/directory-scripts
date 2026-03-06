import json
import subprocess
import sys
from datetime import date
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "warning-suppressions-manage.py"


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def test_warning_suppressions_manage_add_and_list(tmp_path):
    path = tmp_path / "warning-suppressions.json"
    path.write_text("{}", encoding="utf-8")

    add_result = run_cli(
        "--path",
        str(path),
        "add",
        "--check-id",
        "FT:KAnonViolation",
        "--entity-id",
        "bbmri-eric:ID:EU_demo:collection:demo",
        "--entity-type",
        "COLLECTION",
        "--reason",
        "known false positive",
    )
    assert add_result.returncode == 0

    list_result = run_cli("--path", str(path), "list")
    assert list_result.returncode == 0
    assert "FT:KAnonViolation :: bbmri-eric:ID:EU_demo:collection:demo" in list_result.stdout

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["version"] == 2
    assert payload["suppressions"][0]["entity_type"] == "COLLECTION"


def test_warning_suppressions_manage_prune_stale_dry_run(tmp_path):
    path = tmp_path / "warning-suppressions.json"
    path.write_text(
        json.dumps(
            {
                "version": 2,
                "suppressions": [
                    {
                        "check_id": "FT:KAnonViolation",
                        "entity_id": "x",
                        "expires_on": "2020-01-01",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    result = run_cli("--path", str(path), "prune-stale", "--dry-run")
    assert result.returncode == 0
    assert "Expired entries to prune: 1" in result.stdout
    assert "Dry run enabled" in result.stdout


def test_warning_suppressions_manage_add_defaults_added_on_to_today(tmp_path):
    path = tmp_path / "warning-suppressions.json"
    path.write_text("{}", encoding="utf-8")

    add_result = run_cli(
        "--path",
        str(path),
        "add",
        "--check-id",
        "FT:KAnonViolation",
        "--entity-id",
        "bbmri-eric:ID:EU_demo:collection:demo",
    )
    assert add_result.returncode == 0

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["suppressions"][0]["added_on"] == date.today().isoformat()


def test_warning_suppressions_manage_add_fix_only_records_target_flags(tmp_path):
    path = tmp_path / "warning-suppressions.json"
    path.write_text("{}", encoding="utf-8")

    add_result = run_cli(
        "--path",
        str(path),
        "add",
        "--check-id",
        "FT/facts.k_anonymity.drop_rows_k10",
        "--entity-id",
        "bbmri-eric:ID:EU_demo:collection:demo",
        "--fix-only",
    )
    assert add_result.returncode == 0

    payload = json.loads(path.read_text(encoding="utf-8"))
    entry = payload["suppressions"][0]
    assert entry["check_id"] == "FT/facts.k_anonymity.drop_rows_k10"
    assert entry["suppress_warning"] is False
    assert "suppress_fix" not in entry
