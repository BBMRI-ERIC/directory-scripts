# vim:ts=8:sw=8:tw=0:noet

import logging as log

from yapsy.IPlugin import IPlugin

from contact_assignment_utils import (
	build_biobank_contact_maps,
	build_collection_contact_usage,
	biobanks_all_same_institution,
	biobanks_same_institution,
	count_institution_groups,
	contact_matches_biobank_institution,
	get_contact_ids,
	get_contact_address_key,
	get_email_domain,
	get_single_biobank_domain_owner,
)
from customwarnings import DataCheckEntityType, DataCheckWarning, DataCheckWarningLevel, make_check_id


CHECK_DOCS = {
	'CTA:CrossBiobankInstitutionContact': {
		'entity': 'CONTACT',
		'fields': ['CONTACT.email', 'CONTACT.collections', 'COLLECTION.contact', 'COLLECTION.biobank', 'BIOBANK.contact'],
		'severity': 'WARNING',
		'summary': 'A contact is reused across biobanks even though its institutional email domain or its biobank-level role points to one specific biobank.',
		'fix': 'Verify whether the cross-biobank reuse is intentional. If the contact belongs to one specific biobank or institution, replace the foreign biobank collection assignments with the correct local contact.'
	},
	'CTA:CollectionForeignInstitutionContact': {
		'entity': 'COLLECTION',
		'fields': ['COLLECTION.contact', 'COLLECTION.biobank', 'CONTACT.email', 'BIOBANK.contact'],
		'severity': 'WARNING',
		'summary': 'A collection uses a contact whose institutional email domain or biobank-level assignment points to another biobank.',
		'fix': 'Review whether the collection contact was assigned by mistake. If the collection is locally managed, replace it with the correct contact for the owning biobank or document the intentional cross-biobank collaboration.'
	}
}


def _biobank_label(dir, biobank_id: str) -> str:
	try:
		biobank = dir.getBiobankById(biobank_id)
	except Exception:
		return biobank_id
	name = biobank.get('name')
	return f"{biobank_id} ({name})" if name else biobank_id


class ContactAssignments(IPlugin):
	CHECK_ID_PREFIX = "CTA"

	def check(self, dir, args):
		warnings = []
		log.info("Running probabilistic cross-biobank contact assignment checks (ContactAssignments)")

		contact_to_collections, contact_to_biobank_counts = build_collection_contact_usage(dir)
		_, main_contact_to_biobanks, domain_to_biobanks, address_to_biobanks, biobank_signatures = build_biobank_contact_maps(dir)

		for contact in dir.getContacts():
			contact_id = contact.get('id')
			if not contact_id:
				continue
			biobank_counts = contact_to_biobank_counts.get(contact_id, {})
			if len(biobank_counts) <= 1:
				continue
			used_biobanks = sorted(biobank_counts.keys())
			if biobanks_all_same_institution(used_biobanks, biobank_signatures):
				continue
			if count_institution_groups(used_biobanks, biobank_signatures) > 2:
				continue
			domain = get_email_domain(contact.get('email', ''))
			domain_owner = get_single_biobank_domain_owner(domain, domain_to_biobanks)
			address_key = get_contact_address_key(contact)
			address_owners = sorted(address_to_biobanks.get(address_key, set())) if address_key else []
			main_contact_biobanks = sorted(main_contact_to_biobanks.get(contact_id, set()))
			# Biobank-level ownership must stay unique enough to be meaningful warning evidence.
			# If the same contact is the main biobank contact for multiple biobanks, that pattern is
			# only a shared cross-institution reuse signal and should remain INFO-only.
			if len(main_contact_biobanks) > 1:
				continue
			reasons = []
			if main_contact_biobanks and biobanks_all_same_institution(main_contact_biobanks, biobank_signatures):
				reasons.append(
					f"the contact is the biobank-level contact of {', '.join(_biobank_label(dir, biobank_id) for biobank_id in main_contact_biobanks)}"
				)
			if domain_owner:
				reasons.append(
					f"the institutional email domain '{domain}' is the biobank-contact domain of {_biobank_label(dir, domain_owner)}"
				)
			elif len(address_owners) == 1:
				reasons.append(
					f"the contact address matches the biobank-contact address of {_biobank_label(dir, address_owners[0])}"
				)
			if not reasons:
				continue
			example_collections = sorted(contact_to_collections.get(contact_id, []))[:3]
			message = (
				f"Contact is reused by collections in multiple biobanks ({', '.join(used_biobanks)}), but "
				+ " and ".join(reasons)
				+ f". Example collection assignments: {', '.join(example_collections)}. "
				+ "This may be a false positive in collaborative setups, but it is suspicious and should be reviewed."
			)
			action = (
				"Review whether the same contact is intentionally reused across these biobanks. "
				"If not, replace the foreign biobank collection assignments with the correct local contact."
			)
			warnings.append(
				DataCheckWarning(
					make_check_id(self, "CrossBiobankInstitutionContact"),
					"",
					dir.getContactNN(contact_id),
					DataCheckWarningLevel.WARNING,
					contact_id,
					DataCheckEntityType.CONTACT,
					'NA',
					message,
					action,
				)
			)

		for collection in dir.getCollections():
			collection_id = collection.get('id')
			if not collection_id:
				continue
			collection_biobank_id = collection.get('biobank', {}).get('id')
			if not collection_biobank_id:
				continue
			for contact_id in get_contact_ids(collection.get('contact')):
				biobank_counts = contact_to_biobank_counts.get(contact_id, {})
				if len(biobank_counts) <= 1:
					continue
				try:
					contact = dir.getContact(contact_id)
				except Exception:
					continue
				domain = get_email_domain(contact.get('email', ''))
				domain_owner = get_single_biobank_domain_owner(domain, domain_to_biobanks)
				address_key = get_contact_address_key(contact)
				address_owners = sorted(address_to_biobanks.get(address_key, set())) if address_key else []
				if contact_matches_biobank_institution(contact, collection_biobank_id, biobank_signatures):
					continue
				foreign_reasons = []
				main_contact_biobanks = sorted(main_contact_to_biobanks.get(contact_id, set()) - {collection_biobank_id})
				if len(main_contact_biobanks) > 1:
					continue
				if main_contact_biobanks and biobanks_all_same_institution(main_contact_biobanks, biobank_signatures):
					if not any(biobanks_same_institution(collection_biobank_id, biobank_id, biobank_signatures) for biobank_id in main_contact_biobanks):
						foreign_reasons.append(
							f"the contact is the biobank-level contact of {', '.join(_biobank_label(dir, biobank_id) for biobank_id in main_contact_biobanks)}"
						)
				if domain_owner and domain_owner != collection_biobank_id:
					if not biobanks_same_institution(collection_biobank_id, domain_owner, biobank_signatures):
						foreign_reasons.append(
							f"the institutional email domain '{domain}' is the biobank-contact domain of {_biobank_label(dir, domain_owner)}"
						)
				elif len(address_owners) == 1 and address_owners[0] != collection_biobank_id:
					if not biobanks_same_institution(collection_biobank_id, address_owners[0], biobank_signatures):
						foreign_reasons.append(
							f"the contact address matches the biobank-contact address of {_biobank_label(dir, address_owners[0])}"
						)
				if len(main_contact_to_biobanks.get(contact_id, set())) > 1 and not foreign_reasons:
					continue
				if not foreign_reasons:
					continue
				other_biobanks = sorted(
					biobank_id
					for biobank_id in biobank_counts.keys()
					if biobank_id != collection_biobank_id
					and not biobanks_same_institution(collection_biobank_id, biobank_id, biobank_signatures)
				)
				if not other_biobanks:
					continue
				if count_institution_groups([collection_biobank_id, *other_biobanks], biobank_signatures) > 2:
					continue
				message = (
					f"Collection {collection_id} belongs to {_biobank_label(dir, collection_biobank_id)} but uses contact {contact_id}, while "
					+ " and ".join(foreign_reasons)
					+ f". The same contact is also used by collections in {', '.join(_biobank_label(dir, biobank_id) for biobank_id in other_biobanks)}. "
					+ "This may indicate a mistaken foreign-institution contact assignment; false positives are possible in collaborative setups."
				)
				action = (
					"Review whether this collection should instead use a contact from its own biobank. "
					"If the cross-biobank contact is intentional, document or suppress the exception."
				)
				warnings.append(
					DataCheckWarning(
						make_check_id(self, "CollectionForeignInstitutionContact"),
						"",
						dir.getCollectionNN(collection_id),
						DataCheckWarningLevel.WARNING,
						collection_id,
						DataCheckEntityType.COLLECTION,
						dir.isCollectionWithdrawn(collection_id),
						message,
						action,
					)
				)

		return warnings
