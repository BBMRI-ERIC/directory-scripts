"""Test text consistency check behavior."""

from checks.TextConsistency import TextConsistency


class DirectoryStub:
    """Expose caller-provided active Czech collections to the deterministic text-consistency plugin.
    """
    def __init__(self, collections):
        """Retain the caller's collection records for deterministic text checks.

        Args:
            collections: Synthetic collection records exposed to the text-consistency check.
        """
        self._collections = collections

    def getCollections(self):
        """Return synthetic collection records available to the code under test.

        Returns:
            The synthetic collection records available to the code under test.
        """
        return list(self._collections)

    def getCollectionNN(self, collection_id):
        """Return fixture national-node code for the requested collection.

        Args:
            collection_id: Collection identifier whose fixture national-node code this stub returns.

        Returns:
            The fixture national-node code for the requested collection.
        """
        return "CZ"

    def isCollectionWithdrawn(self, collection_id):
        """Report the fixture marks the requested collection as withdrawn.

        Args:
            collection_id: Collection identifier whose fixture withdrawal status this stub reports.

        Returns:
            Whether the fixture marks the requested collection as withdrawn.
        """
        return False


def build_collection(collection_id, **overrides):
    """Build the collection fixture.

    Args:
        collection_id: Identifier inserted into the synthetic collection record.
        **overrides: Field overrides merged into the synthetic collection record.

    Returns:
        New active collection dictionary with empty description and ontology lists,
        unset age bounds, and overrides supplying the text/metadata contradiction.
    """
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


def test_text_consistency_plugin_emits_expected_warning_ids():
    """Verify text consistency plugin emits expected warning ids.

    Returns:
        None. Verifies text consistency plugin emits expected warning ids.
    """
    directory = DirectoryStub(
        [
            build_collection(
                "col1",
                description="A pediatric prospective follow-up cohort with paraffin blocks and long COVID cases.",
                type=["SAMPLE"],
                materials=["TISSUE_FROZEN"],
                diagnosis_available=[],
                age_high=None,
            )
        ]
    )

    warnings = TextConsistency().check(directory, args=None)

    assert [(warning.directoryEntityID, warning.dataCheckID) for warning in warnings] == [
        ("col1", "TXT:AgeRange"),
        ("col1", "TXT:StudyType"),
        ("col1", "TXT:FFPEMaterial"),
        ("col1", "TXT:CovidDiag"),
    ]
    assert any(warning.dataCheckID == "TXT:StudyType" and warning.fix_proposals for warning in warnings)
    assert any(warning.dataCheckID == "TXT:CovidDiag" and warning.fix_proposals for warning in warnings)
