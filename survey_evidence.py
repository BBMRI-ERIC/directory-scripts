"""Immutable provenance contracts for source-preserving combined survey analysis."""

from dataclasses import dataclass
from hashlib import sha256
import json
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any


def freeze(value: Any) -> Any:
    """Copy mutable JSON containers into immutable evidence structures.

    Args:
        value: JSON-compatible evidence value whose nested containers need protection.

    Returns:
        Recursively copied read-only mappings and tuples, with scalar values unchanged.
    """
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    return value


def plain(value: Any) -> Any:
    """Convert immutable evidence wrappers into ordinary JSON containers.

    Args:
        value: Evidence wrapper, nested read-only container, or JSON scalar to serialize.

    Returns:
        A detached dictionary/list/scalar tree retaining false and null distinctly.
    """
    if isinstance(value, FrozenRecord):
        return plain(value.data)
    if isinstance(value, Mapping):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    return value


def canonical_json(value: Mapping[str, Any]) -> str:
    """Serialize analytical content with deterministic object ordering.

    Args:
        value: Combined payload or evidence material already ordered by domain rules.

    Returns:
        UTF-8-safe JSON text with sorted keys and no NaN or Infinity literals.
    """
    return json.dumps(plain(value), sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n"


def fingerprint(value: Any) -> str:
    """Hash immutable or ordinary JSON evidence without depending on dictionary order.

    Args:
        value: Identity, scope, or source material used to bind reviewed decisions.

    Returns:
        Lowercase SHA-256 of the canonical JSON representation.
    """
    return sha256(canonical_json(value).encode()).hexdigest()


@dataclass(frozen=True)
class FrozenRecord:
    """Read-only wrapper protecting source evidence from accidental mutation.

    Attributes:
        data: Recursively immutable copy of the record's JSON-compatible fields.
    """

    data: Mapping[str, Any]

    def __post_init__(self) -> None:
        """Detach and protect the supplied record mapping.

        Returns:
            None. The frozen instance receives an immutable evidence snapshot.
        """
        if not isinstance(self.data, Mapping):
            raise ValueError("Evidence record must be a mapping")
        object.__setattr__(self, "data", freeze(self.data))


class EvidenceItem(FrozenRecord):
    """One source answer or narrative carrying survey, question and scope provenance."""

    def __post_init__(self) -> None:
        """Validate answer provenance before freezing its nested values.

        Returns:
            None. Invalid provenance identifiers or source references raise ValueError.
        """
        if self.data.get("survey") not in {"SO2", "MuCP"}:
            raise ValueError("Evidence survey must be SO2 or MuCP")
        for key in ("evidence_id", "source_record_id", "question_id", "question_label", "scope_id"):
            if not isinstance(self.data.get(key), str) or not self.data[key].strip():
                raise ValueError(f"Evidence lacks {key}")
        refs = self.data.get("source_refs")
        if not isinstance(refs, (list, tuple)) or not refs or any(
                not isinstance(ref, Mapping) or not isinstance(ref.get("locator"), str)
                or not ref["locator"].strip() or not (ref.get("source_id") or ref.get("path"))
                or any(key in ref and (not isinstance(ref[key], str) or not ref[key].strip())
                       for key in ("source_id", "path")) for ref in refs):
            raise ValueError("Evidence lacks usable source_refs")
        super().__post_init__()


class SurveyScope(FrozenRecord):
    """Explicit reported submission or collection scope without inferred inheritance."""


class SourceRecord(FrozenRecord):
    """One contributing source response with immutable identity, scopes and evidence."""


class ResolutionRecord(FrozenRecord):
    """Auditable identity decision including candidates, method and reviewed override."""


class AnalyticalObservation(FrozenRecord):
    """One question state for one analytical biobank with original contribution links."""


class CombinedBiobank(FrozenRecord):
    """A unique overlapping biobank retaining all contributing survey responses."""


def validate_evidence_links(biobank: CombinedBiobank) -> None:
    """Reject incomplete or dangling provenance in one analytical biobank.

    Args:
        biobank: Immutable biobank dossier with evidence and derived observations.

    Returns:
        None. All evidence IDs and derived contribution references are validated.
    """
    evidence = biobank.data.get("evidence", ())
    source_surveys = {}
    for survey, records in (("SO2", biobank.data.get("so2_source_records", ())),
                            ("MuCP", biobank.data.get("mucp_source_records", ()))):
        for record in records:
            source_surveys[record["record_id"]] = survey
    ids = set()
    for item in evidence:
        EvidenceItem(item)
        if (source_surveys.get(item["source_record_id"]) != item["survey"]
                        or item["scope_id"] not in biobank.data.get("scopes", {})):
            raise ValueError("Evidence references unknown source survey or scope")
        scope = biobank.data.get("scopes", {}).get(item["scope_id"], {})
        if not isinstance(scope, Mapping) or scope.get("source_record_id") != item["source_record_id"]:
            raise ValueError("Evidence references another source's scope")
        if item["evidence_id"] in ids:
            raise ValueError("Duplicate evidence ID")
        ids.add(item["evidence_id"])
    for observation in biobank.data.get("observations", ()):
        contributors = observation.get("contribution_ids", ())
        if not contributors or any(item not in ids for item in contributors):
            raise ValueError("Invalid analytical contribution reference")
        by_id = {item["evidence_id"]: item for item in evidence}
        if any(by_id[eid]["survey"] != observation.get("survey")
               or by_id[eid]["question_id"] != observation.get("question_id") for eid in contributors):
            raise ValueError("Analytical contribution references another survey or question")
    by_id = {item["evidence_id"]: item for item in evidence}
    for theme in biobank.data.get("thematic_groups", ()):
        for eid in theme.get("contribution_ids", ()):
            if (eid not in by_id or
                    f'{by_id[eid]["survey"]}:{by_id[eid]["question_id"]}' not in theme.get("questions", ())):
                raise ValueError("Invalid thematic contribution reference")
