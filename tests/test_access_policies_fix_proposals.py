from checks.AccessPolicies import AccessPolicies


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
                "sample_access_joint_project": True,
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
                    "sample_access_joint_project": True,
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
