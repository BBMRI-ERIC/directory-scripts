from fact_descriptor_sync import build_collection_descriptor_proposal
from check_fix_helpers import build_fact_alignment_fix_proposals


def test_descriptor_proposal_preserves_broader_icd_codes_and_replaces_totals():
    collection = {
        "id": "bbmri-eric:ID:EU_BBMRI-ERIC:collection:CRC-Cohort",
        "diagnosis_available": "urn:miriam:icd:C18,urn:miriam:icd:C19",
        "materials": "",
        "sex": "FEMALE,MALE",
        "size": "10",
        "number_of_donors": "10",
    }
    facts = [
        {
            "id": "f1",
            "sex": "*",
            "age_range": "*",
            "sample_type": "*",
            "disease": {"name": "*"},
            "number_of_samples": 25,
            "number_of_donors": 20,
        },
        {
            "id": "f2",
            "sex": "FEMALE",
            "age_range": "Adult",
            "sample_type": "NAV",
            "disease": {"name": "urn:miriam:icd:C18.0"},
            "number_of_samples": 5,
            "number_of_donors": 4,
        },
        {
            "id": "f3",
            "sex": "MALE",
            "age_range": "Adult",
            "sample_type": "TISSUE_PARAFFIN_EMBEDDED",
            "disease": {"name": "urn:miriam:icd:C19"},
            "number_of_samples": 20,
            "number_of_donors": 16,
        },
    ]

    proposal = build_collection_descriptor_proposal(collection, facts, replace_existing=False)
    proposed = proposal["proposed"]

    assert proposed["diagnosis_available"] == ["urn:miriam:icd:C18", "urn:miriam:icd:C19"]
    assert proposed["materials"] == ["TISSUE_PARAFFIN_EMBEDDED"]
    assert proposed["size"] == 25
    assert proposed["number_of_donors"] == 20


def test_descriptor_proposal_can_replace_existing_multi_value_fields():
    collection = {
        "id": "bbmri-eric:ID:CZ_demo:collection:col1",
        "diagnosis_available": "urn:miriam:icd:C18,urn:miriam:icd:C50",
        "materials": "SERUM",
        "sex": "FEMALE",
    }
    facts = [
        {
            "id": "f1",
            "sex": "*",
            "age_range": "*",
            "sample_type": "*",
            "disease": {"name": "*"},
            "number_of_samples": 1,
            "number_of_donors": 1,
        },
        {
            "id": "f2",
            "sex": "MALE",
            "age_range": "Adult",
            "sample_type": "PLASMA",
            "disease": {"name": "urn:miriam:icd:C18.1"},
            "number_of_samples": 1,
            "number_of_donors": 1,
        },
    ]

    proposal = build_collection_descriptor_proposal(collection, facts, replace_existing=True)
    proposed = proposal["proposed"]

    assert proposed["diagnosis_available"] == ["urn:miriam:icd:C18"]
    assert proposed["materials"] == ["PLASMA"]
    assert proposed["sex"] == ["MALE"]


def test_descriptor_proposal_treats_nan_target_cells_as_missing_values():
    collection = {
        "id": "bbmri-eric:ID:CZ_demo:collection:col1",
        "diagnosis_available": float("nan"),
        "materials": float("nan"),
        "sex": float("nan"),
        "age_low": float("nan"),
        "age_high": float("nan"),
        "age_unit": float("nan"),
    }
    facts = [
        {
            "id": "f1",
            "sex": "MALE",
            "age_range": "Adult",
            "sample_type": "PLASMA",
            "disease": {"name": "urn:miriam:icd:C18.1"},
            "number_of_samples": 1,
            "number_of_donors": 1,
        },
    ]

    proposal = build_collection_descriptor_proposal(collection, facts, replace_existing=False)
    proposed = proposal["proposed"]

    assert proposal["current"]["diagnosis_available"] == []
    assert proposal["current"]["materials"] == []
    assert proposal["current"]["sex"] == []
    assert proposal["current"]["age_unit"] is None
    assert proposed["diagnosis_available"] == ["urn:miriam:icd:C18.1"]
    assert proposed["materials"] == ["PLASMA"]
    assert proposed["sex"] == ["MALE"]
    assert proposed["age_unit"] == "YEAR"


def test_descriptor_proposal_replace_existing_can_clear_materials_and_sex():
    collection = {
        "id": "bbmri-eric:ID:CZ_demo:collection:col2",
        "diagnosis_available": "urn:miriam:icd:C18",
        "materials": "SERUM",
        "sex": "FEMALE,MALE",
    }
    facts = [
        {
            "id": "f1",
            "sex": "*",
            "age_range": "*",
            "sample_type": "*",
            "disease": {"name": "*"},
            "number_of_samples": 5,
            "number_of_donors": 4,
        },
        {
            "id": "f2",
            "sex": "*",
            "age_range": "Adult",
            "sample_type": "NAV",
            "disease": {"name": "urn:miriam:icd:C18.1"},
            "number_of_samples": 1,
            "number_of_donors": 1,
        },
    ]

    proposal = build_collection_descriptor_proposal(collection, facts, replace_existing=True)
    proposed = proposal["proposed"]

    assert proposed["diagnosis_available"] == ["urn:miriam:icd:C18"]
    assert proposed["materials"] == []
    assert proposed["sex"] == []


def test_descriptor_proposal_preserves_month_age_unit_from_fact_ranges():
    collection = {
        "id": "bbmri-eric:ID:CZ_demo:collection:col3",
        "age_low": "",
        "age_high": "",
        "age_unit": "",
    }
    facts = [
        {
            "id": "f1",
            "sex": "*",
            "age_range": "0-11 months",
            "sample_type": "*",
            "disease": {"name": "*"},
            "number_of_samples": 5,
            "number_of_donors": 4,
        },
        {
            "id": "f2",
            "sex": "*",
            "age_range": "12-23 months",
            "sample_type": "*",
            "disease": {"name": "*"},
            "number_of_samples": 3,
            "number_of_donors": 3,
        },
    ]

    proposal = build_collection_descriptor_proposal(collection, facts, replace_existing=False)
    proposed = proposal["proposed"]

    assert proposed["age_low"] == 0
    assert proposed["age_high"] == 23
    assert proposed["age_unit"] == "MONTH"


def test_descriptor_proposal_skips_age_update_for_mixed_fact_units():
    collection = {
        "id": "bbmri-eric:ID:CZ_demo:collection:col4",
        "age_low": "",
        "age_high": "",
        "age_unit": "",
    }
    facts = [
        {
            "id": "f1",
            "sex": "*",
            "age_range": "0-11 months",
            "sample_type": "*",
            "disease": {"name": "*"},
            "number_of_samples": 5,
            "number_of_donors": 4,
        },
        {
            "id": "f2",
            "sex": "*",
            "age_range": "1-2 years",
            "sample_type": "*",
            "disease": {"name": "*"},
            "number_of_samples": 3,
            "number_of_donors": 3,
        },
    ]

    proposal = build_collection_descriptor_proposal(collection, facts, replace_existing=False)
    proposed = proposal["proposed"]

    assert proposed["age_low"] is None
    assert proposed["age_high"] is None
    assert proposed["age_unit"] is None
    assert any("mixed units" in note for note in proposal["notes"])


def test_descriptor_proposal_widens_existing_age_range_to_cover_fact_span():
    collection = {
        "id": "bbmri-eric:ID:CZ_demo:collection:col5",
        "age_low": "20",
        "age_high": "60",
        "age_unit": "YEAR",
    }
    facts = [
        {
            "id": "f1",
            "sex": "*",
            "age_range": "Adult",
            "sample_type": "*",
            "disease": {"name": "*"},
            "number_of_samples": 5,
            "number_of_donors": 4,
        },
        {
            "id": "f2",
            "sex": "*",
            "age_range": "Aged (65-79 years)",
            "sample_type": "*",
            "disease": {"name": "*"},
            "number_of_samples": 3,
            "number_of_donors": 3,
        },
    ]

    proposal = build_collection_descriptor_proposal(collection, facts, replace_existing=False)
    proposed = proposal["proposed"]

    assert proposed["age_low"] == 19
    assert proposed["age_high"] == 79
    assert proposed["age_unit"] == "YEAR"


def test_fact_alignment_fix_proposals_keep_age_notes_on_age_only():
    collection = {
        "id": "bbmri-eric:ID:CZ_demo:collection:col6",
        "diagnosis_available": "urn:miriam:icd:C18.0",
        "materials": "",
        "sex": "",
        "age_low": "",
        "age_high": "",
        "age_unit": "",
    }
    facts = [
        {
            "id": "f1",
            "sex": "*",
            "age_range": "Aged (>80 years)",
            "sample_type": "PLASMA",
            "disease": {"name": "urn:miriam:icd:C18.9"},
            "number_of_samples": 5,
            "number_of_donors": 4,
        },
    ]

    proposals = build_fact_alignment_fix_proposals(collection, facts)
    proposal_map = {proposal.field: proposal for proposal in proposals}

    assert "Open-ended fact-sheet age groups" not in proposal_map["diagnosis_available"].rationale
    assert "Open-ended fact-sheet age groups" not in proposal_map["materials"].rationale
    assert "Open-ended fact-sheet age groups" in proposal_map["age_low"].rationale
