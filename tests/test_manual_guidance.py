"""Validate explicit Manual links to reviewed JSON guidance, not prose semantics."""

import importlib.util
from pathlib import Path


def load_validator():
    """Load the cross-repository validator without running its CLI.

    Returns:
        Imported module exposing deterministic validation diagnostics.
    """
    path = Path(__file__).resolve().parents[1] / "scripts" / "validate_manual_guidance.py"
    spec = importlib.util.spec_from_file_location("manual_guidance_validator", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_matching_annotation_and_labels_are_valid():
    """Accept a reviewed entry linked through stable Manual labels.

    Returns:
        None.
    """
    from vocabulary_guidance import content_hash
    module = load_validator()
    entry = {"id": "imaging", "manual_section_ids": ["datasets"], "explanation": "Review image types."}
    guidance = {"manual_sections": {"datasets": {"label": "migration-datasets"}},
                "migrations": [entry], "miabis_bindings": [], "structural_changes": []}
    text = r"\label{migration-datasets}" + "\n% directory-guidance: imaging sha256=" + content_hash(entry)
    assert module.validate_manual_references(guidance, text) == []


def test_missing_or_changed_annotation_requires_review():
    """Report stale prose fingerprints without claiming the prose was updated.

    Returns:
        None.
    """
    module = load_validator()
    guidance = {"manual_sections": {"datasets": {"label": "missing"}},
                "migrations": [{"id": "imaging", "manual_section_ids": ["datasets"]}],
                "miabis_bindings": [], "structural_changes": []}
    diagnostics = module.validate_manual_references(guidance, "% directory-guidance: imaging sha256=" + "a" * 64)
    assert any("missing" in text for text in diagnostics)
    assert any("review" in text for text in diagnostics)


def test_changing_referenced_source_requires_prose_review():
    """Do not hide evidence changes behind an unchanged guidance entry ID.

    Returns:
        None.
    """
    from vocabulary_guidance import content_hash
    module = load_validator()
    entry = {"id": "imaging", "manual_section_ids": ["datasets"], "evidence_ids": ["source"]}
    guidance = {"schema_version": 1, "sources": {"source": {"sha256": "a" * 64}},
                "manual_sections": {"datasets": {"label": "migration-datasets"}},
                "migrations": [entry], "miabis_bindings": [], "structural_changes": []}
    text = r"\label{migration-datasets}" + "\n% directory-guidance: imaging sha256=" + content_hash(entry)
    text += "\n% directory-guidance-document: sha256=" + content_hash(guidance)
    assert module.validate_manual_references(guidance, text) == []
    guidance["sources"]["source"]["sha256"] = "b" * 64
    assert any("review" in line for line in module.validate_manual_references(guidance, text))
