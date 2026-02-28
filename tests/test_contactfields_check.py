from types import SimpleNamespace

import __main__

from checks.ContactFields import ContactFields


class ContactFieldsDirectoryStub:
    def __init__(self):
        self.contacts = [
            {
                "id": "ct_placeholder",
                "email": "person@example.org",
                "country": "NL",
                "biobanks": [{"id": "bbmri-eric:ID:NL_PLACEHOLDER"}],
            },
            {
                "id": "ct_unknown_placeholder",
                "email": "person@unknown.de",
                "country": "DE",
                "biobanks": [{"id": "bbmri-eric:ID:DE_UNKNOWN_PLACEHOLDER"}],
            },
            {
                "id": "ct_test_placeholder",
                "email": "person@test.com",
                "country": "DE",
                "biobanks": [{"id": "bbmri-eric:ID:DE_TEST_PLACEHOLDER"}],
            },
            {
                "id": "ct_country_mismatch",
                "email": "person@clinic.cz",
                "country": "DE",
                "collections": [{"id": "bbmri-eric:ID:DE_MAIN:collection:COL1"}],
            },
            {
                "id": "ct_generic_ok",
                "email": "person@gmail.com",
                "country": "DE",
                "biobanks": [{"id": "bbmri-eric:ID:DE_GENERIC"}],
            },
            {
                "id": "ct_ext_ok",
                "email": "person@clinic.cz",
                "country": "DE",
                "biobanks": [{"id": "bbmri-eric:ID:EXT_DE_EXTERNAL"}],
            },
        ]
        self.biobanks = {
            "bbmri-eric:ID:NL_PLACEHOLDER": {
                "id": "bbmri-eric:ID:NL_PLACEHOLDER",
                "country": "NL",
            },
            "bbmri-eric:ID:DE_MAIN": {
                "id": "bbmri-eric:ID:DE_MAIN",
                "country": "DE",
            },
            "bbmri-eric:ID:DE_UNKNOWN_PLACEHOLDER": {
                "id": "bbmri-eric:ID:DE_UNKNOWN_PLACEHOLDER",
                "country": "DE",
            },
            "bbmri-eric:ID:DE_TEST_PLACEHOLDER": {
                "id": "bbmri-eric:ID:DE_TEST_PLACEHOLDER",
                "country": "DE",
            },
            "bbmri-eric:ID:DE_GENERIC": {
                "id": "bbmri-eric:ID:DE_GENERIC",
                "country": "DE",
            },
            "bbmri-eric:ID:EXT_DE_EXTERNAL": {
                "id": "bbmri-eric:ID:EXT_DE_EXTERNAL",
                "country": "DE",
            },
        }
        self.collection_biobank_map = {
            "bbmri-eric:ID:DE_MAIN:collection:COL1": "bbmri-eric:ID:DE_MAIN",
        }

    def getContacts(self):
        return self.contacts

    def getContactNN(self, contact_id):
        for contact in self.contacts:
            if contact["id"] == contact_id:
                return contact["country"]
        raise KeyError(contact_id)

    def getCollectionBiobankId(self, collection_id):
        return self.collection_biobank_map[collection_id]

    def getBiobankById(self, biobank_id):
        return self.biobanks.get(biobank_id)


def test_contactfields_reports_placeholder_and_country_suffix_email_warnings():
    __main__.remoteCheckList = ["emails"]
    args = SimpleNamespace(disableChecksRemote=["emails"], purgeCaches=[])

    warnings = ContactFields().check(ContactFieldsDirectoryStub(), args)
    warnings_by_contact = {}
    for warning in warnings:
        warnings_by_contact.setdefault(warning.directoryEntityID, []).append(warning)

    placeholder_warning_ids = {
        warning.dataCheckID for warning in warnings_by_contact["ct_placeholder"]
    }
    assert "CTF:EmailPlaceholder" in placeholder_warning_ids
    assert "CTF:EmailCountrySuffix" not in placeholder_warning_ids

    unknown_placeholder_warning_ids = {
        warning.dataCheckID
        for warning in warnings_by_contact["ct_unknown_placeholder"]
    }
    assert "CTF:EmailPlaceholder" in unknown_placeholder_warning_ids
    assert "CTF:EmailCountrySuffix" not in unknown_placeholder_warning_ids

    test_placeholder_warning_ids = {
        warning.dataCheckID
        for warning in warnings_by_contact["ct_test_placeholder"]
    }
    assert "CTF:EmailPlaceholder" in test_placeholder_warning_ids
    assert "CTF:EmailCountrySuffix" not in test_placeholder_warning_ids

    mismatch_warning_ids = {
        warning.dataCheckID for warning in warnings_by_contact["ct_country_mismatch"]
    }
    assert "CTF:EmailCountrySuffix" in mismatch_warning_ids
    mismatch_warning = next(
        warning
        for warning in warnings_by_contact["ct_country_mismatch"]
        if warning.dataCheckID == "CTF:EmailCountrySuffix"
    )
    assert ".cz" in mismatch_warning.message
    assert "DE" in mismatch_warning.message

    generic_warning_ids = {
        warning.dataCheckID for warning in warnings_by_contact.get("ct_generic_ok", [])
    }
    assert "CTF:EmailCountrySuffix" not in generic_warning_ids

    ext_warning_ids = {
        warning.dataCheckID for warning in warnings_by_contact.get("ct_ext_ok", [])
    }
    assert "CTF:EmailCountrySuffix" not in ext_warning_ids
