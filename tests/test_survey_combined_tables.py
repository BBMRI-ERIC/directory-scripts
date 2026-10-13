"""Tests for combined-report biobank-grouped tables."""

import shutil
import subprocess

import pytest


def _api():
    """Load the combined table renderer after checking its new module exists.

    Returns:
        The production ``render_biobank_table`` function.
    """
    from survey_combined_tables import render_biobank_table

    return render_biobank_table


def test_country_banners_and_only_midrules_between_banks():
    """Render one country-grouped table without heavy bank-boundary rules.

    Returns:
        None. Banners span columns and bank blocks have only midrules.
    """
    rows = [_row("B", "IT", "Beta", "[MuCP] [Liver] 10 donors"),
            _row("A", "AT", "Alpha", "[MuCP] [Plasma] 20 donors"),
            _row("C", "IT", "Gamma", "[MuCP] [Collection not identified] 3 samples")]
    tex = _api()(rows, "ll", ["Biobank", "Answer"], country_headings=True)
    assert tex.count(r"\begin{longtable}") == 1
    assert r"\rowcolor{gray!15}" in tex
    assert r"\multicolumn{2}{c}{\textbf{Austria}}" in tex
    assert tex.index("Austria") < tex.index("Italy")
    data = tex.split(r"\endlastfoot", 1)[1]
    assert r"\toprule" not in data and r"\bottomrule" not in data
    assert "Beta &" in data and "Gamma &" in data and r"\midrule" in data


def _row(bank_id, country, label, value):
    """Build one already-escaped combined-report table row.

    Args:
        bank_id: Canonical Directory biobank identifier.
        country: Reported country used for stable ordering.
        label: TeX-escaped biobank display label.
        value: TeX-escaped non-biobank cell.

    Returns:
        Row mapping accepted by the production renderer.
    """
    return {"biobank_id": bank_id, "country": country,
            "biobank_label": label, "cells": [value]}


def test_default_and_dtto_repeated_cells_group_by_canonical_identity():
    """Apply repeat policy within ID groups without merging equal display names.

    Returns:
        None. Country/name/ID ordering is stable and distinct IDs remain distinct.
    """
    render = _api()
    rows = [
        _row("ID:DE_B", "DE", "Shared Name", "second"),
        _row("ID:FR_A", "FR", "Shared Name", "third"),
        _row("ID:DE_B", "DE", "Shared Name", "fourth"),
        _row("ID:DE_A", "DE", "Alpha", "first"),
    ]

    empty = render(rows, r"p{0.4\linewidth}p{0.5\linewidth}",
                   ["Biobank", "Evidence"])
    ditto = render(rows, r"p{0.4\linewidth}p{0.5\linewidth}",
                   ["Biobank", "Evidence"], "dtto")

    assert empty.index("Alpha") < empty.index("Shared Name") < empty.index("third")
    assert empty.count("Shared Name &") == 2
    assert empty.count("Continued: Shared Name") >= 2
    assert "\\midrule" in empty
    assert "Continued: Shared Name" in empty
    assert "\\emph{dtto}" not in empty
    assert "\\emph{dtto}" in ditto


def test_renderer_rejects_invalid_repetition_mode_and_malformed_rows():
    """Fail closed for unsupported display modes and incomplete row contracts.

    Returns:
        None. Callers get an actionable validation error, not malformed TeX.
    """
    render = _api()
    with pytest.raises(ValueError, match="repeated_entries"):
        render([_row("ID:A", "AA", "A", "x")], "ll", ["Bank", "Evidence"], "same")
    with pytest.raises(ValueError, match="biobank_id"):
        render([{"country": "AA", "biobank_label": "A", "cells": ["x"]}],
               "ll", ["Bank", "Evidence"])


@pytest.mark.skipif(not all(shutil.which(command) for command in
                            ("xelatex", "pdfinfo", "pdftotext")),
                    reason="XeLaTeX and Poppler are required for pagination verification")
@pytest.mark.parametrize("country_headings", [False, True])
def test_long_bank_block_compiles_and_each_continuation_page_names_bank(tmp_path, country_headings):
    """Compile a multi-page bank block and inspect each page's fixed continuation header.

    Args:
        tmp_path: Isolated source/PDF directory owned by this test.
        country_headings: Whether to exercise the new logical country-grouped table.

    Returns:
        None. Every continuation page retains its bank identity in compiled output.
    """
    from so2_descriptive_report import _preamble, _tex

    render = _api()
    long_name = "Long Bank & Institute " + "Research Centre " * 12
    rows = [_row("ID:DE_LONG", "DE", _tex(long_name),
                 _tex(f"Source quantity {index}: " + "evidence phrase " * 14))
            for index in range(240)]
    table = render(rows, r"p{0.4\linewidth}p{0.5\linewidth}",
                   ["Biobank", "Evidence"], country_headings=country_headings)
    source = tmp_path / "continuation.tex"
    source.write_text("\n".join([_preamble(), r"\begin{document}", table,
                                  r"\end{document}"]), encoding="utf-8")
    subprocess.run(["xelatex", "-interaction=nonstopmode", "-halt-on-error",
                    "-output-directory", str(tmp_path), str(source)],
                   cwd=tmp_path, check=True, capture_output=True, text=True)
    pdf = tmp_path / "continuation.pdf"
    pages = int(subprocess.check_output(["pdfinfo", str(pdf)], text=True)
                .split("Pages:", 1)[1].splitlines()[0].strip())
    assert pages >= 2
    for page in range(1, pages + 1):
        text = subprocess.check_output(["pdftotext", "-f", str(page), "-l", str(page),
                                        str(pdf), "-"], text=True)
        if page > 1:
            normalized = " ".join(text.split())
            prefix = "Previous page ended in Germany: " if country_headings else "Continued: "
            assert prefix + " ".join(long_name.split()) in normalized
        assert "Source quantity" in text
