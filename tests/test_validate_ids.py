from checks.ValidateIDs import ValidateIDs


class ValidateIDsDirectoryStub:
    def __init__(self):
        self._biobanks = [
            {"id": "bbmri-eric:ID:EU_BBMRI-ERIC", "withdrawn": False},
            {"id": "bbmri-eric:ID:IARC_PBTA", "withdrawn": False},
        ]
        self._collections = [
            {
                "id": "bbmri-eric:ID:EU_BBMRI-ERIC:collection:CRC-Cohort",
                "biobank": {"id": "bbmri-eric:ID:EU_BBMRI-ERIC"},
                "withdrawn": False,
            }
        ]
        self._contacts = [
            {"id": "bbmri-eric:contactID:EU_BBMRI-ERIC:main"},
            {"id": "bbmri-eric:contactID:EXT_demo:main"},
        ]
        self._networks = [
            {"id": "bbmri-eric:networkID:EU_BBMRI-ERIC:networks:CRC-Cohort"},
            {"id": "bbmri-eric:networkID:EXT_demo:net1"},
        ]

    def getBiobanks(self):
        return self._biobanks

    def getCollections(self):
        return self._collections

    def getContacts(self):
        return self._contacts

    def getNetworks(self):
        return self._networks

    def getBiobankNN(self, biobank_id):
        return "EU" if ":EU_" in biobank_id else "IARC"

    def getCollectionNN(self, collection_id):
        return "EU"

    def getContactNN(self, contact_id):
        return "EXT" if ":EXT_" in contact_id else "EU"

    def getNetworkNN(self, network_id):
        return "EXT" if ":EXT_" in network_id else "EU"


def test_validate_ids_allows_eu_and_iarc_non_country_prefixes():
    warnings = ValidateIDs().check(ValidateIDsDirectoryStub(), args=None)
    warning_ids = {(warning.directoryEntityID, warning.dataCheckID) for warning in warnings}

    assert ("bbmri-eric:ID:EU_BBMRI-ERIC", "VID:BBExtPrefix") not in warning_ids
    assert ("bbmri-eric:ID:IARC_PBTA", "VID:BBExtPrefix") not in warning_ids
    assert ("bbmri-eric:contactID:EU_BBMRI-ERIC:main", "VID:CtExtPrefix") not in warning_ids
    assert ("bbmri-eric:contactID:EXT_demo:main", "VID:CtExtPrefix") not in warning_ids
    assert (
        "bbmri-eric:networkID:EU_BBMRI-ERIC:networks:CRC-Cohort",
        "VID:NetExtPrefix",
    ) not in warning_ids
    assert ("bbmri-eric:networkID:EXT_demo:net1", "VID:NetExtPrefix") not in warning_ids
