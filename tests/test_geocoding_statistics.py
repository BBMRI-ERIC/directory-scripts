"""Reconcile biobank coordinate-source counts independently of institution totals."""

from dataclasses import replace

from geocoding_utils import CoordinateResult, format_statistics, summarize_results
from test_geocoding_locations import context


def test_one_institution_two_biobank_locations_counts_once():
    """Count institutions by name/country, not by their addresses or coordinate pairs.

    Returns:
        None. Warm-cache research remains AI-derived and distinct biobanks count individually.
    """
    bank = context()
    rows = [(bank, CoordinateResult((12, 48), "institution", "input", evidence={"institution": "Example University", "country": "ZZ"})),
            (replace(bank, biobank_id="bbmri-eric:ID:ZZ_TWO"), CoordinateResult((13, 49), "institution", "cache", evidence={"institution": " example  UNIVERSITY ", "country": "zz"}))]
    result = summarize_results(rows)
    assert result["considered"] == result["institution_biobanks"] == 2
    assert result["institutions_represented"] == 1
    text = format_statistics(result)
    assert "AI-assisted institution resolution: 2 biobanks" in text
    assert "Institutions represented: 1" in text
    assert "campus" not in text.lower()


def test_source_and_address_strata_reconcile():
    """Attribute each biobank once using actual successful query fields and channel.

    Returns:
        None. Source totals and cache/API specificity subtotals reconcile without counting attempts.
    """
    bank = context()
    results = [CoordinateResult((0, 48), "directory", "input"),
               CoordinateResult((1, 2), "manual", "input", evidence={"policy": "always"}),
               CoordinateResult(None, "unresolved", reason="service_disabled"),
               CoordinateResult((1, 2), "address", "api", ("address", "city", "country")),
               CoordinateResult((1, 2), "address", "cache", ("city", "country"))]
    rows = [(replace(bank, biobank_id=f"bbmri-eric:ID:ZZ_{i}"), result) for i, result in enumerate(results)]
    summary = summarize_results(rows)
    assert summary["considered"] == 5
    assert summary["directory"] == summary["manual"] == summary["unresolved"] == 1
    assert summary["address_total"] == 2
    assert summary["address_by_specificity"]["street"]["api"] == 1
    assert summary["address_by_specificity"]["city"]["cache"] == 1
    assert "Address geocoding succeeded: 2 (cache: 1; API: 1)" in format_statistics(summary)


def test_minimum_precision_and_unresolved_reasons_are_explicit():
    """Prevent unresolved broad matches from being presented as successful geocoding.

    Returns:
        None. The summary states the acceptance floor and explains excluded coarse outcomes.
    """
    summary = summarize_results([(context(), CoordinateResult(None, "unresolved", reason="below_city_precision"))])
    text = format_statistics(summary)
    assert "Minimum accepted geocoder match: city/locality" in text
    assert "Below city-level or unverified match: 1" in text
    assert "Unresolved: 1" in text and "Address geocoding succeeded: 0" in text
