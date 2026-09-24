"""Test semiempty fields check behavior."""

from checks.SemiemptyFields import SemiemptyFields


class SemiemptyFieldsDirectoryStub:
    """Expose biobank and collection descriptions containing known uninformative placeholders.
    """
    def getBiobanks(self):
        """Return synthetic biobank records available to the code under test.

        Returns:
            The synthetic biobank records available to the code under test.
        """
        return [
            {
                "id": "bb1",
                "withdrawn": False,
                "name": "Biobank",
                "description": "Description Not Available",
            }
        ]

    def getCollections(self):
        """Return synthetic collection records available to the code under test.

        Returns:
            The synthetic collection records available to the code under test.
        """
        return [
            {
                "id": "col1",
                "withdrawn": False,
                "name": "Main Collection",
                "description": "To be provided",
            }
        ]

    def getBiobankNN(self, biobank_id):
        """Return fixture national-node code for the requested biobank.

        Args:
            biobank_id: Biobank identifier whose fixture national-node code this stub returns.

        Returns:
            The fixture national-node code for the requested biobank.
        """
        return "CZ"

    def getCollectionNN(self, collection_id):
        """Return fixture national-node code for the requested collection.

        Args:
            collection_id: Collection identifier whose fixture national-node code this stub returns.

        Returns:
            The fixture national-node code for the requested collection.
        """
        return "CZ"


def test_semiempty_fields_reports_placeholder_descriptions():
    """Verify semiempty fields reports placeholder descriptions.

    Returns:
        None. Verifies semiempty fields reports placeholder descriptions.
    """
    warnings = SemiemptyFields().check(SemiemptyFieldsDirectoryStub(), args=None)
    warning_ids = {warning.dataCheckID for warning in warnings}

    assert "SE:BBDescPlaceholder" in warning_ids
    assert "SE:CollDescPlaceholder" in warning_ids
    assert "SE:CollDescShort" not in warning_ids
