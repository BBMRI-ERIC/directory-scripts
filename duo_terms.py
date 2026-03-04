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


def get_duo_term_metadata(term_id: str) -> dict:
    """Return validated DUO term metadata for a term id."""
    return dict(DUO_TERM_METADATA[term_id])
