"""Test nncontacts behavior."""

from nncontacts import NNContacts


def test_active_operational_contacts_exclude_governance_only_contacts():
    """Route operational contacts without former, external, or AoM/FC-only ones.

    Returns:
        None. Six Nodes use each eligible active MC or Work Programme email
        exactly once, excluding governance-only, former and external records.
    """
    expected = {
        "DK": {"kms@ssi.dk"},
        "ME": {"masaz@ucg.ac.me"},
        "PT": {"ana.reis@gimm.pt", "sergio.dias@gimm.pt"},
        "QA": {"fqafoud@qf.org.qa", "efthenou@qf.org.qa"},
        "SI": {"urban.bren@um.si"},
        "UA": {"h.chytaieva@audubonbio.com", "b.shkurupii@audubonbio.com"},
    }
    for code, emails in expected.items():
        assert set(NNContacts.get_contacts(code).split(", ")) == emails
        assert len(NNContacts.get_contacts(code).split(", ")) == len(emails)
        assert NNContacts.NNtoEmails[code] == NNContacts.NODE_TO_EMAILS[code]
        assert NNContacts.is_member_node(code)


def test_member_country_classification_is_not_limited_to_contact_directory():
    """Countries remain members/observers without inventing missing contact emails.

    Returns:
        None. Slovenia, Qatar and Denmark are eligible countries, but EXT is not.
    """
    for code in ("SI", "QA", "DK"):
        assert NNContacts.is_member_node(code)
    assert not NNContacts.is_member_node("EXT")


def test_nncontacts_exposes_central_member_and_contact_metadata():
    """Verify nncontacts exposes central member and contact metadata.

    Returns:
        None. Verifies nncontacts exposes central member and contact metadata.
    """
    assert NNContacts.is_member_node("CZ") is True
    assert NNContacts.is_member_node("EU") is False
    assert NNContacts.get_contacts("CZ") == NNContacts.NNtoEmails["CZ"]
    assert NNContacts.compose_recipients("CZ", "owner@example.org").startswith(
        "owner@example.org"
    )


def test_nncontacts_classifies_staging_areas_consistently():
    """Verify nncontacts classifies staging areas consistently.

    Returns:
        None. Verifies nncontacts classifies staging areas consistently.
    """
    assert NNContacts.extract_staging_area("bbmri-eric:ID:EXT_FOO") == "EXT"
    assert NNContacts.is_non_member_staging_area("EXT", country="DE") is True
    assert NNContacts.is_non_member_staging_area("EU", country="DE") is True
    assert NNContacts.is_non_member_staging_area("ZZZ", country="DE") is True
    assert NNContacts.is_non_member_staging_area("DE", country="DE") is False
    assert NNContacts.is_non_member_staging_area("AT", country="DE") is False
    assert NNContacts.is_iso_country_code("AT") is True
    assert NNContacts.is_iso_country_code("EU") is False
    assert NNContacts.is_permitted_non_country_prefix("EU") is True
    assert NNContacts.is_permitted_non_country_prefix("IARC") is True
    assert NNContacts.expected_schema_name("CZ") == "BBMRI-CZ"
    assert NNContacts.expected_schema_name("EU") == "BBMRI-EU"
    assert NNContacts.schema_matches_staging_area("BBMRI-EU", "EU") is True
