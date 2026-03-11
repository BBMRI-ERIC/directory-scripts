from checks.AccessPolicies import AccessPolicies, CHECK_DOCS


class DirectoryStub:
    def getBiobanks(self):
        return [
            {
                "id": "bb1",
                "withdrawn": False,
                "collaboration_non_for_profit": True,
                "collaboration_commercial": False,
                "collections": [],
            }
        ]

    def getCollections(self):
        return [
            {
                "id": "bbmri-eric:ID:CZ_demo:collection:col1",
                "withdrawn": False,
                "materials": ["DNA"],
                "type": ["DISEASE_SPECIFIC"],
                "data_use": [],
                "data_categories": ["BIOLOGICAL_SAMPLES"],
                "access_joint_project": "samples",
                "biobank": {"id": "bb1"},
            }
        ]

    def getCollectionBiobankId(self, collection_id):
        return "bb1"

    def getBiobankById(self, biobank_id):
        return {
            "id": "bb1",
            "withdrawn": False,
            "collaboration_non_for_profit": True,
            "collaboration_commercial": False,
        }

    def getCollectionNN(self, collection_id):
        return "CZ"

    def getBiobankNN(self, biobank_id):
        return "CZ"


def test_access_policies_attach_duo_fix_proposals():
    warnings = AccessPolicies().check(DirectoryStub(), args=None)
    warning_map = {warning.dataCheckID: warning for warning in warnings}

    assert "AP:JointDuo" in warning_map
    assert "AP:DiseaseDuoMissing" in warning_map
    assert warning_map["AP:JointDuo"].fix_proposals[0].proposed_value == ["DUO:0000020"]
    assert warning_map["AP:DiseaseDuoMissing"].fix_proposals[0].proposed_value == ["DUO:0000007"]
    assert any(warning.dataCheckID == "AP:GenericDuoMissing" and len(warning.fix_proposals) == 2 for warning in warnings)


def test_access_policies_treats_duo_underscore_and_colon_as_same_term():
    class DirectoryUnderscoreStub(DirectoryStub):
        def getCollections(self):
            return [
                {
                    "id": "bbmri-eric:ID:CZ_demo:collection:col1",
                    "withdrawn": False,
                    "materials": ["DNA"],
                    "type": ["DISEASE_SPECIFIC"],
                    "data_use": ["DUO_0000007"],
                    "data_categories": ["BIOLOGICAL_SAMPLES"],
                    "access_joint_project": "samples",
                    "biobank": {"id": "bb1"},
                }
            ]

    warnings = AccessPolicies().check(DirectoryUnderscoreStub(), args=None)
    assert not any(warning.dataCheckID == "AP:DiseaseDuoMissing" for warning in warnings)


def test_access_policies_skips_bio_duo_missing_for_nav_only_materials():
    class DirectoryNavMaterialsStub(DirectoryStub):
        def getCollections(self):
            return [
                {
                    "id": "bbmri-eric:ID:CZ_demo:collection:col1",
                    "withdrawn": False,
                    "materials": ["NAV"],
                    "type": ["SAMPLE"],
                    "data_use": ["DUO:0000006"],
                    "data_categories": ["BIOLOGICAL_SAMPLES"],
                    "biobank": {"id": "bb1"},
                }
            ]

    warnings = AccessPolicies().check(DirectoryNavMaterialsStub(), args=None)
    assert not any(warning.dataCheckID == "AP:BioDuoMissing" for warning in warnings)


def test_access_policies_use_generic_access_fields_only():
    class DirectoryGenericAccessStub(DirectoryStub):
        def getCollections(self):
            return [
                {
                    "id": "bbmri-eric:ID:CZ_demo:collection:col1",
                    "withdrawn": False,
                    "materials": ["DNA"],
                    "type": ["DISEASE_SPECIFIC"],
                    "data_use": ["DUO:0000007"],
                    "data_categories": ["BIOLOGICAL_SAMPLES", "MEDICAL_RECORDS"],
                    "access_description": "Access subject to review.",
                    "biobank": {"id": "bb1"},
                }
            ]

    warnings = AccessPolicies().check(DirectoryGenericAccessStub(), args=None)
    assert not any(warning.dataCheckID == "AP:AccessMissing" for warning in warnings)


def test_access_policies_raise_generic_access_missing_once():
    class DirectoryMissingAccessStub(DirectoryStub):
        def getCollections(self):
            return [
                {
                    "id": "bbmri-eric:ID:CZ_demo:collection:col1",
                    "withdrawn": False,
                    "materials": ["DNA"],
                    "type": ["DISEASE_SPECIFIC"],
                    "data_use": ["DUO:0000007"],
                    "data_categories": ["BIOLOGICAL_SAMPLES", "MEDICAL_RECORDS", "IMAGING_DATA"],
                    "biobank": {"id": "bb1"},
                }
            ]

    warnings = AccessPolicies().check(DirectoryMissingAccessStub(), args=None)
    access_missing = [warning for warning in warnings if warning.dataCheckID == "AP:AccessMissing"]
    assert len(access_missing) == 1
    assert not any(warning.dataCheckID in {"AP:SampleAccess", "AP:DataAccessMissing", "AP:ImgAccess"} for warning in warnings)


def test_access_policies_old_access_check_ids_do_not_return():
    assert "AP:SampleAccess" not in CHECK_DOCS
    assert "AP:DataAccessMissing" not in CHECK_DOCS
    assert "AP:ImgAccess" not in CHECK_DOCS


def test_access_policies_check_docs_do_not_reference_old_modality_access_fields():
    deprecated_fields = {
        "sample_access_description",
        "sample_access_fee",
        "sample_access_joint_project",
        "sample_access_uri",
        "data_access_description",
        "data_access_fee",
        "data_access_joint_project",
        "data_access_uri",
        "image_access_description",
        "image_access_fee",
        "image_joint_project",
        "image_access_uri",
    }
    documented_fields = {
        field
        for check_doc in CHECK_DOCS.values()
        for field in check_doc.get("fields", [])
    }
    assert documented_fields.isdisjoint(deprecated_fields)
