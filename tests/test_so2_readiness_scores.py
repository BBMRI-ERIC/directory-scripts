"""Verify source-based readiness scoring, reference replay, and report integration."""

from copy import deepcopy
import json
from pathlib import Path

import pytest
from hypothesis import given, strategies as st


ROOT = Path(__file__).resolve().parents[1]


def verified_bindings(mapping):
    """Bind scoring fixtures to the actual checked-in form fields and choices.

    Args:
        mapping: Seven-component scoring configuration used by the fixture.

    Returns:
        Validated, lightweight field binding evidence for saved scoring models.
    """
    from so2_descriptive_report import load_form_manifest_structure
    from so2_readiness_scores import bind_form_fields
    return bind_form_fields(mapping, load_form_manifest_structure(ROOT / "survey-mappings/so2_2025_form.json"))


def scoring_inputs():
    """Read public rules and construct invented, non-response-derived vectors.

    Returns:
        Mapping and 148 invented records; the first is an explicit formula
        witness and rows 61/99 differ for conflict-pagination checks. No private
        Josephine file or actual respondent vector is needed by portable tests.
    """
    mapping = json.loads((ROOT / "survey-mappings/so2_2025_readiness_scores.json").read_text())
    scores = dict(zip("acludpr", [0, 1, .5, 1, .5, .66, .75]))
    answers = {key: next(rule["answer"] for rule in mapping["components"][key]["rules"] if rule["score"] == score)
               for key,score in scores.items()}
    fixture = {"records": [{"source_row": row, "answers": deepcopy(answers)} for row in range(5,153)]}
    for row,score in ((61,.5),(99,1)):
        fixture["records"][row-5]["answers"]["a"] = next(rule["answer"] for rule in mapping["components"]["a"]["rules"] if rule["score"] == score)
    return mapping, fixture


def test_reference_reproduces_every_spreadsheet_score_and_heatmap_cell():
    """Literal decimals and the hash-bound blank override reproduce Josephine.

    Returns:
        None. All 1,332 cached scores and 25 cell counts agree independently.
    """
    from so2_readiness_scores import score_sources, reference_view, DEFAULT_REFERENCE

    mapping, fixture = scoring_inputs()
    reference_path = ROOT / "tests/fixtures/so2_readiness_reference.json"
    if not reference_path.is_file() or not DEFAULT_REFERENCE.is_file():
        pytest.skip("Optional local Josephine replay requires the ignored private reference dataset.")
    from so2_readiness_scores import load_scoring_mapping
    schema = json.loads((ROOT / "survey-mappings/so2_2025_descriptive_report.json").read_text())
    mapping = load_scoring_mapping(schema["questions"])
    fixture = json.loads(reference_path.read_text())
    scored = score_sources(fixture["records"], mapping)
    view = reference_view(scored, mapping, mapping["reference"]["source_sha256"])
    assert len(scored) == 148
    for record, expected in zip(view["source_scores"], fixture["records"]):
        actual = [record["components"][k]["score"] for k in "ac ludpr".replace(" ", "")]
        assert actual + [record["traceability"], record["qm"]] == pytest.approx(expected["expected"], abs=1e-12, rel=0)
    assert view["matrix"] == fixture["matrix"]
    assert view["complete_pairs"] == 148
    assert scored[-1]["components"]["p"]["score"] is None
    assert scored[-1]["qm"] is None
    assert view["overrides"][0]["source_row"] == mapping["reference"]["blank_overrides"][0]["source_row"]


def test_synthetic_formula_witness_uses_literal_decimals():
    """Keep portable numerical regression coverage without real response vectors.

    Returns:
        None. Independently specified component values produce the expected totals.
    """
    from so2_readiness_scores import score_sources
    mapping, fixture = scoring_inputs()
    record = score_sources(fixture["records"][:1],mapping)[0]
    assert [record["components"][k]["score"] for k in "acludpr"] == [0,1,.5,1,.5,.66,.75]
    assert record["traceability"] == .5625
    assert record["qm"] == pytest.approx(.72,abs=1e-12,rel=0)


def test_public_rules_work_without_josephine_reference_data(tmp_path, monkeypatch):
    """Reference responses and replay policy are optional private inputs, not runtime requirements.

    Args:
        tmp_path: Temporary directory intentionally containing no private policy.
        monkeypatch: Temporary override redirecting the optional reference path.

    Returns:
        None. Public rules score invented responses and never create a reference replay.
    """
    import so2_readiness_scores as module
    monkeypatch.setattr(module,"DEFAULT_REFERENCE",tmp_path / "absent.json")
    schema = json.loads((ROOT / "survey-mappings/so2_2025_descriptive_report.json").read_text())
    mapping = module.load_scoring_mapping(schema["questions"])
    assert "reference" not in mapping
    _, fixture = scoring_inputs()
    view = module.reference_view(module.score_sources(fixture["records"][:1],mapping),mapping,"a"*64)
    assert view["complete_pairs"] == 1 and not view["is_josephine_replay"] and not view["overrides"]


def test_missing_unknown_and_custody_precedence_are_explicit():
    """Do not manufacture zero scores or average multi-choice alternatives.

    Returns:
        None. Unknown text is unscorable and precedence has a diagnostic.
    """
    from so2_readiness_scores import score_sources, reference_view

    mapping, fixture = scoring_inputs()
    record = deepcopy(fixture["records"][0])
    record["answers"]["p"] = ""
    record["answers"]["a"] = "Yes, maybe"
    record["answers"]["c"] = ";".join(rule["answer"] for rule in reversed(mapping["components"]["c"]["rules"][:2]))
    scored = score_sources([record], mapping)
    assert scored[0]["components"]["a"]["status"] == "unrecognised"
    assert scored[0]["components"]["c"]["score"] == 1
    assert scored[0]["components"]["c"]["precedence_applied"] is True
    assert scored[0]["traceability"] is None and scored[0]["qm"] is None
    view = reference_view(scored, mapping, "different-workbook")
    assert not view["overrides"] and view["complete_pairs"] == 0
    assert view["is_josephine_replay"] is False


@pytest.mark.parametrize("value,expected", [(0,0),(.1999,0),(.2,1),(.4,2),(.6,3),(.8,4),(1,4)])
def test_band_boundaries(value, expected):
    """Use left-closed equal-width bands including one in the final band.

    Args:
        value: Score on or near a documented band boundary.
        expected: Zero-based band assigned by the explicit interval convention.

    Returns:
        None. Exact boundaries receive the specified higher band.
    """
    from so2_readiness_scores import score_band
    assert score_band(value) == expected


@given(st.permutations(range(6)))
def test_custody_precedence_is_independent_of_answer_text_order(order):
    """Rule precedence, not the survey's token order, determines custody score.

    Args:
        order: Generated permutation of the six verified custody answer choices.

    Returns:
        None. All selections retain their rules, choose one, and flag differing scores.
    """
    from so2_readiness_scores import score_sources

    mapping, fixture = scoring_inputs()
    record = deepcopy(fixture["records"][0])
    record["answers"]["c"] = ";".join(mapping["components"]["c"]["rules"][i]["answer"] for i in order)
    component = score_sources([record], mapping)[0]["components"]["c"]
    assert component["score"] == 1 and component["precedence_applied"] is True
    assert len(component["matched_rules"]) == 6 and not component["unknown_selections"]


@pytest.mark.parametrize("value", [None, True, -0.1, 1.1, float("nan"), float("inf"), "0.5"])
def test_invalid_scores_fail_explicitly(value):
    """Never band invalid numeric data or silently coerce booleans.

    Args:
        value: Deliberately invalid score value from a malformed configuration.

    Returns:
        None. Invalid scores fail rather than becoming a numerical category.
    """
    from so2_readiness_scores import score_band
    with pytest.raises(ValueError, match="score"):
        score_band(value)


def test_agreeing_duplicates_collapse_and_conflicts_never_enter_heatmap():
    """Retain separate source vectors without selecting a convenient answer.

    Returns:
        None. Two agreeing sources count once; conflicting alternatives count zero.
    """
    from so2_readiness_scores import score_sources, build_readiness_model, validate_readiness_model

    mapping, fixture = scoring_inputs()
    records = [deepcopy(fixture["records"][0]) for _ in range(4)]
    for index, record in enumerate(records):
        record["source_row"] = index + 5
    records[-1]["answers"]["a"] = "Yes"
    sources = score_sources(records, mapping)
    groups = [{"source_rows": [5,6], "institution": "A&B_Institute", "country": "CZ", "biobank_id": "CZ_TEST"},
              {"source_rows": [7,8], "institution": "Second", "country": "AT", "biobank_id": None}]
    model = build_readiness_model(sources, groups, mapping, "different-workbook", verified_bindings(mapping))
    assert model["main"]["complete_pairs"] == 1
    assert model["main"]["conflicting_observations"] == 1
    assert len(model["observations"][0]["alternatives"]) == 2
    assert model["main"]["observations"] == 2
    validate_readiness_model(model)
    model["main"]["matrix"][0][0] += 1
    with pytest.raises(ValueError, match="readiness"):
        validate_readiness_model(model)


def test_scoring_rules_must_match_verified_question_uids_and_choices():
    """Reject edited or incompatible rules before producing outputs.

    Returns:
        None. Missing choice coverage and mismatched field UIDs fail clearly.
    """
    from so2_readiness_scores import validate_scoring_mapping

    mapping, _ = scoring_inputs()
    schema = json.loads((ROOT / "survey-mappings/so2_2025_descriptive_report.json").read_text())
    validate_scoring_mapping(mapping, schema["questions"])
    bad = deepcopy(mapping)
    bad["components"]["a"]["form_uid"] = "wrong"
    with pytest.raises(ValueError, match="UID"):
        validate_scoring_mapping(bad, schema["questions"])
    bad = deepcopy(mapping)
    bad["components"]["a"]["rules"].pop()
    with pytest.raises(ValueError, match="choices"):
        validate_scoring_mapping(bad, schema["questions"])


def test_readiness_is_last_section_and_charts_use_existing_publication_pipeline(tmp_path):
    """Render vector heatmaps and a contact-free repeated-header score table.

    Args:
        tmp_path: Temporary output location for report-relative chart paths.

    Returns:
        None. Both views register standalone chart sources without changing legacy reports.
    """
    from so2_descriptive_report import InputError, render_descriptive_tex
    from test_so2_descriptive_report import report_payload, structured_report_question

    payload = report_payload(structured_report_question())
    before = render_descriptive_tex(payload, None).tex
    assert "QM vs traceability readiness" not in before
    payload = complete_scoring_payload(tmp_path)
    rendered = render_descriptive_tex(payload, chart_dir=tmp_path / "charts", report_path=tmp_path / "report.tex")
    assert r"\section{QM vs traceability readiness}" in rendered.tex
    assert r"A\&B\_Institute" in rendered.tex
    assert r"\endhead" in rendered.tex and "Source rows" in rendered.tex
    assert set(rendered.chart_fragments) >= {"readiness-main", "readiness-source"}
    assert "readiness-main.pdf" in rendered.tex
    assert rendered.tex.index("QM vs traceability readiness") > rendered.tex.index("Question identifier:")
    payload["readiness_scores"]["main"]["complete_pairs"] = 99
    with pytest.raises(InputError, match="readiness"):
        render_descriptive_tex(payload, None)


def test_saved_scores_are_bound_to_report_source_and_observation_membership():
    """A self-consistent model from a different cohort cannot be spliced into a report.

    Returns:
        None. Source checksums and exact merged row groups must agree.
    """
    from so2_readiness_scores import score_sources, build_readiness_model, validate_readiness_model

    mapping, fixture = scoring_inputs()
    sources = score_sources(fixture["records"][:2], mapping)
    groups = [{"source_rows": [5,6], "institution": "Test", "country": "CZ", "biobank_id": None}]
    model = build_readiness_model(sources, groups, mapping, "b"*64, verified_bindings(mapping))
    with pytest.raises(ValueError, match="checksum"):
        validate_readiness_model(model, source_sha256="a"*64)
    with pytest.raises(ValueError, match="membership"):
        validate_readiness_model(model, observation_sources=[{"source_rows": [5], "biobank_id": None}, {"source_rows": [6], "biobank_id": None}])
    validate_readiness_model(model, source_sha256="b"*64, observation_sources=[{"source_rows": [5,6], "biobank_id": None}])


@pytest.mark.parametrize("count", [True, 1.0])
def test_saved_model_does_not_accept_boolean_or_float_counts(count):
    """JSON type distinctions matter even when Python numeric equality agrees.

    Args:
        count: Invalid boolean or float that compares equal to integer one.

    Returns:
        None. Count fields must survive reconstruction with their exact JSON type.
    """
    from so2_readiness_scores import score_sources, build_readiness_model, validate_readiness_model

    mapping, fixture = scoring_inputs()
    sources = score_sources(fixture["records"][:1], mapping)
    groups = [{"source_rows": [5], "institution": "Test", "country": "CZ", "biobank_id": None}]
    model = build_readiness_model(sources, groups, mapping, "b"*64, verified_bindings(mapping))
    model["main"]["complete_pairs"] = count
    with pytest.raises(ValueError, match="readiness"):
        validate_readiness_model(model)


def test_self_consistent_scores_cannot_replace_preserved_raw_answers():
    """Cross-check the new model against independent preserved source records.

    Returns:
        None. Recomputed but altered answers cannot overwrite audited source evidence.
    """
    from so2_readiness_scores import score_sources, build_readiness_model, validate_readiness_model

    mapping, fixture = scoring_inputs()
    original = deepcopy(fixture["records"][0])
    altered = deepcopy(original)
    altered["answers"]["a"] = "Yes"
    groups = [{"source_rows": [5], "institution": "Test", "country": "CZ", "biobank_id": None}]
    model = build_readiness_model(score_sources([altered], mapping), groups, mapping, "b"*64, verified_bindings(mapping))
    schema = json.loads((ROOT / "survey-mappings/so2_2025_descriptive_report.json").read_text())
    columns = {k:next(q["column"] for q in schema["questions"] if q["question_id"]==c["question_id"]) for k,c in mapping["components"].items()}
    preserved = [{"source_row": 5, "answers": {columns[k]:v for k,v in original["answers"].items()}}]
    with pytest.raises(ValueError, match="raw answer"):
        validate_readiness_model(model, source_records=preserved, questions=schema["questions"])


@pytest.mark.parametrize("change", ["uid", "choices", "field_type"])
def test_actual_manifest_bindings_must_match_not_only_the_schema(change):
    """Wrong authoritative fields fail even with an unchanged descriptive schema.

    Args:
        change: Actual manifest property deliberately made incompatible with custody.

    Returns:
        None. Missing UID, empty choices, or wrong field type cannot be scored.
    """
    from so2_descriptive_report import load_form_manifest_structure
    from so2_readiness_scores import bind_form_fields

    mapping, _ = scoring_inputs()
    form = load_form_manifest_structure(ROOT / "survey-mappings/so2_2025_form.json")
    uid = mapping["components"]["c"]["form_uid"]
    if change == "uid":
        form["field_bindings"]["changed"] = form["field_bindings"].pop(uid)
        form["field_bindings"]["changed"]["uid"] = "changed"
    elif change == "choices":
        form["field_bindings"][uid]["choices"] = []
    else:
        form["field_bindings"][uid]["field_type"] = "single_choice"
    with pytest.raises(ValueError, match="form"):
        bind_form_fields(mapping, form)


def write_scoring_workbook(tmp_path):
    """Write a small anonymised SO2 envelope with all schema columns.

    Args:
        tmp_path: Temporary directory receiving the synthetic XLSX.

    Returns:
        Input path with two conflicting submissions for one explicit biobank.
    """
    import openpyxl
    from datetime import datetime

    mapping, fixture = scoring_inputs()
    schema = json.loads((ROOT / "survey-mappings/so2_2025_descriptive_report.json").read_text())
    headers = schema["columns"]["respondent_context"] + schema["columns"]["administrative_exclusions"] + [q["column"] for q in schema["questions"]]
    headers = list(dict.fromkeys(headers))
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Content"
    sheet.append(["Alias", "SO2_2025"])
    sheet.append(["Export Date", datetime(2026, 10, 13)])
    sheet.append([])
    sheet.append(headers)
    columns = {k:next(q["column"] for q in schema["questions"] if q["question_id"] == c["question_id"]) for k,c in mapping["components"].items()}
    for index in range(2):
        record = {columns[k]:v for k,v in fixture["records"][0]["answers"].items()}
        record.update({"Name of Institution": "A&B_Institute", "Country": "CZ", "BiobankID in the Directory (if available)": "CZ_TEST"})
        if index:
            record[columns["a"]] = "Yes"
        sheet.append([record.get(h, "") for h in headers])
    path = tmp_path / "source.xlsx"
    workbook.save(path)
    return path


def complete_scoring_payload(tmp_path):
    """Generate a complete redacted CLI payload with independent raw evidence.

    Args:
        tmp_path: Temporary directory receiving synthetic inputs and payload JSON.

    Returns:
        Full descriptive payload with verified form bindings and preserved sources.
    """
    from test_survey_so2_directory import load_module

    cli = load_module()
    source = write_scoring_workbook(tmp_path)
    output = tmp_path / "payload.json"
    args = cli.build_cli().parse_args([
        "describe", "-i", str(source), "--descriptive-schema", str(ROOT / "survey-mappings/so2_2025_descriptive_report.json"),
        "--form-json", str(ROOT / "survey-mappings/so2_2025_form.json"), "-o", str(output), "--overwrite",
    ])
    assert cli.run_describe(args) == 0
    return json.loads(output.read_text())


@pytest.mark.parametrize("missing", ["responses_summary", "form_structure"])
def test_rerender_requires_independent_source_and_form_provenance(tmp_path, missing):
    """Do not silently bypass cross-checks when an enclosing evidence field is deleted.

    Args:
        tmp_path: Temporary location for a fully generated redacted payload.
        missing: Independent evidence section removed from the otherwise valid JSON.

    Returns:
        None. Removing raw responses or form provenance cannot weaken validation.
    """
    from so2_descriptive_report import InputError, render_descriptive_tex
    payload = complete_scoring_payload(tmp_path)
    del payload[missing]
    with pytest.raises(InputError, match="readiness"):
        render_descriptive_tex(payload, None)


@pytest.mark.parametrize("section,field", [("responses_summary", "source_records"), ("responses_summary", "observation_sources"), ("form_structure", "source_sha256"), ("form_structure", "field_bindings")])
def test_null_independent_evidence_does_not_bypass_checks(tmp_path, section, field):
    """Explicit JSON nulls must not disable mandatory report integrity checks.

    Args:
        tmp_path: Temporary directory receiving a complete synthetic report payload.
        section: Enclosing evidence object containing the required field.
        field: Required independent evidence replaced by null.

    Returns:
        None. Null source records, memberships or form evidence fail before rendering.
    """
    from so2_descriptive_report import InputError, render_descriptive_tex
    payload = complete_scoring_payload(tmp_path)
    payload[section][field] = None
    with pytest.raises(InputError, match="readiness"):
        render_descriptive_tex(payload, None)


def test_rerender_cross_checks_independent_manifest_bindings(tmp_path):
    """Changing mapping and embedded binding together cannot forge an authoritative UID.

    Args:
        tmp_path: Temporary directory for a complete redacted CLI payload.

    Returns:
        None. A self-consistent forged UID fails against separately preserved form fields.
    """
    from so2_descriptive_report import InputError, render_descriptive_tex
    from so2_readiness_scores import score_sources, build_readiness_model
    payload = complete_scoring_payload(tmp_path)
    original = payload["readiness_scores"]
    mapping = deepcopy(original["mapping"])
    bindings = deepcopy(original["form_bindings"])
    mapping["components"]["c"]["form_uid"] = "forged-uid"
    bindings["components"]["c"]["uid"] = "forged-uid"
    records = [{"source_row": s["source_row"], "answers": {k:c["raw_answer"] for k,c in s["components"].items()}} for s in original["source_scores"]]
    groups = [{k:g[k] for k in ("source_rows", "institution", "country", "biobank_id")} for g in original["observations"]]
    payload["readiness_scores"] = build_readiness_model(score_sources(records,mapping),groups,mapping,original["source_sha256"],bindings)
    with pytest.raises(InputError, match="readiness"):
        render_descriptive_tex(payload, None)


def test_native_readiness_charts_and_conflict_blocks_paginate(tmp_path):
    """Compile both standalone charts and a multipage table without orphan alternatives.

    Args:
        tmp_path: Temporary directory for native XeLaTeX documents and PDFs.

    Returns:
        None. All three conflicting source rows share a page with their institution;
        continued table pages repeat their column headers.
    """
    import shutil
    from so2_readiness_scores import score_sources, build_readiness_model, readiness_section
    from so2_descriptive_report import _preamble, _tex, _run_xelatex
    pdfplumber = pytest.importorskip("pdfplumber")
    if not shutil.which("xelatex"):
        pytest.skip("Native layout validation requires XeLaTeX.")
    mapping, fixture = scoring_inputs()
    sources = score_sources(fixture["records"], mapping)
    groups = [{"source_rows": [s["source_row"]], "institution": f"Institution {s['source_row']:03d}", "country": "CZ", "biobank_id": None}
              for s in sources if s["source_row"] not in (6,61,99)]
    groups.append({"source_rows": [6,61,99], "institution": "Institution 050 conflict", "country": "CZ", "biobank_id": None})
    model = build_readiness_model(sources, groups, mapping, "b"*64, verified_bindings(mapping))
    section, fragments = readiness_section(model, _tex)
    for key,fragment in fragments.items():
        chart = tmp_path / (key + ".tex")
        chart.write_text(_preamble()+"\n"+r"\begin{document}"+"\n"+fragment+"\n"+r"\end{document}")
        chart_pdf = _run_xelatex(chart, tmp_path)
        with pdfplumber.open(chart_pdf) as doc:
            assert len(doc.pages) == 1
            if key == "readiness-source":
                assert "Completescorepairs:148" in "".join(doc.pages[0].extract_text().split())
        section = section.replace("%% "+key,fragment)
    report = tmp_path / "scores.tex"
    report.write_text(_preamble()+"\n"+r"\begin{document}"+"\n"+section+"\n"+r"\end{document}")
    report_pdf = _run_xelatex(report, tmp_path, passes=2)
    with pdfplumber.open(report_pdf) as doc:
        pages = ["".join(page.extract_text().split()) for page in doc.pages]
    conflict_page = next(page for page in pages if "99:conflicting" in page)
    assert all(text in conflict_page for text in ("Institution050conflict", "6:conflicting", "61:conflicting"))
    table_pages = [page for page in pages if "Institution/CC" in page]
    assert len(table_pages) >= 3
    assert all("Sourcerows" in page and "status" in page for page in table_pages)


def test_cli_scores_before_merging_and_is_deterministic(tmp_path):
    """Exercise the full Directory-free CLI using redacted original submissions.

    Args:
        tmp_path: Temporary directory for synthetic inputs and output JSON.

    Returns:
        None. Conflicting source vectors survive grouping and reruns are deterministic.
    """
    from test_survey_so2_directory import load_module

    cli = load_module()
    source = write_scoring_workbook(tmp_path)
    output = tmp_path / "report.json"
    args = cli.build_cli().parse_args([
        "describe", "-i", str(source), "--descriptive-schema", str(ROOT / "survey-mappings/so2_2025_descriptive_report.json"),
        "--form-json", str(ROOT / "survey-mappings/so2_2025_form.json"), "-o", str(output), "--overwrite",
    ])
    assert cli.run_describe(args) == 0
    first = output.read_bytes()
    model = json.loads(first)["readiness_scores"]
    assert model["main"]["observations"] == 1
    assert model["main"]["conflicting_observations"] == 1
    assert model["main"]["complete_pairs"] == 0
    assert model["source_view"]["complete_pairs"] == 2
    assert model["source_view"]["overrides"] == []
    assert model["source_scores"][0]["components"]["a"]["raw_answer"] == "No"
    assert model["source_scores"][1]["components"]["a"]["raw_answer"] == "Yes"
    assert cli.run_describe(args) == 0 and first == output.read_bytes()


def test_readiness_compile_failure_rolls_back_every_output(tmp_path, monkeypatch):
    """A failed new heatmap cannot replace any previously published artifact.

    Args:
        tmp_path: Temporary directory holding old JSON, TeX, PDF and chart files.
        monkeypatch: Pytest override for the compiler failure, restored after testing.

    Returns:
        None. The whole describe transaction preserves every old output byte.
    """
    from test_survey_so2_directory import load_module
    import so2_descriptive_report as descriptive

    cli = load_module()
    source = write_scoring_workbook(tmp_path)
    output, tex, pdf = [tmp_path / name for name in ("report.json", "report.tex", "report.pdf")]
    charts = tmp_path / "charts"
    charts.mkdir()
    sentinel = charts / "readiness-main.pdf"
    old = {output:b"old json", tex:b"old tex", pdf:b"old pdf", sentinel:b"old chart"}
    for path,content in old.items():
        path.write_bytes(content)

    def fail_heatmap(path, output_dir, passes=1):
        """Return mock chart bytes until the new main-readiness chart fails.

        Args:
            path: Staged TeX chart filename used to identify the target heatmap.
            output_dir: Staging directory receiving successful mock PDFs.
            passes: Requested compiler passes; irrelevant to the injected failure.

        Returns:
            Mock successful PDF path for charts preceding the readiness failure.

        Raises:
            InputError: On the new readiness heatmap rather than an earlier chart.
        """
        if path.stem == "readiness-main":
            raise descriptive.InputError("injected readiness chart failure")
        target = output_dir / (path.stem + ".pdf")
        target.write_bytes(b"%PDF-1.4 fake")
        return target

    monkeypatch.setattr(descriptive, "_run_xelatex", fail_heatmap)
    args = cli.build_cli().parse_args([
        "describe", "-i", str(source), "--descriptive-schema", str(ROOT / "survey-mappings/so2_2025_descriptive_report.json"),
        "--form-json", str(ROOT / "survey-mappings/so2_2025_form.json"), "-o", str(output),
        "--output-tex", str(tex), "--output-pdf", str(pdf), "--output-chart-dir", str(charts), "--overwrite",
    ])
    with pytest.raises(cli.InputError, match="readiness chart failure"):
        cli.run_describe(args)
    assert all(path.read_bytes() == content for path,content in old.items())
    assert sorted(p.name for p in charts.iterdir()) == ["readiness-main.pdf"]
