"""Tests for deterministic fact-sheet emulation analysis and review packets."""

import json

import pytest

from fact_sheet_emulation import (
    analyze_collection_records,
    build_ai_review_packet,
    render_ai_review_markdown,
)


PARENT_ID = "bbmri-eric:ID:AT_MUG:collection:FFPEblocksCollection"
BIOBANK_ID = "bbmri-eric:ID:AT_MUG"


def _collection(collection_id, name, **values):
    collection = {
        "id": collection_id,
        "name": name,
        "biobank": {"id": values.pop("biobank_id", BIOBANK_ID)},
        "country": values.pop("country", "AT"),
        "contact": {"id": "contact-1"},
        "location": "Graz",
        "license": "https://example.test/license",
        "storage_temperatures": ["temperatureRoom"],
        "type": ["SAMPLE", "POPULATION_BASED"],
        "materials": ["TISSUE_PARAFFIN_EMBEDDED"],
    }
    collection.update(values)
    return collection


def _at_anatomy_records():
    parent = _collection(
        PARENT_ID,
        "FFPE Blocks Collection",
        size=100,
        diagnosis_available=[{"name": "urn:miriam:icd:C50"}],
        body_part_examined=["T-28000", "T-04000"],
    )
    children = [
        _collection(
            f"{PARENT_ID}:1",
            "FFPE blocks Collection - Breast",
            parent_collection={"id": PARENT_ID},
            body_part_examined=["T-28000"],
            type=["SAMPLE", "POPULATION_BASED", "IMAGE"],
            size=40,
        ),
        _collection(
            f"{PARENT_ID}:2",
            "FFPE blocks Collection - Lymphatic system",
            parent_collection={"id": PARENT_ID},
            body_part_examined=["T-04000"],
            type=["SAMPLE", "POPULATION_BASED", "IMAGE"],
            size=35,
        ),
        _collection(
            f"{PARENT_ID}:3",
            "FFPE blocks Collection - Bones",
            parent_collection={"id": PARENT_ID},
            size=25,
        ),
    ]
    return [parent, *children]


def test_sibling_anatomy_family_is_high_confidence_but_not_currently_representable():
    analysis = analyze_collection_records(_at_anatomy_records())

    assert len(analysis["candidate_families"]) == 1
    family = analysis["candidate_families"][0]
    assert family["family_kind"] == "siblings"
    assert family["target_collection_id"] == PARENT_ID
    assert family["emulation_confidence"] == "high"
    assert family["operational_conflict_count"] == 0

    anatomy = next(
        row
        for row in analysis["dimension_candidates"]
        if row["dimension"] == "anatomical_site"
    )
    assert anatomy["classification"] == "existing_directory_attribute"
    assert anatomy["representability"] == "future_fact_dimension_required"
    assert anatomy["member_coverage"] == 3
    assert anatomy["structured_member_coverage"] == 2

    values = [
        row
        for row in analysis["dimension_values"]
        if row["dimension"] == "anatomical_site"
    ]
    assert len(values) == 3
    assert {row["extraction_method"] for row in values} == {
        "structured_field",
        "name_suffix",
    }

    migration = analysis["migration_mapping"][0]
    assert migration["readiness"] == "future_dimension_required"
    assert "unsupported_fact_dimension:anatomical_site" in migration["blockers"]

    assert analysis["proposed_facts"] == []
    assert migration["target_total_evidence_source"] == "target_collection_metadata"


def test_at_mug_regression_shape_keeps_71_anatomy_members_and_31_structured_values():
    parent = _collection(
        PARENT_ID,
        "FFPE Blocks Collection",
        size=5_471_431,
        diagnosis_available=[
            {"name": "urn:miriam:icd:C50"},
            {"name": "urn:miriam:icd:C64"},
        ],
    )
    children = []
    for index in range(71):
        values = {
            "parent_collection": {"id": PARENT_ID},
            "size": index + 1,
        }
        if index < 31:
            values["body_part_examined"] = [f"T-{index:05d}"]
            values["type"] = ["SAMPLE", "POPULATION_BASED", "IMAGE"]
        children.append(
            _collection(
                f"{PARENT_ID}:{index}",
                f"FFPE blocks Collection - Organ {index}",
                **values,
            )
        )

    analysis = analyze_collection_records([parent, *children])
    family = analysis["candidate_families"][0]
    anatomy = next(
        row
        for row in analysis["dimension_candidates"]
        if row["dimension"] == "anatomical_site"
    )
    anatomy_values = [
        row
        for row in analysis["dimension_values"]
        if row["dimension"] == "anatomical_site"
    ]

    assert family["member_count"] == 71
    assert family["emulation_confidence"] == "high"
    assert anatomy["member_coverage"] == 71
    assert anatomy["structured_member_coverage"] == 31
    assert sum(row["extraction_method"] == "name_suffix" for row in anatomy_values) == 40
    assert analysis["migration_mapping"][0]["readiness"] == "future_dimension_required"
    assert analysis["proposed_facts"] == []


def test_image_type_added_with_body_part_is_not_an_operational_conflict():
    analysis = analyze_collection_records(_at_anatomy_records())

    type_comparison = next(
        row
        for row in analysis["field_comparisons"]
        if row["field"] == "type"
    )
    assert type_comparison["status"] == "same"
    assert type_comparison["normalization"] == "ignored_schema_coupled_IMAGE"


def test_supported_material_partition_previews_all_but_one_star_rows_without_summing():
    parent_id = "bbmri-eric:ID:CZ_BB1:collection:parent"
    parent = _collection(parent_id, "Material collection", country="CZ", size=999)
    children = [
        _collection(
            f"{parent_id}:serum",
            "Material collection - Serum",
            country="CZ",
            parent_collection={"id": parent_id},
            materials=["SERUM"],
            size=60,
            number_of_donors=40,
        ),
        _collection(
            f"{parent_id}:dna",
            "Material collection - DNA",
            country="CZ",
            parent_collection={"id": parent_id},
            materials=["DNA"],
            size=50,
            number_of_donors=35,
        ),
    ]

    analysis = analyze_collection_records([parent, *children])

    rows = analysis["proposed_facts"]
    assert len(rows) == 2
    assert {row["sample_type"] for row in rows} == {"SERUM", "DNA"}
    assert {row["row_kind"] for row in rows} == {"all_but_one_star"}
    assert {row["number_of_samples"] for row in rows} == {60, 50}
    assert {row["number_of_donors"] for row in rows} == {40, 35}
    assert analysis["migration_mapping"][0]["readiness"] == "ready_current_fact_schema"
    assert (
        analysis["migration_mapping"][0]["target_total_evidence_source"]
        == "target_collection_metadata"
    )


def test_multiple_supported_dimensions_produce_independent_all_but_one_star_previews():
    parent_id = "bbmri-eric:ID:CZ_BB1:collection:two-dimensions"
    parent = _collection(parent_id, "Partition", country="CZ", size=30)
    children = [
        _collection(
            f"{parent_id}:1",
            "Partition - Female serum",
            country="CZ",
            parent_collection={"id": parent_id},
            materials=["SERUM"],
            sex=["FEMALE"],
            size=10,
        ),
        _collection(
            f"{parent_id}:2",
            "Partition - Male DNA",
            country="CZ",
            parent_collection={"id": parent_id},
            materials=["DNA"],
            sex=["MALE"],
            size=20,
        ),
    ]

    analysis = analyze_collection_records([parent, *children])

    rows = analysis["proposed_facts"]
    assert len(rows) == 4
    assert {row["row_kind"] for row in rows} == {"all_but_one_star"}
    assert {(row["sex"], row["sample_type"]) for row in rows} == {
        ("FEMALE", "*"),
        ("MALE", "*"),
        ("*", "SERUM"),
        ("*", "DNA"),
    }
    assert all(row["number_of_samples"] in {10, 20} for row in rows)
    expected_counts = {
        f"{parent_id}:1": 10,
        f"{parent_id}:2": 20,
    }
    assert all(
        row["number_of_samples"] == expected_counts[row["source_collection_id"]]
        for row in rows
    )
    assert {
        row["source_collection_id"]
        for row in rows
    } == set(expected_counts)


def test_repeated_top_level_name_can_be_high_confidence_but_oom_blocks_migration():
    records = [
        _collection(
            "bbmri-eric:ID:UK_BB1:collection:1",
            "Legacy collection",
            biobank_id="bbmri-eric:ID:UK_BB1",
            country="UK",
            order_of_magnitude="4",
        ),
        _collection(
            "bbmri-eric:ID:UK_BB1:collection:2",
            "Legacy collection",
            biobank_id="bbmri-eric:ID:UK_BB1",
            country="UK",
            order_of_magnitude="5",
        ),
    ]

    analysis = analyze_collection_records(records)

    family = analysis["candidate_families"][0]
    assert family["family_kind"] == "top_level_same_name"
    assert family["emulation_confidence"] == "high"
    assert family["target_collection_id"] == ""
    migration = analysis["migration_mapping"][0]
    assert migration["readiness"] == "blocked"
    assert "missing_exact_counts" in migration["blockers"]
    assert "target_collection_required" in migration["blockers"]
    assert "ambiguous_partition_dimension" in migration["blockers"]


def test_top_level_structured_dimension_suffixes_form_one_conservative_family():
    records = [
        _collection(
            "serum",
            "Legacy samples - SERUM",
            materials=["SERUM"],
            size=10,
        ),
        _collection(
            "dna",
            "Legacy samples - DNA",
            materials=["DNA"],
            size=20,
        ),
    ]

    analysis = analyze_collection_records(records, scope="top-level")

    family = analysis["candidate_families"][0]
    assert family["family_kind"] == "top_level_dimension_suffix"
    assert family["base_name"] == "Legacy samples"
    assert family["target_collection_id"] == ""
    assert {row["sample_type"] for row in analysis["proposed_facts"]} == {
        "SERUM",
        "DNA",
    }
    assert {row["row_kind"] for row in analysis["proposed_facts"]} == {
        "all_but_one_star"
    }
    assert all(
        row["target_collection_id"] == ""
        for row in analysis["proposed_facts"]
    )
    assert "target_collection_required" in analysis["migration_mapping"][0]["blockers"]


def test_top_level_dimension_suffix_family_reuses_unique_umbrella_target():
    records = [
        _collection("umbrella", "Legacy samples", size=30),
        _collection(
            "serum",
            "Legacy samples - SERUM",
            materials=["SERUM"],
            size=10,
        ),
        _collection(
            "dna",
            "Legacy samples - DNA",
            materials=["DNA"],
            size=20,
        ),
    ]

    analysis = analyze_collection_records(records, scope="top-level")

    assert len(analysis["candidate_families"]) == 1
    assert analysis["candidate_families"][0]["target_collection_id"] == "umbrella"
    assert analysis["migration_mapping"][0]["target_action"] == "reuse_existing_umbrella"
    assert {
        row["source_collection_id"]
        for row in analysis["proposed_facts"]
        if row["row_kind"] == "all_but_one_star"
    } == {"serum", "dna"}


def test_different_top_level_names_are_not_grouped_only_by_biobank():
    records = [
        _collection("one", "Blood collection"),
        _collection("two", "Tumour collection"),
    ]

    assert analyze_collection_records(records)["candidate_families"] == []


def test_operational_conflict_is_reported_and_blocks_migration():
    parent_id = "parent"
    parent = _collection(parent_id, "Parent", size=20)
    first = _collection(
        "first",
        "Parent - A",
        parent_collection={"id": parent_id},
        size=10,
        sop=["sop-a"],
    )
    second = _collection(
        "second",
        "Parent - B",
        parent_collection={"id": parent_id},
        size=10,
        sop=["sop-b"],
    )

    analysis = analyze_collection_records([parent, first, second])

    family = analysis["candidate_families"][0]
    assert family["operational_conflict_count"] == 1
    assert family["emulation_confidence"] == "low"
    assert "operational_conflicts:sop" in analysis["migration_mapping"][0]["blockers"]


def test_missing_operational_value_is_unknown_not_a_conflict():
    parent_id = "parent"
    parent = _collection(parent_id, "Parent", size=20)
    first = _collection(
        "first",
        "Parent - A",
        parent_collection={"id": parent_id},
        size=10,
        sop=["sop-a"],
    )
    second = _collection(
        "second",
        "Parent - B",
        parent_collection={"id": parent_id},
        size=10,
    )

    analysis = analyze_collection_records([parent, first, second])

    comparison = next(
        row for row in analysis["field_comparisons"] if row["field"] == "sop"
    )
    assert comparison["status"] == "unknown"
    assert analysis["candidate_families"][0]["operational_conflict_count"] == 0
    assert analysis["migration_mapping"][0]["readiness"] == "blocked"
    assert "unresolved_operational_fields:sop" in analysis["migration_mapping"][0]["blockers"]


def test_missing_critical_operational_metadata_blocks_migration_previews():
    parent_id = "parent"
    records = [
        {"id": parent_id, "name": "Parent", "biobank": {"id": BIOBANK_ID}, "size": 20},
        {
            "id": "first",
            "name": "Parent - SERUM",
            "biobank": {"id": BIOBANK_ID},
            "parent_collection": {"id": parent_id},
            "materials": ["SERUM"],
            "size": 10,
        },
        {
            "id": "second",
            "name": "Parent - DNA",
            "biobank": {"id": BIOBANK_ID},
            "parent_collection": {"id": parent_id},
            "materials": ["DNA"],
            "size": 10,
        },
    ]

    analysis = analyze_collection_records(records)

    migration = analysis["migration_mapping"][0]
    assert migration["readiness"] == "blocked"
    assert "unresolved_operational_fields:contact,license,storage_temperatures,type" in migration["blockers"]
    assert [row for row in analysis["proposed_facts"] if row["row_kind"] != "all_star"] == []


def test_network_and_networks_aliases_are_compared_as_operational_membership():
    parent_id = "parent"
    parent = _collection(parent_id, "Parent", size=20)
    first = _collection(
        "first",
        "Parent - SERUM",
        parent_collection={"id": parent_id},
        materials=["SERUM"],
        networks=[{"id": "network-a"}],
        size=10,
    )
    second = _collection(
        "second",
        "Parent - DNA",
        parent_collection={"id": parent_id},
        materials=["DNA"],
        network=[{"id": "network-b"}],
        size=10,
    )

    analysis = analyze_collection_records([parent, first, second])

    assert "network_membership" in analysis["candidate_families"][0]["operational_conflict_fields"]
    assert analysis["migration_mapping"][0]["readiness"] == "blocked"


def test_parent_operational_conflict_blocks_reuse_as_migration_target():
    parent_id = "parent"
    parent = _collection(parent_id, "Parent", size=20, license="parent-license")
    children = [
        _collection(
            "first",
            "Parent - SERUM",
            parent_collection={"id": parent_id},
            materials=["SERUM"],
            size=10,
        ),
        _collection(
            "second",
            "Parent - DNA",
            parent_collection={"id": parent_id},
            materials=["DNA"],
            size=10,
        ),
    ]

    analysis = analyze_collection_records([parent, *children])

    migration = analysis["migration_mapping"][0]
    assert migration["readiness"] == "blocked"
    assert "target_operational_conflicts:license" in migration["blockers"]


def test_unrelated_sibling_names_without_structured_variation_get_no_migration_advice():
    parent_id = "parent"
    parent = _collection(parent_id, "Administrative parent", size=20)
    children = [
        _collection("first", "Specimens 2020", parent_collection={"id": parent_id}, size=10),
        _collection("second", "Long follow-up", parent_collection={"id": parent_id}, size=10),
    ]

    analysis = analyze_collection_records([parent, *children])

    family = analysis["candidate_families"][0]
    assert family["deterministic_classification"] == "operationally_distinct"
    assert family["emulation_confidence"] == "low"
    assert "insufficient_conceptual_identity" in analysis["migration_mapping"][0]["blockers"]
    assert analysis["proposed_facts"] == []


def test_structured_variation_alone_does_not_make_unrelated_siblings_one_collection():
    parent_id = "parent"
    parent = _collection(parent_id, "Administrative parent", size=20)
    children = [
        _collection(
            "first",
            "Prospective cancer study",
            parent_collection={"id": parent_id},
            materials=["SERUM"],
            size=10,
        ),
        _collection(
            "second",
            "Population reference samples",
            parent_collection={"id": parent_id},
            materials=["DNA"],
            size=10,
        ),
    ]

    analysis = analyze_collection_records([parent, *children])

    family = analysis["candidate_families"][0]
    migration = analysis["migration_mapping"][0]
    assert family["deterministic_classification"] == "operationally_distinct"
    assert "insufficient_conceptual_identity" in migration["blockers"]
    assert analysis["proposed_facts"] == []


def test_conflicting_structured_purpose_is_an_operational_blocker():
    parent_id = "parent"
    parent = _collection(parent_id, "Parent", size=20, purpose="research")
    children = [
        _collection(
            "first",
            "Parent - SERUM",
            parent_collection={"id": parent_id},
            materials=["SERUM"],
            purpose="research",
            size=10,
        ),
        _collection(
            "second",
            "Parent - DNA",
            parent_collection={"id": parent_id},
            materials=["DNA"],
            purpose="diagnostics",
            size=10,
        ),
    ]

    analysis = analyze_collection_records([parent, *children])

    migration = analysis["migration_mapping"][0]
    assert "operational_conflicts:purpose" in migration["blockers"]
    assert migration["readiness"] == "blocked"


def test_conflicting_descriptions_require_review_and_block_source_fact_previews():
    parent_id = "parent"
    parent = _collection(parent_id, "Parent", size=20)
    children = [
        _collection(
            "first",
            "Parent - SERUM",
            parent_collection={"id": parent_id},
            materials=["SERUM"],
            description="Prospective cancer study; protocol A",
            size=10,
        ),
        _collection(
            "second",
            "Parent - DNA",
            parent_collection={"id": parent_id},
            materials=["DNA"],
            description="Population reference samples; protocol B",
            size=10,
        ),
    ]

    analysis = analyze_collection_records([parent, *children])

    migration = analysis["migration_mapping"][0]
    assert "context_conflicts:description" in migration["blockers"]
    assert migration["readiness"] == "blocked"
    assert [
        row for row in analysis["proposed_facts"] if row["row_kind"] != "all_star"
    ] == []


def test_multivalued_supported_dimension_blocks_fact_preview():
    parent_id = "parent"
    parent = _collection(parent_id, "Parent", size=20)
    first = _collection(
        "first",
        "Parent - A",
        parent_collection={"id": parent_id},
        materials=["SERUM", "DNA"],
        size=10,
    )
    second = _collection(
        "second",
        "Parent - B",
        parent_collection={"id": parent_id},
        materials=["PLASMA"],
        size=10,
    )

    analysis = analyze_collection_records([parent, first, second])

    assert "multi_valued_dimension:sample_type" in analysis["migration_mapping"][0]["blockers"]
    assert [row for row in analysis["proposed_facts"] if row["row_kind"] != "all_star"] == []


def test_identical_multivalued_characterization_is_not_a_dimension():
    parent_id = "parent"
    parent = _collection(parent_id, "Parent", size=20)
    children = [
        _collection(
            "first",
            "Parent - A",
            parent_collection={"id": parent_id},
            data_categories=["MEDICAL_RECORDS", "BIOLOGICAL_SAMPLES"],
            size=10,
        ),
        _collection(
            "second",
            "Parent - B",
            parent_collection={"id": parent_id},
            data_categories=["BIOLOGICAL_SAMPLES", "MEDICAL_RECORDS"],
            size=10,
        ),
    ]

    analysis = analyze_collection_records([parent, *children])

    assert all(
        row["dimension"] != "data_category"
        for row in analysis["dimension_candidates"]
    )


def test_existing_target_all_star_is_retained_as_evidence_not_proposed():
    records = _at_anatomy_records()
    facts = {
        PARENT_ID: [
            {
                "id": "fact-total",
                "sex": "*",
                "age_range": "*",
                "sample_type": "*",
                "disease": {"name": "*"},
                "number_of_samples": 98,
            }
        ]
    }

    analysis = analyze_collection_records(records, facts_by_collection=facts)

    assert analysis["proposed_facts"] == []
    assert (
        analysis["migration_mapping"][0]["target_total_evidence_source"]
        == "existing_target_all_star"
    )
    assert "target_all_star_samples_metadata_mismatch" in analysis["migration_mapping"][0]["blockers"]


def test_multiple_target_all_star_rows_block_migration():
    records = _at_anatomy_records()
    all_star = {
        "sex": "*",
        "age_range": "*",
        "sample_type": "*",
        "disease": {"name": "*"},
        "number_of_samples": 100,
    }
    facts = {
        PARENT_ID: [
            {"id": "fact-total-1", **all_star},
            {"id": "fact-total-2", **all_star},
        ]
    }

    analysis = analyze_collection_records(records, facts_by_collection=facts)

    assert "multiple_target_all_star_rows" in analysis["migration_mapping"][0]["blockers"]
    assert analysis["migration_mapping"][0]["readiness"] == "blocked"
    assert analysis["proposed_facts"] == []


def test_sibling_family_cannot_hide_cross_country_operational_conflict():
    parent_id = "parent"
    records = [
        _collection(parent_id, "Parent", size=20),
        _collection("first", "Parent - A", parent_collection={"id": parent_id}, size=10),
        _collection(
            "second",
            "Parent - B",
            country="DE",
            parent_collection={"id": parent_id},
            size=10,
        ),
    ]

    analysis = analyze_collection_records(records)

    assert "country" in analysis["candidate_families"][0]["operational_conflict_fields"]
    assert analysis["migration_mapping"][0]["readiness"] == "blocked"


def test_ai_review_packet_is_self_contained_and_json_serializable():
    analysis = analyze_collection_records(_at_anatomy_records())

    packet = build_ai_review_packet(analysis)
    encoded = json.dumps(packet)
    markdown = render_ai_review_markdown(packet)

    assert packet["schema_version"] == "1.2"
    assert any(
        "independent all-but-one-star marginals" in instruction
        for instruction in packet["instructions"]
    )
    assert packet["cases"]
    assert "Do not sum" in " ".join(packet["instructions"])
    assert packet["expected_output_schema"]["required"] == ["reviews"]
    review_required = packet["expected_output_schema"]["properties"]["reviews"]["items"]["required"]
    assert {"migration_readiness", "operational_boundary_evidence", "unsupported_dimensions"}.issubset(review_required)
    assert PARENT_ID in encoded
    assert "## Expected output" in markdown
    assert "## Cases" in markdown
    assert "anatomical_site" in markdown


def test_ai_review_packet_uses_strict_json_null_for_nan_counts():
    records = _at_anatomy_records()
    records[1]["size"] = float("nan")
    analysis = analyze_collection_records(records)

    packet = build_ai_review_packet(analysis)
    encoded = json.dumps(packet, allow_nan=False)

    assert "NaN" not in encoded
    assert packet["cases"][0]["source_collections"][0]["size"] is None


def _diagnosis(code):
    return [{"name": f"urn:miriam:icd:{code}"}]


def _family_for_collection_ids(analysis, collection_ids):
    expected = set(collection_ids)
    matches = [
        family
        for family in analysis["candidate_families"]
        if expected.issubset(set(family["source_collection_ids"]))
    ]
    assert len(matches) == 1
    return matches[0]


def _description_evidence(analysis, family):
    comparison = next(
        row
        for row in analysis["field_comparisons"]
        if row["family_id"] == family["family_id"]
        and row["field"] == "description"
    )
    return comparison["description_evidence"]


def _diagnosis_pair(
    biobank_id,
    first_id,
    second_id,
    *,
    first_name="Cohort alpha",
    second_name="Cohort beta",
    first_diagnosis="C50",
    second_diagnosis="C64",
    first_description="DNA samples from a shared cohort.",
    second_description="DNA samples from a shared cohort.",
    country="ES",
):
    common = {
        "biobank_id": biobank_id,
        "country": country,
        "size": 10,
        "number_of_donors": 8,
        "description": first_description,
    }
    first = _collection(
        first_id,
        first_name,
        **common,
        diagnosis_available=_diagnosis(first_diagnosis),
    )
    second = _collection(
        second_id,
        second_name,
        **{**common, "description": second_description},
        diagnosis_available=_diagnosis(second_diagnosis),
    )
    return [first, second]


def _sibling_pair(
    label,
    *,
    first_description,
    second_description,
    first_diagnosis="C50",
    second_diagnosis="C64",
    first_values=None,
    second_values=None,
):
    biobank_id = f"bbmri-eric:ID:SYN_{label.upper()}"
    parent_id = f"{biobank_id}:collection:umbrella"
    parent = _collection(
        parent_id,
        f"{label} umbrella",
        biobank_id=biobank_id,
        country="DE",
        size=20,
        description="Umbrella collection.",
    )
    first = _collection(
        f"{parent_id}:1",
        f"{label} - first",
        biobank_id=biobank_id,
        country="DE",
        parent_collection={"id": parent_id},
        size=10,
        number_of_donors=8,
        description=first_description,
        diagnosis_available=_diagnosis(first_diagnosis),
        **(first_values or {}),
    )
    second = _collection(
        f"{parent_id}:2",
        f"{label} - second",
        biobank_id=biobank_id,
        country="DE",
        parent_collection={"id": parent_id},
        size=10,
        number_of_donors=8,
        description=second_description,
        diagnosis_available=_diagnosis(second_diagnosis),
        **(second_values or {}),
    )
    return [parent, first, second]


def test_exact_non_dimension_equality_discovers_diagnosis_partition():
    records = _diagnosis_pair(
        "bbmri-eric:ID:SYN_EXACT",
        "bbmri-eric:ID:SYN_EXACT:collection:alpha",
        "bbmri-eric:ID:SYN_EXACT:collection:beta",
        first_name="Respiratory cohort asthma stratum",
        second_name="Respiratory cohort COPD stratum",
    )

    analysis = analyze_collection_records(records, scope="top-level")

    family = _family_for_collection_ids(analysis, [record["id"] for record in records])
    assert family["discovery_rule"] == "exact_non_dimension_equality"
    assert "exact_non_dimension_equality" in family["identity_evidence"]
    assert any(
        row["dimension"] == "disease"
        for row in analysis["dimension_candidates"]
        if row["family_id"] == family["family_id"]
    )


def test_differently_named_diagnosis_families_use_three_conceptual_anchors():
    cases = [
        (
            _diagnosis_pair(
                "bbmri-eric:ID:SYN_DESCRIPTION",
                "bbmri-eric:ID:SYN_DESCRIPTION:collection:one",
                "bbmri-eric:ID:SYN_DESCRIPTION:collection:two",
                first_name="Case material",
                second_name="Reference material",
                first_description="Samples from the same population cohort.",
                second_description="Samples from the same population cohort.",
            ),
            "informative_identical_description",
        ),
        (
            _diagnosis_pair(
                "bbmri-eric:ID:SYN_ID_SERIES",
                "bbmri-eric:ID:SYN_ID_SERIES:collection:DX-2025-01",
                "bbmri-eric:ID:SYN_ID_SERIES:collection:DX-2025-02",
                first_name="First diagnosis stratum",
                second_name="Second diagnosis stratum",
                first_description="Samples from diagnosis alpha.",
                second_description="Samples from diagnosis beta.",
            ),
            "specific_id_series",
        ),
        (
            _diagnosis_pair(
                "bbmri-eric:ID:SYN_DESCRIPTION_FRAME",
                "bbmri-eric:ID:SYN_DESCRIPTION_FRAME:collection:one",
                "bbmri-eric:ID:SYN_DESCRIPTION_FRAME:collection:two",
                first_name="Rare disease set one",
                second_name="Rare disease set two",
                first_description=(
                    "DNA samples obtained from patients with Alpha syndrome."
                ),
                second_description=(
                    "DNA samples obtained from patients with Beta syndrome."
                ),
            ),
            "diagnosis_derived_description_frame",
        ),
    ]

    for records, expected_rule in cases:
        analysis = analyze_collection_records(records, scope="top-level")
        family = _family_for_collection_ids(
            analysis, [record["id"] for record in records]
        )
        assert family["discovery_rule"] == expected_rule

    frame_analysis = analyze_collection_records(cases[2][0], scope="top-level")
    frame_family = _family_for_collection_ids(
        frame_analysis, [record["id"] for record in cases[2][0]]
    )
    assert _description_evidence(frame_analysis, frame_family)["classification"] == (
        "dimension_derived_difference"
    )


@pytest.mark.parametrize(
    ("label", "first_description", "second_description", "boundary_category", "token"),
    [
        (
            "phase",
            "The prospective cohort phase 1 was acquired in 2018.",
            "The prospective cohort phase 2 was acquired in 2020.",
            "phase",
            "phase",
        ),
        (
            "reexamination",
            "Samples came from the baseline examination.",
            "Samples came from the ongoing re-examination.",
            "re-examination",
            "re-examination",
        ),
        (
            "project",
            "Samples were collected for Project Alpha.",
            "Samples were collected for Project Beta.",
            "project",
            "project",
        ),
        (
            "autopsy",
            "Post-mortem autopsy tissue was collected after death.",
            "Living donor tissue was collected during routine care.",
            "autopsy",
            "autopsy",
        ),
        (
            "timepoint",
            "Samples were collected at the baseline visit.",
            "Samples were collected at the 12-month follow-up visit.",
            "timepoint",
            "follow-up",
        ),
    ],
)
def test_description_boundary_markers_prevent_emulation(
    label,
    first_description,
    second_description,
    boundary_category,
    token,
):
    records = _sibling_pair(
        label,
        first_description=first_description,
        second_description=second_description,
    )
    analysis = analyze_collection_records(records)
    family = _family_for_collection_ids(
        analysis, [record["id"] for record in records[1:]]
    )

    assert family["deterministic_classification"] != "likely_emulation"
    evidence = _description_evidence(analysis, family)
    assert evidence["classification"] == "operational_boundary_difference"
    assert evidence["boundary_category"] == boundary_category
    assert evidence["snippets"]
    assert all(len(item["snippet"]) <= 240 for item in evidence["snippets"])
    assert token in json.dumps(evidence, ensure_ascii=True).casefold()


def test_placeholder_description_is_not_a_conceptual_family_anchor():
    records = _sibling_pair(
        "placeholder",
        first_description="To be provided",
        second_description="To be provided",
    )
    analysis = analyze_collection_records(records)
    family = _family_for_collection_ids(
        analysis, [record["id"] for record in records[1:]]
    )

    assert family["deterministic_classification"] != "likely_emulation"
    assert family["requires_external_review"]
    assert _description_evidence(analysis, family)["classification"] == (
        "placeholder_uninformative"
    )


def test_scientific_question_catalogue_is_not_fact_sheet_emulation():
    records = _sibling_pair(
        "scientific_questions",
        first_description="Structured clinical variable catalogue.",
        second_description="Structured clinical variable catalogue.",
        first_values={"data_categories": ["QUESTIONNAIRE"]},
        second_values={"data_categories": ["MEDICAL_RECORDS"]},
    )
    analysis = analyze_collection_records(records)
    family = _family_for_collection_ids(
        analysis, [record["id"] for record in records[1:]]
    )

    assert family["deterministic_classification"] == "scientific_question_catalogue"
    assert not [
        row
        for row in analysis["proposed_facts"]
        if row["family_id"] == family["family_id"] and row["row_kind"] != "all_star"
    ]


def test_imaging_body_region_family_is_review_only_without_operational_proof():
    biobank_id = "bbmri-eric:ID:SYN_BCU"
    records = [
        _collection(
            f"{biobank_id}:collection:brain",
            "Imaging archive - Brain",
            biobank_id=biobank_id,
            country="IT",
            body_part_examined=["Brain"],
            type=["SAMPLE", "IMAGE"],
            description="Imaging data from the repository.",
            size=10,
        ),
        _collection(
            f"{biobank_id}:collection:abdomen",
            "Imaging archive - Abdomen",
            biobank_id=biobank_id,
            country="IT",
            body_part_examined=["Abdomen"],
            type=["SAMPLE", "IMAGE"],
            description="Imaging data from the repository.",
            size=10,
        ),
    ]

    analysis = analyze_collection_records(records, scope="top-level")
    family = _family_for_collection_ids(
        analysis, [record["id"] for record in records]
    )

    assert family["review_only"] is True
    assert family["deterministic_classification"] == "review_only"
    assert family["requires_external_review"]
    assert any(
        row["dimension"] == "anatomical_site"
        for row in analysis["dimension_candidates"]
        if row["family_id"] == family["family_id"]
    )


def test_multivalued_diagnosis_blocks_fact_preview():
    records = _sibling_pair(
        "multivalued_diagnosis",
        first_description="Samples from a shared cohort.",
        second_description="Samples from a shared cohort.",
    )
    records[1]["diagnosis_available"] = _diagnosis("C50") + _diagnosis("C18")
    analysis = analyze_collection_records(records)
    family = _family_for_collection_ids(
        analysis, [record["id"] for record in records[1:]]
    )
    migration = next(
        row
        for row in analysis["migration_mapping"]
        if row["family_id"] == family["family_id"]
    )

    assert "multi_valued_dimension:disease" in migration["blockers"]
    assert not [
        row
        for row in analysis["proposed_facts"]
        if row["family_id"] == family["family_id"] and row["row_kind"] != "all_star"
    ]


def test_coarse_diagnosis_mapping_blocks_fact_preview():
    records = _sibling_pair(
        "coarse_diagnosis",
        first_description="Samples from a shared cohort.",
        second_description="Samples from a shared cohort.",
        first_diagnosis="C00-C99",
        second_diagnosis="D00-D48",
    )
    analysis = analyze_collection_records(records)
    family = _family_for_collection_ids(
        analysis, [record["id"] for record in records[1:]]
    )
    migration = next(
        row
        for row in analysis["migration_mapping"]
        if row["family_id"] == family["family_id"]
    )

    assert "coarse_diagnosis_mapping" in migration["blockers"]
    assert not [
        row
        for row in analysis["proposed_facts"]
        if row["family_id"] == family["family_id"] and row["row_kind"] != "all_star"
    ]


def test_negated_or_control_diagnosis_blocks_fact_preview():
    records = _sibling_pair(
        "negated_control_diagnosis",
        first_description="Participants diagnosed with breast cancer.",
        second_description="Healthy controls without a diagnosis were enrolled.",
        first_diagnosis="C50",
        second_diagnosis="Z00.6",
    )
    records[1]["name"] = "Negated/control cohort - healthy controls"
    analysis = analyze_collection_records(records)
    family = _family_for_collection_ids(
        analysis, [record["id"] for record in records[1:]]
    )
    migration = next(
        row
        for row in analysis["migration_mapping"]
        if row["family_id"] == family["family_id"]
    )

    assert "negated_or_control_diagnosis" in migration["blockers"]
    assert not [
        row
        for row in analysis["proposed_facts"]
        if row["family_id"] == family["family_id"] and row["row_kind"] != "all_star"
    ]


def test_exact_equivalence_also_discovers_material_partition():
    biobank_id = "bbmri-eric:ID:SYN_MATERIAL_EQUIVALENCE"
    records = [
        _collection(
            f"{biobank_id}:collection:serum",
            "Legacy inventory serum",
            biobank_id=biobank_id,
            country="AT",
            materials=["SERUM"],
            description="Serum inventory stratum.",
            size=10,
        ),
        _collection(
            f"{biobank_id}:collection:dna",
            "Legacy inventory DNA",
            biobank_id=biobank_id,
            country="AT",
            materials=["DNA"],
            description="DNA inventory stratum.",
            size=20,
        ),
    ]

    analysis = analyze_collection_records(records, scope="top-level")

    family = _family_for_collection_ids(analysis, [record["id"] for record in records])
    assert family["discovery_rule"] == "exact_non_dimension_equality"
    assert any(
        row["dimension"] == "sample_type"
        for row in analysis["dimension_candidates"]
        if row["family_id"] == family["family_id"]
    )


def test_copied_description_with_only_age_difference_is_not_enough_to_group_projects():
    biobank_id = "bbmri-eric:ID:SYN_PROJECTS"
    records = [
        _collection(
            f"{biobank_id}:collection:alpha",
            "SANALZ research cohort",
            biobank_id=biobank_id,
            description="Samples collected according to the institutional protocol.",
            age_low=18,
        ),
        _collection(
            f"{biobank_id}:collection:beta",
            "LIQDEM scientific project",
            biobank_id=biobank_id,
            description="Samples collected according to the institutional protocol.",
            age_low=65,
        ),
    ]

    assert analyze_collection_records(records, scope="top-level")["candidate_families"] == []


def test_placeholder_description_does_not_anchor_top_level_diagnosis_records():
    records = _diagnosis_pair(
        "bbmri-eric:ID:SYN_PLACEHOLDER_TOP",
        "bbmri-eric:ID:SYN_PLACEHOLDER_TOP:collection:alpha",
        "bbmri-eric:ID:SYN_PLACEHOLDER_TOP:collection:beta",
        first_name="Alpha cases",
        second_name="Beta references",
        first_description="To be provided",
        second_description="To be provided",
    )

    assert analyze_collection_records(records, scope="top-level")["candidate_families"] == []


def test_autopsy_and_living_covid_records_are_operationally_distinct():
    records = _diagnosis_pair(
        "bbmri-eric:ID:SYN_COVID",
        "bbmri-eric:ID:SYN_COVID:collection:autopsy",
        "bbmri-eric:ID:SYN_COVID:collection:positive",
        first_name="COVID autopsy tissues",
        second_name="COVID positive samples",
        first_description="COVID-19 samples collected by the hospital biobank.",
        second_description="COVID-19 samples collected by the hospital biobank.",
    )

    analysis = analyze_collection_records(records, scope="top-level")
    family = _family_for_collection_ids(analysis, [record["id"] for record in records])

    assert family["deterministic_classification"] == "operationally_distinct"
    assert "autopsy" in family["operational_boundary_categories"]


def test_shared_phase_background_is_neutral_boundary_evidence():
    records = _sibling_pair(
        "shared_background",
        first_description="Samples support a shared phase III trial background.",
        second_description="Samples support a shared phase III trial background.",
    )

    analysis = analyze_collection_records(records)
    family = _family_for_collection_ids(
        analysis, [record["id"] for record in records[1:]]
    )

    assert family["operational_boundary_categories"] == []
    assert _description_evidence(analysis, family)["classification"] == "informative_equal"


def test_laboratory_phase_language_abstains_instead_of_becoming_a_boundary():
    records = _sibling_pair(
        "laboratory_phase",
        first_description="The assay was evaluated in laboratory phase 1.",
        second_description="The assay was evaluated in laboratory phase 2.",
    )

    analysis = analyze_collection_records(records)
    family = _family_for_collection_ids(
        analysis, [record["id"] for record in records[1:]]
    )

    assert family["deterministic_classification"] == "review_only"
    assert family["operational_boundary_categories"] == []
    assert _description_evidence(analysis, family)["classification"] == "ambiguous"


def test_duplicate_diagnosis_mapping_blocks_fact_preview():
    records = _sibling_pair(
        "duplicate_diagnosis",
        first_description="Samples from one diagnosis inventory.",
        second_description="Samples from one diagnosis inventory.",
    )
    parent_id = records[0]["id"]
    records.append(
        _collection(
            f"{parent_id}:3",
            "duplicate diagnosis - third",
            biobank_id=records[0]["biobank"]["id"],
            country="DE",
            parent_collection={"id": parent_id},
            size=10,
            number_of_donors=8,
            description="Samples from one diagnosis inventory.",
            diagnosis_available=_diagnosis("C50"),
        )
    )

    analysis = analyze_collection_records(records)
    family = _family_for_collection_ids(
        analysis, [record["id"] for record in records[1:]]
    )
    migration = next(
        row
        for row in analysis["migration_mapping"]
        if row["family_id"] == family["family_id"]
    )

    assert "duplicate_diagnosis_mapping" in migration["blockers"]
    assert not [
        row
        for row in analysis["proposed_facts"]
        if row["family_id"] == family["family_id"] and row["row_kind"] != "all_star"
    ]


def test_variable_catalogue_without_fact_dimension_variation_is_not_discovered():
    biobank_id = "bbmri-eric:ID:SYN_CONCRETE"
    records = [
        _collection(
            f"{biobank_id}:collection:variable-{index}",
            f"Clinical variable {index}",
            biobank_id=biobank_id,
            country="NL",
            materials=["NAV"],
            description="Clinical variable catalogue entry.",
            data_categories=["MEDICAL_RECORDS" if index % 2 else "QUESTIONNAIRE"],
        )
        for index in range(12)
    ]

    assert analyze_collection_records(records, scope="top-level")["candidate_families"] == []


def test_specific_id_series_accepts_meaningful_alphabetic_suffixes():
    biobank_id = "bbmri-eric:ID:SYN_ID_ALPHA"
    records = [
        _collection(
            f"{biobank_id}:collection:AD52_ESA_{suffix}",
            name,
            biobank_id=biobank_id,
            country="ES",
            description=name,
            diagnosis_available=_diagnosis(code),
        )
        for suffix, name, code in (
            ("APSO", "Psoriatic arthritis", "L40.5"),
            ("AR", "Rheumatoid arthritis", "M06.9"),
            ("SPA", "Spondyloarthritis", "M45"),
        )
    ]

    analysis = analyze_collection_records(records, scope="top-level")
    family = _family_for_collection_ids(analysis, [record["id"] for record in records])

    assert family["discovery_rule"] == "specific_id_series"
    assert family["deterministic_classification"] == "likely_emulation"


def test_diagnosis_frame_keeps_with_and_without_control_in_one_family():
    biobank_id = "bbmri-eric:ID:SYN_ARTHRITIS"
    records = []
    for local_id, name, description, diagnoses in (
        (
            "CCA-00027",
            "Rheumatoid arthritis DNA",
            "DNA samples obtained from patients with Rheumatoid arthritis",
            ["M06.9"],
        ),
        (
            "CCA-00028",
            "Ankylosing spondylitis DNA",
            "DNA samples obtained from patients with Ankylosing spondylitis",
            ["M45"],
        ),
        (
            "CCA-00029",
            "Psoriatic arthritis DNA",
            "DNA samples obtained from patients with Psoriatic arthritis",
            ["L40.5"],
        ),
        (
            "CCA-00030",
            "Rheumatoid arthritis, spondylitis and psoriatic arthritis control DNA",
            "DNA samples obtained from patients without Rheumatoid arthritis, Ankylosing spondylitis or psoriatic arthritis",
            ["M06.9", "M45", "L40.5"],
        ),
    ):
        records.append(
            _collection(
                f"{biobank_id}:collection:{local_id}",
                name,
                biobank_id=biobank_id,
                country="ES",
                materials=["DNA"],
                description=description,
                diagnosis_available=[
                    {"name": f"urn:miriam:icd:{code}"} for code in diagnoses
                ],
            )
        )

    analysis = analyze_collection_records(records, scope="top-level")
    family = _family_for_collection_ids(analysis, [record["id"] for record in records])
    migration = next(
        row
        for row in analysis["migration_mapping"]
        if row["family_id"] == family["family_id"]
    )

    assert len(analysis["candidate_families"]) == 1
    assert family["discovery_rule"] == "diagnosis_derived_description_frame"
    assert "negated_or_control_diagnosis" in migration["blockers"]
    assert "multi_valued_dimension:disease" in migration["blockers"]


def test_id_series_does_not_override_different_eligibility_criteria():
    biobank_id = "bbmri-eric:ID:SYN_BIOHELD"
    records = [
        _collection(
            f"{biobank_id}:collection:Bio-HeLD_{suffix}",
            f"Fraunhofer {label} Cohort",
            biobank_id=biobank_id,
            country="DE",
            description=(
                f"Collection from {label} participants. Inclusion criteria are "
                f"diagnosed {label}; exclusion criteria follow protocol {suffix}."
            ),
            diagnosis_available=_diagnosis(code),
        )
        for suffix, label, code in (
            ("Asthma", "asthma", "J45"),
            ("COPD", "COPD", "J44"),
            ("H", "healthy", "Z00"),
        )
    ]

    analysis = analyze_collection_records(records, scope="top-level")
    family = _family_for_collection_ids(analysis, [record["id"] for record in records])

    assert family["discovery_rule"] == "specific_id_series"
    assert family["deterministic_classification"] == "operationally_distinct"
    assert "eligibility" in family["operational_boundary_categories"]


def _material_partition_with_shared_diagnosis():
    parent_id = "bbmri-eric:ID:AT_TEST:collection:shared"
    parent = _collection(
        parent_id,
        "Shared collection",
        size=20,
        diagnosis_available=[{"name": "urn:miriam:icd:C50"}],
    )
    children = [
        _collection(
            f"{parent_id}:{material.casefold()}",
            f"Shared collection - {material}",
            parent_collection={"id": parent_id},
            materials=[material],
            diagnosis_available=[{"name": "urn:miriam:icd:C50"}],
            size=10,
        )
        for material in ("SERUM", "PLASMA")
    ]
    return parent_id, [parent, *children]


def test_shared_diagnosis_does_not_block_material_fact_preview():
    _, records = _material_partition_with_shared_diagnosis()

    analysis = analyze_collection_records(records)
    migration = analysis["migration_mapping"][0]
    source_rows = [
        row
        for row in analysis["proposed_facts"]
        if row["row_kind"] != "all_star"
    ]

    assert "duplicate_diagnosis_mapping" not in migration["blockers"]
    assert migration["readiness"] == "ready_current_fact_schema"
    assert len(source_rows) == 2


def test_target_total_mismatch_blocks_source_fact_previews():
    parent_id, records = _material_partition_with_shared_diagnosis()
    facts = {
        parent_id: [
            {
                "id": "fact-total",
                "sex": "*",
                "age_range": "*",
                "sample_type": "*",
                "disease": {"name": "*"},
                "number_of_samples": 19,
            }
        ]
    }

    analysis = analyze_collection_records(records, facts_by_collection=facts)
    migration = analysis["migration_mapping"][0]

    assert "target_all_star_samples_metadata_mismatch" in migration["blockers"]
    assert migration["readiness"] == "blocked"
    assert analysis["proposed_facts"] == []


def test_ai_review_packet_bounds_large_source_evidence():
    records = _at_anatomy_records()
    records[1]["keywords"] = "x" * 5000

    packet = build_ai_review_packet(analyze_collection_records(records))
    source = next(
        row
        for row in packet["cases"][0]["source_collections"]
        if row["collection_id"] == records[1]["id"]
    )

    assert len(source["keywords"]) <= 1000
    assert "[truncated:" in source["keywords"]
    assert "x" * 1500 not in json.dumps(packet)
    case = packet["cases"][0]
    assert "field_summary" in case
    assert "biobank" in case["field_summary"]["same"]["operational"]
    assert all(
        comparison["status"] != "same"
        and not (
            comparison["status"] == "unknown"
            and comparison["missing_scope"] == "all"
        )
        for comparison in case["field_comparisons"]
    )
    assert all(
        "member_values" not in comparison
        for comparison in case["field_comparisons"]
    )
