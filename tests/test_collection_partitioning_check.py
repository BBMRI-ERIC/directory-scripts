"""Test collection partitioning check behavior."""

from checks.CollectionPartitioning import CollectionPartitioning


class CollectionPartitioningDirectoryStub:
    """Supply parent/child totals and facts covering valid, overcounted, and missing partitions.
    """
    def __init__(self):
        """Populate collection, child, and fact lookups for partition-total comparisons.
        """
        self.collections = {
            "parent_ok": {
                "id": "parent_ok",
                "withdrawn": False,
                "size": 10,
                "number_of_donors": 8,
                "facts": [{"id": "fact_parent_ok"}],
            },
            "child_ok_1": {
                "id": "child_ok_1",
                "withdrawn": False,
                "size": 4,
                "number_of_donors": 3,
                "facts": [{"id": "fact_child_ok_1"}],
            },
            "child_ok_2": {
                "id": "child_ok_2",
                "withdrawn": False,
                "size": 5,
                "number_of_donors": 4,
                "facts": [{"id": "fact_child_ok_2"}],
            },
            "parent_over": {
                "id": "parent_over",
                "withdrawn": False,
                "size": 7,
                "number_of_donors": 5,
                "facts": [{"id": "fact_parent_over"}],
            },
            "child_over_1": {
                "id": "child_over_1",
                "withdrawn": False,
                "size": 5,
                "number_of_donors": 4,
                "facts": [{"id": "fact_child_over_1"}],
            },
            "child_over_2": {
                "id": "child_over_2",
                "withdrawn": False,
                "size": 4,
                "number_of_donors": 3,
                "facts": [{"id": "fact_child_over_2"}],
            },
            "parent_missing": {
                "id": "parent_missing",
                "withdrawn": False,
                "size": 10,
                "number_of_donors": 10,
                "facts": [{"id": "fact_parent_missing"}],
            },
            "child_missing_known": {
                "id": "child_missing_known",
                "withdrawn": False,
                "size": 6,
                "number_of_donors": 6,
                "facts": [{"id": "fact_child_missing_known"}],
            },
            "child_missing_unknown": {
                "id": "child_missing_unknown",
                "withdrawn": False,
                "facts": [{"id": "fact_child_missing_unknown"}],
            },
        }
        self.child_map = {
            "parent_ok": [self.collections["child_ok_1"], self.collections["child_ok_2"]],
            "parent_over": [self.collections["child_over_1"], self.collections["child_over_2"]],
            "parent_missing": [
                self.collections["child_missing_known"],
                self.collections["child_missing_unknown"],
            ],
        }
        self.fact_map = {
            "parent_ok": [
                {
                    "id": "fact_parent_ok",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": "*",
                    "number_of_samples": 10,
                    "number_of_donors": 8,
                }
            ],
            "child_ok_1": [
                {
                    "id": "fact_child_ok_1",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": "*",
                    "number_of_samples": 4,
                    "number_of_donors": 3,
                }
            ],
            "child_ok_2": [
                {
                    "id": "fact_child_ok_2",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": "*",
                    "number_of_samples": 5,
                    "number_of_donors": 4,
                }
            ],
            "parent_over": [
                {
                    "id": "fact_parent_over",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": "*",
                    "number_of_samples": 7,
                    "number_of_donors": 5,
                }
            ],
            "child_over_1": [
                {
                    "id": "fact_child_over_1",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": "*",
                    "number_of_samples": 5,
                    "number_of_donors": 4,
                }
            ],
            "child_over_2": [
                {
                    "id": "fact_child_over_2",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": "*",
                    "number_of_samples": 4,
                    "number_of_donors": 3,
                }
            ],
            "parent_missing": [
                {
                    "id": "fact_parent_missing",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": "*",
                    "number_of_samples": 10,
                    "number_of_donors": 10,
                }
            ],
            "child_missing_known": [
                {
                    "id": "fact_child_missing_known",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": "*",
                    "number_of_samples": 6,
                    "number_of_donors": 6,
                }
            ],
            "child_missing_unknown": [
                {
                    "id": "fact_child_missing_unknown",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": "*",
                }
            ],
        }

    def getCollections(self):
        """Return synthetic collection records available to the code under test.

        Returns:
            The synthetic collection records available to the code under test.
        """
        return [
            self.collections["parent_ok"],
            self.collections["parent_over"],
            self.collections["parent_missing"],
        ]

    def getDirectSubcollections(self, collection_id):
        """Return fixture direct-child collections for the requested parent.

        Args:
            collection_id: Parent collection identifier whose fixture children this stub returns.

        Returns:
            The fixture direct-child collections for the requested parent.
        """
        return self.child_map.get(collection_id, [])

    def getCollectionFacts(self, collection_id):
        """Return synthetic fact rows associated with the requested collection.

        Args:
            collection_id: Collection identifier whose fixture fact rows this stub returns.

        Returns:
            The synthetic fact rows associated with the requested collection.
        """
        return self.fact_map.get(collection_id, [])

    def getCollectionNN(self, collection_id):
        """Return fixture national-node code for the requested collection.

        Args:
            collection_id: Collection identifier whose fixture national-node code this stub returns.

        Returns:
            The fixture national-node code for the requested collection.
        """
        return "CZ"

    def getCollectionContact(self, collection_id):
        """Return fixture contact record associated with the requested collection.

        Args:
            collection_id: Collection identifier whose fixture contact record this stub returns.

        Returns:
            The fixture contact record associated with the requested collection.
        """
        return {"email": "collection@example.org"}

    def isCollectionWithdrawn(self, collection_id):
        """Report the fixture marks the requested collection as withdrawn.

        Args:
            collection_id: Collection identifier whose fixture withdrawal status this stub reports.

        Returns:
            Whether the fixture marks the requested collection as withdrawn.
        """
        return False


def test_collection_partitioning_reports_exceeding_and_unverifiable_children():
    """Verify collection partitioning reports exceeding and unverifiable children.

    Returns:
        None. Verifies collection partitioning reports exceeding and unverifiable children.
    """
    warnings = CollectionPartitioning().check(
        CollectionPartitioningDirectoryStub(),
        args=None,
    )
    warnings_by_collection = {}
    for warning in warnings:
        warnings_by_collection.setdefault(warning.directoryEntityID, set()).add(
            warning.dataCheckID
        )

    assert warnings_by_collection["parent_over"] >= {
        "CP:SizeOver",
        "CP:DonorOver",
        "CP:FactSizeOver",
        "CP:FactDonorOver",
    }
    assert warnings_by_collection["parent_missing"] >= {
        "CP:SizeUnknown",
        "CP:DonorUnknown",
        "CP:FactSizeUnknown",
        "CP:FactDonorUnknown",
    }
    assert "parent_ok" not in warnings_by_collection
