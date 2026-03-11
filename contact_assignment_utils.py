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


def is_institution_specific_domain(domain: str) -> bool:
    """Return whether an email domain looks institution-specific enough for warnings."""
    if not domain:
        return False
    if domain in PUBLIC_EMAIL_DOMAINS:
        return False
    return True


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


def build_biobank_contact_maps(dir) -> tuple[dict[str, str], dict[str, set[str]], dict[str, set[str]]]:
    """Return biobank main-contact mappings and domain associations.

    Returns:
        - biobank_id -> main contact id
        - contact id -> biobank ids for which it is the biobank-level contact
        - institution-specific main-contact email domain -> biobank ids
    """
    biobank_to_contact: dict[str, str] = {}
    contact_to_biobanks: dict[str, set[str]] = defaultdict(set)
    domain_to_biobanks: dict[str, set[str]] = defaultdict(set)

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

    return biobank_to_contact, contact_to_biobanks, domain_to_biobanks


def get_single_biobank_domain_owner(domain: str, domain_to_biobanks: dict[str, set[str]]) -> str | None:
    """Return the unique biobank associated with a main-contact domain, if any."""
    owners = sorted(domain_to_biobanks.get(domain, set()))
    if len(owners) == 1:
        return owners[0]
    return None
