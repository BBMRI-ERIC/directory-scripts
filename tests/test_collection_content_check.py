"""Test collection content check behavior."""

from checks.CollectionContent import CollectionContent


class CollectionContentDirectoryStub:
    """Expose an MRI collection with inconsistent SAMPLE typing and no ORPHA mapper.
    """
    def getCollections(self):
        """Return synthetic collection records available to the code under test.

        Returns:
            The synthetic collection records available to the code under test.
        """
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
        """Return fixture national-node code for the requested collection.

        Args:
            collection_id: Collection identifier whose fixture national-node code this stub returns.

        Returns:
            The fixture national-node code for the requested collection.
        """
        return "CZ"

    def issetOrphaCodesMapper(self):
        """Report the ORPHA/ICD mapper fixture is available to the check.

        Returns:
            Whether the ORPHA/ICD mapper fixture is available to the check.
        """
        return False

    def getOrphaCodesMapper(self):
        """Return ORPHA/ICD mapper fixture supplied to the collection-content check.

        Returns:
            None: this fixture intentionally has no ORPHA mapper.
        """
        return None


def test_collection_content_requires_image_collection_type_for_imaging_metadata():
    """Verify collection content requires image collection type for imaging metadata.

    Returns:
        None. Verifies collection content requires image collection type for imaging metadata.
    """
    warnings = CollectionContent().check(CollectionContentDirectoryStub(), args=None)
    warning_ids = {warning.dataCheckID for warning in warnings}

    assert "CC:ImageTypeMissing" in warning_ids
    assert "CC:ImageCatMissing" not in warning_ids


class OrphaCodesMapperStub:
    """Resolve ORPHA validity and ICD crosswalks entirely from caller-provided dictionaries.
    """
    def __init__(self, *, valid_orpha=None, icd_to_orpha=None, orpha_to_icd=None):
        """Retain the supplied diagnosis-crosswalk inputs for deterministic mapping checks.

        Args:
            valid_orpha: Fixture ORPHA code set used by the mapping test double.
            icd_to_orpha: Fixture ICD-to-ORPHA mapping used by the mapping test double.
            orpha_to_icd: Fixture ORPHA-to-ICD mapping used by the mapping test double.
        """
        self.valid_orpha = set(valid_orpha or [])
        self.icd_to_orpha = dict(icd_to_orpha or {})
        self.orpha_to_icd = dict(orpha_to_icd or {})

    def isValidOrphaCode(self, code):
        """Report the supplied ORPHA code belongs to the fixture valid-code set.

        Args:
            code: ORPHA code evaluated against the fixture valid-code set.

        Returns:
            Whether the supplied ORPHA code belongs to the fixture valid-code set.
        """
        return code in self.valid_orpha

    def icd10ToOrpha(self, code):
        """Return configured ICD-10 to ORPHA mappings from the mapper double.

        Args:
            code: ICD-10 code whose fixture ORPHA mappings this stub returns.

        Returns:
            The configured ICD-10 to ORPHA mappings from the mapper double.
        """
        return list(self.icd_to_orpha.get(code, []))

    def orphaToIcd10(self, code):
        """Return configured ORPHA to ICD-10 mappings from the mapper double.

        Args:
            code: ORPHA code whose fixture ICD-10 mappings this stub returns.

        Returns:
            The configured ORPHA to ICD-10 mappings from the mapper double.
        """
        return list(self.orpha_to_icd.get(code, []))

    def orphaToNamesString(self, code):
        """Return configured ORPHA labels from the mapper double.

        Args:
            code: ORPHA code formatted into the fixture display name.

        Returns:
            The configured ORPHA labels from the mapper double.
        """
        return f"ORPHA {code}"


class CollectionContentCrosswalkDirectoryStub:
    """Expose one leaf collection and its ORPHA mapper without accessing the Directory.
    """
    def __init__(self, collection, mapper):
        """Retain the supplied diagnosis-crosswalk inputs for deterministic mapping checks.

        Args:
            collection: Synthetic collection record evaluated by the check under test.
            mapper: ORPHA/ICD mapper fixture passed to the collection-content check.
        """
        self.collection = collection
        self.mapper = mapper

    def getCollections(self):
        """Return synthetic collection records available to the code under test.

        Returns:
            The synthetic collection records available to the code under test.
        """
        return [self.collection]

    def getCollectionNN(self, collection_id):
        """Return fixture national-node code for the requested collection.

        Args:
            collection_id: Collection identifier whose fixture national-node code this stub returns.

        Returns:
            The fixture national-node code for the requested collection.
        """
        return "CZ"

    def issetOrphaCodesMapper(self):
        """Report the ORPHA/ICD mapper fixture is available to the check.

        Returns:
            Whether the ORPHA/ICD mapper fixture is available to the check.
        """
        return True

    def getOrphaCodesMapper(self):
        """Return ORPHA/ICD mapper fixture supplied to the collection-content check.

        Returns:
            The ORPHA/ICD mapper fixture supplied to the collection-content check.
        """
        return self.mapper

    def getCollectionsDescendants(self, collection_id):
        """Return fixture descendant collections for the requested collection.

        Args:
            collection_id: Collection identifier whose fixture descendant set this stub returns.

        Returns:
            The fixture descendant collections for the requested collection.
        """
        return []


def test_collection_content_adds_orpha_fix_for_rd_collection_and_suppresses_legacy_rd_suggest():
    """Verify collection content adds orpha fix for rd collection and suppresses legacy rd suggest.

    Returns:
        None. Verifies collection content adds orpha fix for rd collection and suppresses legacy rd suggest.
    """
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
    """Verify collection content does not suggest non exact orpha for non rd collection.

    Returns:
        None. Verifies collection content does not suggest non exact orpha for non rd collection.
    """
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
    """Verify collection content adds icd fix from orpha and suppresses legacy orpha icd suggest.

    Returns:
        None. Verifies collection content adds icd fix from orpha and suppresses legacy orpha icd suggest.
    """
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
