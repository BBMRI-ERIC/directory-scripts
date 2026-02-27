from nncontacts import NNContacts


def test_nncontacts_exposes_central_member_and_contact_metadata():
    assert NNContacts.is_member_node("CZ") is True
    assert NNContacts.is_member_node("EU") is False
    assert NNContacts.get_contacts("CZ") == NNContacts.NNtoEmails["CZ"]
    assert NNContacts.compose_recipients("CZ", "owner@example.org").startswith(
        "owner@example.org"
    )


def test_nncontacts_classifies_staging_areas_consistently():
    assert NNContacts.extract_staging_area("bbmri-eric:ID:EXT_FOO") == "EXT"
    assert NNContacts.is_non_member_staging_area("EXT", country="DE") is True
    assert NNContacts.is_non_member_staging_area("EU", country="DE") is True
    assert NNContacts.is_non_member_staging_area("ZZZ", country="DE") is True
    assert NNContacts.is_non_member_staging_area("DE", country="DE") is False
    assert NNContacts.is_non_member_staging_area("AT", country="DE") is False
    assert NNContacts.is_iso_country_code("AT") is True
    assert NNContacts.is_iso_country_code("EU") is False
