"""Offline CLI contracts for EOSC review preparation, import and approval."""

from importlib import import_module
import json
from pathlib import Path
import sys
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
cli = import_module("eosc-organisation-matcher")


class DirectoryFake:
    def __init__(self, **kwargs):
        assert not kwargs["include_withdrawn_entities"]
        assert not kwargs["only_withdrawn_entities"]

    def getDirectoryUrl(self):
        return "https://directory.example"

    def getSchema(self):
        return "ERIC"

    def getBiobanks(self):
        return [{"id": "B1", "juridical_person": "Institute Alpha", "country": "BE"},
                {"id": "withdrawn", "juridical_person": "Institute Alpha", "country": "BE"}]

    def isBiobankWithdrawn(self, bid):
        return bid == "withdrawn"


@pytest.fixture
def adapter(monkeypatch):
    data = {"sheet_name": "Members", "workbook_sha256": "digest", "organisations": [{
        "organisation_id": "001", "name": "Universiteit Alpha", "acronym": "UA", "country": "Belgium",
        "membership_type": "Member", "membership_status": "Active"}]}
    calls = []
    monkeypatch.setattr(cli, "read_membership", lambda *a, **kw: data)
    monkeypatch.setattr(cli, "write_matches_xlsx", lambda *a: calls.append(a))
    return data, calls


def run(*args):
    return cli.main(["-i", "source.xlsx", *map(str, args)], directory_factory=DirectoryFake)


def test_help_is_offline_and_no_withdrawn_option(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"], directory_factory=lambda **kw: pytest.fail("Directory accessed"))
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "--prepare-ai-review" in output
    assert "--include-withdrawn" not in output
    assert "--only-withdrawn" not in output


def test_stdout_exact_columns_counts_and_active_ids(adapter, capsys):
    adapter[0]["organisations"][0]["name"] = "Institute Alpha"
    run()
    output = capsys.readouterr().out.splitlines()
    assert output == ["Organisation ID\tEOSC-A Name\tBBMRI-ERIC Name\tList of biobankIDs",
                      "001\tInstitute Alpha\tInstitute Alpha\tB1", "EOSC-A Members: 1", "EOSC-A Observers: 0"]
    run("-N")
    assert capsys.readouterr().out == ""


def test_prepare_import_approve_export_and_resume(adapter, tmp_path, capsys):
    prefix = tmp_path / "review"
    run("--prepare-ai-review", prefix)
    packet = json.loads(prefix.with_suffix(".json").read_text())
    assert "untrusted evidence" in prefix.with_suffix(".md").read_text()
    assert capsys.readouterr().out == ""
    case = packet["cases"][0]
    response = {"packet_id": packet["packet_id"], "reviews": [{
        "case_id": case["case_id"], "decision": "match", "target_id": "001",
        "reviewed_target_ids": ["001"], "relation": "translated_name", "rationale": "Primary evidence",
        "evidence_sources": [{"url": "https://institution.example/legal", "supports": "Same institution",
                              "accessed_on": "2026-09-08"}]}]}
    result_path = tmp_path / "results.json"
    result_path.write_text(json.dumps(response))
    registry_path = tmp_path / "registry.json"
    run("--import-ai-review", result_path, "--review-packet", prefix.with_suffix(".json"),
        "--output-mapping", registry_path)
    registry = json.loads(registry_path.read_text())
    assert registry["decisions"][0]["approval"] == "proposed"
    run("--mapping-file", registry_path, "--prepare-ai-review", tmp_path / "repeat")
    assert json.loads((tmp_path / "repeat.json").read_text())["cases"] == []
    approved = tmp_path / "approved.json"
    run("--mapping-file", registry_path, "--approve-review", registry["decisions"][0]["review_id"],
        "--reviewer", "Human reviewer", "--output-mapping", approved)
    assert json.loads(registry_path.read_text()) == registry
    assert json.loads(approved.read_text())["decisions"][0]["approval"] == "approved"
    run("--mapping-file", approved, "-X", tmp_path / "matched.xlsx")
    assert adapter[1][-1][1][0]["biobank_ids"] == ["B1"]
    assert "EOSC-A Members: 1" in capsys.readouterr().out


def test_existing_output_never_overwritten_and_packet_pair_preflight(adapter, tmp_path):
    prefix = tmp_path / "review"
    prefix.with_suffix(".md").write_text("my work")
    with pytest.raises(SystemExit) as exc:
        run("--prepare-ai-review", prefix)
    assert exc.value.code == 2
    assert prefix.with_suffix(".md").read_text() == "my work"
    assert not prefix.with_suffix(".json").exists()


def test_duplicate_json_keys_fail(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"approval":"proposed", "approval":"approved"}')
    with pytest.raises(ValueError, match="Duplicate"):
        cli._load_json(path)


@pytest.mark.parametrize("extra", [
    ["--import-ai-review", "results.json"], ["--approve-review", "id", "--output-mapping", "out.json"],
    ["--dry-run"], ["--review-scope", "all"], ["--review-packet", "packet.json"],
    ["--migrate-proposal", "old.json", "--mapping-file", "registry.json", "--dry-run"],
])
def test_invalid_mode_arguments_fail_before_loading_directory(extra):
    with pytest.raises(SystemExit) as exc:
        cli.main(["-i", "absent.xlsx", *extra], directory_factory=lambda **kw: pytest.fail("Directory accessed"))
    assert exc.value.code == 2


def test_packet_write_failure_removes_only_new_files(tmp_path, monkeypatch):
    first, second = tmp_path / "first.json", tmp_path / "second.md"
    original = Path.open

    def failing(path, *args, **kwargs):
        if path == second:
            raise OSError("simulated failure")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", failing)
    with pytest.raises(OSError):
        cli._write_new_texts([(first, "{}"), (second, "text")])
    assert not first.exists()
    assert not second.exists()


def test_real_workbook_export_uses_consolidated_helpers(tmp_path, capsys):
    from openpyxl import Workbook, load_workbook

    source = tmp_path / "membership.xlsx"
    output = tmp_path / "matched.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Members"
    sheet.append(["Organisation ID", "Name", "Acronym", "Country",
                  "Membership Type", "Membership Status"])
    sheet.append(["001", "Institute Alpha", "IA", "Belgium", "Member", "Active"])
    workbook.save(source)
    workbook.close()
    original_bytes = source.read_bytes()

    assert cli.main(["-i", str(source), "-X", str(output)],
                    directory_factory=DirectoryFake) == 0

    assert source.read_bytes() == original_bytes
    written = load_workbook(output)
    try:
        assert written.sheetnames == ["Matched institutions", "Members"]
        assert list(written.worksheets[0].values)[1] == (
            "001", "Institute Alpha", "Institute Alpha", "B1")
        assert written["Members"]["G1"].value == "Node Contributor"
        assert written["Members"]["G2"].value == cli.CONTRIBUTOR_TAG
    finally:
        written.close()
    assert "EOSC-A Members: 1" in capsys.readouterr().out


def test_help_does_not_import_workbook_directory_or_retired_helpers(tmp_path):
    code = f"""
import builtins
import runpy
import sys

sys.path.insert(0, {str(ROOT)!r})
original_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if name.split(".")[0] in {{
        "openpyxl", "directory", "eosc_membership_xlsx", "eosc_organisation_matching"
    }}:
        raise AssertionError("Unexpected eager or retired import: " + name)
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import
sys.argv = [{str(ROOT / "eosc-organisation-matcher.py")!r}, "--help"]
runpy.run_path(sys.argv[0], run_name="__main__")
"""
    result = subprocess.run([sys.executable, "-c", code], cwd=tmp_path,
                            text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "--prepare-ai-review" in result.stdout
