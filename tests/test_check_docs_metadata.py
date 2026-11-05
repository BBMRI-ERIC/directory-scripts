"""Test check docs metadata behavior."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


GENERATOR_PATH = (
    Path(__file__).resolve().parents[2]
    / "BBMRI-ERIC-Directory-Data-Manager-Manual"
    / "scripts"
    / "generate_checks_docs.py"
)
CHECKS_DIR = Path(__file__).resolve().parents[1] / "checks"


def test_collection_category_documentation_is_complete_and_human_readable():
    """Keep current category names and actionable imaging guidance in manual metadata.

    Returns:
        None. Imaging documentation names every accepted category without runtime placeholders.
    """
    import ast

    tree = ast.parse((CHECKS_DIR / "CollectionContent.py").read_text())
    assignment = next(
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "CHECK_DOCS" for target in node.targets)
    )
    docs = ast.literal_eval(assignment.value)
    image = docs["CC:ImageCatMissing"]
    assert "%s" not in image["summary"]
    for category in ("Body image", "Whole slide image", "Photo image", "IMAGING_DATA"):
        assert category in image["summary"]
    assert "deprecated" in image["summary"]
    assert image["fix"]
    assert "Biological samples" in docs["CC:SampleCatMismatch"]["summary"]
    for check_id in ("CC:DiagCatMismatch", "CC:MedRecDiagGap"):
        assert "Clinical dataset" in docs[check_id]["summary"]


@pytest.mark.skipif(not GENERATOR_PATH.exists(), reason="manual generator not available")
def test_manual_renderers_group_identical_check_ids_and_preserve_source_links(tmp_path):
    """Render one documented check while retaining every implementation location.

    Args:
        tmp_path: Isolated directory receiving generated Markdown and TeX fixtures.

    Returns:
        None. Both renderers produce one entry, two source links and unchanged raw records.
    """
    spec = spec_from_file_location("generate_checks_docs", GENERATOR_PATH)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    checks = [
        {"check_id": "CC:Example", "module": "CollectionContent", "file": "Example.py",
         "line": line, "level": "ERROR", "entity": "COLLECTION", "fields": ["id"],
         "message": "Example summary", "action": "Review the collection"}
        for line in (10, 20)
    ]
    cache = {"plugins": {"CollectionContent": {"checks": checks}}}
    module.write_checks_md(cache, tmp_path / "checks.md")
    module.write_checks_tex(cache, tmp_path / "checks.tex")
    md = (tmp_path / "checks.md").read_text()
    tex = (tmp_path / "checks.tex").read_text()
    assert md.count("| CC:Example |") == 1
    assert tex.count(r"\label{check:CC:Example}") == 1
    for line in (10, 20):
        assert f"Example.py#L{line}" in md
        assert f"Example.py#L{line}" in tex
    assert all("implementation_locations" not in check for check in checks)
    assert len(checks) == 2


@pytest.mark.skipif(not GENERATOR_PATH.exists(), reason="manual generator not available")
@pytest.mark.parametrize("field,value", [("message", "Other summary"), ("level", "WARNING"),
                                        ("fields", ["name"])])
def test_manual_renderers_reject_conflicting_duplicate_metadata(tmp_path, field, value):
    """Reject lossy grouping when one check ID has conflicting documentation.

    Args:
        tmp_path: Isolated output directory for renderer failure cases.
        field: Effective documentation attribute varied between duplicate records.
        value: Conflicting value that must not be silently discarded.

    Returns:
        None. Both renderers reject ambiguous metadata with an actionable check ID.
    """
    spec = spec_from_file_location("generate_checks_docs", GENERATOR_PATH)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    check = {"check_id": "CC:Example", "module": "CollectionContent", "file": "Example.py",
             "line": 10, "level": "ERROR", "entity": "COLLECTION", "fields": ["id"],
             "message": "Example summary", "action": "Review the collection"}
    cache = {"plugins": {"CollectionContent": {"checks": [check, {**check, field: value, "line": 20}]}}}
    for renderer in (module.write_checks_md, module.write_checks_tex):
        with pytest.raises(ValueError, match="CC:Example"):
            renderer(cache, tmp_path / "checks.out")


@pytest.mark.skipif(not GENERATOR_PATH.exists(), reason="manual generator not available")
def test_check_docs_metadata_matches_all_plugins():
    """Verify check docs metadata matches all plugins.

    Returns:
        None. Verifies check docs metadata matches all plugins.
    """
    spec = spec_from_file_location("generate_checks_docs", GENERATOR_PATH)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    cache = module.build_cache(CHECKS_DIR)
    assert cache.get("doc_mismatches", []) == []

    for plugin_name, plugin in cache["plugins"].items():
        assert plugin["doc_mismatches"] == [], plugin_name
        for check in plugin["checks"]:
            doc = check.get("doc", {})
            assert doc, check["check_id"]
            dynamic_metadata = set(doc.get("dynamic_metadata", []))
            if "severity" not in dynamic_metadata:
                assert doc["severity"] == check["level"]
            if "entity" not in dynamic_metadata:
                assert doc["entity"] == check["entity"]
            assert isinstance(doc["fields"], list)

    documented_checks = {
        check["check_id"]: check.get("doc", {})
        for plugin in cache["plugins"].values()
        for check in plugin["checks"]
    }
    assert documented_checks[
        "MAC:MemberNonMember"
    ]["severity"] == "WARNING"
    assert documented_checks[
        "MAC:MemberDupOtherArea"
    ]["entity"] == "BIOBANK"
    assert documented_checks["BBF:JuridicalMissing"][
        "fields"
    ] == ["juridical_person"]
    assert documented_checks["CTF:EmailPlaceholder"]["fields"] == ["email"]
    assert documented_checks["CTF:EmailCountrySuffix"]["fields"] == [
        "CONTACT.email",
        "BIOBANK.country",
    ]
    assert documented_checks["CP:SizeOver"]["fields"] == [
        "COLLECTION.size",
        "COLLECTION.sub_collection",
    ]
    assert documented_checks["AI:Curated"]["fields"] == []
    assert documented_checks["TXT:AgeRange"]["fields"] == [
        "COLLECTION.age_high",
        "COLLECTION.age_low",
        "COLLECTION.description",
        "COLLECTION.name",
    ]
    assert documented_checks["TXT:StudyType"]["fields"] == [
        "COLLECTION.description",
        "COLLECTION.name",
        "COLLECTION.type",
    ]
    assert documented_checks["TXT:FFPEMaterial"]["fields"] == [
        "COLLECTION.description",
        "COLLECTION.materials",
        "COLLECTION.name",
    ]
    assert documented_checks["TXT:CovidDiag"]["fields"] == [
        "COLLECTION.description",
        "COLLECTION.diagnosis_available",
        "COLLECTION.name",
    ]
    assert documented_checks["BCO:AccessConflict"]["fields"] == [
        "commercial_use",
        "network",
    ]
    assert documented_checks["BCO:BBNetFlag"]["fields"] == ["network"]
    assert documented_checks["C19:BBNetMissing"]["fields"] == ["network"]
    assert documented_checks["C19:TypeMissing"]["fields"] == ["type"]
    assert documented_checks["C19:DiagRange"]["fields"] == ["diagnosis_available"]
    assert documented_checks["CC:OrphaNeedsIcd"]["fields"] == [
        "diagnosis_available"
    ]
    assert documented_checks["CC:ImageTypeMissing"]["fields"] == [
        "type",
    ]
    assert documented_checks["FT:CollFactsMismatch"]["fields"] == [
        "diagnosis_available",
        "facts",
        "id",
        "materials",
        "sex",
    ]
