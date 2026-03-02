from checks.CollectionContent import CollectionContent


class CollectionContentDirectoryStub:
    def getCollections(self):
        return [
            {
                "id": "col1",
                "withdrawn": False,
                "type": ["SAMPLE"],
                "data_categories": ["IMAGING_DATA"],
                "order_of_magnitude": 1,
                "size": 10,
                "imaging_modality": ["MRI"],
                "image_dataset_type": ["RAW"],
            }
        ]

    def getCollectionNN(self, collection_id):
        return "CZ"

    def issetOrphaCodesMapper(self):
        return False

    def getOrphaCodesMapper(self):
        return None


def test_collection_content_requires_image_collection_type_for_imaging_metadata():
    warnings = CollectionContent().check(CollectionContentDirectoryStub(), args=None)
    warning_ids = {warning.dataCheckID for warning in warnings}

    assert "CC:ImageTypeMissing" in warning_ids
    assert "CC:ImageCatMissing" not in warning_ids
