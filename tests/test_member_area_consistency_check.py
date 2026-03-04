from checks.MemberAreaConsistency import MemberAreaConsistency


class MemberAreaDirectoryStub:
    def __init__(self):
        self.biobanks = [
            {
                "id": "bbmri-eric:ID:EXT_DE_NONMEMBER_ONLY",
                "country": "DE",
                "juridical_person": "Rare Disease Institute",
                "withdrawn": False,
                "contact": {"id": "ct1"},
            },
            {
                "id": "bbmri-eric:ID:DE_HOME",
                "country": "DE",
                "juridical_person": "Shared Institution",
                "withdrawn": False,
                "contact": {"id": "ct2"},
            },
            {
                "id": "bbmri-eric:ID:EXT_DE_DUPLICATE",
                "country": "DE",
                "juridical_person": "Shared Institution",
                "withdrawn": False,
                "contact": {"id": "ct3"},
            },
            {
                "id": "bbmri-eric:ID:EU_DE_DUPLICATE",
                "country": "DE",
                "juridical_person": "EU Hosted Institution",
                "withdrawn": False,
                "contact": {"id": "ct4"},
            },
            {
                "id": "bbmri-eric:ID:DE_EU_HOME",
                "country": "DE",
                "juridical_person": "EU Hosted Institution",
                "withdrawn": False,
                "contact": {"id": "ct5"},
            },
            {
                "id": "bbmri-eric:ID:AT_WRONG_PREFIX",
                "country": "DE",
                "juridical_person": "Wrong Prefix Institution",
                "withdrawn": False,
                "contact": {"id": "ct6"},
            },
            {
                "id": "bbmri-eric:ID:EXT_US_EXTERNAL",
                "country": "US",
                "juridical_person": "External Institution",
                "withdrawn": False,
                "contact": {"id": "ct7"},
            },
        ]
        self.contacts = {
            "ct1": {"email": "ct1@example.org"},
            "ct2": {"email": "ct2@example.org"},
            "ct3": {"email": "ct3@example.org"},
            "ct4": {"email": "ct4@example.org"},
            "ct5": {"email": "ct5@example.org"},
            "ct6": {"email": "ct6@example.org"},
            "ct7": {"email": "ct7@example.org"},
        }

    def getBiobanks(self):
        return self.biobanks

    def getBiobankContact(self, biobank_id):
        biobank = next(item for item in self.biobanks if item["id"] == biobank_id)
        return self.contacts[biobank["contact"]["id"]]



def test_member_area_consistency_check_distinguishes_warning_and_error_cases():
    plugin = MemberAreaConsistency()
    warnings = plugin.check(MemberAreaDirectoryStub(), args=None)
    warnings_by_id = {warning.directoryEntityID: warning for warning in warnings}

    assert (
        warnings_by_id["bbmri-eric:ID:EXT_DE_NONMEMBER_ONLY"].dataCheckID
        == "MAC:MemberNonMember"
    )
    assert warnings_by_id[
        "bbmri-eric:ID:EXT_DE_NONMEMBER_ONLY"
    ].level.name == "WARNING"

    assert (
        warnings_by_id["bbmri-eric:ID:EXT_DE_DUPLICATE"].dataCheckID
        == "MAC:MemberDupOtherArea"
    )
    assert warnings_by_id["bbmri-eric:ID:EXT_DE_DUPLICATE"].level.name == "ERROR"

    assert (
        warnings_by_id["bbmri-eric:ID:EU_DE_DUPLICATE"].dataCheckID
        == "MAC:MemberDupOtherArea"
    )
    assert warnings_by_id["bbmri-eric:ID:EU_DE_DUPLICATE"].level.name == "ERROR"

    assert (
        warnings_by_id["bbmri-eric:ID:AT_WRONG_PREFIX"].dataCheckID
        == "MAC:IsoStageMismatch"
    )
    assert warnings_by_id["bbmri-eric:ID:AT_WRONG_PREFIX"].level.name == "ERROR"

    assert "bbmri-eric:ID:EXT_US_EXTERNAL" not in warnings_by_id
