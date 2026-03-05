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
        proposal.entity_id == "col3" and proposal.proposed_value == ["f3b", "f3c"]
        for proposal in kanon_fix_proposals
    )
