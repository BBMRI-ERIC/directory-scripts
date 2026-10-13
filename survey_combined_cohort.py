"""Select canonical survey cohorts and keep participation distinct from missing answers."""

from typing import Any, Mapping, Sequence


def select_biobank_cohort(so2_ids: Sequence[str], mucp_ids: Sequence[str],
                         join: str = "all-MuCP") -> dict[str, Any]:
    """Select unique accepted identities using an explicit join policy.

    Args:
        so2_ids: Accepted SO2 canonical biobank identifiers, possibly repeated.
        mucp_ids: Accepted MuCP canonical biobank identifiers, possibly repeated.
        join: inner, all-MuCP, all-SO2 or outer; MuCP is the default primary cohort.

    Returns:
        Join name and sorted selected, SO2, MuCP and intersection identifier lists.

    Raises:
        ValueError: If the mode or any identifier is invalid.
    """
    if join not in {"inner", "all-MuCP", "all-SO2", "outer"}:
        raise ValueError(f"Unsupported survey join: {join!r}")
    if any(not isinstance(value, str) or not value for value in (*so2_ids, *mucp_ids)):
        raise ValueError("Survey cohort identifiers must be nonempty strings")
    so2, mucp = set(so2_ids), set(mucp_ids)
    selected = {"inner": so2 & mucp, "all-MuCP": mucp,
                "all-SO2": so2, "outer": so2 | mucp}[join]
    return {"join": join, "selected_ids": sorted(selected), "so2_ids": sorted(so2),
            "mucp_ids": sorted(mucp), "intersection_ids": sorted(so2 & mucp)}


def survey_participating_biobanks(biobanks: Sequence[Mapping[str, Any]],
                                 surveys: Sequence[str]) -> list[Mapping[str, Any]]:
    """Select banks represented in every requested survey, not complete answers.

    Args:
        biobanks: Selected bank mappings with participation flags or legacy source records.
        surveys: SO2/MuCP names required by a question or shared analysis.

    Returns:
        Original bank mappings with all required survey submissions present.

    Raises:
        ValueError: If an unknown survey is requested.
    """
    if any(survey not in {"SO2", "MuCP"} for survey in surveys):
        raise ValueError("Participation requires SO2 or MuCP")
    result = []
    for bank in biobanks:
        flags = bank.get("survey_participation")
        if flags is None:
            # Legacy analytical fixtures and version-1 payloads represent overlap.
            flags = {survey: bool(bank.get(key)) if key in bank else True
                     for survey, key in (("SO2", "so2_source_records"), ("MuCP", "mucp_source_records"))}
        if all(flags.get(survey) is True for survey in surveys):
            result.append(bank)
    return result
