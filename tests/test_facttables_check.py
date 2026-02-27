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

    assert "FactTables:AllStarSamplesMismatchCollectionSize" in warning_ids
    assert "FactTables:AllStarDonorsMismatchCollectionDonors" in warning_ids
    assert "FactTables:AllStarAggregateAggregates4" in warning_ids
