"""Helpers for attaching structured fix proposals to QC warnings."""

from __future__ import annotations

from typing import Any, Iterable

from duo_terms import get_duo_term_metadata
from fact_descriptor_sync import (
    build_collection_descriptor_proposal,
    parse_collection_multi_value_field,
)
from fix_proposals import make_fix_proposal


MULTI_VALUE_COLLECTION_FIELDS = {
    "data_use",
    "type",
    "diagnosis_available",
    "materials",
    "sex",
}


def current_collection_field_value(collection: dict[str, Any], field: str) -> Any:
    """Return a normalized collection field value for fix export."""
    if field in MULTI_VALUE_COLLECTION_FIELDS:
        return parse_collection_multi_value_field(collection.get(field))
    value = collection.get(field)
    if value in (None, ""):
        return None
    return value


def make_collection_term_append_fix(
    *,
    update_id: str,
    module: str,
    collection: dict[str, Any],
    field: str,
    term_id: str,
    confidence: str,
    human_explanation: str,
    rationale: str = "",
    replace_required: bool = False,
    exclusive_group: str = "",
    blocking_reason: str = "",
):
    """Return a collection append fix for one ontology/code term."""
    current_value = current_collection_field_value(collection, field)
    return make_fix_proposal(
        update_id=update_id,
        module=module,
        entity_type="COLLECTION",
        entity_id=collection["id"],
        field=field,
        mode="append",
        confidence=confidence,
        current_value_at_export=current_value,
        proposed_value=[term_id],
        human_explanation=human_explanation,
        rationale=rationale,
        term_explanations=[get_duo_term_metadata(term_id)] if term_id.startswith("DUO:") else [],
        replace_required=replace_required,
        blocking_reason=blocking_reason,
        exclusive_group=exclusive_group,
    )


def make_collection_scalar_set_fix(
    *,
    update_id: str,
    module: str,
    collection: dict[str, Any],
    field: str,
    proposed_value: Any,
    confidence: str,
    human_explanation: str,
    rationale: str = "",
    blocking_reason: str = "",
):
    """Return a collection scalar set fix."""
    return make_fix_proposal(
        update_id=update_id,
        module=module,
        entity_type="COLLECTION",
        entity_id=collection["id"],
        field=field,
        mode="set",
        confidence=confidence,
        current_value_at_export=current_collection_field_value(collection, field),
        proposed_value=proposed_value,
        human_explanation=human_explanation,
        rationale=rationale,
        blocking_reason=blocking_reason,
    )


def make_collection_multi_value_fix(
    *,
    update_id: str,
    module: str,
    collection: dict[str, Any],
    field: str,
    proposed_values: Iterable[str],
    confidence: str,
    human_explanation: str,
    rationale: str = "",
    mode: str = "append",
    replace_required: bool = False,
    blocking_reason: str = "",
    exclusive_group: str = "",
):
    """Return a collection multi-value fix."""
    proposed = [value for value in proposed_values if value]
    return make_fix_proposal(
        update_id=update_id,
        module=module,
        entity_type="COLLECTION",
        entity_id=collection["id"],
        field=field,
        mode=mode,
        confidence=confidence,
        current_value_at_export=current_collection_field_value(collection, field),
        proposed_value=proposed,
        human_explanation=human_explanation,
        rationale=rationale,
        replace_required=replace_required,
        blocking_reason=blocking_reason,
        exclusive_group=exclusive_group,
    )


def build_fact_alignment_fix_proposals(collection: dict[str, Any], facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return collection descriptor fixes derived conservatively from fact sheets."""
    proposal = build_collection_descriptor_proposal(collection, facts, replace_existing=False)
    fix_proposals = []
    change_map = {change["field"]: change for change in proposal["changes"]}
    notes = proposal.get("notes", [])
    note_text = " ".join(notes).strip()

    for field, module in (
        ("diagnosis_available", "diagnoses"),
        ("materials", "materials"),
        ("sex", "clinical_profile"),
        ("age_low", "age"),
        ("age_high", "age"),
        ("age_unit", "age"),
        ("size", "counts"),
        ("number_of_donors", "counts"),
    ):
        change = change_map.get(field)
        if change is None:
            continue
        confidence = "certain" if module in {"diagnoses", "materials", "counts"} else "almost_certain"
        if module == "age" and note_text:
            confidence = "uncertain"
        fix_proposals.append(
            make_fix_proposal(
                update_id=f"{module}.{field}.from_facts",
                module=module,
                entity_type="COLLECTION",
                entity_id=collection["id"],
                field=field,
                mode="append" if field in {"diagnosis_available", "materials", "sex"} else "set",
                confidence=confidence,
                current_value_at_export=change["current"],
                proposed_value=change["proposed"],
                human_explanation=(
                    f"Update collection field {field} from fact-sheet derived values."
                ),
                rationale=(
                    "The fact-sheet-derived proposal reuses the same conservative normalization as the fact-sheet descriptor updater."
                    + (f" {note_text}" if note_text else "")
                ),
                blocking_reason=(
                    note_text if confidence == "uncertain" else ""
                ),
            )
        )
    return fix_proposals
