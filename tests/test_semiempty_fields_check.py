from checks.SemiemptyFields import SemiemptyFields


class SemiemptyFieldsDirectoryStub:
    def getBiobanks(self):
        return [
            {
                "id": "bb1",
                "withdrawn": False,
                "name": "Biobank",
                "description": "Description Not Available",
            }
        ]

    def getCollections(self):
        return [
            {
                "id": "col1",
                "withdrawn": False,
                "name": "Main Collection",
                "description": "To be provided",
            }
        ]

    def getBiobankNN(self, biobank_id):
        return "CZ"

    def getCollectionNN(self, collection_id):
        return "CZ"


def test_semiempty_fields_reports_placeholder_descriptions():
    warnings = SemiemptyFields().check(SemiemptyFieldsDirectoryStub(), args=None)
    warning_ids = {warning.dataCheckID for warning in warnings}

    assert "SE:BBDescPlaceholder" in warning_ids
    assert "SE:CollDescPlaceholder" in warning_ids
    assert "SE:CollDescShort" not in warning_ids
