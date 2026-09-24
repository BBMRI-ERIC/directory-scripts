"""Validated DUO term metadata used in human-readable fix proposals.

The labels/definitions in this registry were checked on 2026-03-04 against the
official DUO ontology source at:
https://raw.githubusercontent.com/EBISPOT/DUO/master/src/ontology/duo.owl
"""

from __future__ import annotations

DUO_SOURCE_NAME = "Data Use Ontology (DUO)"
DUO_SOURCE_URL = "https://raw.githubusercontent.com/EBISPOT/DUO/master/src/ontology/duo.owl"
DUO_SOURCE_CHECKED_AT = "2026-03-04"


DUO_TERM_METADATA = {
    "DUO:0000006": {
        "term_id": "DUO:0000006",
        "label": "health or medical or biomedical research",
        "definition": "Use is allowed for health, medical, or biomedical purposes and excludes population-origins or ancestry research.",
        "source_name": DUO_SOURCE_NAME,
        "source_url": DUO_SOURCE_URL,
        "source_checked_at": DUO_SOURCE_CHECKED_AT,
    },
    "DUO:0000007": {
        "term_id": "DUO:0000007",
        "label": "disease-specific research",
        "definition": "Use is allowed provided it is related to the specified disease.",
        "source_name": DUO_SOURCE_NAME,
        "source_url": DUO_SOURCE_URL,
        "source_checked_at": DUO_SOURCE_CHECKED_AT,
    },
    "DUO:0000018": {
        "term_id": "DUO:0000018",
        "label": "not for profit, non commercial use only",
        "definition": "Use is limited to not-for-profit organizations and non-commercial use.",
        "source_name": DUO_SOURCE_NAME,
        "source_url": DUO_SOURCE_URL,
        "source_checked_at": DUO_SOURCE_CHECKED_AT,
    },
    "DUO:0000020": {
        "term_id": "DUO:0000020",
        "label": "collaboration required",
        "definition": "The requestor must agree to collaborate with the primary study investigator or investigators.",
        "source_name": DUO_SOURCE_NAME,
        "source_url": DUO_SOURCE_URL,
        "source_checked_at": DUO_SOURCE_CHECKED_AT,
    },
    "DUO:0000021": {
        "term_id": "DUO:0000021",
        "label": "ethics approval required",
        "definition": "The requestor must provide documentation of local IRB or ERB approval.",
        "source_name": DUO_SOURCE_NAME,
        "source_url": DUO_SOURCE_URL,
        "source_checked_at": DUO_SOURCE_CHECKED_AT,
    },
    "DUO:0000029": {
        "term_id": "DUO:0000029",
        "label": "return to database or resource",
        "definition": "The requestor must return derived or enriched data to the database or resource.",
        "source_name": DUO_SOURCE_NAME,
        "source_url": DUO_SOURCE_URL,
        "source_checked_at": DUO_SOURCE_CHECKED_AT,
    },
    "DUO:0000042": {
        "term_id": "DUO:0000042",
        "label": "general research use",
        "definition": "Use is allowed for general research use for any research purpose.",
        "source_name": DUO_SOURCE_NAME,
        "source_url": DUO_SOURCE_URL,
        "source_checked_at": DUO_SOURCE_CHECKED_AT,
    },
}


def normalize_duo_term_id(term_id: str) -> str:
    """Return a canonical DUO term ID using the ``DUO:0000000`` form.

    Args:
        term_id: Candidate DUO identifier using either ``DUO:`` or ``DUO_``
            storage syntax.

    Returns:
        Canonical colon-separated identifier when the input uses underscore
        syntax, otherwise the stripped value unchanged.
    """
    value = str(term_id or "").strip()
    if not value:
        return value
    if value.upper().startswith("DUO_"):
        return "DUO:" + value.split("_", 1)[1]
    return value


def normalize_duo_term_ids(term_ids) -> list[str]:
    """Return canonical DUO term IDs, preserving first-seen order.

    Args:
        term_ids: Existing iterable of stored DUO terms, with false-like input
            treated as an empty sequence.

    Returns:
        De-duplicated canonical identifiers in first-seen order.
    """
    normalized = []
    for term_id in term_ids or []:
        canonical = normalize_duo_term_id(term_id)
        if canonical and canonical not in normalized:
            normalized.append(canonical)
    return normalized


def detect_duo_term_storage_style(term_ids) -> str:
    """Return the preferred DUO storage style inferred from existing values.

    Args:
        term_ids: Existing iterable of stored DUO terms examined in order.

    Returns:
        ``underscore`` or ``colon`` according to the first recognizable
        stored value, defaulting to ``underscore`` for empty input.
    """
    for term_id in term_ids or []:
        value = str(term_id or "").strip()
        if value.upper().startswith("DUO_"):
            return "underscore"
        if value.upper().startswith("DUO:"):
            return "colon"
    return "underscore"


def serialize_duo_term_id(term_id: str, *, style: str) -> str:
    """Serialize a DUO term ID in the requested style.

    Args:
        term_id: Identifier normalized before applying the requested style.
        style: Target storage style; ``underscore`` changes a canonical prefix
            while other values retain canonical colon syntax.

    Returns:
        The normalized identifier encoded for the selected storage convention.
    """
    canonical = normalize_duo_term_id(term_id)
    if style == "underscore" and canonical.upper().startswith("DUO:"):
        return "DUO_" + canonical.split(":", 1)[1]
    return canonical


def get_duo_term_metadata(term_id: str) -> dict:
    """Return validated DUO term metadata for a term ID.

    Args:
        term_id: DUO identifier in any supported storage syntax.

    Returns:
        New dictionary copied from the checked-in metadata registry.

    Raises:
        KeyError: If the normalized identifier is not represented in the
            registry.
    """
    return dict(DUO_TERM_METADATA[normalize_duo_term_id(term_id)])
