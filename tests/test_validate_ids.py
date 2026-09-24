"""Test validate ids behavior."""

from checks.ValidateIDs import ValidateIDs


class ValidateIDsDirectoryStub:
    """Provide EU/IARC/EXT identifiers to test permitted non-country staging prefixes.
    """
    def __init__(self):
        """Populate EU/IARC/EXT entity IDs and their parent relationships.
        """
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
        """Return synthetic biobank records available to the code under test.

        Returns:
            The synthetic biobank records available to the code under test.
        """
        return self._biobanks

    def getCollections(self):
        """Return synthetic collection records available to the code under test.

        Returns:
            The synthetic collection records available to the code under test.
        """
        return self._collections

    def getContacts(self):
        """Return synthetic contact records available to the code under test.

        Returns:
            The synthetic contact records available to the code under test.
        """
        return self._contacts

    def getNetworks(self):
        """Return synthetic network records available to the code under test.

        Returns:
            The synthetic network records available to the code under test.
        """
        return self._networks

    def getBiobankNN(self, biobank_id):
        """Return fixture national-node code for the requested biobank.

        Args:
            biobank_id: Biobank identifier whose fixture national-node code this stub returns.

        Returns:
            The fixture national-node code for the requested biobank.
        """
        return "EU" if ":EU_" in biobank_id else "IARC"

    def getCollectionNN(self, collection_id):
        """Return fixture national-node code for the requested collection.

        Args:
            collection_id: Collection identifier whose fixture national-node code this stub returns.

        Returns:
            The fixture national-node code for the requested collection.
        """
        return "EU"

    def getContactNN(self, contact_id):
        """Return fixture national-node code for the requested contact.

        Args:
            contact_id: Contact identifier whose fixture national-node code this stub returns.

        Returns:
            The fixture national-node code for the requested contact.
        """
        return "EXT" if ":EXT_" in contact_id else "EU"

    def getNetworkNN(self, network_id):
        """Return fixture national-node code for the requested network.

        Args:
            network_id: Network identifier whose fixture national-node code this stub returns.

        Returns:
            The fixture national-node code for the requested network.
        """
        return "EXT" if ":EXT_" in network_id else "EU"


def test_validate_ids_allows_eu_and_iarc_non_country_prefixes():
    """Verify validate ids allows eu and iarc non country prefixes.

    Returns:
        None. Verifies validate ids allows eu and iarc non country prefixes.
    """
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
