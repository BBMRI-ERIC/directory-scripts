"""Tests for the Node biobank statistics exporter policy core."""
import importlib.util
import io
import logging
from pathlib import Path
import sys

from openpyxl import load_workbook
import pytest

def _module():
    path = Path(__file__).parents[1] / "exporter-nn-biobank-stats.py"
    spec = importlib.util.spec_from_file_location("nn_stats", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

def test_policy_has_only_initial_supported_mappings():
    module = _module()
    assert module.POLICY_VERSION
    assert {rule.name for rule in module.CATEGORY_POLICY if rule.types} == {"hospital-integrated", "population-based"}

def test_frontier_prunes_mapped_parent_and_tie_uses_row_priority():
    module = _module()
    result = module.classify_biobank_collections([
        {"id": "hospital", "type": {"id": "HOSPITAL"}},
        {"id": "population", "type": {"id": "POPULATION_BASED"}},
        {"id": "child", "parent_collection": {"id": "hospital"}, "type": {"id": "POPULATION_BASED"}},
    ])
    assert result.category == "hospital-integrated"
    assert result.votes == {"hospital-integrated": 1, "population-based": 1}
    assert result.tie and result.mixed


def test_report_model_keeps_federated_platform_unavailable():
    module = _module()

    class Directory:
        def getNegotiatorCoverage(self):
            return {"bb": type("Coverage", (), {"status": "fully"})()}
        def getBiobanks(self): return [{"id": "bb"}]
        def getBiobankNN(self, _): return "CZ"
        def getCollections(self): return [{"id": "c", "biobank": {"id": "bb"}, "type": {"id": "HOSPITAL"}}]
        def getBiobankServices(self, _): return []
        def getBiobankQualityInfo(self): return __import__("pandas").DataFrame()
        def getCollectionQualityInfo(self): return __import__("pandas").DataFrame()

    model = module.build_report_model(Directory())
    assert model["federated_platform"].available is False
    assert model["nodes"]["CZ"]["hospital-integrated"]["negotiator_fully"] == 1


def test_stdout_marks_unavailable_federated_platform():
    module = _module()
    model = {"nodes": {"EXT": {"total biobanks": {metric: 0 for metric in module.METRICS}}}, "problems": {"EXT": ["bb"]}}
    buffer = io.StringIO()
    module.render_stdout(model, buffer)
    assert "Node EXT" in buffer.getvalue()
    assert "N/A" in buffer.getvalue()


def _model(module, nodes=("AT", "EXT")):
    """Create a complete report fixture with zero and unavailable values."""
    metrics = {
        metric: 0
        for metric in module.METRICS
    }
    node_rows = {
        row: dict(metrics)
        for row in module.ROWS
    }
    node_rows["total biobanks"].update(
        total_biobanks=2,
        directory_biobanks=2,
        negotiator_fully=1,
        q_org_eric=1,
        q_collection_accredited=1,
    )
    node_rows["hospital-integrated"].update(
        total_biobanks=1,
        directory_biobanks=1,
        negotiator_fully=1,
    )
    return {
        "nodes": {node: {row: dict(values) for row, values in node_rows.items()} for node in nodes},
        "federated_platform": module.SourceResult(False, "Locator/Finder inventory API unavailable"),
        "problems": {node: [f"{node}-problem"] for node in nodes},
        "metadata": {
            "Directory schema": "ERIC",
            "Emergency DAG checks skipped": False,
        },
    }


def test_stdout_is_alphabetical_aligned_and_distinguishes_unavailable_values():
    module = _module()
    buffer = io.StringIO()

    module.render_stdout(_model(module), buffer)

    text = buffer.getvalue()
    assert text.index("Node AT") < text.index("Node EXT")
    assert "N/A" in text
    assert " 0" in text
    assert "Biobanks without collections or services: 1" in text
    assert "AT-problem" not in text
    at_lines = text.split("Node EXT", 1)[0].splitlines()
    table_lines = [line for line in at_lines if "|" in line]
    assert len({len(line) for line in table_lines}) == 1


def test_xlsx_has_grouped_headers_blanks_and_metadata(tmp_path):
    module = _module()
    output = tmp_path / "report.xlsx"

    module.write_xlsx_report(_model(module), output)

    workbook = load_workbook(output, data_only=True)
    assert workbook.sheetnames == ["AT", "EXT"]
    sheet = workbook["AT"]
    assert "B1:D1" in {str(range_) for range_ in sheet.merged_cells.ranges}
    assert sheet["B1"].value == "Biobanks"
    assert sheet["E1"].value == "Negotiator: biobanks"
    assert sheet["H1"].value == "Q-labels: organizations"
    assert sheet["J1"].value == "Q-labels: collections"
    assert [sheet.cell(row=row, column=1).value for row in range(3, 3 + len(module.ROWS))] == list(module.ROWS)
    assert sheet["D3"].value is None
    assert sheet["B6"].value is None
    assert sheet["B3"].value == 2
    assert sheet["E3"].value == 1
    assert sheet["F3"].value == 0
    values = [cell.value for row in sheet.iter_rows() for cell in row]
    assert "N/A" not in values
    assert "Problems: biobanks without collections or services" in values
    assert "Legend" in values
    assert "Directory schema" in values
    assert "ERIC" in values
    assert "Emergency DAG checks skipped" in values
    assert "unique biobanks" in values
    assert any(value and "unique collections" in str(value) for value in values)


def test_xlsx_sanitizes_long_node_names_and_rejects_collisions(tmp_path):
    module = _module()
    long_node = "Invalid/[Node] name with more than thirty-one characters"
    output = tmp_path / "safe.xlsx"

    module.write_xlsx_report(_model(module, (long_node,)), output)

    workbook = load_workbook(output, data_only=True)
    assert len(workbook.sheetnames[0]) <= 31
    assert all(character not in workbook.sheetnames[0] for character in "[]:*?/\\")

    collision = tmp_path / "collision.xlsx"
    collision.write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError, match="collision"):
        module.write_xlsx_report(_model(module, ("A/B", "A?B")), collision)
    assert collision.read_text(encoding="utf-8") == "keep"


def test_parser_and_main_use_shared_cli_contract(tmp_path, monkeypatch, caplog):
    module = _module()
    parser = module.build_argument_parser()
    args = parser.parse_args([
        "representatives.xlsx", "-X", "out.xlsx", "-N", "-v",
        "-P", "TEST", "-u", "user", "-p", "password", "-t", "token",
        "--purge-cache", "directory",
    ])
    assert args.schema == "TEST"
    assert args.nostdout is True
    assert args.verbose is True
    assert args.purgeCaches == ["directory"]
    assert args.outputXLSX == ["out.xlsx"]
    assert hasattr(args, "emergency_skip_dag_checks")

    calls = []

    class FakeDirectory:
        def __init__(self, **kwargs):
            calls.append(("directory", kwargs))

        def loadNegotiatorRepresentatives(self, path):
            calls.append(("load", path))

    monkeypatch.setattr(module, "build_report_model", lambda directory: _model(module, ("AT",)))
    output = tmp_path / "main.xlsx"
    module.main([
        "representatives.xlsx", "-X", str(output), "-N", "-P", "TEST",
        "-u", "user", "-p", "password", "-t", "token", "--purge-cache",
        "directory", "--emergency-skip-dag-checks",
    ], FakeDirectory)
    assert output.exists()
    assert calls[0][0] == "directory"
    assert calls[0][1]["schema"] == "TEST"
    assert calls[0][1]["purgeCaches"] == ["directory"]
    assert calls[0][1]["username"] == "user"
    assert calls[0][1]["password"] == "password"
    assert calls[0][1]["token"] == "token"
    assert calls[0][1]["skip_graph_dag_validation"] is True
    assert calls[1] == ("load", "representatives.xlsx")
    assert sum("Unsupported biobank categories" in record.message for record in caplog.records) == 1
    assert not any("AT-problem" in record.message for record in caplog.records)

    caplog.clear()
    caplog.set_level(logging.INFO, logger=module.__name__)
    module.main(["representatives.xlsx", "-N", "-v"], FakeDirectory)
    assert any("AT-problem" in record.message for record in caplog.records)


def test_main_does_not_publish_xlsx_after_loader_failure(tmp_path):
    module = _module()
    output = tmp_path / "must-not-exist.xlsx"

    class FailingDirectory:
        def __init__(self, **kwargs):
            pass

        def loadNegotiatorRepresentatives(self, path):
            raise ValueError("Malformed Negotiator workbook")

    with pytest.raises(ValueError, match="Malformed Negotiator workbook"):
        module.main(["broken.xlsx", "-X", str(output), "-N"], FailingDirectory)
    assert not output.exists()
