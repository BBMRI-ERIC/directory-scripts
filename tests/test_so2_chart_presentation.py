"""Check standalone SO2 chart presentation without changing combined-survey charts."""

from copy import deepcopy

import so2_descriptive_report as report
from test_so2_descriptive_report import single_choice_payload_with_missing, multi_choice_payload


def test_so2_donuts_preserve_labels_and_shared_pies():
    """Keep source data, denominator variants and labels while hollowing SO2 pies.

    Returns:
        None. Only standalone SO2 fragments have a donut center.
    """
    payload = single_choice_payload_with_missing()
    before = deepcopy(payload)
    rendered = report.render_descriptive_tex(payload, None)
    assert rendered.tex.count(r"\fill[white] (0,0) circle (0.75);") == 2
    assert payload == before
    for answered_only, fragment in zip((False, True), rendered.chart_fragments.values(), strict=True):
        pie = report._pie_fragment(payload["questions"][0], answered_only)
        assert r"\fill[white] (0,0) circle (0.75);" not in pie
        unwrapped = fragment.replace(r"\noindent\resizebox{\linewidth}{!}{" + "\n", "", 1)
        unwrapped = unwrapped.replace(r"\end{tikzpicture}" + "\n" + r"}\par", r"\end{tikzpicture}", 1)
        assert unwrapped.replace(r"\fill[white] (0,0) circle (0.75);" + "\n", "") == pie
        assert fragment.startswith(r"\noindent\resizebox{\linewidth}{!}{")
        document = next(value for value in rendered.chart_documents.values() if fragment in value)
        assert r"\par" + "\n" + fragment in document


def test_so2_bar_order_descends_without_mutating_shared_order():
    """Descending presentation leaves canonical data and shared renderer order intact.

    Returns:
        None. SO2 categories are sorted by count, including missing answers.
    """
    payload = multi_choice_payload()
    question = payload["questions"][0]
    question["categories"] = [
        {**question["categories"][0], "value": label, "count": count}
        for label, count in (("Small", 1), ("Large", 8), ("Medium", 4))
    ]
    before = deepcopy(payload)
    rendered = report.render_descriptive_tex(payload, None)
    fragment = next(iter(rendered.chart_fragments.values()))
    assert fragment.index("Large") < fragment.index("Medium") < fragment.index("Small")
    assert payload == before
    shared = report._bar_fragment(question)
    assert shared.index("Small") < shared.index("Large") < shared.index("Medium")
