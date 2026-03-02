from ai_cache import compute_checksum
from ai_check_generation import generate_payloads


class DirectoryStub:
    def __init__(self, collections):
        self._collections = collections
        self.include_withdrawn_entities = False
        self.only_withdrawn_entities = False

    def getCollections(self):
        return list(self._collections)

    def getSchema(self):
        return "ERIC"

    def isCollectionWithdrawn(self, collection_id):
        return False


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


def findings_by_rule(payloads, rule_name):
    for payload in payloads:
        if payload["rule"] == rule_name:
            return payload["findings"]
    raise AssertionError(f"Missing payload for {rule_name}")


def test_compute_checksum_ignores_runtime_metadata():
    left = {
        "id": "col1",
        "name": "Collection",
        "mg_updatedOn": "2026-03-01T12:00:00",
        "mg_updatedBy": "alice",
        "nested": {"mg_insertedOn": "2026-03-01T12:00:00", "value": 1},
    }
    right = {
        "id": "col1",
        "name": "Collection",
        "mg_updatedOn": "2026-03-02T12:00:00",
        "mg_updatedBy": "bob",
        "nested": {"mg_insertedOn": "2026-03-02T12:00:00", "value": 1},
    }

    assert compute_checksum(left) == compute_checksum(right)


def test_age_text_skips_mixed_population_but_flags_pediatric_gap():
    directory = DirectoryStub(
        [
            build_collection(
                "mixed",
                description="Samples from adult and pediatric patients.",
                age_high=None,
            ),
            build_collection(
                "pediatric",
                description="A pediatric oncology cohort.",
                age_high=30,
            ),
        ]
    )

    findings = findings_by_rule(generate_payloads(directory), "AgeText")

    assert [finding["entity_id"] for finding in findings] == ["pediatric"]
    assert "pediatric population" in findings[0]["message"]


def test_study_text_is_conservative_for_case_control_and_prospective():
    directory = DirectoryStub(
        [
            build_collection(
                "follow-up",
                description="Participants are seen for follow-up every year.",
                type=["SAMPLE"],
            ),
            build_collection(
                "prospective-cohort",
                description="A prospective cohort study.",
                type=["COHORT", "LONGITUDINAL"],
            ),
            build_collection(
                "healthy-controls",
                description="Patients are compared to healthy controls after vaccination.",
                type=["COHORT", "PROSPECTIVE_COLLECTION"],
            ),
        ]
    )

    findings = findings_by_rule(generate_payloads(directory), "StudyText")

    assert [finding["entity_id"] for finding in findings] == ["follow-up"]
    assert "LONGITUDINAL" in findings[0]["message"]


def test_ffpe_text_skips_slide_and_derived_mentions_but_keeps_blocks():
    directory = DirectoryStub(
        [
            build_collection(
                "slides",
                description="Whole slide images from H&E-stained FFPE tissue sections.",
                materials=["TISSUE_STAINED"],
            ),
            build_collection(
                "derived",
                description="Isolated DNA obtained from FFPE blocks.",
                materials=["DNA"],
            ),
            build_collection(
                "blocks",
                description="Paraffin blocks are also available in this collection.",
                materials=["TISSUE_FROZEN"],
            ),
        ]
    )

    findings = findings_by_rule(generate_payloads(directory), "FFPEText")

    assert [finding["entity_id"] for finding in findings] == ["blocks"]
    assert "TISSUE_PARAFFIN_EMBEDDED" in findings[0]["message"]


def test_covid_text_supports_long_covid_and_skips_context_only_cases():
    directory = DirectoryStub(
        [
            build_collection(
                "long-covid",
                description="A post-COVID and long COVID outpatient cohort.",
                diagnosis_available=[],
            ),
            build_collection(
                "vaccination-only",
                description="Samples before and after COVID-19 vaccination.",
                diagnosis_available=[],
            ),
            build_collection(
                "negative",
                description="Severe acute respiratory syndrome coronavirus 2 not detected.",
                name="COVID-19 negative",
                diagnosis_available=[{"name": "urn:miriam:icd:Z03.8"}],
            ),
            build_collection(
                "acute",
                description="COVID-19 patients hospitalized during acute infection.",
                diagnosis_available=[],
            ),
        ]
    )

    findings = findings_by_rule(generate_payloads(directory), "CovidText")
    findings_by_id = {finding["entity_id"]: finding for finding in findings}

    assert set(findings_by_id) == {"long-covid", "acute"}
    assert "U09.9" in findings_by_id["long-covid"]["message"]
    assert "U07.1/U07.2" in findings_by_id["acute"]["message"]


def test_payloads_store_checked_entity_and_source_checksums():
    directory = DirectoryStub(
        [build_collection("col1", description="A prospective follow-up cohort.", type=["SAMPLE"])]
    )

    payloads = generate_payloads(directory)
    study_payload = next(payload for payload in payloads if payload["rule"] == "StudyText")

    assert study_payload["checked_fields"] == [
        "COLLECTION.name",
        "COLLECTION.description",
        "COLLECTION.type",
    ]
    assert study_payload["checked_entities"][0]["entity_id"] == "col1"
    assert study_payload["checked_entities"][0]["entity_checksum"]
    assert study_payload["checked_entities"][0]["source_checksum"]
    assert study_payload["findings"][0]["entity_checksum"] == study_payload["checked_entities"][0]["entity_checksum"]
