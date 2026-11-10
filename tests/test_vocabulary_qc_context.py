"""Verify once-per-run compatibility levels and evidence-based reference advice."""

import pytest


@pytest.mark.parametrize("observed,expected,level", [
    ("v13.200.1", "v13.209.1", "WARNING"),
    ("v13.210.0", "v13.209.1", "INFO"),
    ("v13.209.1", "v13.209.1", None),
    ("13.209.1", "v13.209.1", None),
    ("unreported", "v13.209.1", "INFO"),
])
def test_software_comparison_is_ordered_and_nonblocking(observed, expected, level):
    """Compare validated releases without using commit text as an ordered number.

    Args:
        observed: Software release reported by the Directory instance.
        expected: Reviewed release baseline shipped with the QC guidance.
        level: Expected combined diagnostic level, or no mismatch message.

    Returns:
        None.
    """
    from vocabulary_status import compatibility_message
    guidance = {"expectations": {"software": {"release": expected}}, "sources": {}}
    snapshot = {"server_manifest": {"SpecificationVersion": observed}, "content_hashes": {}}
    result = compatibility_message(snapshot, guidance)
    assert (result["level"] if result else None) == level
    if result:
        assert observed in result["text"]
        assert expected in result["text"]


def test_newer_software_and_older_model_are_one_warning():
    """Preserve independently ordered model state within a single diagnostic.

    Returns:
        None.
    """
    from vocabulary_status import compatibility_message
    guidance = {"expectations": {
        "software": {"release": "v13.209.1"},
        "model": {"expected_reference_id": "new", "older_reference_ids": ["old"], "newer_reference_ids": []},
    }, "sources": {"new": {"semantic_hash": "new-model"}, "old": {"semantic_hash": "old-model"}}}
    snapshot = {"server_manifest": {"SpecificationVersion": "v13.210.1"},
                "content_hashes": {"schema": "old-model"}}
    result = compatibility_message(snapshot, guidance)
    assert result["level"] == "WARNING"
    assert "older" in result["text"] and "newer" in result["text"]
    assert "model" in result["text"]


def test_unknown_model_is_not_called_older():
    """Do not infer a model migration from the installed software version.

    Returns:
        None.
    """
    from vocabulary_status import compatibility_message
    guidance = {"expectations": {"model": {
        "expected_reference_id": "new", "older_reference_ids": [], "newer_reference_ids": [],
    }}, "sources": {"new": {"semantic_hash": "expected"}}}
    result = compatibility_message({"content_hashes": {"schema": "different"}}, guidance)
    assert result["level"] == "INFO"
    assert "unverified" in result["text"]
    assert "older" not in result["text"]


def test_deprecation_requires_an_explicit_declaration():
    """Ignore negated, historical or speculative occurrences of deprecated.

    Returns:
        None.
    """
    from vocabulary_status import deprecation_state
    assert deprecation_state("Deprecated value, please use a more specific type.") == "deprecated"
    assert deprecation_state("This term is deprecated.") == "deprecated"
    assert deprecation_state("This term is not deprecated.") != "deprecated"
    assert deprecation_state("Previously deprecated, now restored.") != "deprecated"
    assert deprecation_state("May be deprecated in a future release.") != "deprecated"
    assert deprecation_state("Deprecated in 2025; restored in 2026.") != "deprecated"
    assert deprecation_state("Deprecated value; no longer deprecated after restoration.") != "deprecated"


def test_term_fingerprint_ignores_order_but_not_meaning():
    """Allow CSV/API storage differences without hiding changed definitions.

    Returns:
        None.
    """
    from vocabulary_status import term_fingerprint
    assert term_fingerprint({"name": "X", "label": "X", "parent": "", "order": "1"}) == term_fingerprint({"name": "X", "label": "X", "parent": None})
    assert term_fingerprint({"name": "X", "definition": "Old"}) != term_fingerprint({"name": "X", "definition": "New"})


def test_context_is_printed_once_with_visible_newer_info():
    """Keep version context out of entity findings and visible without verbose logging.

    Returns:
        None.
    """
    import io
    from vocabulary_status import print_vocabulary_context
    context = {"guidance": {"schema_version": 1, "sources": {}, "production_checks": {},
                            "expectations": {"software": {"release": "v13.209.1"}}},
               "snapshot": {"target": "https://example.test", "schema": "ERIC", "channel": "cache",
                            "retrieved_at": "2026-11-05T12:00:00+00:00",
                            "server_manifest": {"SpecificationVersion": "v13.210.0"}}}
    output = io.StringIO()
    print_vocabulary_context(context, stream=output)
    print_vocabulary_context(context, stream=output)
    text = output.getvalue()
    assert text.count("Directory reference:") == 1
    assert text.count("INFO: Directory compatibility:") == 1
    assert "cache" in text
    assert "QC tool:" in text
