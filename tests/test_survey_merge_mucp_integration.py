"""End-to-end source-preserving combined survey CLI regressions using synthetic data."""

import importlib.util
from datetime import datetime
import json
from pathlib import Path

import openpyxl
import pytest

from survey_combined import execute_merge
from test_survey_mucp import _write_fixture


class FakeDirectory:
    """Read-only synthetic Directory catalogue for canonical identity integration.

    Attributes:
        biobanks: One eligible synthetic institution with its canonical Directory ID.
        contacts: Empty contact catalogue; matching uses explicit IDs or exact names.
    """

    biobanks = [{"id": "bbmri-eric:ID:ZZ_TEST", "name": "Synthetic institute", "country": "ZZ"}]
    contacts = []

    def getLoadedCollections(self):
        """Return the empty loaded collection catalogue.

        Returns:
            Empty list; the fixture has only submission-level identity evidence.
        """
        return []

    def getBiobanks(self):
        """Return eligible synthetic biobanks.

        Returns:
            One canonical institution permitted by the reporting scope.
        """
        return self.biobanks

    def getDirectoryUrl(self):
        """Return the synthetic Directory target for provenance.

        Returns:
            An invalid-domain URL that must never be contacted by the test.
        """
        return "https://directory.example.invalid"

    def getSchema(self):
        """Return the source schema name recorded in combined metadata.

        Returns:
            The public ERIC schema identifier.
        """
        return "ERIC"


def fixture_arguments(tmp_path):
    """Prepare genuine SO2 form mappings with tiny, entirely synthetic responses.

    Args:
        tmp_path: Isolated temporary directory for all source fixtures and target outputs.

    Returns:
        Parsed peer-command options covering three SO2 questions and one MuCP-only criterion.
    """
    spec = importlib.util.spec_from_file_location("merge_cli", "survey-so2-directory.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    schema = json.loads(Path("survey-mappings/so2_2025_descriptive_report.json").read_text())
    schema["questions"] = schema["questions"][:3]
    schema_path = tmp_path / "so2-schema.json"
    schema_path.write_text(json.dumps(schema))
    headers = (schema["columns"]["respondent_context"] + [q["column"] for q in schema["questions"]]
               + schema["columns"]["administrative_exclusions"])
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Content"
    sheet.append(["Alias", "SO2_2025"])
    sheet.append(["Export Date", datetime(2026, 10, 2)])
    sheet.append([])
    sheet.append(headers)
    values = {"Country": "ZZ", "Name of Institution": "Synthetic institute",
              "BiobankID in the Directory (if available)": "ZZ_TEST",
              schema["questions"][0]["column"]: schema["questions"][0]["categories"][0],
              schema["questions"][1]["column"]: "University;Other (please specify):",
              schema["questions"][2]["column"]: "Synthetic free text & qualification"}
    sheet.append([values.get(header) for header in headers])
    sheet.append([values.get(header) for header in headers])
    source_path = tmp_path / "so2.xlsx"
    workbook.save(source_path)
    mucp, mucp_schema, _ = _write_fixture(tmp_path)
    overrides = tmp_path / "overrides.json"
    overrides.write_text(json.dumps({"schema_version": "1", "decisions": [], "input_bindings": []}))
    crosswalk = tmp_path / "crosswalk.json"
    crosswalk.write_text(json.dumps({"schema_version": "1", "themes": []}))
    visualizations = tmp_path / "visualizations.json"
    visualizations.write_text(json.dumps({"schema_version": "1", "heatmaps": [], "upsets": []}))
    args = module.build_cli().parse_args(["merge-mucp", "-i", str(source_path),
        "--descriptive-schema", str(schema_path), "--form-json", "survey-mappings/so2_2025_form.json",
        "--mucp-json", str(mucp), "--mucp-schema", str(mucp_schema),
        "--match-overrides", str(overrides), "--crosswalk", str(crosswalk),
        "--visualization-registry", str(visualizations), "-o", str(tmp_path / "combined.json"),
        "--output-match-review", str(tmp_path / "review.md")])
    args.username = args.password = args.directory_token = None
    return args


def directory_factory(args):
    """Supply an offline catalogue without running any Directory request.

    Args:
        args: Parsed command options, intentionally unused by the synthetic source.

    Returns:
        A read-only catalogue with one canonical institution.
    """
    return FakeDirectory()


@pytest.mark.parametrize("record_type", ["submission", "country_summary"])
def test_scope_override_preserves_owned_evidence_and_original_provenance(tmp_path, record_type):
    """A reviewed collection split must remain usable through quantities and publication.

    Args:
        tmp_path: Temporary location for an entirely invented multi-scope response.
        record_type: Original submission or national summary whose one collection
            is explicitly assigned to a known biobank by the reviewed override.

    Returns:
        None. Only assigned collection evidence enters its biobank, with the original
        respondent ID retained separately from internal virtual record ownership.
    """
    from survey_identity import identity_fingerprint
    from survey_mucp import load_mucp_document
    args = fixture_arguments(tmp_path)
    source = Path(args.mucp_json)
    raw = json.loads(source.read_text())
    response = raw["responses"][0]
    response["record_type"] = record_type
    response["collections"] = [{"collection_id":"INVENTED-1", "name":"Invented scope", "scope":"collection",
                                "answers":response["answers"], "fields":{}}]
    source.write_text(json.dumps(raw))
    document = load_mucp_document(source,Path(args.mucp_schema),Path("survey-mappings/mucp_answer_states_v1.json"))
    original = document.records[0]
    scope_id = original.data["scopes"][1]["scope_id"]
    decision = {"survey":"MuCP", "source_record_id":original.data["record_id"], "scope_id":scope_id,
                "identity_fingerprint":identity_fingerprint(original), "action":"accept",
                "biobank_id":"bbmri-eric:ID:ZZ_TEST", "reason":"Invented scope audit", "reviewer":"test", "reviewed_on":"2026-10-13"}
    Path(args.match_overrides).write_text(json.dumps({"schema_version":"1", "input_bindings":[], "decisions":[decision]}))
    payload = execute_merge(args,directory_factory)
    bank = payload["biobanks"][0]
    evidence = [item for item in bank["evidence"] if item["survey"]=="MuCP"]
    record = bank["mucp_source_records"][0]
    assert evidence and all(item["scope_id"]==scope_id for item in evidence)
    assert all(item["source_record_id"]==record["record_id"] for item in evidence)
    assert all(item["original_source_record_id"]==original.data["record_id"] for item in evidence)
    assert bank["scopes"][scope_id]["source_record_id"]==record["record_id"]
    assert bank["reporting_unit_kind"]=="resolved_biobank"
    assert record["original_record_type"]==record_type
    unassigned = next(b for b in payload["biobanks"] if b["biobank_id"].startswith("mucp-source:"))
    assert scope_id not in unassigned["scopes"]
    assert not any(item["scope_id"]==scope_id for item in unassigned["evidence"])
    assert original.data["record_id"]==document.records[0].data["record_id"]
    assert Path(args.output_json).is_file()


@pytest.mark.parametrize("filename", ["mucp_answer_states_v1.json","mucp_reporting_policy.json","so2_mucp_report_presentation.json","mucp_reviewed_quantities.json","so2_2025_association_heatmaps.json","so2_mucp_combined.schema.json"])
def test_implicit_configuration_inputs_cannot_be_overwritten(tmp_path, monkeypatch, filename):
    """Protect implicitly loaded configuration even when output overwrite is requested.

    Args:
        tmp_path: Temporary directory for invented response fixtures and output paths.
        monkeypatch: Temporary publication guard preventing accidental real writes.
        filename: Implicit source configuration targeted by a deliberately unsafe output.

    Returns:
        None. Input/output collisions fail before publication and preserve original bytes.
    """
    import survey_combined_report
    args = fixture_arguments(tmp_path)
    target = Path("survey-mappings") / filename
    original = target.read_bytes() if target.exists() else None
    args.output_json = str(target)
    args.overwrite = True

    def reject_publication(*values, **options):
        """Prevent unsafe publication while exercising the pre-publication guards.

        Args:
            *values: Publication positional arguments, ignored by the safety stub.
            **options: Publication keyword arguments, ignored by the safety stub.

        Returns:
            None. The stub always fails rather than writing to configuration paths.

        Raises:
            AssertionError: If validation fails to reject the input/output collision.
        """
        raise AssertionError("Unsafe publication reached")

    monkeypatch.setattr(survey_combined_report,"publish_combined_outputs",reject_publication)
    with pytest.raises(ValueError,match="distinct"):
        execute_merge(args,directory_factory)
    assert (target.read_bytes() if target.exists() else None)==original


def test_repeated_sources_one_biobank_and_mucp_only_questions(tmp_path):
    """Exercise the real parsing and matching pipeline with duplicate SO2 submissions.

    Args:
        tmp_path: Isolated directory for synthetic inputs and published combined artifacts.

    Returns:
        None. Both source surveys remain complete while every statistic counts one biobank.
    """
    args = fixture_arguments(tmp_path)
    payload = execute_merge(args, directory_factory)
    assert len(payload["biobanks"]) == 1
    bb = payload["biobanks"][0]
    assert len(bb["so2_source_records"]) == 2
    assert len(bb["mucp_source_records"]) == 1
    stats = payload["descriptive_statistics"]
    assert len(stats["SO2"]["questions"]) == 3
    assert any(q["question_id"] == "B.test.answer" for q in stats["MuCP"]["questions"])
    assert all(q["population"]["N"] == 1 for survey in ("SO2", "MuCP") for q in stats[survey]["questions"])
    quantities = stats["MuCP"]["modality_quantities"]
    aggregates = stats["MuCP"]["quantity_aggregates"]
    assert quantities["observations"] == []
    assert aggregates["modality_totals"] == []
    assert aggregates["country_totals"] == []
    assert aggregates["version"] == 1
    assert {"contributions", "modality_totals", "country_totals",
            "excluded_contributions", "diagnostics"} <= set(aggregates)
    assert all(total["basis"] != "direct_modality" for total in aggregates["country_totals"])
    first = Path(args.output_json).read_bytes()
    args.overwrite = True
    execute_merge(args, directory_factory)
    assert Path(args.output_json).read_bytes() == first
    assert b"private-bytes-must-not-copy" not in first


def test_merge_stores_additive_quantity_aggregates_and_preserves_raw_summary(tmp_path):
    """Store versioned aggregates beside unchanged extractor observations.

    Args:
        tmp_path: Isolated directory for synthetic inputs and the combined JSON output.

    Returns:
        None. Combined schema validation accepts the additive aggregate contract.
    """
    args = fixture_arguments(tmp_path)
    args.output_tex = args.output_pdf = args.output_chart_dir = args.output_biobank_pdf_dir = None
    document = json.loads(Path(args.mucp_json).read_text())
    document["questionnaire"]["checkbox_questions"].append({
        "id": "C.omics_data.wgs", "part": "C", "group": "omics_data", "key": "wgs",
        "label": "WGS", "type": "checkbox", "aliases": [],
    })
    document["responses"][0]["answers"]["C.omics_data.wgs"] = {
        "value": True, "answer_state": "selected", "raw_text": "Selected",
        "qualifier_text": "100 participants",
        "evidence": [{"source_id": "SRC-001", "locator": "page 2: WGS"}],
    }
    Path(args.mucp_json).write_text(json.dumps(document), encoding="utf-8")
    payload = execute_merge(args, directory_factory)

    mucp = payload["descriptive_statistics"]["MuCP"]
    observations = mucp["modality_quantities"]["observations"]
    assert len(observations) == 1
    assert observations[0]["value"] == 100
    assert observations[0]["source_unit"] == "participants"
    assert observations[0]["original_wording"] == "Selected"
    quantity_evidence = next(
        item for item in payload["biobanks"][0]["evidence"]
        if item["evidence_id"] == observations[0]["quantity_evidence_id"]
    )
    assert quantity_evidence["qualifier_text"] == "100 participants"
    assert observations[0]["source_refs"][0]["locator"] == "page 2: WGS"
    aggregates = mucp["quantity_aggregates"]
    assert aggregates["version"] == 1
    assert len(aggregates["modality_totals"]) == 1
    total = aggregates["modality_totals"][0]
    assert total["modality_id"] == "wgs"
    assert total["unit"] == "donors"
    assert total["basis"] == "direct_modality"
    assert total["reported_total"] == 100
    assert total["segments"] == [{
        "biobank_id": "bbmri-eric:ID:ZZ_TEST", "value": 100,
        "quantity_ids": [observations[0]["quantity_id"]],
    }]
    assert aggregates["country_totals"] == []
    assert set(aggregates) == {
        "version", "unit_policy", "contributions", "modality_totals", "country_totals",
        "excluded_contributions", "diagnostics",
    }


def test_invalid_source_never_publishes(tmp_path):
    """Block all output when an unsupported MuCP version is encountered.

    Args:
        tmp_path: Isolated input/output directory containing incompatible source metadata.

    Returns:
        None. Validation occurs before publication and leaves no partial artifacts.
    """
    args = fixture_arguments(tmp_path)
    document = json.loads(Path(args.mucp_json).read_text())
    document["schema_version"] = "999"
    Path(args.mucp_json).write_text(json.dumps(document))
    with pytest.raises(ValueError, match="version"):
        execute_merge(args, directory_factory)
    assert not Path(args.output_json).exists()
    assert not Path(args.output_match_review).exists()


def test_opt_in_parent_context_retains_complete_source_answer(tmp_path):
    """Reuse SO2 parent-context presentation without semantically filtering selections.

    Args:
        tmp_path: Isolated synthetic source and TeX publication directory.

    Returns:
        None. Opt-in displays both the enabling Other and all other raw parent selections.
    """
    args = fixture_arguments(tmp_path)
    args.output_tex = str(tmp_path / "combined.tex")
    args.include_parent_context = True
    execute_merge(args, directory_factory)
    tex = Path(args.output_tex).read_text()
    assert "Parent context" in tex
    assert "University;Other (please specify):" in tex


def test_validated_manifest_reaches_combined_and_standalone_dossiers(tmp_path):
    """Render dossier inventories from the already-validated combined payload.

    Args:
        tmp_path: Isolated synthetic source and output directory.

    Returns:
        None. Both renderer paths show only the manifest filename, not its path.
    """
    import survey_combined_report

    args = fixture_arguments(tmp_path)
    payload = execute_merge(args, directory_factory)
    combined_tex = survey_combined_report.render_combined_tex(payload, {"include_dossiers": True}).tex
    standalone = survey_combined_report.render_individual_biobank_documents(payload, {})
    standalone_tex = next(iter(standalone.values()))

    for tex in (combined_tex, standalone_tex):
        assert "MuCP response source files" in tex
        assert "source.pdf" in tex
        assert "synthetic/source.pdf" not in tex
        assert "private-bytes-must-not-copy" not in tex


def test_readable_merge_preserves_raw_provenance_and_identity(tmp_path):
    """New readable statistics must not rewrite source or resolution evidence.

    Args:
        tmp_path: Private synthetic source, output and schema directory.

    Returns:
        None. Combined quantities, presentation and raw records remain distinct.
    """
    import survey_combined_report

    args = fixture_arguments(tmp_path)
    args.output_tex = str(tmp_path / "readable.tex")
    args.include_dossiers = True
    source = json.loads(Path(args.mucp_json).read_text())
    payload = execute_merge(args, directory_factory)
    bank = payload["biobanks"][0]
    assert bank["identity_resolutions"] and len(bank["so2_source_records"]) == 2
    assert bank["mucp_source_records"][0]["record_id"] == source["responses"][0]["response_id"]
    native = next(item for item in bank["evidence"] if item.get("question_id") == "B.test.answer")
    assert native["raw_answer"] is True
    assert native["source_refs"][0]["source_id"] == "SRC-001"
    assert payload["inputs"]["report_presentation_sha256"]
    assert payload["inputs"]["mucp_reporting_policy_sha256"]
    quantity = payload["descriptive_statistics"]["MuCP"]["modality_quantities"]
    assert quantity["coverage"]["cohort_N"] == 1 and quantity["observations"] == []
    tex = Path(args.output_tex).read_text()
    assert "MuCP response source files" in tex and "source.pdf" in tex
    assert "Applicable unticked" in tex
    assert "Scope-state coverage" not in tex
    assert "Counts by material type and data type" in tex
    assert "Not reported" in tex and "Eligible measurement coverage" not in tex
    standalone = next(iter(survey_combined_report.render_individual_biobank_documents(payload, {}).values()))
    assert "MuCP response source files" in standalone and "source.pdf" in standalone


def test_readable_merge_does_not_change_describe(tmp_path):
    """Combined-only quantity and presentation work leaves descriptive bytes stable.

    Args:
        tmp_path: Isolated synthetic workbook and merge outputs.

    Returns:
        None. Independent standalone descriptive material is identical before/after merge.
    """
    import so2_descriptive_report as descriptive
    from survey_evidence import canonical_json

    args = fixture_arguments(tmp_path)
    schema = descriptive.load_descriptive_schema(args.descriptive_schema)
    form = descriptive.load_form_manifest_structure(args.form_json)
    workbook = descriptive.read_descriptive_workbook(args.survey_file, schema)
    before = canonical_json(descriptive.build_descriptive_payload(workbook, schema, form))
    execute_merge(args, directory_factory)
    after = canonical_json(descriptive.build_descriptive_payload(workbook, schema, form))
    assert before == after
