from text_consistency import build_text_consistency_findings


def build_collection(collection_id, **overrides):
    collection = {
        "id": collection_id,
        "name": "Collection",
        "description": "",
        "type": [],
        "materials": [],
        "diagnosis_available": [],
        "age_low": None,
        "age_high": None,
        "withdrawn": False,
    }
    collection.update(overrides)
    return collection


def findings_by_id(collection):
    return {finding["check_id"]: finding for finding in build_text_consistency_findings(collection)}


def test_age_range_skips_mixed_population_but_flags_pediatric_gap():
    mixed = build_collection(
        "mixed",
        description="Samples from adult and pediatric patients.",
        age_high=None,
    )
    pediatric = build_collection(
        "pediatric",
        description="A pediatric oncology cohort.",
        age_high=30,
    )

    assert build_text_consistency_findings(mixed) == []
    findings = findings_by_id(pediatric)
    assert list(findings) == ["TXT:AgeRange"]
    assert "pediatric population" in findings["TXT:AgeRange"]["message"]


def test_study_type_is_conservative_for_case_control_and_prospective():
    follow_up = build_collection(
        "follow-up",
        description="Participants are seen for follow-up every year.",
        type=["SAMPLE"],
    )
    prospective_cohort = build_collection(
        "prospective-cohort",
        description="A prospective cohort study.",
        type=["COHORT", "LONGITUDINAL"],
    )
    healthy_controls = build_collection(
        "healthy-controls",
        description="Patients are compared to healthy controls after vaccination.",
        type=["COHORT", "PROSPECTIVE_COLLECTION"],
    )

    follow_up_findings = findings_by_id(follow_up)
    assert list(follow_up_findings) == ["TXT:StudyType"]
    assert "LONGITUDINAL" in follow_up_findings["TXT:StudyType"]["message"]
    assert build_text_consistency_findings(prospective_cohort) == []
    assert build_text_consistency_findings(healthy_controls) == []


def test_ffpe_material_skips_slide_and_derived_mentions_but_keeps_blocks():
    slides = build_collection(
        "slides",
        description="Whole slide images from H&E-stained FFPE tissue sections.",
        materials=["TISSUE_STAINED"],
    )
    derived = build_collection(
        "derived",
        description="Isolated DNA obtained from FFPE blocks.",
        materials=["DNA"],
    )
    blocks = build_collection(
        "blocks",
        description="Paraffin blocks are also available in this collection.",
        materials=["TISSUE_FROZEN"],
    )

    assert build_text_consistency_findings(slides) == []
    assert build_text_consistency_findings(derived) == []
    findings = findings_by_id(blocks)
    assert list(findings) == ["TXT:FFPEMaterial"]
    assert "TISSUE_PARAFFIN_EMBEDDED" in findings["TXT:FFPEMaterial"]["message"]


def test_covid_diag_supports_long_covid_and_skips_context_only_cases():
    long_covid = build_collection(
        "long-covid",
        description="A post-COVID and long COVID outpatient cohort.",
        diagnosis_available=[],
    )
    vaccination_only = build_collection(
        "vaccination-only",
        description="Samples before and after COVID-19 vaccination.",
        diagnosis_available=[],
    )
    negative = build_collection(
        "negative",
        description="Severe acute respiratory syndrome coronavirus 2 not detected.",
        name="COVID-19 negative",
        diagnosis_available=[{"name": "urn:miriam:icd:Z03.8"}],
    )
    acute = build_collection(
        "acute",
        description="COVID-19 patients hospitalized during acute infection.",
        diagnosis_available=[],
    )

    long_findings = findings_by_id(long_covid)
    assert list(long_findings) == ["TXT:CovidDiag"]
    assert "U09.9" in long_findings["TXT:CovidDiag"]["message"]
    assert build_text_consistency_findings(vaccination_only) == []
    assert build_text_consistency_findings(negative) == []
    acute_findings = findings_by_id(acute)
    assert list(acute_findings) == ["TXT:CovidDiag"]
    assert "U07.1/U07.2" in acute_findings["TXT:CovidDiag"]["message"]
