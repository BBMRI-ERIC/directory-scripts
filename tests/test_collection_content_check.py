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


class OrphaCodesMapperStub:
    def __init__(self, *, valid_orpha=None, icd_to_orpha=None, orpha_to_icd=None):
        self.valid_orpha = set(valid_orpha or [])
        self.icd_to_orpha = dict(icd_to_orpha or {})
        self.orpha_to_icd = dict(orpha_to_icd or {})

    def isValidOrphaCode(self, code):
        return code in self.valid_orpha

    def icd10ToOrpha(self, code):
        return list(self.icd_to_orpha.get(code, []))

    def orphaToIcd10(self, code):
        return list(self.orpha_to_icd.get(code, []))

    def orphaToNamesString(self, code):
        return f"ORPHA {code}"


class CollectionContentCrosswalkDirectoryStub:
    def __init__(self, collection, mapper):
        self.collection = collection
        self.mapper = mapper

    def getCollections(self):
        return [self.collection]

    def getCollectionNN(self, collection_id):
        return "CZ"

    def issetOrphaCodesMapper(self):
        return True

    def getOrphaCodesMapper(self):
        return self.mapper

    def getCollectionsDescendants(self, collection_id):
        return []


def test_collection_content_adds_orpha_fix_for_rd_collection_and_suppresses_legacy_rd_suggest():
    mapper = OrphaCodesMapperStub(
        valid_orpha={"58"},
        icd_to_orpha={"E75.2": [{"code": "58", "mapping_type": "E"}]},
    )
    collection = {
        "id": "col-rd",
        "withdrawn": False,
        "type": ["RD"],
        "data_categories": ["MEDICAL_RECORDS"],
        "diagnosis_available": [{"name": "urn:miriam:icd:E75.2"}],
    }

    warnings = CollectionContent().check(CollectionContentCrosswalkDirectoryStub(collection, mapper), args=None)
    warning_ids = {warning.dataCheckID for warning in warnings}

    assert "CC:RDOrphaMissing" in warning_ids
    assert "CC:DiagCrosswalkOrphaSuggest" in warning_ids
    assert "CC:RDOrphaSuggest" not in warning_ids

    suggest_warning = next(warning for warning in warnings if warning.dataCheckID == "CC:DiagCrosswalkOrphaSuggest")
    assert len(suggest_warning.fix_proposals) == 1
    assert suggest_warning.fix_proposals[0].field == "diagnosis_available"
    assert suggest_warning.fix_proposals[0].mode == "append"
    assert suggest_warning.fix_proposals[0].proposed_value == ["ORPHA:58"]
    assert suggest_warning.fix_proposals[0].confidence == "certain"


def test_collection_content_does_not_suggest_non_exact_orpha_for_non_rd_collection():
    mapper = OrphaCodesMapperStub(
        valid_orpha={"123"},
        icd_to_orpha={"A01.1": [{"code": "999", "mapping_type": "NTBT"}]},
    )
    collection = {
        "id": "col-non-rd",
        "withdrawn": False,
        "type": ["SAMPLE"],
        "data_categories": ["MEDICAL_RECORDS"],
        "diagnosis_available": [{"name": "ORPHA:123"}, {"name": "urn:miriam:icd:A01.1"}],
    }

    warnings = CollectionContent().check(CollectionContentCrosswalkDirectoryStub(collection, mapper), args=None)
    warning_ids = {warning.dataCheckID for warning in warnings}

    assert "CC:DiagCrosswalkOrphaSuggest" not in warning_ids
    assert "CC:DiagCrosswalkOrphaAmbiguous" not in warning_ids


def test_collection_content_adds_icd_fix_from_orpha_and_suppresses_legacy_orpha_icd_suggest():
    mapper = OrphaCodesMapperStub(
        valid_orpha={"58"},
        orpha_to_icd={"58": [{"code": "E75.2", "mapping_type": "E"}]},
    )
    collection = {
        "id": "col-orpha",
        "withdrawn": False,
        "type": ["RD"],
        "data_categories": ["MEDICAL_RECORDS"],
        "diagnosis_available": [{"name": "ORPHA:58"}],
    }

    warnings = CollectionContent().check(CollectionContentCrosswalkDirectoryStub(collection, mapper), args=None)
    warning_ids = {warning.dataCheckID for warning in warnings}

    assert "CC:DiagCrosswalkIcdSuggest" in warning_ids
    assert "CC:OrphaIcdSuggest" not in warning_ids

    suggest_warning = next(warning for warning in warnings if warning.dataCheckID == "CC:DiagCrosswalkIcdSuggest")
    assert len(suggest_warning.fix_proposals) == 1
    assert suggest_warning.fix_proposals[0].field == "diagnosis_available"
    assert suggest_warning.fix_proposals[0].mode == "append"
    assert suggest_warning.fix_proposals[0].proposed_value == ["urn:miriam:icd:E75.2"]
    assert suggest_warning.fix_proposals[0].confidence == "certain"
