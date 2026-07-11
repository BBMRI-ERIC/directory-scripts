#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

"""Shared helpers for probabilistic contact-assignment QC checks."""

from __future__ import annotations

from collections import Counter, defaultdict


PUBLIC_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "outlook.com",
        "hotmail.com",
        "live.com",
        "msn.com",
        "yahoo.com",
        "yahoo.co.uk",
        "icloud.com",
        "me.com",
        "mac.com",
        "aol.com",
        "proton.me",
        "protonmail.com",
        "pm.me",
        "gmx.com",
        "gmx.de",
        "web.de",
    }
)


def get_contact_ids(field) -> list[str]:
    """Return referenced contact IDs from a Molgenis contact field."""
    if isinstance(field, dict):
        contact_id = field.get("id")
        return [contact_id] if contact_id else []
    if isinstance(field, list):
        contact_ids = []
        for item in field:
            if isinstance(item, dict):
                contact_id = item.get("id")
            else:
                contact_id = item
            if contact_id:
                contact_ids.append(contact_id)
        return contact_ids
    if isinstance(field, str) and field:
        return [field]
    return []


def get_email_domain(email: str) -> str:
    """Return normalized email domain or empty string."""
    if not isinstance(email, str) or "@" not in email:
        return ""
    return email.rsplit("@", 1)[1].strip().lower()


def _normalize_text(value: str) -> str:
    """Return a conservative lowercase normalized text token."""
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().lower().split())


def is_institution_specific_domain(domain: str) -> bool:
    """Return whether an email domain looks institution-specific enough for warnings."""
    if not domain:
        return False
    if domain in PUBLIC_EMAIL_DOMAINS:
        return False
    return True


def get_contact_address_key(contact: dict) -> str:
    """Return a normalized address-based institution key or empty string.

    Address is treated as institution evidence only when the street/address is present
    together with at least one additional locality signal. City alone is intentionally
    ignored because it is too weak for institution identity.
    """
    if not isinstance(contact, dict):
        return ""
    address = _normalize_text(contact.get("address"))
    zip_code = _normalize_text(contact.get("zip"))
    city = _normalize_text(contact.get("city"))
    country = _normalize_text(contact.get("country"))
    if not address:
        return ""
    locality = zip_code or city or country
    if not locality:
        return ""
    return f"{address}|{locality}|{country}"


def build_collection_contact_usage(dir) -> tuple[dict[str, list[str]], dict[str, Counter]]:
    """Return contact -> collections and contact -> collection-counts-by-biobank maps."""
    contact_to_collections: dict[str, list[str]] = defaultdict(list)
    contact_to_biobank_counts: dict[str, Counter] = defaultdict(Counter)

    for collection in dir.getCollections():
        biobank_id = collection.get("biobank", {}).get("id")
        for contact_id in get_contact_ids(collection.get("contact")):
            contact_to_collections[contact_id].append(collection["id"])
            if biobank_id:
                contact_to_biobank_counts[contact_id][biobank_id] += 1

    return contact_to_collections, contact_to_biobank_counts


def build_biobank_contact_maps(dir) -> tuple[
    dict[str, str],
    dict[str, set[str]],
    dict[str, set[str]],
    dict[str, set[str]],
    dict[str, dict[str, str]],
]:
    """Return biobank main-contact mappings and domain associations.

    Returns:
        - biobank_id -> main contact id
        - contact id -> biobank ids for which it is the biobank-level contact
        - institution-specific main-contact email domain -> biobank ids
        - normalized main-contact address key -> biobank ids
        - biobank_id -> {"domain": ..., "address_key": ...}
    """
    biobank_to_contact: dict[str, str] = {}
    contact_to_biobanks: dict[str, set[str]] = defaultdict(set)
    domain_to_biobanks: dict[str, set[str]] = defaultdict(set)
    address_to_biobanks: dict[str, set[str]] = defaultdict(set)
    biobank_signatures: dict[str, dict[str, str]] = {}

    for biobank in dir.getBiobanks():
        biobank_id = biobank.get("id")
        if not biobank_id or ":networkID:" in biobank_id:
            continue
        contact_ids = get_contact_ids(biobank.get("contact"))
        if len(contact_ids) != 1:
            continue
        contact_id = contact_ids[0]
        biobank_to_contact[biobank_id] = contact_id
        contact_to_biobanks[contact_id].add(biobank_id)
        try:
            contact = dir.getContact(contact_id)
        except Exception:
            continue
        domain = get_email_domain(contact.get("email", ""))
        if is_institution_specific_domain(domain):
            domain_to_biobanks[domain].add(biobank_id)
        address_key = get_contact_address_key(contact)
        if address_key:
            address_to_biobanks[address_key].add(biobank_id)
        biobank_signatures[biobank_id] = {
            "domain": domain if is_institution_specific_domain(domain) else "",
            "address_key": address_key,
        }

    return biobank_to_contact, contact_to_biobanks, domain_to_biobanks, address_to_biobanks, biobank_signatures


def get_single_biobank_domain_owner(domain: str, domain_to_biobanks: dict[str, set[str]]) -> str | None:
    """Return the unique biobank associated with a main-contact domain, if any."""
    owners = sorted(domain_to_biobanks.get(domain, set()))
    if len(owners) == 1:
        return owners[0]
    return None


def biobanks_same_institution(
    biobank_a: str,
    biobank_b: str,
    biobank_signatures: dict[str, dict[str, str]],
) -> bool:
    """Return whether two biobanks share the same institution by domain or address."""
    if biobank_a == biobank_b:
        return True
    signature_a = biobank_signatures.get(biobank_a, {})
    signature_b = biobank_signatures.get(biobank_b, {})
    domain_a = signature_a.get("domain", "")
    domain_b = signature_b.get("domain", "")
    if domain_a and domain_b and domain_a == domain_b:
        return True
    address_a = signature_a.get("address_key", "")
    address_b = signature_b.get("address_key", "")
    if address_a and address_b and address_a == address_b:
        return True
    return False


def contact_matches_biobank_institution(
    contact: dict,
    biobank_id: str,
    biobank_signatures: dict[str, dict[str, str]],
) -> bool:
    """Return whether a contact matches the institution of a biobank main contact."""
    signature = biobank_signatures.get(biobank_id, {})
    domain = get_email_domain(contact.get("email", ""))
    if is_institution_specific_domain(domain) and domain and domain == signature.get("domain", ""):
        return True
    address_key = get_contact_address_key(contact)
    if address_key and address_key == signature.get("address_key", ""):
        return True
    return False


def biobanks_all_same_institution(
    biobank_ids: list[str],
    biobank_signatures: dict[str, dict[str, str]],
) -> bool:
    """Return whether every biobank in the list belongs to the same institution."""
    if len(biobank_ids) <= 1:
        return True
    first = biobank_ids[0]
    return all(
        biobanks_same_institution(first, other, biobank_signatures)
        for other in biobank_ids[1:]
    )


def count_institution_groups(
    biobank_ids: list[str],
    biobank_signatures: dict[str, dict[str, str]],
) -> int:
    """Return the number of institution groups represented by biobank IDs."""
    remaining = list(dict.fromkeys(biobank_ids))
    groups = 0
    while remaining:
        seed = remaining.pop(0)
        groups += 1
        remaining = [
            biobank_id
            for biobank_id in remaining
            if not biobanks_same_institution(seed, biobank_id, biobank_signatures)
        ]
    return groups
