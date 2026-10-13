"""Regress evidence-pattern versus explicit-availability intersection semantics."""

import importlib
import json
from hashlib import sha256

import pytest


def test_registry_includes_cross_survey_data_technology_intersections():
    """Require both scoped MuCP data and SO2 technology sets in approved definitions.

    Returns:
        None. MuCP-led cross-survey UpSets are not replaced by separate plots.
    """
    from pathlib import Path
    registry = json.loads(Path("survey-mappings/so2_mucp_visualizations.json").read_text())
    cross = [item for item in registry["upsets"] if item["id"].startswith("mucp-data-so2-")]
    assert len(cross) == 2
    for item in cross:
        assert any(q.startswith("MuCP:") for q in item["questions"])
        assert any(q.startswith("SO2:") for q in item["questions"])


def test_approved_upsets_use_classified_checkbox_patterns_and_curated_titles():
    """Use complete reported patterns without affirmative jargon or unknown negatives.

    Returns:
        None. Both MuCP-only and mixed definitions use the reviewed projection.
    """
    from pathlib import Path
    registry = json.loads(Path("survey-mappings/so2_mucp_visualizations.json").read_text())
    titles = {item["id"]: item["title"] for item in registry["upsets"]}
    assert all(item["projection"] == "reported_checkbox_pattern" for item in registry["upsets"])
    assert titles["mucp-biospecimens"] == "[MuCP] Part C: Reported biospecimens"
    assert titles["mucp-omics"] == "[MuCP] Part C: Reported OMICs data"
    assert titles["mucp-available-data"] == "[MuCP] Part C: Reported data types"
    assert all("affirmative" not in title.casefold() for title in titles.values())


def test_upset_unticked_and_missing_groups_have_different_dispositions():
    """Keep all-No answered rows while excluding absent group evidence.

    Returns:
        None. Minimum-N counts complete all-zero rows, not missing responses.
    """
    from survey_descriptive import build_combined_upset_matrix
    definition = {"id": "group", "questions": ["MuCP:C.a", "MuCP:C.b"],
                  "projection": "reported_checkbox_pattern", "minimum_n": 5}
    banks = [{"biobank_id": str(index), "country": "AT", "name": str(index), "observations": [
        {"survey": "MuCP", "question_id": question,
         "state": "reported_yes_in_one_or_more_scopes" if index == offset else "explicitly_no_in_all_reported_applicable_scopes",
         "has_affirmative_evidence": index == offset}
        for offset, question in enumerate(("C.a", "C.b"))]} for index in range(5)]
    banks.append({"biobank_id": "missing", "country": "AT", "name": "missing", "observations": []})
    result = build_combined_upset_matrix(definition, banks)
    assert result["matrix_N"] == 5
    assert result["all_zero_biobanks"] == 3
    assert result["exclusions"] == {"missing": 1}
    assert result["omission_reason"] is None


def test_cross_survey_upset_retains_scope_states_and_excludes_so2_conflicts():
    """Count affirmative evidence once per bank without claiming same-scope data access.

    Returns:
        None. Variable MuCP scopes remain visible and unknowns are not negatives.
    """
    from survey_descriptive import build_combined_upset_matrix
    definition = {"id": "cross", "questions": ["MuCP:C.data", "SO2:q"], "minimum_n": 1,
        "sets": [{"question": "MuCP:C.data", "label": "[MuCP] Data"},
                 {"question": "SO2:q", "category": "NGS", "label": "[SO2] NGS access"}]}
    bb = {"biobank_id": "A", "country": "XX", "name": "A", "observations": [
        {"survey": "MuCP", "question_id": "C.data", "state": "varying_across_scopes", "has_affirmative_evidence": True},
        {"survey": "SO2", "question_id": "q", "state": "known", "selected_values": ["NGS"]}]}
    result = build_combined_upset_matrix(definition, [bb])
    assert result["rows"][0]["set_001"] and result["rows"][0]["set_002"]
    assert result["state_matrix"]["A"]["MuCP:C.data"] == "varying_across_scopes"
    bb["observations"][1]["state"] = "conflicting_submissions"
    assert build_combined_upset_matrix(definition, [bb])["rows"] == []


def test_technology_sets_do_not_claim_unknown_or_other_checkbox_as_access():
    """Forced Other and uncertainty responses must not become technology sets.

    Returns:
        None. Only declared concrete technologies enter availability comparisons.
    """
    from survey_descriptive import combined_upset_definition
    selector = "SO2:q_035_does_the_repository_have_a_direct_access_to_data_from_any_of_the_followi"
    data = "MuCP:C.omics_data.wgs"
    definition = combined_upset_definition({"id": "cross", "questions": [data, selector]}, {
        data: {"label": "WGS"}, selector: {"categories": ["Other (please specify):", "I don’t know", "Next-gen sequencing"]}})
    assert [item["label"] for item in definition["sets"]] == ["[MuCP] WGS reported", "[SO2] Next-gen sequencing"]


def test_uncertain_technology_answer_is_excluded_not_an_all_zero_pattern():
    """Unknown and forced-Other-only responses cannot become negative technology vectors.

    Returns:
        None. Projection exclusions remain explicit and source answers are retained.
    """
    from survey_descriptive import combined_upset_definition, build_combined_upset_matrix
    qid = "q_035_does_the_repository_have_a_direct_access_to_data_from_any_of_the_followi"
    selector = "SO2:" + qid
    definition = combined_upset_definition({"id": "access", "questions": [selector]}, {
        selector: {"categories": ["I don’t know", "Other (please specify):", "NGS"]}})
    for selected in (["I don’t know"], ["Other (please specify):"], ["I don’t know", "NGS"]):
        bank = {"biobank_id": "A", "country": "XX", "name": "A", "observations": [
            {"survey": "SO2", "question_id": qid, "state": "known", "selected_values": selected}]}
        matrix = build_combined_upset_matrix(definition, [bank])
        assert not matrix["rows"]
        assert sum(matrix["exclusions"].values()) == 1
        checkbox_pattern = build_combined_upset_matrix(
            {**definition, "projection": "reported_checkbox_pattern"}, [bank])
        assert not checkbox_pattern["rows"]
        assert sum(checkbox_pattern["exclusions"].values()) == 1
        assert checkbox_pattern["state_matrix"]["A"][selector] == "known"


def test_reviewed_so2_heatmaps_retain_categories_and_unknown_state():
    """Reuse reviewed SO2 pairs without dropping conflicting biobank observations.

    Returns:
        None. Default pairs retain ordered axes and append exceptional analytical states.
    """
    from pathlib import Path
    module = importlib.import_module("survey_descriptive")
    pairs = module.reviewed_so2_heatmaps(Path("survey-mappings/so2_2025_association_heatmaps.json"))
    assert len(pairs) == 4
    definition = pairs[0]
    data = {definition["questions"][0]: [{"observation_id": "A", "state": "conflicting_submissions"}],
            definition["questions"][1]: [{"observation_id": "A", "state": "missing"}]}
    result = module.build_association_from_observations(definition, data)
    assert result["pair"]["cells"]["conflicting_submissions|missing"] == 1
    assert result["definition"]["row_categories"][0] == definition["row_categories"][0]


@pytest.mark.parametrize("category", ["No observations", "Unmapped source category"])
@pytest.mark.parametrize("paired", [False, True])
def test_omitted_heatmap_rejects_actual_unknown_category_even_without_pairs(category, paired):
    """Reject literal respondent categories despite an omitted or unpaired panel.

    Args:
        category: Uncurated source response, including the old internal sentinel text.
        paired: Whether the source observation also has a column response.

    Returns:
        None. Empty opposite axes cannot erase real evidence or bypass curation.
    """
    from pathlib import Path
    from survey_descriptive import build_association_from_observations
    from survey_combined_report import load_report_presentation, validate_heatmap_presentation

    definition = {"id": "mucp-consent-sharing", "questions": ["MuCP:consent", "MuCP:sharing"], "minimum_n": 5}
    observations = {"MuCP:consent": [{"observation_id": "A", "state": "known", "selected_values": [category]}]}
    if paired:
        observations["MuCP:sharing"] = [{"observation_id": "A",
            "state": "explicitly_no_in_all_reported_applicable_scopes"}]
    heatmap = build_association_from_observations(definition, observations)
    assert heatmap["omission_reason"]
    assert heatmap["pair"]["paired_denominator"] == int(paired)
    assert category in heatmap["definition"]["row_categories"]
    presentation = load_report_presentation(Path("survey-mappings/so2_mucp_report_presentation.json"))
    with pytest.raises(ValueError, match="curated.*category"):
        validate_heatmap_presentation([heatmap["definition"]], presentation)


def test_curated_heatmap_labels_cover_all_categories():
    """Require exact source-value labels for all seven approved pairs and states.

    Returns:
        None. Ordinal categories and exceptional states remain distinct.
    """
    from pathlib import Path
    from survey_combined_report import load_report_presentation
    from survey_descriptive import MUCP_STATES
    from so2_descriptive_report import load_association_heatmap_registry
    presentation = load_report_presentation(Path("survey-mappings/so2_mucp_report_presentation.json"))["heatmaps"]
    registry = load_association_heatmap_registry(Path("survey-mappings/so2_2025_association_heatmaps.json"))
    expected_ids = {"so2-" + item.definition_id for item in registry} | {"mucp-consent-sharing", "qms-sops"}
    assert set(presentation) == expected_ids
    for item in registry:
        labels = presentation["so2-" + item.definition_id]
        assert set(item.row_categories) <= set(labels["row_tick_labels"])
        assert set(item.column_categories) <= set(labels["column_tick_labels"])
        assert len({labels["row_tick_labels"][category] for category in item.row_categories}) == len(item.row_categories)
        assert len({labels["column_tick_labels"][category] for category in item.column_categories}) == len(item.column_categories)
    assert len(registry[0].row_categories) == len(registry[0].column_categories) == 5
    assert len(registry[-1].row_categories) == len(registry[-1].column_categories) == 4
    assert set(MUCP_STATES) <= set(presentation["mucp-consent-sharing"]["row_tick_labels"])
    assert set(MUCP_STATES) <= set(presentation["qms-sops"]["column_tick_labels"])
    assert presentation["so2-personnel_infrastructure"]["row_tick_labels"][registry[1].row_categories[0]] == "need more info"
    assert presentation["so2-personnel_infrastructure"]["column_tick_labels"][registry[1].column_categories[0]] == "need more info"
    for labels in presentation.values():
        assert all(1 <= len(labels[key]) <= 3 for key in ("row_axis_lines", "column_axis_lines"))
        assert labels["row_tick_labels"].get("conflicting_submissions") or labels["column_tick_labels"].get("conflicting_submissions")


def test_qms_sops_axis_uses_registry_order_even_without_observed_levels():
    """Preserve five ordered QMS levels rather than alphabetizing observed answers.

    Returns:
        None. Zero-count source levels remain on the combined QMS axis.
    """
    from pathlib import Path
    from survey_descriptive import build_association_from_observations, reviewed_so2_heatmaps
    registry = reviewed_so2_heatmaps(Path("survey-mappings/so2_2025_association_heatmaps.json"))
    qms = registry[0]["column_categories"]
    definition = {"id": "qms-sops", "questions": ["SO2:qms", "MuCP:sops"],
                  "row_categories": qms, "minimum_n": 1}
    result = build_association_from_observations(definition, {
        "SO2:qms": [{"observation_id": "A", "state": "known", "selected_values": [qms[-1]]}],
        "MuCP:sops": [{"observation_id": "A", "state": "explicitly_no_in_all_reported_applicable_scopes"}],
    })
    assert result["definition"]["row_categories"][:5] == qms


def test_unknown_checkbox_is_not_negative_availability():
    """Keep unmarked states in evidence patterns and exclude them from strict availability.

    Returns:
        None. Absent positive evidence membership never establishes biological absence.
    """
    module = importlib.import_module("survey_descriptive")
    bb = {"biobank_id": "A", "country": "AT", "name": "Alpha", "observations": [
        {"survey": "MuCP", "question_id": "C.serum", "state": "reported_yes_in_one_or_more_scopes", "has_affirmative_evidence": True},
        {"survey": "MuCP", "question_id": "C.plasma", "state": "unknown_or_unmarked", "has_affirmative_evidence": False}]}
    definition = {"id": "specimens", "questions": ["MuCP:C.serum", "MuCP:C.plasma"],
                  "projection": "affirmative_evidence_pattern", "minimum_n": 1}
    pattern = module.build_combined_upset_matrix(definition, [bb])
    assert pattern["rows"][0]["set_001"] is True
    assert pattern["state_matrix"]["A"]["MuCP:C.plasma"] == "unknown_or_unmarked"
    strict = module.build_combined_upset_matrix({**definition, "projection": "explicit_availability_complete_case"}, [bb])
    assert strict["rows"] == []
    assert strict["exclusions"]["unknown_or_unmarked"] == 1


def test_reported_checkbox_pattern_reconciles_no_unknown_and_scope_states():
    """Project present unticked answers as no while retaining unknown and raw states.

    Returns:
        None. Complete patterns retain explicit no rows; unknown and incomplete patterns are diagnosed.
    """
    from survey_descriptive import build_combined_upset_matrix

    definition = {"id": "reported", "questions": ["MuCP:C.serum"],
        "projection": "reported_checkbox_pattern", "minimum_n": 1}
    banks = [
        {"biobank_id": "NO", "country": "AT", "name": "No", "observations": [
            {"survey": "MuCP", "question_id": "C.serum",
             "state": "explicitly_no_in_all_reported_applicable_scopes", "has_affirmative_evidence": False,
             "flags": [], "scope_ids": ["scope-no"]}]},
        {"biobank_id": "UNKNOWN", "country": "AT", "name": "Unknown", "observations": [
            {"survey": "MuCP", "question_id": "C.serum", "state": "unknown_or_unmarked",
             "has_affirmative_evidence": False, "flags": []}]},
        {"biobank_id": "PARTIAL", "country": "AT", "name": "Partial", "observations": [
            {"survey": "MuCP", "question_id": "C.serum",
             "state": "reported_yes_in_one_or_more_scopes", "has_affirmative_evidence": True,
             "flags": ["partial_scope_coverage"]}]},
    ]

    result = build_combined_upset_matrix(definition, banks)

    assert result["matrix_N"] == 1
    assert result["rows"] == [{"observation_id": "NO", "country": "AT", "institution": "No",
                               "set_001": False}]
    assert result["state_matrix"]["UNKNOWN"]["MuCP:C.serum"] == "unknown_or_unmarked"
    assert result["state_matrix"]["NO"]["MuCP:C.serum"] == "explicitly_no_in_all_reported_applicable_scopes"
    assert result["exclusions"] == {"unknown_or_unmarked": 1, "incomplete_scope_coverage": 1}


def test_reported_checkbox_pattern_retains_distinct_collection_variation():
    """Retain a varying pattern dot as evidence in at least one distinct collection.

    Returns:
        None. Variation is not universal coverage and remains explicit in the state matrix.
    """
    from survey_descriptive import build_combined_upset_matrix

    definition = {"id": "reported", "questions": ["MuCP:C.data"],
        "projection": "reported_checkbox_pattern", "minimum_n": 1}
    bank = {"biobank_id": "A", "country": "AT", "name": "A", "observations": [
        {"survey": "MuCP", "question_id": "C.data", "state": "varying_across_scopes",
         "has_affirmative_evidence": True, "flags": [], "scope_assessment": "distinct_collections_vary"}]}

    result = build_combined_upset_matrix(definition, [bank])

    assert result["rows"][0]["set_001"] is True
    assert result["state_matrix"]["A"]["MuCP:C.data"] == "varying_across_scopes"
    assert "at least one reported collection" in result["interpretation"]


def test_heatmap_uses_unique_identity_and_semantic_axes():
    """Build interpretable paired categorical counts rather than collection-row counts.

    Returns:
        None. Paired biobank counts and their fixed category axes reconcile exactly.
    """
    module = importlib.import_module("survey_descriptive")
    definition = {"id": "pair", "questions": ["SO2:q1", "SO2:q2"], "minimum_n": 1}
    data = {"SO2:q1": [{"observation_id": "A", "state": "known", "selected_values": ["Yes"]}],
            "SO2:q2": [{"observation_id": "A", "state": "known", "selected_values": ["No"]}]}
    result = module.build_association_from_observations(definition, data)
    assert result["pair"]["paired_denominator"] == 1
    assert result["pair"]["cells"]["Yes|No"] == 1


def test_declared_heatmap_categories_do_not_create_observed_variation():
    """Suppress association graphics when all five source observations are unknown.

    Returns:
        None. Declared zero-count categories do not satisfy the populated-category gate.
    """
    from survey_descriptive import build_association_from_observations
    definition = {"id": "unknown", "questions": ["MuCP:q1", "MuCP:q2"], "minimum_n": 5,
                  "row_categories": ["Yes", "No"], "column_categories": ["Yes", "No"]}
    data = {qid: [{"observation_id": str(index), "state": "unknown_or_unmarked"} for index in range(5)]
            for qid in definition["questions"]}
    result = build_association_from_observations(definition, data)
    assert result["omission_reason"] is not None
    assert result["pair"]["classifiable_denominator"] == 0


def test_combined_bundle_keeps_string_id_and_hashes(tmp_path):
    """Bind external assets to the analytical cohort rather than workbook row numbers.

    Args:
        tmp_path: Isolated output directory for generated CSV/R bundle files.

    Returns:
        None. Canonical source identity and projection semantics are present in the bundle.
    """
    import json
    module = importlib.import_module("so2_descriptive_upsets")
    matrix = {"id": "test", "title": "Reports", "questions": ["MuCP:C.q"], "projection": "affirmative_evidence_pattern",
              "sets": ["set_001"], "set_labels": ["Serum reported"], "omission_reason": None,
              "rows": [{"observation_id": "bbmri-eric:ID:AT_A", "country": "AT", "institution": "Alpha", "set_001": True}]}
    target = tmp_path / "bundle"
    module.write_matrix_upset_bundle([matrix], target, {"cohort": ["bbmri-eric:ID:AT_A"]})
    assert "bbmri-eric:ID:AT_A" in (target / "test.csv").read_text()
    manifest = json.loads((target / "input-manifest.json").read_text())
    assert manifest["analytical_unit"] == "unique_selected_biobank"
    assert manifest["definitions"][0]["projection"] == "affirmative_evidence_pattern"
    renderer = (target / "render-descriptive-upsets.R").read_text()
    assert "patchwork::plot_annotation" in renderer
    assert "strwrap" in renderer
    assert "No affirmative evidence" not in renderer
    assert "Affirmative evidence pattern" not in renderer


def test_rendered_bundle_rejects_edited_csv_despite_unchanged_manifest(tmp_path):
    """Bind rendered assets to actual CSV bytes as well as copied manifest fingerprints.

    Args:
        tmp_path: Isolated bundle directory containing synthetic PDF byte attestations.

    Returns:
        None. Editing input vectors invalidates assets before any report is published.
    """
    module = importlib.import_module("so2_descriptive_upsets")
    matrix = {"id": "test", "title": "Reports", "questions": ["MuCP:C.q"], "projection": "affirmative_evidence_pattern",
              "sets": ["set_001"], "set_labels": ["Serum reported"], "omission_reason": None,
              "rows": [{"observation_id": "A", "country": "AT", "institution": "Alpha", "set_001": True}]}
    target = tmp_path / "bundle"
    module.write_matrix_upset_bundle([matrix], target, {})
    incoming = json.loads((target / "input-manifest.json").read_text())
    output = {}
    for key in ("upset_pdf", "deviation_pdf"):
        name = incoming["definitions"][0][key]
        content = b"%PDF-1.4\nsynthetic test bytes"
        (target / name).write_bytes(content)
        output[key] = name
        output[key.replace("_pdf", "_sha256")] = sha256(content).hexdigest()
    from survey_combined_intersections import build_intersection_catalogue
    output["intersections"] = [{key: bar[key] for key in ("bar_id", "pattern", "count")} for bar in build_intersection_catalogue(matrix)]
    (target / "output-manifest.json").write_text(json.dumps({"bundle_version": "2",
        "canonical_sha256": incoming["canonical_sha256"], "outputs": {"test": output}}))
    assert module.validate_matrix_upset_bundle([matrix], {}, target).state == "complete"
    script = target / "render-descriptive-upsets.R"
    original = script.read_text()
    script.write_text(original + "\n# Edited renderer\n")
    with pytest.raises(module.InputError, match="renderer|script"):
        module.validate_matrix_upset_bundle([matrix], {}, target)
    script.write_text(original)
    csv_path = target / "test.csv"
    csv_path.write_text(csv_path.read_text().replace("True", "False"))
    with pytest.raises(module.InputError, match="CSV"):
        module.validate_matrix_upset_bundle([matrix], {}, target)


def test_stale_or_incomplete_bundle_does_not_replace_published_outputs(tmp_path):
    """Bind assets to reporting policy and presentation before replacement.

    Args:
        tmp_path: Synthetic source and publication directory.

    Returns:
        None. Stale or incomplete assets cannot replace the existing JSON output.
    """
    from pathlib import Path
    from survey_combined import execute_merge
    from so2_descriptive_upsets import InputError
    from test_survey_merge_mucp_integration import fixture_arguments, directory_factory

    args = fixture_arguments(tmp_path)
    args.output_upset_r_dir = str(tmp_path / "upsets")
    payload = execute_merge(args, directory_factory)
    hashes = payload["upset_canonical_material"]["input_hashes"]
    assert hashes["mucp_reporting_policy_sha256"] == sha256(
        Path("survey-mappings/mucp_reporting_policy.json").read_bytes()).hexdigest()
    assert hashes["report_presentation_sha256"] == sha256(
        Path("survey-mappings/so2_mucp_report_presentation.json").read_bytes()).hexdigest()
    original = Path(args.output_json).read_bytes()
    bundle = Path(args.output_upset_r_dir)
    incoming = json.loads((bundle / "input-manifest.json").read_text())
    args.output_upset_r_dir = None
    args.upset_assets_dir = str(bundle)
    args.overwrite = True

    with pytest.raises(InputError, match="manifest"):
        execute_merge(args, directory_factory)
    assert Path(args.output_json).read_bytes() == original
    (bundle / "output-manifest.json").write_text(json.dumps({"bundle_version": "1",
        "canonical_sha256": incoming["canonical_sha256"], "outputs": {}}))
    changed_policy = {**payload["upset_canonical_material"], "input_hashes": {
        **hashes, "mucp_reporting_policy_sha256": "0" * 64}}
    from so2_descriptive_upsets import validate_matrix_upset_bundle
    with pytest.raises(InputError, match="hash mismatch"):
        validate_matrix_upset_bundle(payload["upset_matrices"], changed_policy, bundle)
    changed_presentation = {**payload["upset_canonical_material"], "input_hashes": {
        **hashes, "report_presentation_sha256": "0" * 64}}
    with pytest.raises(InputError, match="hash mismatch"):
        validate_matrix_upset_bundle(payload["upset_matrices"], changed_presentation, bundle)
    (bundle / "output-manifest.json").write_text(json.dumps({"bundle_version": "1",
        "canonical_sha256": "0" * 64, "outputs": {}}))
    with pytest.raises(InputError, match="hash mismatch"):
        execute_merge(args, directory_factory)
    assert Path(args.output_json).read_bytes() == original
    assert incoming["canonical_sha256"] != "0" * 64
def test_reused_so2_heatmap_interpretation_uses_unique_biobanks():
    """Adapt the legacy interpretation unit along with its new cohort denominator.

    Returns:
        None. Combined heatmap captions cannot describe raw submitted response rows.
    """
    from pathlib import Path
    from survey_descriptive import reviewed_so2_heatmaps
    definitions = reviewed_so2_heatmaps(Path("survey-mappings/so2_2025_association_heatmaps.json"))
    assert all("submitted response rows" not in item["interpretation"] for item in definitions)
