from checks.TextConsistency import TextConsistency


class DirectoryStub:
    def __init__(self, collections):
        self._collections = collections

    def getCollections(self):
        return list(self._collections)

    def getCollectionNN(self, collection_id):
        return "CZ"

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


def test_text_consistency_plugin_emits_expected_warning_ids():
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
