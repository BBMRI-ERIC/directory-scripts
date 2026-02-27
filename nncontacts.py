# vim:ts=4:sw=4:sts=4:tw=0:et

"""Canonical BBMRI Node contact and staging-area metadata.

This module is the single source of truth for:
- BBMRI Node contact routing used by warnings/exporters
- member-node classification
- staging-area parsing and classification helpers
- ISO-like country-code recognition used in consistency checks
"""

from __future__ import annotations


class NNContacts:
    """Central registry of BBMRI Node contacts and staging-area helpers."""

    DEFAULT_ESCALATION_EMAILS = (
        "petr.holub@bbmri-eric.eu, e.van.enckevort@rug.nl, a.w.hodselmans@rug.nl"
    )

    NODE_TO_EMAILS = {
        "AT": "kurt.zatloukal@medunigraz.at, heimo.mueller@medunigraz.at, cornelia.stumptner@medunigraz.at, georg.goebel@i-med.ac.at",
        "BE": "annelies.debucquoy@kankerregister.org",
        "BG": "kaneva@mmcbg.org",
        "CH": "christine.currat@chuv.ch",
        "CY": "Deltas@ucy.ac.cy",
        "CZ": "dudova@ics.muni.cz, hopet@ics.muni.cz",
        "DE": "michael.hummel@charite.de, caecilia.engels@charite.de, cornelia.specht@charite.de",
        "EE": "andres.metspalu@ut.ee, kristjan.metsalu@ut.ee",
        "ES": "eortega@cnio.es",
        "EU": "petr.holub@bbmri-eric.eu, e.van.enckevort@rug.nl",
        "FI": "marco.hautalahti@finbb.fi, pauli.wihuri@finbb.fi",
        "GR": "s.kolyva@pasteur.gr, thanos@bioacademy.gr, koumakis@ics.forth.gr",
        "HU": "molnarmj@gmail.com",
        "IT": "marialuisa.lavitrano@unimib.it, luciano.milanesi@itb.cnr.it, barbara.parodi@hsanmartino.it, elena.bravo@iss.it, matteo.gnocchi@itb.cnr.it, marco.moscatelli@itb.cnr.it",
        "LT": "tomas.simulevic@nvi.lt",
        "LV": "klovins@biomed.lu.lv, vita@biomed.lu.lv, inese.polaka@rtu.lv, linda.zaharenko@biomed.lu.lv",
        "MT": "lidia.ryabova@um.edu.mt, eric.santucci@um.edu.mt",
        "NL": "e.j.van.enckevort@rug.nl, m.a.swertz@gmail.com, tieneke.schaaij-visser@lygature.org",
        "NO": "vegard.marschhauser@ntnu.no, kristian.hveem@ntnu.no",
        "PL": "dominik.strapagiel@biol.uni.lodz.pl, blazej.marciniak@biol.uni.lodz.pl, andrzej.strug@gumed.edu.pl, aklis@bee2code.com",
        "SE": "anna.beskow@uppsalabiobank.uu.se, nils.hailer@uu.se",
        "TR": "nese.atabey@ibg.edu.tr",
        "IARC": "kozlakidisz@iarc.fr",
    }

    # Backward-compatible alias used throughout the legacy scripts.
    NNtoEmails = NODE_TO_EMAILS

    MEMBER_NODE_CODES = frozenset(code for code in NODE_TO_EMAILS if code not in {"EU", "IARC"})
    GLOBAL_STAGING_AREA_CODES = frozenset({"EU", "IARC"})
    NON_MEMBER_STAGING_AREA_CODES = frozenset({"EXT"}) | GLOBAL_STAGING_AREA_CODES
    ISO_3166_ALPHA2_CODES = frozenset(
        {
            "AD", "AE", "AF", "AG", "AI", "AL", "AM", "AO", "AQ", "AR", "AS", "AT",
            "AU", "AW", "AX", "AZ", "BA", "BB", "BD", "BE", "BF", "BG", "BH", "BI",
            "BJ", "BL", "BM", "BN", "BO", "BQ", "BR", "BS", "BT", "BV", "BW", "BY",
            "BZ", "CA", "CC", "CD", "CF", "CG", "CH", "CI", "CK", "CL", "CM", "CN",
            "CO", "CR", "CU", "CV", "CW", "CX", "CY", "CZ", "DE", "DJ", "DK", "DM",
            "DO", "DZ", "EC", "EE", "EG", "EH", "ER", "ES", "ET", "FI", "FJ", "FK",
            "FM", "FO", "FR", "GA", "GB", "GD", "GE", "GF", "GG", "GH", "GI", "GL",
            "GM", "GN", "GP", "GQ", "GR", "GS", "GT", "GU", "GW", "GY", "HK", "HM",
            "HN", "HR", "HT", "HU", "ID", "IE", "IL", "IM", "IN", "IO", "IQ", "IR",
            "IS", "IT", "JE", "JM", "JO", "JP", "KE", "KG", "KH", "KI", "KM", "KN",
            "KP", "KR", "KW", "KY", "KZ", "LA", "LB", "LC", "LI", "LK", "LR", "LS",
            "LT", "LU", "LV", "LY", "MA", "MC", "MD", "ME", "MF", "MG", "MH", "MK",
            "ML", "MM", "MN", "MO", "MP", "MQ", "MR", "MS", "MT", "MU", "MV", "MW",
            "MX", "MY", "MZ", "NA", "NC", "NE", "NF", "NG", "NI", "NL", "NO", "NP",
            "NR", "NU", "NZ", "OM", "PA", "PE", "PF", "PG", "PH", "PK", "PL", "PM",
            "PN", "PR", "PS", "PT", "PW", "PY", "QA", "RE", "RO", "RS", "RU", "RW",
            "SA", "SB", "SC", "SD", "SE", "SG", "SH", "SI", "SJ", "SK", "SL", "SM",
            "SN", "SO", "SR", "SS", "ST", "SV", "SX", "SY", "SZ", "TC", "TD", "TF",
            "TG", "TH", "TJ", "TK", "TL", "TM", "TN", "TO", "TR", "TT", "TV", "TW",
            "TZ", "UA", "UG", "UM", "US", "UY", "UZ", "VA", "VC", "VE", "VG", "VI",
            "VN", "VU", "WF", "WS", "YE", "YT", "ZA", "ZM", "ZW", "UK",
        }
    )

    @classmethod
    def normalize_code(cls, code: str | None) -> str:
        """Return a normalized uppercase code."""
        if code is None:
            return ""
        return str(code).strip().upper()

    @classmethod
    def get_contacts(cls, code: str | None) -> str:
        """Return routing contacts for a node/staging area code."""
        normalized = cls.normalize_code(code)
        return cls.NODE_TO_EMAILS.get(normalized, cls.DEFAULT_ESCALATION_EMAILS)

    @classmethod
    def has_contacts(cls, code: str | None) -> bool:
        """Return whether contacts are defined for the code."""
        return cls.normalize_code(code) in cls.NODE_TO_EMAILS

    @classmethod
    def compose_recipients(cls, code: str | None, extra_recipients: str = "") -> str:
        """Return a combined warning-recipient string."""
        recipients = []
        extra_recipients = str(extra_recipients).strip().strip(",")
        if extra_recipients:
            recipients.append(extra_recipients)
        recipients.append(cls.get_contacts(code))
        return ", ".join(recipient for recipient in recipients if recipient)

    @classmethod
    def is_member_node(cls, code: str | None) -> bool:
        """Return whether the code is a BBMRI member-node country code."""
        return cls.normalize_code(code) in cls.MEMBER_NODE_CODES

    @classmethod
    def is_iso_country_code(cls, code: str | None) -> bool:
        """Return whether the code is recognized as an ISO-like alpha-2 country code."""
        return cls.normalize_code(code) in cls.ISO_3166_ALPHA2_CODES

    @classmethod
    def extract_staging_area(cls, entity_id: str | None) -> str:
        """Return the staging-area prefix encoded in a Directory entity id."""
        if not isinstance(entity_id, str) or not entity_id:
            return ""
        parts = entity_id.split(":")
        if len(parts) < 3:
            return ""
        return cls.normalize_code(parts[2].split("_", 1)[0])

    @classmethod
    def is_global_staging_area(cls, code: str | None) -> bool:
        """Return whether the staging area is a global BBMRI-managed area."""
        return cls.normalize_code(code) in cls.GLOBAL_STAGING_AREA_CODES

    @classmethod
    def is_non_member_staging_area(
        cls,
        staging_area: str | None,
        *,
        country: str | None = None,
    ) -> bool:
        """Return whether a staging area represents a non-member/global area.

        Non-member areas are either explicitly known global areas (such as EXT/EU/IARC),
        or prefixes that differ from the country and do not correspond to an ISO-like
        alpha-2 country code.
        """
        normalized_staging = cls.normalize_code(staging_area)
        normalized_country = cls.normalize_code(country)
        if not normalized_staging:
            return False
        if normalized_staging in cls.NON_MEMBER_STAGING_AREA_CODES:
            return True
        return (
            normalized_staging != normalized_country
            and not cls.is_iso_country_code(normalized_staging)
        )

    @classmethod
    def labels_as_node_scope(cls, code: str | None) -> bool:
        """Return whether the code should be labeled as a BBMRI node scope."""
        normalized = cls.normalize_code(code)
        return normalized in cls.MEMBER_NODE_CODES or normalized == "EU"
