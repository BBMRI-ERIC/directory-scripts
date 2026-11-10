"""Test complete, conservative metadata comparisons and readable reports."""

import copy


def inputs():
    """Build one exact reviewed binding and one documented Directory extension.

    Returns:
        Independent reference, implementation, guidance and history mappings.
    """
    from vocabulary_status import term_fingerprint
    row = {"name": "Clinical dataset", "definition": "Patient examination data"}
    extra = {"name": "Biological samples", "definition": "Samples"}
    reference = {"revision": "a" * 40, "complete": True,
                 "terms": {"DataCategories": [copy.deepcopy(row)], "ServiceTypes": []}, "sources": {}}
    implementation = {"target": "https://example.test", "schema": "ERIC", "channel": "cache",
                      "retrieved_at": "2026-11-05T12:00:00+00:00",
                      "schema_metadata": {"tables": [
                          {"name": "Collections", "columns": [{"name": "data_categories", "columnType": "ONTOLOGY_ARRAY", "refSchemaName": "DirectoryOntologies", "refTableName": "DataCategories"}]},
                          {"name": "Services", "columns": [{"name": "serviceTypes", "columnType": "REF_ARRAY", "refSchemaName": "DirectoryOntologies", "refTableName": "ServiceTypes"}]},
                      ]},
                      "ontologies": {"DataCategories": [row, extra], "ServiceTypes": []}}
    guidance = {"sources": {"miabis": {"revision": "a" * 40}, "datasets": {
        "term_hashes": {r["name"]: term_fingerprint(r) for r in (row, extra)}
    }}, "miabis_bindings": [
        {"id": "clinical", "miabis_concept": {"source_id": "miabis", "name": row["name"]},
         "directory_terms": [{"table": "DataCategories", "name": row["name"]}],
         "relationship": "equivalent", "review": {"state": "accepted"},
         "evidence_ids": ["miabis", "datasets"], "explanation": "Reviewed same meaning."},
        {"id": "samples", "miabis_concept": None,
         "directory_terms": [{"table": "DataCategories", "name": extra["name"]}],
         "relationship": "directory_extension", "review": {"state": "accepted"},
         "evidence_ids": ["datasets"], "explanation": "Additional Directory term, not a defect."},
    ]}
    snapshots = {
        "data/biobank-directory/molgenis.csv": "tableName,columnName,columnType,refSchema,refTable\nCollections,data_categories,ontology_array,DirectoryOntologies,DataCategories\nServices,serviceTypes,ref_array,DirectoryOntologies,ServiceTypes\n",
        "data/biobank-directory/ontologies/DataCategories.csv": "name,definition\nClinical dataset,Patient examination data\nBiological samples,Samples\n",
        "data/biobank-directory/ontologies/ServiceTypes.csv": "name,definition\n",
    }
    history = {"complete": True, "transitions": [], "start_revision": "b" * 40, "end_revision": "c" * 40,
               "snapshots": {path: {"at_start": text, "at_end": text} for path, text in snapshots.items()}}
    return reference, implementation, guidance, history


def test_all_reference_and_implemented_terms_are_accounted_for():
    """Keep documented extensions visible without making a complete audit fail.

    Returns:
        None.
    """
    from miabis_conformance import compare_reference
    report = compare_reference(*inputs())
    assert report["exit_status"] == 0
    assert report["coverage"]["DataCategories"] == {"reference": 1, "implementation": 2}
    assert {r["classification"] for r in report["comparisons"]} == {"equivalent", "directory_extension"}
    clinical = next(row for row in report["comparisons"] if row["reference_terms"] == ["Clinical dataset"])
    assert clinical["reference_evidence"][0]["definition"] == "Patient examination data"
    assert clinical["directory_evidence"][0]["definition"] == "Patient examination data"
    assert report["manifest_observed_at"] == "2026-11-05T12:00:00+00:00"


def test_changed_meaning_invalidates_reviewed_binding():
    """Do not reuse an accepted comparison after the actual definition changes.

    Returns:
        None.
    """
    from miabis_conformance import compare_reference
    reference, implementation, guidance, history = inputs()
    implementation["ontologies"]["DataCategories"][0]["definition"] = "A different concept"
    report = compare_reference(reference, implementation, guidance, history)
    assert report["exit_status"] == 1
    assert any(r["classification"] == "binding_needs_review" for r in report["comparisons"])


def test_name_similarity_does_not_establish_equivalence():
    """Keep unbound concepts unresolved regardless of whether labels match.

    Returns:
        None.
    """
    from miabis_conformance import compare_reference
    reference, implementation, guidance, history = inputs()
    guidance["miabis_bindings"] = []
    reference["terms"]["DataCategories"].append({"name": "OTHER", "definition": "All other data"})
    report = compare_reference(reference, implementation, guidance, history)
    assert report["exit_status"] == 1
    assert any(r["classification"] == "unresolved" for r in report["comparisons"])
    unbound = [row for row in report["comparisons"] if row["reference_terms"]]
    assert all(row["classification"] == "unresolved" for row in unbound)
    other = next(row for row in unbound if row["reference_terms"] == ["OTHER"])
    assert other["directory_terms"] == []


def test_incomplete_history_prevents_complete_conclusion():
    """A partial historical source cannot support a successful complete audit.

    Returns:
        None.
    """
    from miabis_conformance import compare_reference, render_comparison
    reference, implementation, guidance, history = inputs()
    history["complete"] = False
    report = compare_reference(reference, implementation, guidance, history)
    assert report["exit_status"] == 2
    assert "No complete conformance conclusion" in render_comparison(report, format="markdown")


def test_reports_are_deterministic_and_escape_latex():
    """Preserve stable rendering and prevent term text from becoming TeX syntax.

    Returns:
        None.
    """
    from miabis_conformance import compare_reference, render_comparison
    values = inputs()
    report = compare_reference(*values)
    assert render_comparison(report, format="json") == render_comparison(compare_reference(*values), format="json")
    report["comparisons"][0]["explanation"] = "A&B_10% #1"
    tex = render_comparison(report, format="tex")
    assert r"A\&B\_10\% \#1" in tex


def test_reference_field_pointing_elsewhere_requires_review():
    """Do not certify vocabularies while their actual entity field uses another table.

    Returns:
        None.
    """
    from miabis_conformance import compare_reference
    reference, implementation, guidance, history = inputs()
    implementation["schema_metadata"]["tables"][1]["columns"][0]["refTableName"] = "WrongReference"
    report = compare_reference(reference, implementation, guidance, history)
    assert report["exit_status"] == 1
    assert any(row["field"] == "Services.serviceTypes" and row["review_required"] for row in report["schema_checks"])


def test_history_matching_retains_nonunique_source_intervals():
    """Matching restored contents must not become an invented unique deployment SHA.

    Returns:
        None.
    """
    from miabis_conformance import compare_reference
    reference, implementation, guidance, history = inputs()
    path = "data/biobank-directory/ontologies/DataCategories.csv"
    original = history["snapshots"][path]["at_start"]
    changed = original.replace("Patient examination data", "Different definition")
    history["transitions"] = [
        {"commit": "1" * 40, "committed_at": "2026-01-01T00:00:00Z", "path": path, "previous_path": path, "before": original, "after": changed},
        {"commit": "2" * 40, "committed_at": "2026-01-02T00:00:00Z", "path": path, "previous_path": path, "before": changed, "after": original},
    ]
    report = compare_reference(reference, implementation, guidance, history)
    matched = report["history_matches"]["DataCategories"]
    assert matched["status"] == "matched"
    assert len(matched["matching_intervals"]) == 2
    assert matched["matching_intervals"][0]["before_revision"] == "1" * 40
    assert matched["matching_intervals"][1]["from_revision"] == "2" * 40
    assert "deployed_revision" not in matched
    from miabis_conformance import render_comparison
    assert "Upstream content matching" in render_comparison(report, format="markdown")


def test_unmatched_history_reports_actual_definition_differences():
    """Explain unmatched content instead of merely attaching a historical file list.

    Returns:
        None.
    """
    from miabis_conformance import compare_reference
    reference, implementation, guidance, history = inputs()
    implementation["ontologies"]["DataCategories"][0]["definition"] = "Changed in the instance"
    report = compare_reference(reference, implementation, guidance, history)
    match = report["history_matches"]["DataCategories"]
    assert match["status"] == "no_match"
    assert match["differences_from_latest"]["changed"] == ["Clinical dataset"]
    assert match["matching_intervals"] == []


def test_reference_source_conflict_is_not_a_directory_entity_error():
    """Preserve ambiguity between normative files as a separate reference finding.

    Returns:
        None.
    """
    from miabis_conformance import compare_reference
    reference, implementation, guidance, history = inputs()
    reference["source_conflicts"] = [{"table": "ServiceTypes", "explanation": "The two reference lists disagree."}]
    report = compare_reference(reference, implementation, guidance, history)
    assert report["exit_status"] == 1
    assert report["reference_issues"][0]["table"] == "ServiceTypes"
    from miabis_conformance import render_comparison
    assert "The two reference lists disagree." in render_comparison(report, format="markdown")
