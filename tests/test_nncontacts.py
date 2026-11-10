"""Test nncontacts behavior."""

from nncontacts import NNContacts


def test_approved_operational_contact_review():
    """Keep approved contacts, exclusions, aliases and staging routing intact.

    Returns:
        None. Exact routing matches the approved review, including retained
        legacy contacts and explicit multi-address exceptions for GR and IARC.
    """
    expected = {
        "AT": {"cornelia.stumptner@medunigraz.at"},
        "BE": {"annelies.debucquoy@kankerregister.org", "secretariat.BBMRIbe@kankerregister.org"},
        "BG": {"kaneva@mmcbg.org"},
        "CH": {"christine.currat@chuv.ch", "claudia.lagier@swissbiobanking.ch", "sabine.bavamian@swissbiobanking.ch"},
        "CY": {"CStylianou@mphs.moh.gov.cy"},
        "CZ": {"dudova@ics.muni.cz", "hrstka@mou.cz", "katerina.novakova@mou.cz"},
        "DE": {"cornelia.specht@charite.de", "sara.nussbeck@med.uni-goettingen.de"},
        "DK": {"kms@ssi.dk"},
        "EE": {"steven.smit@ut.ee"},
        "ES": {"teresa.escamez@carm.es", "Jacobo.martinez@fisabio.es"},
        "EU": {"kurt.majcen@bbmri-eric.eu", "petr.holub@bbmri-eric.eu"},
        "EXT": {"SBenvenuti@Telethon.it", "kurt.majcen@bbmri-eric.eu", "petr.holub@bbmri-eric.eu"},
        "FI": {"johanna.makela@finbb.fi", "tom.southerington@finbb.fi"},
        "GR": {"s.kolyva@pasteur.gr", "thanos@bioacademy.gr", "skolyva@gmail.com"},
        "HU": {"molnarmj@gmail.com"},
        "IT": {"marialuisa.lavitrano@unimib.it", "luciano.milanesi@itb.cnr.it", "barbara.parodi@hsanmartino.it", "matteo.gnocchi@itb.cnr.it", "marco.moscatelli@itb.cnr.it"},
        "LT": {"tomas.simulevic@nvi.lt", "daiva.dabkeviciene@nvi.lt"},
        "LV": {"vita@biomed.lu.lv", "inese.polaka@rtu.lv", "linda.zaharenko@biomed.lu.lv"},
        "ME": {"masaz@ucg.ac.me"},
        "MT": {"eric.santucci@um.edu.mt", "Nikolai.p.pace@um.edu.mt"},
        "NL": {"tieneke.schaaij-visser@lygature.org", "julia.bongers@health-ri.nl", "j.hamann@amsterdamumc.nl"},
        "NO": {"vegard.marschhauser@ntnu.no", "kristian.hveem@ntnu.no", "therese.h.nost@uit.no", "therese.h.nost@ntnu.no"},
        "PL": {"blazej.marciniak@biol.uni.lodz.pl", "andrzej.strug@gumed.edu.pl", "aklis@bee2code.com", "iwona.goras@wum.edu.pl", "michal.malewicz@port.lukasiewicz.gov.pl", "radoslaw.zagozdzon@wum.edu.pl"},
        "PT": {"ana.reis@gimm.pt", "sergio.dias@gimm.pt"},
        "QA": {"fqafoud@qf.org.qa", "efthenou@qf.org.qa"},
        "SI": {"urban.bren@um.si"},
        "SK": {"marian.mizik@uniba.sk", "zuzana.dankova@uniba.sk"},
        "TR": {"ali.kilic@ibg.edu.tr", "sanem.avci@ibg.edu.tr"},
        "UA": {"h.chytaieva@audubonbio.com", "b.shkurupii@audubonbio.com"},
        "IARC": {"kozlakidisz@iarc.fr", "kozlakidisz@iarc.who.int", "kozlakidisz@who.int", "Cabouxe@iarc.fr"},
    }
    assert set(NNContacts.NODE_TO_EMAILS) == set(expected)
    for code, emails in expected.items():
        assert set(NNContacts.get_contacts(code).split(", ")) == emails
        assert len(NNContacts.get_contacts(code).split(", ")) == len(emails)
        assert NNContacts.NNtoEmails[code] == NNContacts.NODE_TO_EMAILS[code]
        assert NNContacts.get_contacts(code.lower()) == NNContacts.NODE_TO_EMAILS[code]
    assert NNContacts.DEFAULT_ESCALATION_EMAILS == (
        "petr.holub@bbmri-eric.eu, e.van.enckevort@rug.nl, a.w.hodselmans@rug.nl"
    )


def test_member_country_classification_is_not_limited_to_contact_directory():
    """Countries remain members/observers without inventing missing contact emails.

    Returns:
        None. Sweden remains eligible with no confirmed operational contact;
        recipient composition uses the existing escalation fallback.
    """
    for code in ("SI", "QA", "DK", "SE"):
        assert NNContacts.is_member_node(code)
    assert not NNContacts.has_contacts("SE")
    assert NNContacts.get_contacts("SE") == NNContacts.DEFAULT_ESCALATION_EMAILS
    assert NNContacts.compose_recipients("SE", "owner@example.org") == (
        "owner@example.org, " + NNContacts.DEFAULT_ESCALATION_EMAILS
    )
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
