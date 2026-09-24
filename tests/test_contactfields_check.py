"""Test contactfields check behavior."""

from types import SimpleNamespace

import __main__
import logging

from checks.ContactFields import ContactFields


class ContactFieldsDirectoryStub:
    """Expose contact emails and owners covering placeholder domains and country mismatches.
    """
    def __init__(self):
        """Populate malformed-contact and owner-country lookup cases.
        """
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
        """Return synthetic contact records available to the code under test.

        Returns:
            The synthetic contact records available to the code under test.
        """
        return self.contacts

    def getContactNN(self, contact_id):
        """Return fixture national-node code for the requested contact.

        Args:
            contact_id: Contact identifier whose fixture national-node code this stub returns.

        Returns:
            The fixture national-node code for the requested contact.
        """
        for contact in self.contacts:
            if contact["id"] == contact_id:
                return contact["country"]
        raise KeyError(contact_id)

    def getCollectionBiobankId(self, collection_id):
        """Return fixture parent-biobank identifier for the requested collection.

        Args:
            collection_id: Collection identifier whose fixture parent-biobank ID this stub returns.

        Returns:
            The fixture parent-biobank identifier for the requested collection.
        """
        return self.collection_biobank_map[collection_id]

    def getBiobankById(self, biobank_id):
        """Return synthetic biobank record selected by the requested identifier, or `None` when absent.

        Args:
            biobank_id: Biobank identifier whose fixture record this stub returns or omits.

        Returns:
            The synthetic biobank record selected by the requested identifier, or `None` when absent.
        """
        return self.biobanks.get(biobank_id)


def test_contactfields_reports_placeholder_and_country_suffix_email_warnings():
    """Verify contactfields reports placeholder and country suffix email warnings.

    Returns:
        None. Verifies contactfields reports placeholder and country suffix email warnings.
    """
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


def test_contactfields_skips_remote_email_checks_when_validate_email_package_is_missing(caplog):
    """Verify contactfields skips remote email checks when validate email package is missing.

    Args:
        caplog: Pytest log-capture fixture used to inspect emitted log records.

    Returns:
        None. Verifies contactfields skips remote email checks when validate email package is missing.
    """
    __main__.remoteCheckList = ["emails"]
    args = SimpleNamespace(disableChecksRemote=[], purgeCaches=[])

    plugin = ContactFields()
    original_validator = plugin.check.__globals__["remote_validate_email"]
    plugin.check.__globals__["remote_validate_email"] = None
    try:
        with caplog.at_level(logging.WARNING):
            warnings = plugin.check(ContactFieldsDirectoryStub(), args)
    finally:
        plugin.check.__globals__["remote_validate_email"] = original_validator

    assert any("validate_email package is not installed" in message for message in caplog.messages)
    assert "CTF:EmailPlaceholder" in {warning.dataCheckID for warning in warnings}
    assert "CTF:EmailCountrySuffix" in {warning.dataCheckID for warning in warnings}
    assert "CTF:EmailUnreachable" not in {warning.dataCheckID for warning in warnings}
