"""Test participation bundle bindings, identity scope and publication safety."""

import importlib.util
import json
from pathlib import Path

import pytest

from test_survey_participation import sources, inventory


def test_exported_bundle_is_frozen_and_transactional(tmp_path):
    """Write canonical counts and preserve an existing export without overwrite.

    Args:
        tmp_path: Isolated output directory protecting local reports.

    Returns:
        None. Manifest binds counts and inventory, and no R is invoked.
    """
    from survey_participation import collect_participation
    from survey_map_assets import write_map_bundle, validate_map_assets
    data = collect_participation(*sources())
    output = tmp_path / "maps"
    write_map_bundle(data, inventory(), output, kind="mucp", layouts="both")
    manifest = json.loads((output / "input-manifest.json").read_text())
    assert manifest["kind"] == "mucp"
    assert manifest["counts"]["countries"][0]["shared_count"] == 1
    assert validate_map_assets(data, output, expected_kind="mucp").state == "empty"
    with pytest.raises(ValueError, match="exists"):
        write_map_bundle(data, inventory(), output, kind="mucp", layouts="both")
    assert json.loads((output / "input-manifest.json").read_text()) == manifest


def test_prepared_bytes_and_inventory_are_validated(tmp_path):
    """Reject tampered or inconsistent source files before embedding any map.

    Args:
        tmp_path: Per-test map bundle directory.

    Returns:
        None. A changed counts file cannot be mistaken for merely unrendered assets.
    """
    from survey_participation import collect_participation
    from survey_map_assets import write_map_bundle, validate_map_assets, validate_inventory
    data = collect_participation(sources()[0])
    output = tmp_path / "maps"
    write_map_bundle(data, inventory(), output, kind="so2", layouts="bbmri-members")
    (output / "country-counts.csv").write_text("changed")
    with pytest.raises(ValueError, match="hash|changed"):
        validate_map_assets(data, output, expected_kind="so2")
    frozen = inventory()
    frozen["biobanks"].append(frozen["biobanks"][0])
    with pytest.raises(ValueError):
        validate_inventory(frozen)


def test_new_peers_and_offline_map_arguments():
    """Keep map preparation as peer commands with standard withdrawal options.

    Returns:
        None. Both report kinds parse without calling a Directory or R process.
    """
    spec = importlib.util.spec_from_file_location("map_cli", Path(__file__).parents[1] / "survey-so2-directory.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parser = module.build_cli()
    for command in ("export-so2-map-r", "export-mucp-map-r"):
        tokens = [command, "-i", "source.json", "--output-dir", "maps", "--map-layout", "oec", "-w"]
        if command == "export-mucp-map-r":
            tokens += ["--so2-json", "so2.json"]
        args = parser.parse_args(tokens)
        assert args.include_withdrawn and args.map_layout == "oec"


def test_inventory_export_does_not_connect_when_frozen(tmp_path):
    """Use frozen inventory without constructing Directory or modifying inputs.

    Args:
        tmp_path: Isolated payloads, inventory and destination bundle.

    Returns:
        None. The source report and inventory survive a failed collision request.
    """
    from survey_map_assets import export_map_inputs
    so2, _ = sources()
    source = tmp_path / "source.json"
    source.write_text(json.dumps(so2))
    frozen = tmp_path / "inventory.json"
    frozen.write_text(json.dumps(inventory()))
    from types import SimpleNamespace
    args = SimpleNamespace(input_json=str(source), directory_inventory=str(frozen), output_dir=str(tmp_path / "maps"),
        map_layout="both", participation_identities=None, overwrite=False, command="export-so2-map-r",
        directory_target=None, schema="ERIC", include_withdrawn=False, only_withdrawn=False)

    def forbidden(_args):
        """Reject unintended network-backed Directory construction.

        Args:
            _args: Parser options that must not be used in frozen-inventory mode.

        Returns:
            None; this sentinel always raises.
        """
        raise AssertionError("Directory must not be opened")

    export_map_inputs(args, forbidden)
    assert source.exists() and frozen.exists()
    args.output_dir = str(tmp_path)
    args.overwrite = True
    with pytest.raises(ValueError, match="overlap"):
        export_map_inputs(args, forbidden)


def test_real_merge_provenance_feeds_mucp_map_preparation(tmp_path):
    """Exercise actual survey producers rather than invented provenance field names.

    Args:
        tmp_path: Isolated synthetic XLSX/MuCP sources, reports and map bundle.

    Returns:
        None. Real merge output and descriptive parsing yield a replayable map roster.
    """
    import so2_descriptive_report as descriptive
    from so2_response_merging import merge_descriptive_responses
    from survey_combined import execute_merge
    from survey_map_assets import write_map_bundle
    from survey_map_report import load_report_map_assets
    from survey_participation import collect_participation, directory_inventory
    from test_survey_merge_mucp_integration import fixture_arguments, directory_factory, FakeDirectory

    args = fixture_arguments(tmp_path)
    combined = execute_merge(args, directory_factory)
    schema = descriptive.load_descriptive_schema(args.descriptive_schema)
    form = descriptive.load_form_manifest_structure(args.form_json)
    workbook = descriptive.read_descriptive_workbook(args.survey_file, schema)
    questions = descriptive.validate_descriptive_schema(schema,
        [c for c in workbook.responses.columns if c != schema["output"]["source_row_column"]])
    workbook, summary = merge_descriptive_responses(workbook, schema, questions,
        {"schema_version": 1, "reviewed_sources": {}, "country_overrides": {}})
    so2 = descriptive.build_descriptive_payload(workbook, schema, form)
    so2["responses_summary"] = summary
    roster = collect_participation(so2, combined)
    assert roster["inputs"] == {"so2": combined["inputs"]["so2_sha256"], "mucp": combined["inputs"]["mucp_sha256"]}
    folder = tmp_path / "maps"
    write_map_bundle(roster, directory_inventory(FakeDirectory()), folder, kind="mucp", so2_payload=so2)
    assert load_report_map_assets(combined, folder, "mucp").state == "empty"
