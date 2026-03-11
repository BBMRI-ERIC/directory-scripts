# vim:ts=8:sw=8:tw=0:noet

import logging as log

from yapsy.IPlugin import IPlugin

from contact_assignment_utils import (
	build_biobank_contact_maps,
	build_collection_contact_usage,
	biobanks_all_same_institution,
	get_contact_address_key,
	get_email_domain,
	get_single_biobank_domain_owner,
)
from customwarnings import DataCheckEntityType, DataCheckWarning, DataCheckWarningLevel, make_check_id


CHECK_DOCS = {
	'CTR:CrossBiobankReuse': {
		'entity': 'CONTACT',
		'fields': ['CONTACT.collections', 'COLLECTION.contact', 'COLLECTION.biobank'],
		'severity': 'INFO',
		'summary': 'A contact is reused by collections belonging to more than one biobank.',
		'fix': 'Review whether the same contact is intentionally shared across the listed biobanks. If so, this informational check can be disabled or the specific contact can be suppressed.'
	}
}


class ContactReuse(IPlugin):
	CHECK_ID_PREFIX = "CTR"

	def check(self, dir, args):
		warnings = []
		log.info("Running cross-biobank contact reuse info checks (ContactReuse)")

		contact_to_collections, contact_to_biobank_counts = build_collection_contact_usage(dir)
		_, main_contact_to_biobanks, domain_to_biobanks, address_to_biobanks, biobank_signatures = build_biobank_contact_maps(dir)
		for contact in dir.getContacts():
			contact_id = contact.get('id')
			if not contact_id:
				continue
			biobank_counts = contact_to_biobank_counts.get(contact_id, {})
			if len(biobank_counts) <= 1:
				continue
			biobank_ids = sorted(biobank_counts.keys())
			if biobanks_all_same_institution(biobank_ids, biobank_signatures):
				continue
			# Do not emit the weaker INFO when the same contact already satisfies the
			# stronger institution-tied WARNING logic.
			domain = get_email_domain(contact.get('email', ''))
			domain_owner = get_single_biobank_domain_owner(domain, domain_to_biobanks)
			address_key = get_contact_address_key(contact)
			address_owners = sorted(address_to_biobanks.get(address_key, set())) if address_key else []
			main_contact_biobanks = sorted(main_contact_to_biobanks.get(contact_id, set()))
			has_unique_warning_evidence = False
			if len(main_contact_biobanks) == 1:
				has_unique_warning_evidence = True
			elif domain_owner:
				has_unique_warning_evidence = True
			elif len(address_owners) == 1:
				has_unique_warning_evidence = True
			if has_unique_warning_evidence:
				continue
			example_collections = sorted(contact_to_collections.get(contact_id, []))[:3]
			message = (
				f"Contact is reused by collections in multiple biobanks: {', '.join(biobank_ids)}. "
				f"Example collection assignments: {', '.join(example_collections)}. "
				"This may be intentional shared support, but review whether the cross-biobank reuse is expected."
			)
			action = (
				"Review whether the same contact is intentionally shared across the listed biobanks. "
				"If it is intentional by design, disable this informational plugin or suppress the specific contact."
			)
			warnings.append(
				DataCheckWarning(
					make_check_id(self, "CrossBiobankReuse"),
					"",
					dir.getContactNN(contact_id),
					DataCheckWarningLevel.INFO,
					contact_id,
					DataCheckEntityType.CONTACT,
					'NA',
					message,
					action,
				)
			)
		return warnings
