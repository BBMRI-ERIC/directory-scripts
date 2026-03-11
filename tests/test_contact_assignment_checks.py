from types import SimpleNamespace

from checks.ContactAssignments import ContactAssignments
from checks.ContactReuse import ContactReuse


class ContactAssignmentDirectoryStub:
    def __init__(self):
        self.contacts = [
            {
                "id": "ct_at_mug_main",
                "email": "biobank@medunigraz.at",
                "country": "AT",
            },
            {
                "id": "ct_at_muw_main",
                "email": "biobank@meduniwien.ac.at",
                "country": "AT",
            },
            {
                "id": "ct_at_mug_specialist",
                "email": "sabrina.kral@medunigraz.at",
                "country": "AT",
            },
            {
                "id": "ct_shared_study",
                "email": "coordination@shared-study.org",
                "country": "EU",
            },
            {
                "id": "ct_same_institution_split",
                "email": "shared@same-inst.example",
                "address": "Main Street 1",
                "zip": "12345",
                "city": "Leiden",
                "country": "NL",
            },
            {
                "id": "ct_multi_owner_service",
                "email": "service@umbrella.example",
                "country": "NL",
            },
            {
                "id": "ct_service_a_main",
                "email": "main@inst-a.example",
                "country": "NL",
            },
            {
                "id": "ct_service_b_main",
                "email": "main@inst-b.example",
                "country": "NL",
            },
        ]
        self.biobanks = {
            "bbmri-eric:ID:AT_MUG": {
                "id": "bbmri-eric:ID:AT_MUG",
                "name": "Biobank Graz",
                "country": "AT",
                "contact": {"id": "ct_at_mug_main"},
            },
            "bbmri-eric:ID:AT_MUW": {
                "id": "bbmri-eric:ID:AT_MUW",
                "name": "MedUni Wien Biobank",
                "country": "AT",
                "contact": {"id": "ct_at_muw_main"},
            },
            "bbmri-eric:ID:DE_A": {
                "id": "bbmri-eric:ID:DE_A",
                "name": "Biobank A",
                "country": "DE",
                "contact": None,
            },
            "bbmri-eric:ID:DE_B": {
                "id": "bbmri-eric:ID:DE_B",
                "name": "Biobank B",
                "country": "DE",
                "contact": None,
            },
            "bbmri-eric:ID:NL_INST_A": {
                "id": "bbmri-eric:ID:NL_INST_A",
                "name": "Institution Split A",
                "country": "NL",
                "contact": {"id": "ct_same_institution_split"},
            },
            "bbmri-eric:ID:NL_INST_B": {
                "id": "bbmri-eric:ID:NL_INST_B",
                "name": "Institution Split B",
                "country": "NL",
                "contact": {"id": "ct_same_institution_split_biobank"},
            },
            "bbmri-eric:ID:NL_SERVICE_A": {
                "id": "bbmri-eric:ID:NL_SERVICE_A",
                "name": "Service A",
                "country": "NL",
                "contact": {"id": "ct_service_a_main"},
            },
            "bbmri-eric:ID:NL_SERVICE_B": {
                "id": "bbmri-eric:ID:NL_SERVICE_B",
                "name": "Service B",
                "country": "NL",
                "contact": {"id": "ct_service_b_main"},
            },
            "bbmri-eric:ID:NL_SERVICE_MAIN_A": {
                "id": "bbmri-eric:ID:NL_SERVICE_MAIN_A",
                "name": "Umbrella Owner A",
                "country": "NL",
                "contact": {"id": "ct_multi_owner_service"},
            },
            "bbmri-eric:ID:NL_SERVICE_MAIN_B": {
                "id": "bbmri-eric:ID:NL_SERVICE_MAIN_B",
                "name": "Umbrella Owner B",
                "country": "NL",
                "contact": {"id": "ct_multi_owner_service"},
            },
        }
        self.contacts.extend(
            [
                {
                    "id": "ct_same_institution_split_biobank",
                    "email": "other@same-inst.example",
                    "address": "Main Street 1",
                    "zip": "12345",
                    "city": "Leiden",
                    "country": "NL",
                },
                {
                    "id": "ct_multi_owner_service_b",
                    "email": "helpdesk@umbrella.example",
                    "country": "NL",
                },
            ]
        )
        self.collections = [
            {
                "id": "bbmri-eric:ID:AT_MUG:collection:local",
                "biobank": {"id": "bbmri-eric:ID:AT_MUG"},
                "contact": {"id": "ct_at_mug_specialist"},
                "withdrawn": False,
            },
            {
                "id": "bbmri-eric:ID:AT_MUW:collection:9727-Atrialfibrillation:Atrialfibrillation-CitratPlasma",
                "biobank": {"id": "bbmri-eric:ID:AT_MUW"},
                "contact": {"id": "ct_at_mug_specialist"},
                "withdrawn": False,
            },
            {
                "id": "bbmri-eric:ID:DE_A:collection:shared1",
                "biobank": {"id": "bbmri-eric:ID:DE_A"},
                "contact": {"id": "ct_shared_study"},
                "withdrawn": False,
            },
            {
                "id": "bbmri-eric:ID:DE_B:collection:shared2",
                "biobank": {"id": "bbmri-eric:ID:DE_B"},
                "contact": {"id": "ct_shared_study"},
                "withdrawn": False,
            },
            {
                "id": "bbmri-eric:ID:NL_INST_A:collection:local_a",
                "biobank": {"id": "bbmri-eric:ID:NL_INST_A"},
                "contact": {"id": "ct_same_institution_split"},
                "withdrawn": False,
            },
            {
                "id": "bbmri-eric:ID:NL_INST_B:collection:local_b",
                "biobank": {"id": "bbmri-eric:ID:NL_INST_B"},
                "contact": {"id": "ct_same_institution_split"},
                "withdrawn": False,
            },
            {
                "id": "bbmri-eric:ID:NL_SERVICE_A:collection:service_a",
                "biobank": {"id": "bbmri-eric:ID:NL_SERVICE_A"},
                "contact": {"id": "ct_multi_owner_service"},
                "withdrawn": False,
            },
            {
                "id": "bbmri-eric:ID:NL_SERVICE_B:collection:service_b",
                "biobank": {"id": "bbmri-eric:ID:NL_SERVICE_B"},
                "contact": {"id": "ct_multi_owner_service"},
                "withdrawn": False,
            },
        ]

    def getContacts(self):
        return self.contacts

    def getCollections(self):
        return self.collections

    def getBiobanks(self):
        return list(self.biobanks.values())

    def getBiobankById(self, biobank_id):
        return self.biobanks[biobank_id]

    def getContact(self, contact_id):
        for contact in self.contacts:
            if contact["id"] == contact_id:
                return contact
        raise KeyError(contact_id)

    def getContactNN(self, contact_id):
        return "AT" if "at_" in contact_id else "DE"

    def getCollectionNN(self, collection_id):
        return collection_id.split(":ID:", 1)[1][:2]

    def isCollectionWithdrawn(self, collection_id):
        return False


def test_contact_reuse_reports_cross_biobank_info_only():
    warnings = ContactReuse().check(ContactAssignmentDirectoryStub(), SimpleNamespace())
    warning_ids = {warning.dataCheckID for warning in warnings}
    assert "CTR:CrossBiobankReuse" in warning_ids

    by_contact = {
        warning.directoryEntityID: warning
        for warning in warnings
    }
    assert by_contact["ct_shared_study"].level.name == "INFO"
    assert by_contact["ct_multi_owner_service"].level.name == "INFO"
    assert "ct_same_institution_split" not in by_contact
    assert "ct_at_mug_specialist" not in by_contact


def test_contact_assignments_warn_for_unique_foreign_institution_contact_usage():
    warnings = ContactAssignments().check(ContactAssignmentDirectoryStub(), SimpleNamespace())
    warnings_by_id = {}
    for warning in warnings:
        warnings_by_id.setdefault(warning.dataCheckID, []).append(warning)

    contact_warning = next(
        warning
        for warning in warnings_by_id["CTA:CrossBiobankInstitutionContact"]
        if warning.directoryEntityID == "ct_at_mug_specialist"
    )
    assert "medunigraz.at" in contact_warning.message
    assert "AT_MUG" in contact_warning.message
    assert "AT_MUW" in contact_warning.message

    collection_warning = next(
        warning
        for warning in warnings_by_id["CTA:CollectionForeignInstitutionContact"]
        if warning.directoryEntityID.endswith("Atrialfibrillation-CitratPlasma")
    )
    assert "medunigraz.at" in collection_warning.message
    assert "AT_MUG" in collection_warning.message
    assert "AT_MUW" in collection_warning.message


def test_contact_assignments_do_not_warn_for_generic_cross_biobank_shared_contact():
    warnings = ContactAssignments().check(ContactAssignmentDirectoryStub(), SimpleNamespace())
    warned_entities = {warning.directoryEntityID for warning in warnings}
    assert "ct_shared_study" not in warned_entities
    assert "bbmri-eric:ID:DE_A:collection:shared1" not in warned_entities
    assert "bbmri-eric:ID:DE_B:collection:shared2" not in warned_entities
    assert "ct_same_institution_split" not in warned_entities
    assert "bbmri-eric:ID:NL_INST_A:collection:local_a" not in warned_entities
    assert "bbmri-eric:ID:NL_INST_B:collection:local_b" not in warned_entities
    assert "ct_multi_owner_service" not in warned_entities
    assert "bbmri-eric:ID:NL_SERVICE_A:collection:service_a" not in warned_entities
    assert "bbmri-eric:ID:NL_SERVICE_B:collection:service_b" not in warned_entities
