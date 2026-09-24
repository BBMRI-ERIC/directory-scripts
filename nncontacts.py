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
    """Centralize BBMRI node contacts, staging prefixes, and schema conventions."""

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
        "EU": "kurt.majcen@bbmri-eric.eu, petr.holub@bbmri-eric.eu",
        "EXT": "SBenvenuti@Telethon.it, kurt.majcen@bbmri-eric.eu, petr.holub@bbmri-eric.eu",
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
        "SK": "marian.mizik@uniba.sk",
        "TR": "nese.atabey@ibg.edu.tr",
        "IARC": "kozlakidisz@iarc.fr",
    }

    # Backward-compatible alias used throughout the legacy scripts.
    NNtoEmails = NODE_TO_EMAILS

    MEMBER_NODE_CODES = frozenset(code for code in NODE_TO_EMAILS if code not in {"EU", "IARC"})
    GLOBAL_STAGING_AREA_CODES = frozenset({"EU", "IARC"})
    NON_MEMBER_STAGING_AREA_CODES = frozenset({"EXT"}) | GLOBAL_STAGING_AREA_CODES
    PERMITTED_NON_COUNTRY_PREFIX_CODES = NON_MEMBER_STAGING_AREA_CODES
    STAGING_AREA_TO_SCHEMA = {
        "EU": "BBMRI-EU",
        "EXT": "EXT",
        "IARC": "IARC",
    }
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
        """Return a normalized uppercase code.

        Args:
            code: Text-like code, or ``None`` for a missing value.

        Returns:
            Stripped uppercase text, or an empty string for ``None``.
        """
        if code is None:
            return ""
        return str(code).strip().upper()

    @classmethod
    def get_contacts(cls, code: str | None) -> str:
        """Return routing contacts for a node/staging area code.

        Args:
            code: Node or staging-area code normalized before lookup.

        Returns:
            Configured comma-separated contacts, or the default escalation
            recipients when no exact code mapping exists.
        """
        normalized = cls.normalize_code(code)
        return cls.NODE_TO_EMAILS.get(normalized, cls.DEFAULT_ESCALATION_EMAILS)

    @classmethod
    def has_contacts(cls, code: str | None) -> bool:
        """Return whether contacts are defined for the code.

        Args:
            code: Node or staging-area code normalized before membership lookup.

        Returns:
            Whether the normalized code has an explicit contact mapping.
        """
        return cls.normalize_code(code) in cls.NODE_TO_EMAILS

    @classmethod
    def compose_recipients(cls, code: str | None, extra_recipients: str = "") -> str:
        """Return a combined warning-recipient string.

        Args:
            code: Node or staging-area code whose configured/default contacts
                are used.
            extra_recipients: Optional caller-provided recipient text;
                surrounding commas and whitespace are removed before concatenation.

        Returns:
            Comma-separated extra recipients followed by resolved contacts,
            omitting blank components without parsing or de-duplicating addresses.
        """
        recipients = []
        extra_recipients = str(extra_recipients).strip().strip(",")
        if extra_recipients:
            recipients.append(extra_recipients)
        recipients.append(cls.get_contacts(code))
        return ", ".join(recipient for recipient in recipients if recipient)

    @classmethod
    def is_member_node(cls, code: str | None) -> bool:
        """Return whether the code is a BBMRI member-node country code.

        Args:
            code: Candidate node code normalized before lookup.

        Returns:
            Whether the code is a configured member node, excluding global
            ``EU`` and ``IARC`` staging areas.
        """
        return cls.normalize_code(code) in cls.MEMBER_NODE_CODES

    @classmethod
    def is_iso_country_code(cls, code: str | None) -> bool:
        """Return whether the code is recognized as an ISO-like alpha-2 country code.

        Args:
            code: Candidate alpha-2 code normalized before lookup.

        Returns:
            Whether the code is present in the module's ISO-like code registry.
        """
        return cls.normalize_code(code) in cls.ISO_3166_ALPHA2_CODES

    @classmethod
    def extract_staging_area(cls, entity_id: str | None) -> str:
        """Return the staging-area prefix encoded in a Directory entity id.

        Args:
            entity_id: Directory ID expected to contain at least three
                colon-separated segments, with the third beginning ``PREFIX_...``.

        Returns:
            Normalized third-segment prefix, or an empty string for malformed or
            missing IDs.
        """
        if not isinstance(entity_id, str) or not entity_id:
            return ""
        parts = entity_id.split(":")
        if len(parts) < 3:
            return ""
        return cls.normalize_code(parts[2].split("_", 1)[0])

    @classmethod
    def is_global_staging_area(cls, code: str | None) -> bool:
        """Return whether the staging area is a global BBMRI-managed area.

        Args:
            code: Candidate staging-area code normalized before lookup.

        Returns:
            Whether the code is one of the global BBMRI-managed areas.
        """
        return cls.normalize_code(code) in cls.GLOBAL_STAGING_AREA_CODES

    @classmethod
    def is_non_member_staging_area(
        cls,
        staging_area: str | None,
        *,
        country: str | None = None,
    ) -> bool:
        """Return whether a staging area represents a non-member/global area.

        Args:
            staging_area: Prefix or area code normalized before classification.
            country: Optional reported country used to identify an unknown
                non-country staging prefix.

        Returns:
            ``True`` for configured non-member/global areas and for a non-ISO
            prefix that differs from its reported country; ``False`` for missing
            prefixes.
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
    def is_permitted_non_country_prefix(cls, code: str | None) -> bool:
        """Return whether a non-country staging-area prefix is explicitly allowed.

        Args:
            code: Candidate staging prefix normalized before lookup.

        Returns:
            Whether the code is explicitly permitted as a non-country prefix.
        """
        return cls.normalize_code(code) in cls.PERMITTED_NON_COUNTRY_PREFIX_CODES

    @classmethod
    def expected_schema_name(cls, staging_area: str | None) -> str:
        """Return the expected schema name for a staging-area prefix.

        Args:
            staging_area: Prefix or node code normalized before schema derivation.

        Returns:
            Explicit special mapping, ``BBMRI-<member-node>``, or the normalized
            unknown prefix itself; missing input yields an empty string.
        """
        normalized = cls.normalize_code(staging_area)
        if not normalized:
            return ""
        if normalized in cls.STAGING_AREA_TO_SCHEMA:
            return cls.STAGING_AREA_TO_SCHEMA[normalized]
        if cls.is_member_node(normalized):
            return f"BBMRI-{normalized}"
        return normalized

    @classmethod
    def schema_matches_staging_area(cls, schema: str | None, staging_area: str | None) -> bool:
        """Return whether a schema name matches the expected staging-area schema.

        Args:
            schema: Candidate schema name compared case-insensitively after
                stripping.
            staging_area: Prefix from which the expected schema is derived.

        Returns:
            Whether both normalized names are nonempty and exactly equal.
        """
        normalized_schema = cls.normalize_code(schema)
        expected_schema = cls.normalize_code(cls.expected_schema_name(staging_area))
        return bool(normalized_schema and expected_schema and normalized_schema == expected_schema)

    @classmethod
    def labels_as_node_scope(cls, code: str | None) -> bool:
        """Return whether the code should be labeled as a BBMRI node scope.

        Args:
            code: Candidate label normalized before node-scope classification.

        Returns:
            Whether the code is a member node or the global ``EU`` node scope.
        """
        normalized = cls.normalize_code(code)
        return normalized in cls.MEMBER_NODE_CODES or normalized == "EU"
