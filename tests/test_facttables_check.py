from checks.FactTables import FactTables


class FactTablesDirectoryStub:
    def __init__(self):
        self.collections = [
            {
                "id": "col1",
                "name": "Collection 1",
                "biobank": {"id": "bb1"},
                "contact": {"id": "ct1"},
                "withdrawn": False,
                "facts": [{"id": "f1"}],
                "size": 10,
                "number_of_donors": 8,
            },
            {
                "id": "col2",
                "name": "Collection 2",
                "biobank": {"id": "bb1"},
                "contact": {"id": "ct1"},
                "withdrawn": False,
                "facts": [{"id": "f2"}],
                "size": 5,
            },
            {
                "id": "col3",
                "name": "Collection 3",
                "biobank": {"id": "bb1"},
                "contact": {"id": "ct1"},
                "withdrawn": False,
                "facts": [{"id": "f3a"}, {"id": "f3b"}, {"id": "f3c"}],
                "size": 6,
                "number_of_donors": 6,
                "sex": ["FEMALE", "MALE"],
                "materials": ["TISSUE_PARAFFIN_EMBEDDED"],
                "diagnosis_available": [{"name": "urn:miriam:icd:C18.0"}],
            },
        ]
        self.biobank = {"id": "bb1", "withdrawn": False, "contact": {"id": "ct1"}}
        self.contact = {"id": "ct1", "email": "ct1@example.org"}
        self.facts_by_collection = {
            "col1": [
                {
                    "id": "f1",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": "*",
                    "number_of_samples": 9,
                    "number_of_donors": 7,
                }
            ],
            "col2": [
                {
                    "id": "f2",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": {"name": "ORPHA:1"},
                    "number_of_samples": 5,
                    "number_of_donors": 4,
                }
            ],
            "col3": [
                {
                    "id": "f3a",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": {"name": "*"},
                    "number_of_samples": 6,
                    "number_of_donors": 6,
                },
                {
                    "id": "f3b",
                    "sex": "FEMALE",
                    "age_range": "Adult",
                    "sample_type": "NAV",
                    "disease": {"name": "urn:miriam:icd:C18.0"},
                    "number_of_samples": 2,
                    "number_of_donors": 2,
                },
                {
                    "id": "f3c",
                    "sex": "MALE",
                    "age_range": "Adult",
                    "sample_type": "TISSUE_PARAFFIN_EMBEDDED",
                    "disease": {"name": "urn:miriam:icd:C18.0"},
                    "number_of_samples": 4,
                    "number_of_donors": 4,
                },
            ],
        }

    def getCollections(self):
        return self.collections

    def getCollectionFacts(self, collection_id):
        return self.facts_by_collection.get(collection_id, [])

    def getCollectionBiobankId(self, collection_id):
        return "bb1"

    def getBiobankById(self, biobank_id):
        return self.biobank

    def getCollectionNN(self, collection_id):
        return "CZ"

    def getCollectionContact(self, collection_id):
        return self.contact


class FactTablesAgeRangeBroadStub:
    def __init__(self):
        self.collection = {
            "id": "col-age",
            "name": "Collection with broad age range",
            "biobank": {"id": "bb1"},
            "contact": {"id": "ct1"},
            "withdrawn": False,
            "facts": [{"id": "f-age-1"}, {"id": "f-age-2"}],
            "size": 20,
            "number_of_donors": 20,
            "age_unit": "YEAR",
            "age_low": 0,
            "age_high": 99,
            "sex": ["MALE", "FEMALE"],
            "materials": ["WHOLE_BLOOD"],
            "diagnosis_available": [{"name": "urn:miriam:icd:C18"}],
        }
        self.biobank = {"id": "bb1", "withdrawn": False, "contact": {"id": "ct1"}}
        self.contact = {"id": "ct1", "email": "ct1@example.org"}
        self.facts = [
            {
                "id": "f-age-1",
                "sex": "*",
                "age_range": "*",
                "sample_type": "*",
                "disease": {"name": "*"},
                "number_of_samples": 20,
                "number_of_donors": 20,
            },
            {
                "id": "f-age-2",
                "sex": "MALE",
                "age_range": "2-80 (years)",
                "sample_type": "WHOLE_BLOOD",
                "disease": {"name": "urn:miriam:icd:C18"},
                "number_of_samples": 20,
                "number_of_donors": 20,
            },
        ]

    def getCollections(self):
        return [self.collection]

    def getCollectionFacts(self, collection_id):
        return self.facts

    def getCollectionBiobankId(self, collection_id):
        return "bb1"

    def getBiobankById(self, biobank_id):
        return self.biobank

    def getCollectionNN(self, collection_id):
        return "EU"

    def getCollectionContact(self, collection_id):
        return self.contact


class FactTablesCrcLikeAgeRangeStub:
    def __init__(self):
        self.collection = {
            "id": "bbmri-eric:ID:EU_BBMRI-ERIC:collection:CRC-Cohort",
            "name": "CRC-Cohort",
            "biobank": {"id": "bb1"},
            "contact": {"id": "ct1"},
            "withdrawn": False,
            "facts": [{"id": "f1"}, {"id": "f2"}, {"id": "f3"}, {"id": "f4"}, {"id": "f5"}],
            "size": 100,
            "number_of_donors": 90,
            "age_unit": "YEAR",
            "age_low": 18,
            "age_high": 99,
            "sex": ["MALE", "FEMALE"],
            "materials": ["WHOLE_BLOOD"],
            "diagnosis_available": [{"name": "urn:miriam:icd:C18"}],
        }
        self.biobank = {"id": "bb1", "withdrawn": False, "contact": {"id": "ct1"}}
        self.contact = {"id": "ct1", "email": "ct1@example.org"}
        self.facts = [
            {
                "id": "f1",
                "sex": "*",
                "age_range": "*",
                "sample_type": "*",
                "disease": {"name": "*"},
                "number_of_samples": 100,
                "number_of_donors": 90,
            },
            {
                "id": "f2",
                "sex": "*",
                "age_range": "Child",
                "sample_type": "*",
                "disease": {"name": "*"},
                "number_of_samples": 1,
                "number_of_donors": 1,
            },
            {
                "id": "f3",
                "sex": "*",
                "age_range": "Young Adult",
                "sample_type": "*",
                "disease": {"name": "*"},
                "number_of_samples": 45,
                "number_of_donors": 13,
            },
            {
                "id": "f4",
                "sex": "*",
                "age_range": "Middle-aged",
                "sample_type": "*",
                "disease": {"name": "*"},
                "number_of_samples": 55,
                "number_of_donors": 45,
            },
            {
                "id": "f5",
                "sex": "*",
                "age_range": "Aged (>80 years)",
                "sample_type": "*",
                "disease": {"name": "*"},
                "number_of_samples": 10,
                "number_of_donors": 9,
            },
        ]

    def getCollections(self):
        return [self.collection]

    def getCollectionFacts(self, collection_id):
        return self.facts

    def getCollectionBiobankId(self, collection_id):
        return "bb1"

    def getBiobankById(self, biobank_id):
        return self.biobank

    def getCollectionNN(self, collection_id):
        return "EU"

    def getCollectionContact(self, collection_id):
        return self.contact


def test_facttables_check_reports_all_star_consistency_warnings():
    plugin = FactTables()
    warnings = plugin.check(FactTablesDirectoryStub(), args=None)
    warning_ids = {warning.dataCheckID for warning in warnings}

    assert "FT:AllStarSizeGap" in warning_ids
    assert "FT:AllStarDonorGap" in warning_ids
    assert "FT:AllStarMissing" in warning_ids


def test_facttables_check_ignores_star_rows_and_non_authoritative_nav_material():
    plugin = FactTables()
    warnings = plugin.check(FactTablesDirectoryStub(), args=None)
    warning_keys = {(warning.directoryEntityID, warning.message) for warning in warnings}

    assert not any(
        entity_id == "col3" and "facts table do not match" in message
        for entity_id, message in warning_keys
    )


def test_facttables_check_attaches_fact_alignment_fix_proposals():
    plugin = FactTables()
    warnings = plugin.check(FactTablesDirectoryStub(), args=None)

    proposals = [
        proposal
        for warning in warnings
        for proposal in warning.fix_proposals
    ]

    assert proposals
    assert any(proposal.module == "FT" for proposal in proposals)


def test_facttables_check_attaches_k_anonymity_drop_rows_fix_proposal():
    plugin = FactTables()
    warnings = plugin.check(FactTablesDirectoryStub(), args=None)

    kanon_warnings = [warning for warning in warnings if warning.dataCheckID == "FT:KAnonViolation"]
    assert kanon_warnings
    kanon_fix_proposals = [
        proposal
        for warning in kanon_warnings
        for proposal in warning.fix_proposals
        if proposal.update_id.startswith("facts.k_anonymity.drop_rows_k")
    ]
    assert kanon_fix_proposals
    assert any(proposal.mode == "delete_rows" for proposal in kanon_fix_proposals)
    assert any(proposal.field == "facts" for proposal in kanon_fix_proposals)
    assert any(
        proposal.entity_id == "col3" and set(proposal.proposed_value) >= {"f3b", "f3c"}
        for proposal in kanon_fix_proposals
    )


def test_facttables_age_range_broad_warning_includes_current_and_fact_ranges():
    plugin = FactTables()
    warnings = plugin.check(FactTablesAgeRangeBroadStub(), args=None)

    broad_warnings = [warning for warning in warnings if warning.dataCheckID == "FT:AgeRangeBroad"]
    assert broad_warnings
    message = broad_warnings[0].message
    assert "Collection age range (0-99 YEAR)" in message
    assert "fact-sheet age range (2-80 YEAR)" in message
    assert "suggested range based on the fact sheet is 2-80 YEAR" in message


def test_facttables_age_range_uses_label_based_rows_for_crc_like_cohort():
    plugin = FactTables()
    warnings = plugin.check(FactTablesCrcLikeAgeRangeStub(), args=None)

    broad_warnings = [warning for warning in warnings if warning.dataCheckID == "FT:AgeRangeBroad"]
    assert not broad_warnings

    mismatch_warnings = [warning for warning in warnings if warning.dataCheckID == "FT:AgeRangeMismatch"]
    assert mismatch_warnings
    message = mismatch_warnings[0].message
    assert "Child" not in message
    assert "Fact-sheet age range (2+ YEAR (open upper bound))" in message
    assert "collection age range (18-99 YEAR)" in message
    assert "Open-ended fact-sheet age groups are present" in message
