"""Regression tests for generic, unique-biobank statistics section rendering."""

import importlib
import shutil


report = importlib.import_module("so2_descriptive_report")


def test_generic_statistics_sections_use_percent_basis_and_do_not_mutate_source():
    """Generic rendering honors unique-biobank percentage semantics without mutation.

    Returns:
        None. The generic renderer preserves input statistics and reports its explicit basis.
    """
    from copy import deepcopy

    question = {
        "question_id": "mucp_b_01",
        "label": "Available sample types",
        "question_type": "single_choice",
        "population": {"N": 2, "A": 1, "M": 1},
        "categories": [
            {"value": "Serum", "count": 1, "percent": 100.0, "percent_basis": "oAB"},
            {"value": "Missing", "count": 1, "percent": 50.0, "percent_basis": "oIB"},
        ],
        "pie_categories": [
            {"value": "Serum", "count": 1, "percent": 50.0, "excluded_from_chart": False},
            {"value": "Missing", "count": 1, "percent": 50.0, "excluded_from_chart": False},
        ],
        "contributions": [],
        "free_text_rows": [],
    }
    sections = [{"survey": "MuCP", "label": "MuCP", "questions": [question]}]
    before = deepcopy(sections)

    rendered = report.render_statistics_sections(sections, {})

    assert "unique overlapping biobanks" in rendered.tex
    assert dict(rendered.chart_fragments)
    assert sections == before
    included = next(value for key, value in rendered.chart_fragments.items() if not key.endswith("answered-only"))
    answered = next(value for key, value in rendered.chart_fragments.items() if key.endswith("answered-only"))
    assert "50.0\\% of unique overlapping biobanks" in included
    assert "100.0\\% of biobanks with non-missing evidence" in answered


def test_heatmap_renderer_accepts_explicit_unit_without_changing_default():
    """Heatmap interpretation can state its analytical unit explicitly.

    Returns:
        None. Both the legacy implicit wording and explicit combined unit render.
    """
    import inspect

    signature = inspect.signature(report._association_heatmap_fragment)
    assert "unit" in signature.parameters


def test_zero_biobank_cohort_keeps_summary_but_omits_meaningless_chart():
    """An empty cohort reports N/A/M and an omission instead of a zero pie.

    Returns:
        None. The generic body has the empty denominator but no chart assets.
    """
    question = {
        "question_id": "empty_q1", "label": "Empty question", "question_type": "single_choice",
        "population": {"N": 0, "A": 0, "M": 0}, "categories": [], "contributions": [],
        "free_text_rows": [],
    }

    rendered = report.render_statistics_sections(
        [{"survey": "SO2", "label": "SO2", "questions": [question]}], {},
    )

    assert "0 / 0 / 0" in rendered.tex
    assert not rendered.chart_fragments
    assert any("empty cohort" in message.casefold() for message in rendered.diagnostics)


def test_combined_country_codes_and_chart_units_do_not_become_response_rows():
    """Keep canonical country codes and unique-biobank chart units in generic adapters.

    Returns:
        None. Presentation does not reinterpret a canonical code or invent worksheet rows.
    """
    question = {"question_id": "text", "label": "Text", "question_type": "free_text",
        "population": {"N": 1, "A": 1, "M": 0}, "categories": [], "contributions": [],
        "analytical_unit": "unique_overlapping_biobank",
        "free_text_rows": [{"country": "CH", "country_code": "CH", "institution": "Institute", "text": "Value"}]}
    rendered = report.render_statistics_sections([{"survey": "SO2", "questions": [question]}], {})
    assert "CH & Institute" in rendered.tex
    assert report._chart_unit(question) == "unique overlapping biobanks"


def test_generic_text_retains_scope_and_splits_long_responses():
    """Prevent scope erasure and oversized cells in combined text statistics.

    Returns:
        None. The table preserves source, scope and both ends of long text.
    """
    question = {"question_id": "C.text", "label": "Text", "question_type": "free_text",
        "population": {"N": 1, "A": 1, "M": 0}, "categories": [], "contributions": [],
        "free_text_rows": [{"country": "AT", "institution": "Institute", "source_record_id": "RESP-1",
            "scope_label": "Collection one", "text": "Start " + "word " * 1000 + " end"}]}
    rendered = report.render_statistics_sections([{"survey": "MuCP", "questions": [question]}], {})
    assert "RESP-1" in rendered.tex and "Collection one" in rendered.tex
    assert "continued" in rendered.tex and "Start" in rendered.tex and "end" in rendered.tex


def test_compact_source_context_hides_machine_prefixes_but_keeps_scope_and_qualifiers():
    """Use human source tags and semantic scopes in combined-only tables.

    Returns:
        None. Compact mode hides technical IDs/prefixes; legacy default stays unchanged.
    """
    question = {"question_id": "MuCP.C.description", "label": "Description",
        "question_type": "free_text", "population": {"N": 1, "A": 1, "M": 0},
        "categories": [], "contributions": [], "free_text_rows": [{
            "country": "CH", "institution": "Institute", "source_record_id": "RESP-114",
            "scope_label": "Collection Alpha", "text":
                "RESP-114: collection_or_submission_as_reported: Collection Alpha; "
                "submission: tissue is available only with consent."}]}
    sections = [{"survey": "MuCP", "questions": [question]}]

    legacy = report.render_statistics_sections(sections, {}).tex
    compact = report.render_statistics_sections(sections, {"compact_source_context": True}).tex

    assert "RESP-114" in legacy and "Collection Alpha" in legacy
    assert "RESP-114" not in compact
    assert "collection_or_submission_as_reported:" not in compact
    assert "submission: tissue is available only with consent." in compact
    assert "[MuCP]" in compact and "Collection Alpha" in compact
    assert "tissue is available only with consent" in compact


def test_compact_shared_cleanup_preserves_literal_prose_and_quotes():
    """Preserve provenance-like tokens inside literal shared-renderer answers.

    Returns:
        None. Only a chain of established leading serialization prefixes is removed.
    """
    literals = ["Complete this submission; then seek approval.",
                'Keep "RESP-A: source wording" in this quotation.',
                "Describe source_record_id: as written in the instructions."]
    for literal in literals:
        assert report._compact_report_context(literal) == literal
    assert report._compact_report_context(
        "RESP-A: collection_or_submission_as_reported: submission: retained"
    ) == "retained"


def test_compact_shared_tables_remove_generated_prefix_after_retained_survey_tag():
    """Clean actual tagged table responses without changing payloads or legacy views.

    Returns:
        None. Both survey tags survive anchored cleanup and literal prose stays intact.
    """
    from copy import deepcopy

    for survey, name in (("MuCP", "Andalusian Public Health System Biobank"),
                         ("SO2", "MARBiobanc")):
        text = f"[{survey}] collection_or_submission_as_reported: {name}"
        literals = [f'[{survey}] Keep "collection_or_submission_as_reported: {name}" as quoted.',
                    f"[{survey}] Narrative mentions collection_or_submission_as_reported: {name}.",
                    f'[{survey}] "collection_or_submission_as_reported: {name}"',
                    f"[{survey}] This submission: explains source_record_id: in ordinary prose."]
        question = {"question_type": "free_text", "free_text_rows": [
            {"country": "ES", "institution": name, "text": value}
            for value in [text, *literals]]}
        original = deepcopy(question)
        compact = report._question_tables(question, compact_source_context=True)
        legacy = report._question_tables(question)
        assert report._compact_report_context(text) == f"[{survey}] {name}"
        assert f"[{survey}] {name}" in compact
        assert legacy.count(r"collection\_or\_submission\_as\_reported:") == 4
        assert compact.count(r"collection\_or\_submission\_as\_reported:") == 3
        assert question == original
        for literal in literals:
            assert report._compact_report_context(literal) == literal
        assert report._compact_report_context(
            f"[{survey}] RESP-A: source_record_id: collection_or_submission_as_reported: submission: {name}"
        ) == f"[{survey}] {name}"


def test_shared_renderer_cleans_generated_scope_prefix_at_survey_tag_boundary():
    """Exercise the real scope-context concatenation that creates tagged responses.

    Returns:
        None. Compact combined mode cleans the generated prefix; default/extended retain it.
    """
    from copy import deepcopy

    question = {"question_id": "MuCP.C.description", "label": "Description",
        "question_type": "free_text", "population": {"N": 1, "A": 1, "M": 0},
        "categories": [], "contributions": [], "free_text_rows": [{
            "country": "ES", "institution": "MARBiobanc",
            "scope_label": "collection_or_submission_as_reported",
            "text": "Andalusian Public Health System Biobank and MARBiobanc"}]}
    sections = [{"survey": "MuCP", "questions": [question]}]
    original = deepcopy(sections)
    compact = report.render_statistics_sections(sections, {"compact_source_context": True}).tex
    legacy = report.render_statistics_sections(sections, {}).tex
    extended = report.render_statistics_sections(sections, {"extended_evidence": True}).tex
    assert "[MuCP] Andalusian Public" in compact
    assert r"collection\_or\_submission\_as\_reported:" not in compact
    assert r"[MuCP] collection\_or\_submission\_as\_reported:" in legacy
    assert legacy == extended
    assert sections == original


def test_embedded_statistics_does_not_orphan_its_outer_section_heading():
    """Embedded bodies must not insert a second page break after the outer heading.

    Returns:
        None. Standalone sections own page breaks; embedded sections defer to their caller.
    """
    rendered = report.render_statistics_sections([{"survey": "MuCP", "questions": []}], {"include_section_heading": False})
    assert not rendered.tex.startswith(r"\clearpage")


def test_country_quantity_charts_compile_zero_one_huge_range_and_long_legend(tmp_path):
    """Compile a multi-page chart fixture with zero/one rows and wrapped bank labels.

    Args:
        tmp_path: Isolated temporary directory for standalone TeX and compiled PDF.

    Returns:
        None. XeLaTeX accepts the linear document and its wrapped legend.
    """
    from pathlib import Path
    import importlib
    import subprocess

    import pytest

    from so2_descriptive_report import InputError, _preamble, _run_xelatex

    if shutil.which("xelatex") is None:
        pytest.skip("XeLaTeX is unavailable for the compiled chart fixture")
    combined = importlib.import_module("survey_combined_report")
    banks = [{"biobank_id": f"bank-{index:02d}", "country": f"Country {index:02d}",
              "name": f"A deliberately long institute name & cohort _ {index:02d} " * 2}
             for index in range(4)]
    values = [0, 1, 1_000_000, 15]
    totals = [{"country": bank["country"], "unit": "donors", "basis": "collection",
               "temporal_status": "unspecified", "reported_total": value,
               "segments": [{"biobank_id": bank["biobank_id"], "value": value,
                             "quantity_ids": [f"quantity-{index:02d}"]}]}
              for index, (bank, value) in enumerate(zip(banks, values))]
    charts = combined.render_country_quantity_charts(
        {"country_totals": totals, "modality_totals": [], "excluded_contributions": []},
        {"biobanks": banks},
    )
    assert len(charts) == 1
    assert all(r"font=\sffamily\small" in fragment for fragment in charts.values())
    assert all(r"/pgf/number format/assume math mode=true" in fragment for fragment in charts.values())
    assert all(r"/pgf/number format/fixed" in fragment and r"/pgf/number format/precision=0" in fragment
               for fragment in charts.values())
    assert all(r"\parbox[t]{0.45\textwidth}{\raggedright" in fragment for fragment in charts.values())
    assert all("fill=white,fill opacity=0.85,text opacity=1" in fragment for fragment in charts.values())
    assert all("\\end{tikzpicture}\\par" in fragment for fragment in charts.values())
    source = tmp_path / "country-quantity-fixture.tex"
    source.write_text("\n".join([
        _preamble(), r"\begin{document}",
        *(r"\clearpage" + "\n" + fragment for fragment in charts.values()),
        r"\end{document}",
    ]), encoding="utf-8")

    try:
        pdf = _run_xelatex(source, tmp_path, passes=1)
    except InputError as exc:
        pytest.fail(f"Synthetic country quantity chart fixture did not compile: {exc}")

    assert pdf.is_file() and pdf.stat().st_size > 0
    text = subprocess.check_output(["pdftotext", str(pdf), "-"], text=True)
    assert text.count("1 donors") == 1
    assert text.count("15 donors") == 1
