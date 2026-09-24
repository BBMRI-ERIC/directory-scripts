"""Tests for the Node biobank statistics exporter policy core."""
import importlib.util
import io
import logging
from pathlib import Path
import sys

from openpyxl import load_workbook
import pytest

def _module():
    """Load the Node-statistics exporter module for unit tests.

    Returns:
        Imported exporter-nn-biobank-stats.py module, registered as nn_stats in sys.modules.
    """
    path = Path(__file__).parents[1] / "exporter-nn-biobank-stats.py"
    spec = importlib.util.spec_from_file_location("nn_stats", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

def test_policy_has_only_initial_supported_mappings():
    """Verify policy has only initial supported mappings.

    Returns:
        None. Verifies policy has only initial supported mappings.
    """
    module = _module()
    assert module.POLICY_VERSION
    assert {rule.name for rule in module.CATEGORY_POLICY if rule.types} == {"hospital-integrated", "population-based"}

def test_frontier_prunes_mapped_parent_and_tie_uses_row_priority():
    """Verify frontier prunes mapped parent and tie uses row priority.

    Returns:
        None. Verifies frontier prunes mapped parent and tie uses row priority.
    """
    module = _module()
    result = module.classify_biobank_collections([
        {"id": "hospital", "type": {"id": "HOSPITAL"}},
        {"id": "population", "type": {"id": "POPULATION_BASED"}},
        {"id": "child", "parent_collection": {"id": "hospital"}, "type": {"id": "POPULATION_BASED"}},
    ])
    assert result.category == "hospital-integrated"
    assert result.votes == {"hospital-integrated": 1, "population-based": 1}
    assert result.tie and result.mixed
    assert result.fallback_reason is None


def test_classifier_accepts_string_list_collection_types():
    """Verify classifier accepts string list collection types.

    Returns:
        None. Verifies classifier accepts string list collection types.
    """
    module = _module()

    result = module.classify_biobank_collections([
        {"id": "hospital", "type": ["HOSPITAL"]},
    ])

    assert result.category == "hospital-integrated"
    assert result.votes == {"hospital-integrated": 1}


@pytest.mark.parametrize("cycle_length", [1, 2, 3])
def test_rootless_cycle_forces_provisional_others_fallback(cycle_length):
    """Verify rootless cycle forces provisional others fallback.

    Args:
        cycle_length: Number of nodes in the rootless collection hierarchy cycle.

    Returns:
        None. Verifies rootless cycle forces provisional others fallback.
    """
    module = _module()

    result = module.classify_biobank_collections([
        {"id": "hospital", "type": {"id": "HOSPITAL"}},
        *[{
            "id": f"cycle-{index}",
            "parent_collection": {"id": f"cycle-{(index + 1) % cycle_length}"},
            "type": {"id": "POPULATION_BASED"},
        } for index in range(cycle_length)],
    ])

    assert result.category == "others"
    assert result.provisional is True
    assert result.fallback_reason == "collection hierarchy cycle detected at 'cycle-0'"


@pytest.mark.parametrize(
    ("collections", "expected_reason", "provisional"),
    [
        ([], "no active collections", False),
        ([{"id": "untyped"}], "no supported category votes", False),
        (
            [{"id": "child", "parent_collection": {"id": "missing"}}],
            "parent collection 'missing' is absent from biobank collection set",
            True,
        ),
    ],
)
def test_others_fallbacks_explain_their_reason(collections, expected_reason, provisional):
    """Verify others fallbacks explain their reason.

    Args:
        collections: Synthetic collection records used to assert the reported fallback reason.
        expected_reason: Exact fallback_reason string expected for the collection votes, not the displayed category.
        provisional: Expected provisional flag for the fallback classification.

    Returns:
        None. Verifies others fallbacks explain their reason.
    """
    module = _module()

    result = module.classify_biobank_collections(collections)

    assert result.category == "others"
    assert result.fallback_reason == expected_reason
    assert result.provisional is provisional


def test_provisional_warning_contains_specific_hierarchy_reason(caplog):
    """Verify provisional warning contains specific hierarchy reason.

    Args:
        caplog: Pytest log-capture fixture used to inspect emitted log records.

    Returns:
        None. Verifies provisional warning contains specific hierarchy reason.
    """
    module = _module()

    class Directory:
        """Provide directory used to isolate the tested behavior.
        """
        def getSchema(self):
            """Return schema string selected for the fake Directory session.

            Returns:
                The schema string selected for the fake Directory session.
            """
            return "TEST"
        def getNegotiatorCoverage(self):
            """Return fixture Negotiator coverage classification mapping.

            Returns:
                The fixture Negotiator coverage classification mapping.
            """
            return {"bb": type("Coverage", (), {"status": "fully"})()}
        def getBiobanks(self):
            """Return synthetic biobank records available to the code under test.

            Returns:
                The synthetic biobank records available to the code under test.
            """
            return [{"id": "bb"}]
        def getBiobankNN(self, _):
            """Return fixture national-node code for the requested biobank.

            Args:
                _: Biobank identifier whose fixture national-node code this stub returns.

            Returns:
                The fixture national-node code for the requested biobank.
            """
            return "CZ"
        def getCollections(self):
            """Return synthetic collection records available to the code under test.

            Returns:
                The synthetic collection records available to the code under test.
            """
            return [{
                "id": "cycle-0",
                "biobank": {"id": "bb"},
                "parent_collection": {"id": "cycle-0"},
            }]
        def getBiobankServices(self, _):
            """Return fixture services associated with the requested biobank.

            Args:
                _: Ignored caller value; this fixture always represents a biobank without services.

            Returns:
                The fixture services associated with the requested biobank.
            """
            return []
        def getBiobankQualityInfo(self):
            """Return fixture biobank-quality DataFrame used by the exporter.

            Returns:
                The fixture biobank-quality DataFrame used by the exporter.
            """
            return __import__("pandas").DataFrame()
        def getCollectionQualityInfo(self):
            """Return fixture collection-quality DataFrame used by the exporter.

            Returns:
                The fixture collection-quality DataFrame used by the exporter.
            """
            return __import__("pandas").DataFrame()

    caplog.set_level(logging.WARNING)
    module.build_report_model(Directory())

    assert "collection hierarchy cycle detected at 'cycle-0'" in caplog.text


def test_report_model_keeps_federated_platform_unavailable():
    """Verify report model keeps federated platform unavailable.

    Returns:
        None. Verifies report model keeps federated platform unavailable.
    """
    module = _module()

    class Directory:
        """Provide directory used to isolate the tested behavior.
        """
        def getSchema(self):
            """Return schema string selected for the fake Directory session.

            Returns:
                The schema string selected for the fake Directory session.
            """
            return "TEST"
        def getNegotiatorCoverage(self):
            """Return fixture Negotiator coverage classification mapping.

            Returns:
                The fixture Negotiator coverage classification mapping.
            """
            return {"bb": type("Coverage", (), {"status": "fully"})()}
        def getBiobanks(self):
            """Return synthetic biobank records available to the code under test.

            Returns:
                The synthetic biobank records available to the code under test.
            """
            return [{"id": "bb"}]
        def getBiobankNN(self, _):
            """Return fixture national-node code for the requested biobank.

            Args:
                _: Biobank identifier whose fixture national-node code this stub returns.

            Returns:
                The fixture national-node code for the requested biobank.
            """
            return "CZ"
        def getCollections(self):
            """Return synthetic collection records available to the code under test.

            Returns:
                The synthetic collection records available to the code under test.
            """
            return [{"id": "c", "biobank": {"id": "bb"}, "type": {"id": "HOSPITAL"}}]
        def getBiobankServices(self, _):
            """Return fixture services associated with the requested biobank.

            Args:
                _: Ignored caller value; this fixture always represents a biobank without services.

            Returns:
                The fixture services associated with the requested biobank.
            """
            return []
        def getBiobankQualityInfo(self):
            """Return fixture biobank-quality DataFrame used by the exporter.

            Returns:
                The fixture biobank-quality DataFrame used by the exporter.
            """
            return __import__("pandas").DataFrame()
        def getCollectionQualityInfo(self):
            """Return fixture collection-quality DataFrame used by the exporter.

            Returns:
                The fixture collection-quality DataFrame used by the exporter.
            """
            return __import__("pandas").DataFrame()

    model = module.build_report_model(Directory())
    assert model["federated_platform"].available is False
    assert model["nodes"]["CZ"]["hospital-integrated"]["negotiator_fully"] == 1


def test_report_model_initializes_empty_supported_categories_to_zero():
    """Verify report model initializes empty supported categories to zero.

    Returns:
        None. Verifies report model initializes empty supported categories to zero.
    """
    module = _module()

    class Directory:
        """Provide directory used to isolate the tested behavior.
        """
        skip_graph_dag_validation = False

        def getSchema(self):
            """Return schema string selected for the fake Directory session.

            Returns:
                The schema string selected for the fake Directory session.
            """
            return "TEST"
        def getNegotiatorCoverage(self):
            """Return fixture Negotiator coverage classification mapping.

            Returns:
                The fixture Negotiator coverage classification mapping.
            """
            return {"bb": type("Coverage", (), {"status": "fully"})()}
        def getBiobanks(self):
            """Return synthetic biobank records available to the code under test.

            Returns:
                The synthetic biobank records available to the code under test.
            """
            return [{"id": "bb"}]
        def getBiobankNN(self, _):
            """Return fixture national-node code for the requested biobank.

            Args:
                _: Biobank identifier whose fixture national-node code this stub returns.

            Returns:
                The fixture national-node code for the requested biobank.
            """
            return "CZ"
        def getCollections(self):
            """Return synthetic collection records available to the code under test.

            Returns:
                The synthetic collection records available to the code under test.
            """
            return [{"id": "c", "biobank": {"id": "bb"}, "type": {"id": "HOSPITAL"}}]
        def getBiobankServices(self, _):
            """Return fixture services associated with the requested biobank.

            Args:
                _: Ignored caller value; this fixture always represents a biobank without services.

            Returns:
                The fixture services associated with the requested biobank.
            """
            return []
        def getBiobankQualityInfo(self):
            """Return fixture biobank-quality DataFrame used by the exporter.

            Returns:
                The fixture biobank-quality DataFrame used by the exporter.
            """
            return __import__("pandas").DataFrame(columns=["biobank", "assess_level_bio"])
        def getCollectionQualityInfo(self):
            """Return fixture collection-quality DataFrame used by the exporter.

            Returns:
                The fixture collection-quality DataFrame used by the exporter.
            """
            return __import__("pandas").DataFrame(columns=["collection", "assess_level_col"])

    model = module.build_report_model(Directory())

    assert set(module.ROWS).issubset(model["nodes"]["CZ"])
    assert model["nodes"]["CZ"]["population-based"] == {
        metric: 0 for metric in module.METRICS
    }
    assert model["nodes"]["CZ"]["others"] == {
        metric: 0 for metric in module.METRICS
    }
    for for_xlsx in (False, True):
        rendered = module._node_table_values(model, "CZ", for_xlsx=for_xlsx)
        population = next(row for row in rendered if row[0] == "population-based")
        assert population[1:3] == [0, 0]
        assert population[3] == (None if for_xlsx else "N/A")
        assert population[4:] == [0] * 7
    assert model["metadata"] == {
        "Directory schema": "TEST",
        "Emergency DAG checks skipped": False,
    }


def test_report_metadata_records_real_emergency_state():
    """Verify report metadata records real emergency state.

    Returns:
        None. Verifies report metadata records real emergency state.
    """
    module = _module()

    class Directory:
        """Provide directory used to isolate the tested behavior.
        """
        skip_graph_dag_validation = True

        def getSchema(self):
            """Return schema string selected for the fake Directory session.

            Returns:
                The schema string selected for the fake Directory session.
            """
            return "STAGING"
        def getNegotiatorCoverage(self):
            """Return fixture Negotiator coverage classification mapping.

            Returns:
                The fixture Negotiator coverage classification mapping.
            """
            return {}
        def getBiobanks(self):
            """Return synthetic biobank records available to the code under test.

            Returns:
                The synthetic biobank records available to the code under test.
            """
            return []
        def getCollections(self):
            """Return synthetic collection records available to the code under test.

            Returns:
                The synthetic collection records available to the code under test.
            """
            return []
        def getBiobankQualityInfo(self):
            """Return fixture biobank-quality DataFrame used by the exporter.

            Returns:
                The fixture biobank-quality DataFrame used by the exporter.
            """
            return __import__("pandas").DataFrame()
        def getCollectionQualityInfo(self):
            """Return fixture collection-quality DataFrame used by the exporter.

            Returns:
                The fixture collection-quality DataFrame used by the exporter.
            """
            return __import__("pandas").DataFrame()

    model = module.build_report_model(Directory())

    assert model["metadata"] == {
        "Directory schema": "STAGING",
        "Emergency DAG checks skipped": True,
    }


def test_missing_quality_tables_are_unavailable_not_zero():
    """Verify missing quality tables are unavailable not zero.

    Returns:
        None. Verifies missing quality tables are unavailable not zero.
    """
    module = _module()

    class Directory:
        """Provide directory used to isolate the tested behavior.
        """
        def getSchema(self):
            """Return schema string selected for the fake Directory session.

            Returns:
                The schema string selected for the fake Directory session.
            """
            return "TEST"
        def getNegotiatorCoverage(self):
            """Return fixture Negotiator coverage classification mapping.

            Returns:
                The fixture Negotiator coverage classification mapping.
            """
            return {"bb": type("Coverage", (), {"status": "fully"})()}
        def getBiobanks(self):
            """Return synthetic biobank records available to the code under test.

            Returns:
                The synthetic biobank records available to the code under test.
            """
            return [{"id": "bb"}]
        def getBiobankNN(self, _):
            """Return fixture national-node code for the requested biobank.

            Args:
                _: Biobank identifier whose fixture national-node code this stub returns.

            Returns:
                The fixture national-node code for the requested biobank.
            """
            return "CZ"
        def getCollections(self):
            """Return synthetic collection records available to the code under test.

            Returns:
                The synthetic collection records available to the code under test.
            """
            return [{"id": "c", "biobank": {"id": "bb"}, "type": {"id": "HOSPITAL"}}]
        def getBiobankServices(self, _):
            """Return fixture services associated with the requested biobank.

            Args:
                _: Ignored caller value; this fixture always represents a biobank without services.

            Returns:
                The fixture services associated with the requested biobank.
            """
            return []
        def getBiobankQualityInfo(self):
            """Return fixture biobank-quality DataFrame used by the exporter.

            Returns:
                The fixture biobank-quality DataFrame used by the exporter.
            """
            return __import__("pandas").DataFrame()
        def getCollectionQualityInfo(self):
            """Return fixture collection-quality DataFrame used by the exporter.

            Returns:
                The fixture collection-quality DataFrame used by the exporter.
            """
            return __import__("pandas").DataFrame()

    model = module.build_report_model(Directory())

    assert model["quality_sources"]["q_org_"].available is False
    assert model["quality_sources"]["q_collection_"].available is False
    assert module._node_table_values(model, "CZ", for_xlsx=False)[0][7:] == ["N/A"] * 4
    assert module._node_table_values(model, "CZ", for_xlsx=True)[0][7:] == [None] * 4


def test_empty_quality_tables_with_required_columns_remain_numeric_zero():
    """Verify empty quality tables with required columns remain numeric zero.

    Returns:
        None. Verifies empty quality tables with required columns remain numeric zero.
    """
    module = _module()

    class Directory:
        """Provide directory used to isolate the tested behavior.
        """
        def getSchema(self):
            """Return schema string selected for the fake Directory session.

            Returns:
                The schema string selected for the fake Directory session.
            """
            return "TEST"
        def getNegotiatorCoverage(self):
            """Return fixture Negotiator coverage classification mapping.

            Returns:
                The fixture Negotiator coverage classification mapping.
            """
            return {"bb": type("Coverage", (), {"status": "fully"})()}
        def getBiobanks(self):
            """Return synthetic biobank records available to the code under test.

            Returns:
                The synthetic biobank records available to the code under test.
            """
            return [{"id": "bb"}]
        def getBiobankNN(self, _):
            """Return fixture national-node code for the requested biobank.

            Args:
                _: Biobank identifier whose fixture national-node code this stub returns.

            Returns:
                The fixture national-node code for the requested biobank.
            """
            return "CZ"
        def getCollections(self):
            """Return synthetic collection records available to the code under test.

            Returns:
                The synthetic collection records available to the code under test.
            """
            return [{"id": "c", "biobank": {"id": "bb"}, "type": {"id": "HOSPITAL"}}]
        def getBiobankServices(self, _):
            """Return fixture services associated with the requested biobank.

            Args:
                _: Ignored caller value; this fixture always represents a biobank without services.

            Returns:
                The fixture services associated with the requested biobank.
            """
            return []
        def getBiobankQualityInfo(self):
            """Return fixture biobank-quality DataFrame used by the exporter.

            Returns:
                The fixture biobank-quality DataFrame used by the exporter.
            """
            return __import__("pandas").DataFrame(columns=["biobank", "assess_level_bio"])
        def getCollectionQualityInfo(self):
            """Return fixture collection-quality DataFrame used by the exporter.

            Returns:
                The fixture collection-quality DataFrame used by the exporter.
            """
            return __import__("pandas").DataFrame(columns=["collection", "assess_level_col"])

    model = module.build_report_model(Directory())

    assert model["quality_sources"]["q_org_"].available is True
    assert model["quality_sources"]["q_collection_"].available is True
    assert module._node_table_values(model, "CZ", for_xlsx=False)[0][7:] == [0] * 4
    assert module._node_table_values(model, "CZ", for_xlsx=True)[0][7:] == [0] * 4


def test_stdout_marks_unavailable_federated_platform():
    """Verify stdout marks unavailable federated platform.

    Returns:
        None. Verifies stdout marks unavailable federated platform.
    """
    module = _module()
    model = {"nodes": {"EXT": {"total biobanks": {metric: 0 for metric in module.METRICS}}}, "problems": {"EXT": ["bb"]}}
    buffer = io.StringIO()
    module.render_stdout(model, buffer)
    assert "Node EXT" in buffer.getvalue()
    assert "N/A" in buffer.getvalue()


def _model(module, nodes=("AT", "EXT")):
    """Create a complete report fixture with zero and unavailable values.

    Args:
        module: Loaded module whose source or behavior is inspected by the helper.
        nodes: Directory-node fixture used to build the statistics model.

    Returns:
        Report dictionary with independent per-node row metrics, unavailable FP status, problem IDs, and ERIC provenance.
    """
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
    """Verify stdout is alphabetical aligned and distinguishes unavailable values.

    Returns:
        None. Verifies stdout is alphabetical aligned and distinguishes unavailable values.
    """
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
    """Verify xlsx has grouped headers blanks and metadata.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies xlsx has grouped headers blanks and metadata.
    """
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
    """Verify xlsx sanitizes long node names and rejects collisions.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies xlsx sanitizes long node names and rejects collisions.
    """
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

    assert module._safe_sheet_name("'Quoted'") == "Quoted"
    assert not module._safe_sheet_name("a" * 30 + "'rest").endswith("'")
    with pytest.raises(ValueError, match="collision"):
        module.write_xlsx_report(_model(module, ("Node", "node")), collision)
    assert collision.read_text(encoding="utf-8") == "keep"


def test_parser_and_main_use_shared_cli_contract(tmp_path, monkeypatch, caplog):
    """Verify parser and main use shared cli contract.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.
        caplog: Pytest log-capture fixture used to inspect emitted log records.

    Returns:
        None. Verifies parser and main use shared cli contract.
    """
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
        """Record Directory constructor options and raw representative-loader calls.
        """
        def __init__(self, **kwargs):
            """Intercept Directory construction without loading remote entities.

            Args:
                **kwargs: Directory constructor options observed by this CLI-routing double; no remote data is loaded.
            """
            calls.append(("directory", kwargs))

        def loadNegotiatorRepresentatives(self, path):
            """Record representative-XLSX loading on the Directory double.

            Args:
                path: Raw representative XLSX argument; this double performs no file I/O.

            Returns:
                None. Record representative-XLSX loading on the Directory double.
            """
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
    assert any(
        record.levelno == logging.WARNING
        and "Node AT has 1 active biobank(s) without collections or services." in record.message
        for record in caplog.records
    )

    caplog.clear()
    caplog.set_level(logging.INFO, logger=module.__name__)
    module.main(["representatives.xlsx", "-N", "-v"], FakeDirectory)
    assert any("AT-problem" in record.message for record in caplog.records)


@pytest.mark.parametrize(
    ("source_args", "expected_call"),
    [
        (
            ["--negotiator-representatives-xlsx", "representatives.xlsx"],
            ("representatives", "representatives.xlsx"),
        ),
        (
            ["--negotiator-orphans-xlsx", "orphans.xlsx"],
            ("orphans", "orphans.xlsx"),
        ),
    ],
)
def test_main_selects_explicit_negotiator_xlsx_source(
    source_args, expected_call, monkeypatch
):
    """Verify main selects explicit negotiator xlsx source.

    Args:
        source_args: Negotiator-source arguments supplied to the CLI invocation.
        expected_call: Expected (loader kind, workbook path) entry in the Directory call log.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. Verifies main selects explicit negotiator xlsx source.
    """
    module = _module()
    calls = []

    class FakeDirectory:
        """Record which raw/orphan Negotiator loader is selected by the explicit CLI source option.
        """
        def __init__(self, **kwargs):
            """Intercept Directory construction without loading remote entities.

            Args:
                **kwargs: Directory constructor options observed by this CLI-routing double; no remote data is loaded.
            """
            calls.append(("directory", kwargs))

        def loadNegotiatorRepresentatives(self, path):
            """Record representative-XLSX loading on the Directory double.

            Args:
                path: Raw representative XLSX argument; this double performs no file I/O.

            Returns:
                None. Record representative-XLSX loading on the Directory double.
            """
            calls.append(("representatives", path))

        def loadNegotiatorOrphansReport(self, path):
            """Record orphan-report loading on the Directory double.

            Args:
                path: Orphan-export XLSX argument logged for source-routing assertions; not opened.

            Returns:
                None. Record orphan-report loading on the Directory double.
            """
            calls.append(("orphans", path))

    monkeypatch.setattr(
        module, "build_report_model", lambda directory: _model(module, ("AT",))
    )

    module.main([*source_args, "-N"], FakeDirectory)

    assert calls[1] == expected_call


@pytest.mark.parametrize(
    "source_args",
    [
        [],
        ["legacy.xlsx", "--negotiator-orphans-xlsx", "orphans.xlsx"],
        [
            "--negotiator-representatives-xlsx", "representatives.xlsx",
            "--negotiator-orphans-xlsx", "orphans.xlsx",
        ],
    ],
)
def test_main_requires_exactly_one_negotiator_source(source_args, capsys):
    """Verify main requires exactly one negotiator source.

    Args:
        source_args: Negotiator-source arguments supplied to the CLI invocation.
        capsys: Pytest capture fixture used to inspect process output.

    Returns:
        None. Verifies main requires exactly one negotiator source.
    """
    module = _module()

    with pytest.raises(SystemExit):
        module.main([*source_args, "-N"])

    assert "exactly one Negotiator registration source" in capsys.readouterr().err


def test_main_rejects_reserved_negotiator_api_before_directory_loading(capsys):
    """Verify main rejects reserved negotiator api before directory loading.

    Args:
        capsys: Pytest capture fixture used to inspect process output.

    Returns:
        None. Verifies main rejects reserved negotiator api before directory loading.
    """
    module = _module()
    constructed = False

    class FakeDirectory:
        """Record whether Directory construction occurred before rejecting unavailable API mode.
        """
        def __init__(self, **kwargs):
            """Intercept Directory construction without loading remote entities.

            Args:
                **kwargs: Directory constructor options observed by this CLI-routing double; no remote data is loaded.
            """
            nonlocal constructed
            constructed = True

    with pytest.raises(SystemExit):
        module.main(["--negotiator-api", "-N"], FakeDirectory)

    assert constructed is False
    assert "not implemented" in capsys.readouterr().err


def test_main_does_not_publish_xlsx_after_loader_failure(tmp_path):
    """Verify main does not publish xlsx after loader failure.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies main does not publish xlsx after loader failure.
    """
    module = _module()
    output = tmp_path / "must-not-exist.xlsx"

    class FailingDirectory:
        """Provide failing directory used to isolate the tested behavior.
        """
        def __init__(self, **kwargs):
            """Intercept Directory construction without loading remote entities.

            Args:
                **kwargs: Directory constructor options observed by this CLI-routing double; no remote data is loaded.
            """
            pass

        def loadNegotiatorRepresentatives(self, path):
            """Record representative-XLSX loading on the Directory double.

            Args:
                path: Raw representative XLSX argument; this double performs no file I/O.

            Returns:
                None. Record representative-XLSX loading on the Directory double.
            """
            raise ValueError("Malformed Negotiator workbook")

    with pytest.raises(ValueError, match="Malformed Negotiator workbook"):
        module.main(["broken.xlsx", "-X", str(output), "-N"], FailingDirectory)
    assert not output.exists()
