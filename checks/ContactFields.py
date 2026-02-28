# vim:ts=8:sw=8:tw=0:noet

import re
import logging as log
#import DNS
import os

# this is ugly and only for assertive programming
import __main__ 

from yapsy.IPlugin import IPlugin
from validate_email import validate_email
from diskcache import Cache

from customwarnings import DataCheckWarningLevel, DataCheckWarning, DataCheckEntityType, make_check_id
from nncontacts import NNContacts

PLACEHOLDER_EMAIL_DOMAINS = frozenset({"example.org", "test.com"})
GENERIC_EMAIL_SUFFIXES = frozenset(
    {
        "com",
        "org",
        "net",
        "edu",
        "gov",
        "mil",
        "int",
        "info",
        "biz",
        "name",
        "pro",
        "eu",
    }
)

# Machine-readable check documentation for the manual generator and other tooling.
# Keep severity/entity/fields aligned with the emitted DataCheckWarning(...) calls.
CHECK_DOCS = {'CTF:EmailMissing': {'entity': 'CONTACT',
                                                   'fields': ['email'],
                                                   'severity': 'ERROR',
                                                   'summary': 'Missing email for '
                                                              "contact ('email' "
                                                              'attribute is empty)'},
 'CTF:EmailInvalid': {'entity': 'CONTACT',
                                              'fields': ['email'],
                                              'severity': 'WARNING',
                                              'summary': 'Email for contact is invalid '
                                                         "- offending  'email' "
                                                         'attribute value: '},
 'CTF:EmailUnreachable': {'entity': 'CONTACT',
                                                'fields': ['email'],
                                                'severity': 'WARNING',
                                                'summary': 'Email for contact seems to '
                                                           'be unreachable because of '
                                                           'missing DNS MX record'},
 'CTF:EmailPlaceholder': {'entity': 'CONTACT',
                                                'fields': ['email'],
                                                'fix': 'Replace the placeholder email '
                                                       'address with a real working '
                                                       'contact email address for the '
                                                       'person or organisation.',
                                                'severity': 'ERROR',
                                                'summary': 'The contact email uses a '
                                                           'placeholder domain such '
                                                           'as example.org, test.com, or '
                                                           'unknown.<suffix> and is '
                                                           'not a real operational '
                                                           'email address.'},
 'CTF:EmailCountrySuffix': {'entity': 'CONTACT',
                                                  'fields': ['CONTACT.email', 'BIOBANK.country'],
                                                  'fix': 'Verify that the email '
                                                         'belongs to the correct '
                                                         'institution. If the email '
                                                         'domain uses a country-code '
                                                         'suffix that does not match '
                                                         'the linked biobank country, '
                                                         'replace it with the correct '
                                                         'institutional email or '
                                                         'confirm that the cross-border '
                                                         'assignment is intentional.',
                                                  'severity': 'WARNING',
                                                  'summary': 'The contact email uses a '
                                                             'country-code domain '
                                                             'suffix that does not '
                                                             'match the linked '
                                                             'biobank country. Generic '
                                                             'domains and non-country '
                                                             'staging areas such as '
                                                             'EU and EXT are '
                                                             'excluded.'},
 'CTF:FirstNameMissing': {'entity': 'CONTACT',
                                             'fields': ['first_name'],
                                             'severity': 'WARNING',
                                             'summary': 'Missing first name for '
                                                        "contact ('first_name' "
                                                        'attribute is empty)'},
 'CTF:LastNameMissing': {'entity': 'CONTACT',
                                                    'fields': ['last_name'],
                                                    'severity': 'WARNING',
                                                    'summary': 'Missing last name for '
                                                               "contact ('last_name' "
                                                               'attribute is empty)'},
 'CTF:PhoneMissing': {'entity': 'CONTACT',
                                                   'fields': ['phone'],
                                                   'severity': 'WARNING',
                                                   'summary': 'Missing phone for '
                                                              "contact ('phone' "
                                                              "attribute is empty'"},
 'CTF:PhoneInvalid': {'entity': 'CONTACT',
                                                  'fields': ['phone'],
                                                  'severity': 'ERROR',
                                                  'summary': 'Phone number for contact '
                                                             'does not conform to the '
                                                             'E.123 international '
                                                             'standard (means starts '
                                                             'with + sign, no spaces) '
                                                             '- offending phone number '
                                                             "in 'phone' attribute: "}}


def get_email_domain(email: str) -> str:
    """Return normalized domain part of an email address or empty string."""
    if not isinstance(email, str) or "@" not in email:
        return ""
    return email.rsplit("@", 1)[1].strip().lower()


def is_placeholder_email_domain(domain: str) -> bool:
    """Return whether the email domain is a known placeholder domain."""
    if not domain:
        return False
    if domain in PLACEHOLDER_EMAIL_DOMAINS:
        return True
    return domain.startswith("unknown.")


def get_email_country_suffix(email: str) -> str:
    """Return normalized country-code-like email suffix or empty string."""
    domain = get_email_domain(email)
    if not domain or "." not in domain:
        return ""
    suffix = domain.rsplit(".", 1)[1].upper()
    if suffix.lower() in GENERIC_EMAIL_SUFFIXES:
        return ""
    if not NNContacts.is_iso_country_code(suffix):
        return ""
    return suffix


def get_contact_biobank_contexts(dir, contact: dict) -> list[tuple[str, str]]:
    """Return linked country-based biobank contexts as (biobank_id, country)."""
    contexts: list[tuple[str, str]] = []
    seen_biobanks = set()

    for biobank_ref in contact.get("biobanks", []):
        biobank_id = biobank_ref.get("id")
        if biobank_id:
            seen_biobanks.add(biobank_id)

    for collection_ref in contact.get("collections", []):
        collection_id = collection_ref.get("id")
        if not collection_id:
            continue
        try:
            biobank_id = dir.getCollectionBiobankId(collection_id)
        except Exception:
            continue
        if biobank_id:
            seen_biobanks.add(biobank_id)

    for biobank_id in sorted(seen_biobanks):
        biobank = dir.getBiobankById(biobank_id)
        if not biobank:
            continue
        country_value = biobank.get("country")
        if isinstance(country_value, dict):
            country_value = country_value.get("id") or country_value.get("name")
        country = NNContacts.normalize_code(country_value)
        staging_area = NNContacts.extract_staging_area(biobank.get("id"))
        if not country:
            continue
        if NNContacts.is_non_member_staging_area(staging_area, country=country):
            continue
        contexts.append((biobank_id, country))

    return contexts


def build_country_suffix_warning(contact: dict, contexts: list[tuple[str, str]]) -> str:
    """Return mismatch warning text for an email country suffix."""
    suffix = get_email_country_suffix(contact["email"])
    countries = sorted({country for _, country in contexts})
    biobank_ids = sorted({biobank_id for biobank_id, _ in contexts})
    countries_text = ", ".join(countries)
    biobanks_text = ", ".join(biobank_ids)
    return (
        f"Email for contact uses country-code domain suffix '.{suffix.lower()}', "
        f"but the linked biobank country is {countries_text} "
        f"(linked biobank IDs: {biobanks_text})"
    )

class ContactFields(IPlugin):
	CHECK_ID_PREFIX = "CTF"
	def check(self, dir, args):
		warnings = []
		log.info("Running contact fields checks (ContactFields)")
		ValidateEmails = True
		assert 'emails' in __main__.remoteCheckList
		if 'emails' in args.disableChecksRemote:
			ValidateEmails = False
		else:
			ValidateEmails = True

		cache_dir = 'data-check-cache/emails'
		if not os.path.exists(cache_dir):
			os.makedirs(cache_dir)
		cache = Cache(cache_dir)
		if 'emails' in args.purgeCaches:
			cache.clear()
			
		for contact in dir.getContacts():
			if(not 'first_name' in contact or re.search('^\s*$', contact['first_name'])):
				warnings.append(DataCheckWarning(make_check_id(self, "FirstNameMissing"), "", dir.getContactNN(contact['id']), DataCheckWarningLevel.WARNING, contact['id'], DataCheckEntityType.CONTACT, 'NA', "Missing first name for contact ('first_name' attribute is empty)"))
			if(not 'last_name' in contact or re.search('^\s*$', contact['last_name'])):
				warnings.append(DataCheckWarning(make_check_id(self, "LastNameMissing"), "", dir.getContactNN(contact['id']), DataCheckWarningLevel.WARNING, contact['id'], DataCheckEntityType.CONTACT, 'NA', "Missing last name for contact ('last_name' attribute is empty)"))
			if(not 'email' in contact or re.search('^\s*$', contact['email'])):
				warnings.append(DataCheckWarning(make_check_id(self, "EmailMissing"), "", dir.getContactNN(contact['id']), DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, 'NA', "Missing email for contact ('email' attribute is empty)"))
			elif(not validate_email(contact['email'])):
				warnings.append(DataCheckWarning(make_check_id(self, "EmailInvalid"), "", dir.getContactNN(contact['id']), DataCheckWarningLevel.WARNING, contact['id'], DataCheckEntityType.CONTACT, 'NA', "Email for contact is invalid - offending  'email' attribute value: " + contact['email']))
			else:
				email_domain = get_email_domain(contact['email'])
				placeholder_email = is_placeholder_email_domain(email_domain)
				if placeholder_email:
					warnings.append(DataCheckWarning(make_check_id(self, "EmailPlaceholder"), "", dir.getContactNN(contact['id']), DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, 'NA', "Email for contact uses a placeholder domain and must be replaced - offending 'email' attribute value: " + contact['email']))

				email_country_suffix = get_email_country_suffix(contact['email'])
				if email_country_suffix:
					contexts = get_contact_biobank_contexts(dir, contact)
					if contexts and email_country_suffix not in {country for _, country in contexts}:
						warnings.append(DataCheckWarning(make_check_id(self, "EmailCountrySuffix"), "", dir.getContactNN(contact['id']), DataCheckWarningLevel.WARNING, contact['id'], DataCheckEntityType.CONTACT, 'NA', build_country_suffix_warning(contact, contexts)))

				# This is pretty dramatic test and should be used sparingly
				if ValidateEmails and not placeholder_email:
					contact_email = contact['email']
					log_message = "Validating email " + contact_email
					# XXX: does not work in most cases
					#if(not validate_email(contact['email'],verify=True)):
					try:
						if(contact_email in cache):
							cache_result = cache[contact_email]
							if(cache_result['valid']):
								log_message += " -> OK"
							else:
								log_message += " -> failed"
								warnings.append(cache_result['warning'])
						else:
							if(not validate_email(contact_email,check_mx=True)):
								log_message += " -> failed"
								warning = DataCheckWarning(make_check_id(self, "EmailUnreachable"), "", dir.getContactNN(contact['id']), DataCheckWarningLevel.WARNING, contact['id'], DataCheckEntityType.CONTACT, 'NA', "Email for contact seems to be unreachable because of missing DNS MX record")
								warnings.append(warning)
								cache[contact_email] = { 'valid' : False, 'warning' : warning }
							else:
								log_message += " -> OK"
								cache[contact_email] = { 'valid' : True, 'warning' : None }
						log.info(log_message)
					except (DNS.Base.TimeoutError, DNS.Base.ServerError, DNS.Base.SocketError) as e:
						log_message += " -> failed with exception (" + str(e) + ")"
						log.error(log_message)

			if(not 'phone' in contact or re.search('^\s*$', contact['phone'])):
				warnings.append(DataCheckWarning(make_check_id(self, "PhoneMissing"), "", dir.getContactNN(contact['id']), DataCheckWarningLevel.WARNING, contact['id'], DataCheckEntityType.CONTACT, 'NA', "Missing phone for contact ('phone' attribute is empty'"))
			elif(not re.search('^\+(?:[0-9]??){6,14}[0-9]$', contact['phone'])):
				warnings.append(DataCheckWarning(make_check_id(self, "PhoneInvalid"), "", dir.getContactNN(contact['id']), DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, 'NA', "Phone number for contact does not conform to the E.123 international standard (means starts with + sign, no spaces) - offending phone number in 'phone' attribute: " + contact['phone']))
		return warnings
