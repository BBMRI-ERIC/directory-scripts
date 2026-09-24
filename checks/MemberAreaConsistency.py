# vim:ts=4:sw=4:tw=0:sts=4:et

"""Checks that member-country institutions are not misplaced into non-member areas."""

from __future__ import annotations

import logging as log
import re
from collections import defaultdict

from yapsy.IPlugin import IPlugin

from customwarnings import (
    DataCheckEntityType,
    DataCheckWarning,
    DataCheckWarningLevel,
    make_check_id,
)
from directory import Directory
from nncontacts import NNContacts

# Machine-readable check documentation for the manual generator and other tooling.
# Keep severity/entity/fields aligned with the DataCheckWarning calls below.
CHECK_DOCS = {
    "MAC:IsoStageMismatch": {
        "severity": "ERROR",
        "entity": "BIOBANK",
        "fields": ["country", "id"],
        "summary": "Biobank ID uses a different ISO-like country staging prefix than the biobank country.",
        "background": "Non-member exceptions apply only to dedicated non-member/global areas such as EXT or EU. A staging prefix that itself looks like a country code must match the biobank country.",
        "fix": "Use the member-country staging area that matches the biobank country, or correct the country attribute if the biobank is assigned to the wrong node.",
    },
    "MAC:MemberNonMember": {
        "severity": "WARNING",
        "entity": "BIOBANK",
        "fields": ["country", "id", "juridical_person"],
        "summary": "Institution from a BBMRI member country exists only in a non-member staging area.",
        "background": "Such records can be legitimate when they are outside the national node scope but participate through an exemption, for example rare-disease or pandemic-related inclusion. They still require manual review.",
        "fix": "Move the institution to the member-country staging area if it belongs to the node. Otherwise confirm that the non-member placement is intentional and justified.",
    },
    "MAC:MemberDupOtherArea": {
        "severity": "ERROR",
        "entity": "BIOBANK",
        "fields": ["country", "id", "juridical_person"],
        "summary": "The same institution appears both in the member-country staging area and in another area such as EXT or EU.",
        "background": "A member-country institution should not be duplicated across staging areas. The only operational exception is that EU-hosted institutions may be based in a member country, but they still must not duplicate the same institution already present in the member-country node.",
        "fix": "Keep the institution in one staging area only, or make the juridical person values distinct if the records intentionally represent different legal entities.",
    },
}


class MemberAreaConsistency(IPlugin):
    """Detect member-country institutions placed or duplicated in other staging areas.

    The plugin compares country, ID-derived staging area, and normalized juridical person. It reports mismatches and duplicates without moving or editing entities.
    """
    CHECK_ID_PREFIX = "MAC"

    @staticmethod
    def _normalize_country(value) -> str:
        """Normalize a scalar or EMX reference wrapper to an uppercase country code.

        Args:
            value: Country scalar or mapping containing an ``id`` or ``name`` value.

        Returns:
            A stripped uppercase code, or an empty string when no value is available.
        """
        if isinstance(value, dict):
            value = value.get("id") or value.get("name")
        if value is None:
            return ""
        return str(value).strip().upper()

    @staticmethod
    def _normalize_institution_name(value) -> str:
        """Normalize an institution name for case-insensitive duplicate detection.

        Args:
            value: Juridical-person value to collapse and case-fold.

        Returns:
            A whitespace-normalized case-folded key, or an empty string for ``None``.
        """
        if value is None:
            return ""
        normalized = re.sub(r"\s+", " ", str(value).strip())
        return normalized.casefold()

    @staticmethod
    def _display_name(value) -> str:
        """Normalize institution whitespace while preserving display case.

        Args:
            value: Juridical-person value rendered in warning messages.

        Returns:
            A stripped single-spaced display name, or an empty string for ``None``.
        """
        if value is None:
            return ""
        return re.sub(r"\s+", " ", str(value).strip())

    @staticmethod
    def _safe_contact_email(directory: Directory, biobank_id: str) -> str:
        """Resolve a biobank's primary contact email without propagating lookup failures.

        Args:
            directory: Loaded Directory view used for primary-contact lookup.
            biobank_id: Biobank identifier whose warning contact is requested.

        Returns:
            The stripped email for a mapping contact, otherwise an empty string.
        """
        try:
            contact = directory.getBiobankContact(biobank_id)
        except Exception:
            return ""
        if not isinstance(contact, dict):
            return ""
        return str(contact.get("email", "")).strip()

    def check(self, directory: Directory, args):
        """Inspect biobank staging placement and return member-area consistency warnings.

        Args:
            directory: Loaded Directory view providing visible biobanks and their primary contacts.
            args: Runner options accepted for the common plugin interface; this check discards them.

        Returns:
            MAC warnings for ISO staging mismatches, member institutions in non-member areas, and cross-area duplicates.
        """
        del args
        warnings = []
        log.info("Running member-area consistency checks (MemberAreaConsistency)")

        institutions_by_country = defaultdict(
            lambda: {"__member__": [], "__non_member__": [], "__eu__": []}
        )

        for biobank in directory.getBiobanks():
            biobank_id = biobank.get("id", "")
            country = self._normalize_country(biobank.get("country"))
            if not NNContacts.is_member_node(country):
                continue

            staging_area = NNContacts.extract_staging_area(biobank_id)
            institution_key = self._normalize_institution_name(
                biobank.get("juridical_person")
            )
            institution_name = self._display_name(biobank.get("juridical_person"))
            email = self._safe_contact_email(directory, biobank_id)

            if (
                staging_area
                and staging_area != country
                and NNContacts.is_iso_country_code(staging_area)
            ):
                warnings.append(
                    DataCheckWarning(
                        make_check_id(self, "IsoStageMismatch"),
                        "",
                        country,
                        DataCheckWarningLevel.ERROR,
                        biobank_id,
                        DataCheckEntityType.BIOBANK,
                        str(biobank.get("withdrawn", "")),
                        f"Biobank country is {country} but the ID staging area is {staging_area}. Non-member exceptions apply only to dedicated non-member/global areas such as EXT or EU.",
                        "Align the biobank ID prefix with the country staging area, or correct the country attribute if the biobank is assigned to the wrong node.",
                        email,
                    )
                )
                continue

            if not institution_key or not staging_area:
                continue

            payload = {
                "biobank_id": biobank_id,
                "country": country,
                "staging_area": staging_area,
                "institution_name": institution_name,
                "email": email,
                "withdrawn": str(biobank.get("withdrawn", "")),
            }
            country_key = (country, institution_key)
            if staging_area == country:
                institutions_by_country[country_key]["__member__"].append(payload)
            elif staging_area == "EU":
                institutions_by_country[country_key]["__eu__"].append(payload)
            elif NNContacts.is_non_member_staging_area(staging_area, country=country):
                institutions_by_country[country_key]["__non_member__"].append(payload)

        # Business rule background:
        # - member-country institutions should normally live in the corresponding
        #   member staging area.
        # - an institution may legitimately appear only in a non-member area when it
        #   participates through a BBMRI exception outside the node scope.
        # - EU is special because BBMRI-ERIC-hosted entities can sit in a member
        #   country, but the same institution still must not be duplicated both in the
        #   member-country node and in EU.
        for (_, institution_key), grouped_records in sorted(institutions_by_country.items()):
            del institution_key
            member_records = grouped_records["__member__"]
            non_member_records = grouped_records["__non_member__"]
            eu_records = grouped_records["__eu__"]

            member_ids = sorted(record["biobank_id"] for record in member_records)
            member_id_list = ", ".join(member_ids)

            for record in non_member_records:
                institution_name = record["institution_name"] or "<missing juridical_person>"
                if member_records:
                    warnings.append(
                        DataCheckWarning(
                            make_check_id(
                                self,
                                "MemberDupOtherArea",
                            ),
                            "",
                            record["country"],
                            DataCheckWarningLevel.ERROR,
                            record["biobank_id"],
                            DataCheckEntityType.BIOBANK,
                            record["withdrawn"],
                            f"Institution '{institution_name}' from member country {record['country']} appears in non-member staging area {record['staging_area']} and also in member staging area {record['country']} ({member_id_list}).",
                            "Keep the institution in one staging area only. Use the member-country area for node institutions, and reserve non-member areas for exceptional non-node cases.",
                            record["email"],
                        )
                    )
                else:
                    warnings.append(
                        DataCheckWarning(
                            make_check_id(self, "MemberNonMember"),
                            "",
                            record["country"],
                            DataCheckWarningLevel.WARNING,
                            record["biobank_id"],
                            DataCheckEntityType.BIOBANK,
                            record["withdrawn"],
                            f"Institution '{institution_name}' from member country {record['country']} is stored only in non-member staging area {record['staging_area']}.",
                            "If the institution belongs to the national node, move it to the member-country staging area. Otherwise verify that the non-member placement is an intentional exemption.",
                            record["email"],
                        )
                    )

            if not member_records:
                continue

            for record in eu_records:
                institution_name = record["institution_name"] or "<missing juridical_person>"
                warnings.append(
                    DataCheckWarning(
                        make_check_id(
                            self,
                            "MemberDupOtherArea",
                        ),
                        "",
                        record["country"],
                        DataCheckWarningLevel.ERROR,
                        record["biobank_id"],
                        DataCheckEntityType.BIOBANK,
                        record["withdrawn"],
                        f"Institution '{institution_name}' from member country {record['country']} appears in EU staging area and also in member staging area {record['country']} ({member_id_list}).",
                        "Keep the institution in one staging area only. EU-hosted entities may exist in member countries, but they must not duplicate the same institution already present in the member-country node.",
                        record["email"],
                    )
                )

        return warnings
