# vim:ts=8:sw=8:tw=0:noet

import logging as log

from yapsy.IPlugin import IPlugin

from contact_assignment_utils import build_collection_contact_usage
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
		for contact in dir.getContacts():
			contact_id = contact.get('id')
			if not contact_id:
				continue
			biobank_counts = contact_to_biobank_counts.get(contact_id, {})
			if len(biobank_counts) <= 1:
				continue
			biobank_ids = sorted(biobank_counts.keys())
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
