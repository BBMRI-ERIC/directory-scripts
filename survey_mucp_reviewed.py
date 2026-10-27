"""Apply source-bound, independently reviewed MuCP quantity interpretations."""

import json
from hashlib import sha256
from pathlib import Path

from survey_evidence import SourceRecord, plain


def reviewed_quantity_covers(record, item, value):
    """Identify a reviewed interpretation of the same source-owned count cell.

    Args:
        record: Projected source record containing validated reviewed measurements.
        item: Native count evidence with its question, scope and source references.
        value: Native numeric value whose interpretation may have been superseded.

    Returns:
        True only when a reviewed measurement covers the identical owned source
        locator and value, including explicitly superseded extraction tokens.
        A missing reviewed question ID is allowed only for a proven workbook cell.
    """
    refs = {(r.get("source_id"), r.get("locator")) for r in item.get("source_refs", [])}
    for quantity in record.get("metadata", {}).get("reviewed_quantities", []):
        if quantity["scope_id"] != item.get("scope_id"):
            continue
        if value != quantity["value"] and value not in quantity.get("superseded_index_values", []):
            continue
        if quantity.get("source_field") not in {None, item.get("question_id")}:
            continue
        owned_refs = {(r.get("source_id"), r.get("locator")) for r in quantity["source_refs"]}
        if refs.intersection(owned_refs):
            return True
    return False


def apply_reviewed_quantities(records, source_hash, manifest, raw_responses, path=None):
    """Attach reviewed measurements without rewriting original answer evidence.

    Args:
        records: Immutable projected MuCP source records with owned scopes.
        source_hash: SHA-256 of the exact source-complete JSON being analysed.
        manifest: Lightweight source manifest supplying original-file checksums.
        raw_responses: Original response objects indexed by response ID for proof checks.
        path: Optional explicitly supplied review catalogue; otherwise use the bundled
            catalogue only when its input hash matches the current document.

    Returns:
        Tuple of source records with validated, lightweight reviewed quantities in
        metadata. Unrelated documents receive no bundled corrections.

    Raises:
        ValueError: If an explicit input hash, owned scope, response proof or original
            file checksum disagrees with the review catalogue.
    """
    catalogue_path = Path(path) if path else Path(__file__).parent / "survey-mappings/mucp_reviewed_quantities.json"
    if not catalogue_path.exists():
        return tuple(records)
    catalogue = json.loads(catalogue_path.read_text())
    if catalogue.get("source_sha256") != source_hash:
        if path:
            raise ValueError("Reviewed quantity catalogue input hash mismatch")
        return tuple(records)
    if catalogue.get("schema_version") != 1:
        raise ValueError("Unsupported reviewed quantity catalogue version")
    sources = {s["source_id"]: s for s in manifest}
    index = {r.data["record_id"]: r for r in records}
    grouped = {}
    for measurement in catalogue["measurements"]:
        rid = measurement["response_id"]
        record = index.get(rid)
        if record is None or measurement["scope_id"] not in {s["scope_id"] for s in record.data["scopes"]}:
            raise ValueError("Reviewed quantity references unknown source scope")
        raw = raw_responses[rid]
        proof = sha256(json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if measurement["source_record_sha256"] != proof:
            raise ValueError("Reviewed quantity response proof hash mismatch")
        if not measurement.get("source_refs"):
            raise ValueError("Reviewed quantity requires source references")
        for ref in measurement["source_refs"]:
            source = sources.get(ref.get("source_id"))
            if (not source or ref["source_id"] not in record.data["metadata"].get("source_ids", [])
                    or not ref.get("locator") or source.get("sha256") != ref.get("source_file_sha256")):
                raise ValueError("Reviewed quantity source proof hash or ownership mismatch")
        if measurement["unit"] not in {"donors", "samples", "aliquots", "unit_unclear"} or type(measurement["value"]) is not int or measurement["value"] < 0:
            raise ValueError("Invalid reviewed quantity value or unit")
        grouped.setdefault(rid, []).append(measurement)
    return tuple(SourceRecord({**plain(r), "metadata": {**plain(r.data["metadata"]),
        "reviewed_quantities": grouped.get(r.data["record_id"], [])}}) for r in records)
