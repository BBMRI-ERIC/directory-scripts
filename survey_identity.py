"""Conservative, fingerprint-bound matching of survey records to Directory biobanks."""

from dataclasses import dataclass, field
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import unicodedata
from typing import Any, Mapping

from survey_evidence import SourceRecord, ResolutionRecord, fingerprint, plain


COUNTRIES = {
    "austria": "AT", "belgium": "BE", "bulgaria": "BG", "croatia": "HR",
    "cyprus": "CY", "czech republic": "CZ", "czechia": "CZ", "denmark": "DK",
    "estonia": "EE", "finland": "FI", "france": "FR", "germany": "DE",
    "greece": "GR", "hungary": "HU", "ireland": "IE", "italy": "IT",
    "latvia": "LV", "lithuania": "LT", "luxembourg": "LU", "malta": "MT",
    "netherlands": "NL", "norway": "NO", "poland": "PL", "portugal": "PT",
    "romania": "RO", "slovakia": "SK", "slovenia": "SI", "spain": "ES",
    "sweden": "SE", "switzerland": "CH", "swiss": "CH", "united kingdom": "GB",
    "uk": "GB", "united states": "US", "turkey": "TR", "israel": "IL",
}


def literal_name(value: Any) -> str:
    """Normalize literal institution wording without removing distinguishing tokens.

    Args:
        value: Source institution or Directory name to compare accent-insensitively.

    Returns:
        Case-folded ASCII text with punctuation and whitespace normalized.
    """
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.casefold())).strip()


def country_key(value: Any) -> str:
    """Resolve source country names and two-letter codes to one comparison key.

    Args:
        value: Reported country name/code; unknown names are not guessed.

    Returns:
        Known ISO alpha-2 code or the unchanged upper-case source string.
    """
    return COUNTRIES.get(literal_name(value), str(value or "").strip().upper())


def identity_fingerprint(record: SourceRecord) -> str:
    """Bind a decision to its source identity rather than the entire changing survey.

    Args:
        record: Survey response whose identifying fields/source IDs require review.

    Returns:
        Stable SHA-256 independent of unrelated records added to the same input file.
    """
    return fingerprint({"survey": record.data["survey"], "record_id": record.data["record_id"],
                        "country": record.data.get("country"), "identity": record.data.get("identity", {}),
                        "source_ids": record.data.get("metadata", {}).get("source_ids", ()),
                        "scopes": [{key: scope.get(key) for key in ("scope_id", "kind", "label", "collection_id")}
                                   for scope in record.data.get("scopes", ())]})


@dataclass(frozen=True)
class IdentityCatalogue:
    """Loaded biobank identities and complete email ownership independent of report scope.

    Attributes:
        biobanks: All loaded biobank metadata indexed by canonical Directory ID.
        eligible_ids: Biobank IDs allowed by the configured withdrawn reporting scope.
        emails: Full normalized contact emails mapped to every loaded owning biobank.
        aliases: Explicit reviewed institution aliases indexed by normalized name/country.
        collection_parents: Canonical collection IDs mapped through Directory's parent API.
    """

    biobanks: Mapping[str, Mapping[str, Any]]
    eligible_ids: frozenset[str]
    emails: Mapping[str, set[str]]
    aliases: Mapping[tuple[str, str], set[str]] = field(default_factory=dict)
    collection_parents: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MatchOverrides:
    """Reviewed identity decisions plus explicit legacy findings input bindings.

    Attributes:
        decisions: Source/scope-keyed acceptance or rejection decisions with fingerprints.
        input_bindings: Reviewed pairs of workbook and findings hashes.
    """

    decisions: Mapping[tuple[str, str, str], Mapping[str, Any]]
    input_bindings: tuple[Mapping[str, Any], ...]


def load_match_overrides(path: Path, input_hashes: Mapping[str, str]) -> MatchOverrides:
    """Read persistent decisions without invalidating unchanged records on file append.

    Args:
        path: Override JSON file; contains only explicitly reviewed matching decisions.
        input_hashes: Current input hashes recorded by the caller, not used as blanket invalidation.

    Returns:
        Validated source/scope decisions and legacy source bindings.
    """
    root = json.loads(Path(path).read_text())
    if root.get("schema_version") != "1":
        raise ValueError("Unsupported match override schema_version")
    decisions = {}
    for item in root.get("decisions", []):
        key = (item.get("survey"), item.get("source_record_id"), item.get("scope_id", ""))
        if key in decisions or item.get("action") not in {"accept", "reject"}:
            raise ValueError("Duplicate or invalid override decision")
        if key[0] not in {"SO2", "MuCP"} or not key[1]:
            raise ValueError("Override requires survey and source_record_id")
        for name in ("identity_fingerprint", "reason", "reviewer", "reviewed_on"):
            if not item.get(name):
                raise ValueError(f"Override requires {name}")
        if item["action"] == "accept" and not item.get("biobank_id"):
            raise ValueError("Accept override requires biobank_id")
        decisions[key] = item
    return MatchOverrides(decisions, tuple(root.get("input_bindings", [])))


def build_identity_catalogue(directory: Any) -> IdentityCatalogue:
    """Index complete loaded contact ownership through Directory parent APIs.

    Args:
        directory: Read-only Directory instance exposing loaded entities and configured scope.

    Returns:
        Catalogue including excluded owners, so filtering cannot manufacture unique matches.
    """
    biobanks = {item["id"]: item for item in directory.biobanks}
    contacts = {item["id"]: item for item in directory.contacts}
    owners: dict[str, set[str]] = {}
    for item in biobanks.values():
        contact = item.get("contact")
        cid = contact.get("id") if isinstance(contact, dict) else contact
        if cid:
            owners.setdefault(cid, set()).add(item["id"])
    collection_parents = {}
    for collection in directory.getLoadedCollections():
        contact = collection.get("contact")
        cid = contact.get("id") if isinstance(contact, dict) else contact
        parent_id = directory.getCollectionBiobankId(collection["id"])
        if parent_id in biobanks:
            collection_parents[collection["id"]] = parent_id
            if cid:
                owners.setdefault(cid, set()).add(parent_id)
    for contact in contacts.values():
        for reference in contact.get("biobanks", ()) or ():
            bid = reference.get("id") if isinstance(reference, dict) else reference
            if bid in biobanks:
                owners.setdefault(contact["id"], set()).add(bid)
        for reference in contact.get("collections", ()) or ():
            cid = reference.get("id") if isinstance(reference, dict) else reference
            if directory.getLoadedCollectionById(cid):
                parent_id = directory.getCollectionBiobankId(cid)
                if parent_id in biobanks:
                    owners.setdefault(contact["id"], set()).add(parent_id)
    emails: dict[str, set[str]] = {}
    for cid, contact in contacts.items():
        for email in re.split(r"[;,\s]+", str(contact.get("email") or "").casefold()):
            if "@" in email:
                emails.setdefault(email, set()).update(owners.get(cid, set()))
    return IdentityCatalogue(biobanks, frozenset(item["id"] for item in directory.getBiobanks()), emails,
                             collection_parents=collection_parents)


def resolve_source_identity(record: SourceRecord, catalogue: IdentityCatalogue,
                            overrides: MatchOverrides) -> ResolutionRecord:
    """Resolve one source identity without auto-accepting ambiguous or approximate candidates.

    Args:
        record: Source response and its literal identifying evidence.
        catalogue: Loaded biobank identities and complete contact ownership.
        overrides: Reviewed source decisions bound to the current identity fingerprint.

    Returns:
        Accepted, unmatched, excluded, rejected or manual-review identity with audit details.
    """
    data = record.data
    identity = data.get("identity", {})
    result = {"source_record_id": data["record_id"], "survey": data["survey"], "status": "unmatched",
              "method": "none", "reliability": "low", "explanation": "No unique exact identity",
              "biobank_id": None, "candidate_ids": [], "identity_fingerprint": identity_fingerprint(record)}
    decision = overrides.decisions.get((data["survey"], data["record_id"], ""))
    if decision:
        if data.get("record_type") == "country_summary" and decision["action"] == "accept":
            raise ValueError("Country summary requires an explicit scope override, not root acceptance")
        if decision["identity_fingerprint"] != result["identity_fingerprint"]:
            raise ValueError(f"Stale identity override for {data['record_id']}")
        bid = decision.get("biobank_id")
        if decision["action"] == "accept" and bid not in catalogue.biobanks:
            raise ValueError(f"Unknown override biobank_id {bid}")
        result.update(status="accepted" if decision["action"] == "accept" else "rejected",
                      method="override", biobank_id=bid, reliability="reviewed",
                      explanation=decision["reason"], override=plain(decision))
    elif data.get("record_type") == "country_summary":
        result.update(status="excluded", explanation="Country summary is not biobank-scoped evidence")
    else:
        raw_id = str(identity.get("explicit_biobank_id") or "").strip()
        explicit = raw_id if raw_id.startswith("bbmri-eric:ID:") else "bbmri-eric:ID:" + raw_id
        collection_ids = list(identity.get("collection_ids", ()))
        if ":collection:" in explicit:
            collection_ids.append(explicit)
            raw_id = ""
        collection_owners = {catalogue.collection_parents[value] for value in collection_ids if value in catalogue.collection_parents}
        email_ids = set()
        for email in identity.get("email_addresses", ()):
            email_ids.update(catalogue.emails.get(str(email).strip().casefold(), set()))
        candidates = set()
        method = "none"
        if raw_id:
            candidates = {explicit} if explicit in catalogue.biobanks else set()
            method = "exact_id"
            if not candidates or (email_ids and email_ids != candidates):
                result.update(status="review", explanation="Explicit ID absent or conflicts with email ownership",
                              candidate_ids=sorted(candidates | email_ids))
                return ResolutionRecord(result)
        elif collection_ids:
            if len(collection_owners) != 1 or any(value not in catalogue.collection_parents for value in collection_ids):
                result.update(status="review", candidate_ids=sorted(collection_owners), explanation="Collection IDs missing or belong to multiple biobanks")
                return ResolutionRecord(result)
            candidates, method = collection_owners, "exact_collection_parent"
            if email_ids and email_ids != candidates:
                result.update(status="review", candidate_ids=sorted(candidates | email_ids), explanation="Collection parents conflict with email ownership")
                return ResolutionRecord(result)
        elif email_ids:
            candidates, method = email_ids, "exact_email"
        else:
            name = literal_name(identity.get("institution_name") or identity.get("name"))
            country = country_key(data.get("country"))
            if name and country:
                candidates = {bid for bid, bb in catalogue.biobanks.items()
                              if literal_name(bb.get("name")) == name and country_key(bb.get("country")) == country}
                method = "exact_institution_country"
                if not candidates:
                    candidates = set(catalogue.aliases.get((name, country), set()))
                    method = "reviewed_alias_country"
            if not candidates and name:
                fuzzy = [bid for bid, bb in catalogue.biobanks.items()
                         if country_key(bb.get("country")) == country
                         and SequenceMatcher(None, name, literal_name(bb.get("name"))).ratio() >= .72]
                if fuzzy:
                    result.update(status="review", method="approximate_candidates",
                                  candidate_ids=sorted(fuzzy), explanation="Approximate matches require manual review")
        if candidates:
            name = literal_name(identity.get("institution_name") or identity.get("name"))
            named_ids = {bid for bid, bb in catalogue.biobanks.items()
                         if name and literal_name(bb.get("name")) == name
                         and country_key(bb.get("country")) == country_key(data.get("country"))}
            if (named_ids and named_ids != candidates
                    or raw_id and collection_owners and collection_owners != candidates):
                result.update(status="review", method=method,
                              candidate_ids=sorted(candidates | named_ids | collection_owners),
                              explanation="Exact identity signals point to different biobanks")
                return ResolutionRecord(result)
            result.update(candidate_ids=sorted(candidates), method=method)
            if len(candidates) == 1:
                bid = next(iter(candidates))
                if data.get("country") and country_key(data["country"]) != country_key(catalogue.biobanks[bid].get("country")):
                    result.update(status="review", explanation="Source country conflicts with Directory country")
                else:
                    result.update(status="accepted", biobank_id=bid, reliability="high",
                                  explanation=f"Unique {method} match")
            else:
                result.update(status="review", explanation="Identity evidence belongs to multiple biobanks")
    if result["status"] == "accepted" and result["biobank_id"] not in catalogue.eligible_ids:
        result.update(status="excluded", explanation="Biobank outside configured withdrawn scope")
    return ResolutionRecord(result)


def _project_quantity_index(projected: dict[str, Any], original: Mapping[str, Any], retain_diagnostics: bool) -> None:
    """Keep only index entries whose evidence references prove projection ownership.

    Args:
        projected: Mutable root or collection projection with its own retained scopes.
        original: Immutable original response supplying all evidence-reference owners.
        retain_diagnostics: Whether this unassigned root should retain entries with
            missing or ambiguous ownership outside the attributable quantity index.

    Returns:
        None. Updates projected metadata without mutating original quantities;
        other scopes' entries never enter the projection's numeric inventory.
    """
    metadata = projected.get("metadata", {})
    if "quantity_index" not in metadata:
        return
    owners = {}
    reference_items = list(original.get("evidence", ()))
    for scope in original.get("scopes", ()):
        count = (scope.get("metadata") or {}).get("count", {})
        if isinstance(count, Mapping):
            reference_items.append({"scope_id":scope["scope_id"],"source_refs":count.get("evidence", ())})
    for item in reference_items:
        for ref in item.get("source_refs", ()):
            source = ref.get("source_id") or ref.get("path")
            locator = ref.get("locator")
            if source and locator:
                kind = "source_id" if ref.get("source_id") else "path"
                owners.setdefault((kind,source,locator),set()).add(item["scope_id"])
    retained_scopes = {scope["scope_id"] for scope in projected["scopes"]}
    retained, unknown = [], []
    for entry in metadata["quantity_index"]:
        refs = entry.get("evidence", [])
        known = bool(refs)
        scopes = set()
        for ref in refs:
            kind = "source_id" if ref.get("source_id") else "path"
            key = (kind,ref.get("source_id") or ref.get("path"),ref.get("locator"))
            matching = owners.get(key,set())
            if not matching or len(matching) != 1:
                known = False
            scopes.update(matching)
        if known and len(scopes)==1:
            if scopes <= retained_scopes:
                retained.append(entry)
        else:
            unknown.append({**entry,"projection_diagnostic":"Quantity index ownership is missing or ambiguous; not attributed to a reporting scope."})
    metadata["quantity_index"] = retained
    if retain_diagnostics and unknown:
        metadata.setdefault("unassigned_quantity_index",[]).extend(unknown)


def resolve_scoped_sources(records: Any, catalogue: IdentityCatalogue,
                           overrides: MatchOverrides) -> tuple[tuple[SourceRecord, ...], tuple[ResolutionRecord, ...]]:
    """Apply reviewed scope splits without broadcasting submission evidence.

    Args:
        records: Original survey responses, each containing its own scopes and evidence.
        catalogue: Complete Directory identities and reporting-scope eligibility.
        overrides: Fingerprint-bound root or explicit scope identity decisions.

    Returns:
        Aligned source records and resolutions, including unassigned root diagnostics
        and virtual records containing only evidence from explicitly assigned scopes.
    """
    output, resolutions = [], []
    for record in records:
        data = record.data
        keys = sorted(key for key in overrides.decisions
                      if key[:2] == (data["survey"], data["record_id"]) and key[2])
        root = resolve_source_identity(record, catalogue, overrides)
        if keys:
            root_data = plain(root)
            root_data.update(status="excluded", biobank_id=None,
                             explanation="Explicit scope decisions replace root assignment; unassigned evidence is retained here")
            root = ResolutionRecord(root_data)
        assigned = {key[2] for key in keys}
        if assigned:
            unassigned = plain(record)
            unassigned["scopes"] = [plain(scope) for scope in data.get("scopes", ()) if scope["scope_id"] not in assigned]
            unassigned["evidence"] = [plain(item) for item in data.get("evidence", ()) if item["scope_id"] not in assigned]
            if "reviewed_quantities" in unassigned.get("metadata", {}):
                unassigned["metadata"]["reviewed_quantities"] = [item for item in unassigned["metadata"]["reviewed_quantities"] if item["scope_id"] not in assigned]
            _project_quantity_index(unassigned,data,retain_diagnostics=True)
            output.append(SourceRecord(unassigned))
        else:
            output.append(record)
        resolutions.append(root)
        scopes = {scope["scope_id"]: scope for scope in data.get("scopes", ())}
        for key in keys:
            decision = overrides.decisions[key]
            if key[2] not in scopes:
                raise ValueError(f"Unknown override scope {key[2]} in {data['record_id']}")
            if (data.get("record_type") == "country_summary" and decision["action"] == "accept"
                    and scopes[key[2]].get("kind") != "collection"):
                raise ValueError("A national summary may only assign a reviewed collection scope, not its submission scope")
            if decision["identity_fingerprint"] != identity_fingerprint(record):
                raise ValueError(f"Stale scope override for {data['record_id']}")
            bid = decision.get("biobank_id")
            if decision["action"] == "accept" and bid not in catalogue.biobanks:
                raise ValueError(f"Unknown override biobank_id {bid}")
            virtual_id = data["record_id"] + "#scope:" + fingerprint(key[2])[:16]
            selected = plain(record)
            selected.update(record_id=virtual_id, source_response_id=data["record_id"],
                            original_record_type=data.get("record_type"), record_type="scope_projection",
                            scopes=[plain(scopes[key[2]])],
                            evidence=[plain(item) for item in data.get("evidence", ()) if item["scope_id"] == key[2]])
            for item in (*selected["scopes"], *selected["evidence"]):
                item.update(source_record_id=virtual_id, original_source_record_id=data["record_id"])
            if "reviewed_quantities" in selected.get("metadata", {}):
                selected["metadata"]["reviewed_quantities"] = [item for item in selected["metadata"]["reviewed_quantities"] if item["scope_id"] == key[2]]
            _project_quantity_index(selected,data,retain_diagnostics=False)
            status = "accepted" if decision["action"] == "accept" else "rejected"
            if status == "accepted" and bid not in catalogue.eligible_ids:
                status = "excluded"
            output.append(SourceRecord(selected))
            resolutions.append(ResolutionRecord({"source_record_id": virtual_id,
                "original_source_record_id": data["record_id"], "scope_id": key[2],
                "survey": data["survey"], "status": status, "method": "scope_override",
                "reliability": "reviewed", "biobank_id": bid, "candidate_ids": [],
                "explanation": decision["reason"], "identity_fingerprint": identity_fingerprint(record),
                "override": plain(decision)}))
    return tuple(output), tuple(resolutions)
