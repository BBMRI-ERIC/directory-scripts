"""Score original SO2 readiness responses and render the deduplicated analysis."""

from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


COMPONENTS = tuple("acludpr")
BANDS = ("Very Low", "Low", "Moderate", "High", "Very High")
DEFAULT_MAPPING = Path(__file__).resolve().parent / "survey-mappings/so2_2025_readiness_scores.json"
DEFAULT_REFERENCE = Path(__file__).resolve().parent / "survey-mappings/so2_2025_readiness_reference.json"


def _normalise(value: str) -> str:
    """Canonicalise whitespace without fuzzy or substring answer matching.

    Args:
        value: Literal structured answer or verified choice label.

    Returns:
        Exact case-preserving label with consecutive whitespace collapsed.
    """
    return " ".join(value.split())


def mapping_hash(mapping: Mapping[str, Any]) -> str:
    """Hash the semantic scoring configuration rather than its JSON whitespace.

    Args:
        mapping: Versioned scoring configuration embedded in the saved model.

    Returns:
        SHA-256 of sorted, ASCII JSON with compact separators.
    """
    return sha256(json.dumps(mapping, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def validate_scoring_mapping(mapping: Mapping[str, Any], questions: Sequence[Mapping[str, Any]] | None = None) -> None:
    """Validate scoring rules and optional authoritative SO2 field bindings.

    Args:
        mapping: Version-one configuration containing all seven components.
        questions: Validated descriptive-schema question dictionaries, whose
            UIDs and complete choice sets must match the scoring configuration;
            absent only when validating the self-contained saved model.

    Returns:
        None. Invalid rules fail before any response can be scored.

    Raises:
        ValueError: If configuration versions, scores, field bindings, or
            complete choice coverage are incompatible.
    """
    if not isinstance(mapping, Mapping) or mapping.get("schema_version") != 1 or not isinstance(mapping.get("mapping_version"), str) or not mapping["mapping_version"]:
        raise ValueError("Unsupported SO2 readiness scoring mapping version.")
    components = mapping.get("components")
    if not isinstance(components, Mapping) or set(components) != set(COMPONENTS):
        raise ValueError("SO2 readiness mapping requires exactly seven components.")
    indexed = {q["question_id"]: q for q in questions} if questions is not None else None
    uids = set()
    for key in COMPONENTS:
        component = components[key]
        if not isinstance(component, Mapping) or any(not isinstance(component.get(field), str) or not component[field].strip() for field in ("question_id", "form_uid", "label", "question_label")):
            raise ValueError(f"Invalid readiness component metadata: {key}.")
        if component["form_uid"] in uids:
            raise ValueError("Duplicate readiness form UID.")
        uids.add(component["form_uid"])
        expected_type = "multi_choice" if key == "c" else "single_choice"
        if component.get("question_type") != expected_type:
            raise ValueError(f"Invalid readiness question type for {key}.")
        rules = component.get("rules")
        if not isinstance(rules, list) or not rules:
            raise ValueError(f"Missing readiness rules for {key}.")
        answers = set()
        for rule in rules:
            if not isinstance(rule, Mapping) or not isinstance(rule.get("answer"), str) or not rule["answer"].strip():
                raise ValueError(f"Invalid readiness choice for {key}.")
            answer = _normalise(rule["answer"])
            if answer in answers:
                raise ValueError(f"Duplicate readiness choices for {key}.")
            answers.add(answer)
            score_band(rule.get("score"))
        if indexed is not None:
            question = indexed.get(component["question_id"])
            if question is None or question.get("form_uid") != component["form_uid"]:
                raise ValueError(f"Readiness form UID mismatch for {key}.")
            if question.get("question_type") != expected_type or answers != {_normalise(c) for c in question["categories"]}:
                raise ValueError(f"Readiness choices/type mismatch for {key}.")
    if "reference" not in mapping:
        return
    reference = mapping["reference"]
    if not isinstance(reference, Mapping) or not isinstance(reference.get("source_sha256"), str) or len(reference["source_sha256"]) != 64:
        raise ValueError("Invalid readiness reference hash.")
    rows = reference.get("source_rows")
    if not isinstance(rows, list) or not rows or any(type(row) is not int or row < 1 for row in rows) or len(set(rows)) != len(rows):
        raise ValueError("Invalid readiness reference source rows.")
    overrides = reference.get("blank_overrides")
    if not isinstance(overrides, list):
        raise ValueError("Invalid readiness blank overrides.")
    seen = set()
    for item in overrides:
        if not isinstance(item, Mapping) or item.get("source_row") not in rows or item.get("component") not in COMPONENTS or item.get("raw_answer") != "" or not isinstance(item.get("reason"), str) or not item["reason"]:
            raise ValueError("Invalid readiness blank override binding.")
        pair = (item["source_row"], item["component"])
        if pair in seen:
            raise ValueError("Duplicate readiness blank override.")
        seen.add(pair)
        score_band(item.get("score"))
    matrix = reference.get("matrix")
    if not isinstance(matrix, list) or len(matrix) != 5 or any(not isinstance(row, list) or len(row) != 5 or any(type(n) is not int or n < 0 for n in row) for row in matrix) or sum(map(sum, matrix)) != len(rows):
        raise ValueError("Invalid readiness reference matrix.")


def load_scoring_mapping(questions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Load public scoring rules and an optional private reference-replay policy.

    Args:
        questions: Descriptive-schema questions already bound to the form manifest.

    Returns:
        Validated configuration, optionally enriched from the ignored local
        reference sidecar, later embedded in sensitive output for offline rerenders.

    Raises:
        ValueError: If the file is unreadable, malformed, or incompatible.
    """
    try:
        mapping = json.loads(DEFAULT_MAPPING.read_text(encoding="utf-8"))
        if DEFAULT_REFERENCE.exists():
            private = json.loads(DEFAULT_REFERENCE.read_text(encoding="utf-8"))
            if not isinstance(private, dict) or private.get("schema_version") != 1 or "reference" not in private:
                raise ValueError("Unsupported private readiness reference policy.")
            mapping["reference"] = private["reference"]
        validate_scoring_mapping(mapping, questions)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot load readiness scoring mapping: {exc}") from exc
    return mapping


def score_band(value: float) -> int:
    """Assign a finite unit score to the documented left-closed fifths.

    Args:
        value: Numeric readiness score between zero and one, inclusive.

    Returns:
        Zero-based band: Very Low, Low, Moderate, High, or Very High.

    Raises:
        ValueError: If the value is boolean, missing, nonfinite, or outside [0,1].
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"Invalid readiness score: {value!r}.")
    return sum(value >= boundary for boundary in (.2, .4, .6, .8))


def _validate_form_bindings(mapping: Mapping[str, Any], bindings: Mapping[str, Any]) -> None:
    """Check retained authoritative UIDs, types and complete selectable choices.

    Args:
        mapping: Validated scoring rules specifying the seven authoritative UIDs.
        bindings: Lightweight saved form checksum and seven field dictionaries.

    Returns:
        None. Incompatible or incomplete authoritative metadata cannot be scored.

    Raises:
        ValueError: If form provenance, field UIDs/types, or choices are invalid.
    """
    if not isinstance(bindings, Mapping) or not isinstance(bindings.get("source_sha256"), str) or len(bindings["source_sha256"]) != 64:
        raise ValueError("Missing readiness form checksum.")
    fields = bindings.get("components")
    if not isinstance(fields, Mapping) or set(fields) != set(COMPONENTS):
        raise ValueError("Missing readiness form field bindings.")
    choice_uids = set()
    for key in COMPONENTS:
        field = fields[key]
        definition = mapping["components"][key]
        if not isinstance(field, Mapping) or field.get("uid") != definition["form_uid"] or field.get("field_type") != definition["question_type"] or type(field.get("mandatory")) is not bool:
            raise ValueError(f"Readiness actual form UID/type mismatch for {key}.")
        choices = field.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError(f"Readiness actual form choices missing for {key}.")
        labels = set()
        for choice in choices:
            if not isinstance(choice, Mapping) or any(not isinstance(choice.get(k), str) or not choice[k].strip() for k in ("uid", "label")) or choice["uid"] in choice_uids:
                raise ValueError(f"Invalid or duplicate readiness form choice for {key}.")
            choice_uids.add(choice["uid"])
            label = _normalise(choice["label"])
            if label in labels:
                raise ValueError(f"Duplicate readiness form choice label for {key}.")
            labels.add(label)
        if labels != {_normalise(rule["answer"]) for rule in definition["rules"]}:
            raise ValueError(f"Readiness actual form choices mismatch for {key}.")


def bind_form_fields(mapping: Mapping[str, Any], form_structure: Mapping[str, Any]) -> dict[str, Any]:
    """Select and validate actual manifest fields before scoring source responses.

    Args:
        mapping: Validated scoring rules already checked against the SO2 schema.
        form_structure: Metadata from load_form_manifest_structure, including
            actual manifest field_bindings and the manifest-file SHA-256.

    Returns:
        Lightweight seven-field bindings with choice UIDs/labels, actual field
        types and requiredness, plus the authoritative manifest checksum.

    Raises:
        ValueError: If the actual manifest lacks or contradicts any scoring field.
    """
    try:
        bindings = {"source_sha256": form_structure["source_sha256"], "components": {
            key: deepcopy(form_structure["field_bindings"][definition["form_uid"]])
            for key,definition in mapping["components"].items()
        }}
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Readiness actual form field binding missing: {exc}") from exc
    _validate_form_bindings(mapping, bindings)
    return bindings


def _totals(record: dict[str, Any]) -> None:
    """Attach independently calculable totals and bands to a scored source record.

    Args:
        record: Mutable scored record containing the seven component score objects.

    Returns:
        None. Missing components make only their own total unscorable.
    """
    scores = {k: record["components"][k]["score"] for k in COMPONENTS}
    record["traceability"] = (4*scores["d"] + sum(scores[k] for k in "aclu"))/8 if all(scores[k] is not None for k in "aclud") else None
    record["qm"] = (2*scores["r"] + scores["p"])/3 if all(scores[k] is not None for k in "pr") else None
    record["bands"] = {k: score_band(record[k]) if record[k] is not None else None for k in ("traceability", "qm")}


def score_sources(records: Sequence[Mapping[str, Any]], mapping: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Score literal source answers before any response-merging operation.

    Args:
        records: Contact-free dictionaries with positive unique source_row and
            answers keyed by the seven component letters; raw answers are strings.
        mapping: Validated exact-choice rules; custody rules are precedence ordered.

    Returns:
        Source-row-sorted records retaining raw answers, matched rules, unknown
        selections, scores, precedence diagnostics, totals, and band assignments.
        Input objects are never mutated and no reference overrides apply here.

    Raises:
        ValueError: If source identities, answer shapes, or scoring rules are invalid.
    """
    validate_scoring_mapping(mapping)
    result = []
    seen = set()
    for record in records:
        row = record.get("source_row")
        answers = record.get("answers")
        if type(row) is not int or row < 1 or row in seen or not isinstance(answers, Mapping) or set(answers) != set(COMPONENTS) or any(not isinstance(v, str) for v in answers.values()):
            raise ValueError("Invalid or duplicate readiness source record.")
        seen.add(row)
        scored = {"source_row": row, "components": {}}
        for key in COMPONENTS:
            definition = mapping["components"][key]
            raw = answers[key]
            selections = [_normalise(v) for v in raw.split(";")] if key == "c" else [_normalise(raw)]
            selections = set(filter(None, selections))
            matched = [deepcopy(rule) for rule in definition["rules"] if _normalise(rule["answer"]) in selections]
            unknown = sorted(selections - {_normalise(rule["answer"]) for rule in matched})
            status = "missing" if not selections else "unrecognised" if unknown else "scored"
            scored["components"][key] = {
                "question_id": definition["question_id"], "form_uid": definition["form_uid"],
                "raw_answer": raw, "matched_rules": matched, "unknown_selections": unknown,
                "score": matched[0]["score"] if status == "scored" else None,
                "status": status, "precedence_applied": len({r["score"] for r in matched}) > 1,
            }
        _totals(scored)
        result.append(scored)
    return sorted(result, key=lambda item: item["source_row"])


def _matrix(records: Sequence[Mapping[str, Any]]) -> list[list[int]]:
    """Count complete pairs with traceability rows and QM columns.

    Args:
        records: Source or agreeing analytical vectors with independently computed totals.

    Returns:
        Five-by-five counts in ascending readiness order on both dimensions.
    """
    matrix = [[0]*5 for _ in range(5)]
    for record in records:
        if record["traceability"] is not None and record["qm"] is not None:
            matrix[score_band(record["traceability"])][score_band(record["qm"])] += 1
    return matrix


def reference_view(sources: Sequence[Mapping[str, Any]], mapping: Mapping[str, Any], source_sha256: str) -> dict[str, Any]:
    """Build the source-submission view, applying only hash-bound replay exceptions.

    Args:
        sources: Original source scores without overrides.
        mapping: Validated scoring rules, optionally containing a reviewed
            private reference binding; its absence always disables replay overrides.
        source_sha256: Hash of the actual input workbook, not a user-supplied label.

    Returns:
        Source view with copied scores, matrix, complete-pair count and explicit
        override list; unrelated workbooks never receive Josephine's exception.

    Raises:
        ValueError: If the reference hash matches but rows, blank answers, or
            reference matrix no longer reproduce the reviewed evidence.
    """
    copied = deepcopy(list(sources))
    reference = mapping.get("reference")
    replay = reference is not None and source_sha256 == reference["source_sha256"]
    overrides = []
    if replay:
        if [s["source_row"] for s in copied] != reference["source_rows"]:
            raise ValueError("Readiness reference source rows do not match the hash-bound replay.")
        indexed = {s["source_row"]: s for s in copied}
        for override in reference["blank_overrides"]:
            target = indexed[override["source_row"]]
            component = target["components"][override["component"]]
            if component["raw_answer"] != override["raw_answer"] or component["status"] != "missing":
                raise ValueError("Readiness reference override does not target the verified blank answer.")
            component.update(score=override["score"], status="reference_override")
            _totals(target)
            overrides.append(deepcopy(override))
    matrix = _matrix(copied)
    if replay and matrix != reference["matrix"]:
        raise ValueError("Readiness reference matrix does not reproduce Josephine.")
    return {"is_josephine_replay": replay, "source_scores": copied, "overrides": overrides,
            "matrix": matrix, "complete_pairs": sum(map(sum, matrix)), "source_responses": len(copied)}


def build_readiness_model(sources: Sequence[Mapping[str, Any]], groups: Sequence[Mapping[str, Any]], mapping: Mapping[str, Any], source_sha256: str, form_bindings: Mapping[str, Any]) -> dict[str, Any]:
    """Associate original vectors with reviewed observations without inventing scores.

    Args:
        sources: Pre-merge original scored responses, one per source worksheet row.
        groups: Reviewed observation groups containing source_rows, institution,
            corrected country code, and optional canonical biobank_id.
        mapping: Validated scoring configuration embedded for independent rerendering.
        source_sha256: Original workbook checksum binding the optional reference replay.
        form_bindings: Verified actual manifest checksum and seven bound fields,
            including their choice UIDs/labels, types and mandatory status.

    Returns:
        Versioned self-contained model with source scores, per-observation
        alternative vectors, diagnostics, main counts, and reference/source view.
        Agreement means identical seven-score vectors; differing or incomplete
        vectors are never averaged, unioned, or selected for convenience.

    Raises:
        ValueError: If groups omit, duplicate, or reference nonexistent source rows.
    """
    validate_scoring_mapping(mapping)
    _validate_form_bindings(mapping, form_bindings)
    indexed = {s["source_row"]: s for s in sources}
    if len(indexed) != len(sources):
        raise ValueError("Duplicate readiness scored sources.")
    observations = []
    covered = set()
    accepted = []
    for group in groups:
        rows = group.get("source_rows")
        if not isinstance(rows, list) or not rows or any(type(r) is not int or r not in indexed or r in covered for r in rows) or len(set(rows)) != len(rows):
            raise ValueError("Invalid readiness observation source coverage.")
        if any(not isinstance(group.get(k), str) for k in ("institution", "country")):
            raise ValueError("Invalid readiness institution/country metadata.")
        identity = group.get("biobank_id")
        if identity is not None and (not isinstance(identity, str) or not identity):
            raise ValueError("Invalid readiness biobank identity.")
        covered.update(rows)
        alternatives = {}
        for row in sorted(rows):
            source = indexed[row]
            vector = tuple(source["components"][k]["score"] for k in COMPONENTS)
            if vector not in alternatives:
                alternatives[vector] = {"source_rows": [], "scores": dict(zip(COMPONENTS, vector)),
                                        "traceability": source["traceability"], "qm": source["qm"], "bands": deepcopy(source["bands"])}
            alternatives[vector]["source_rows"].append(row)
        differing = len(alternatives) > 1
        incomplete = any(s is None for vector in alternatives for s in vector)
        status = "conflicting" if differing else "incomplete" if incomplete else "complete"
        observation = {**deepcopy(dict(group)), "source_rows": sorted(rows), "status": status, "alternatives": list(alternatives.values())}
        observations.append(observation)
        if status == "complete":
            accepted.append(indexed[rows[0]])
    if covered != set(indexed):
        raise ValueError("Readiness observation groups do not cover every source response.")
    observations.sort(key=lambda g: (g["country"], g["institution"].casefold(), g["source_rows"][0]))
    matrix = _matrix(accepted)
    return {
        "schema_version": 1, "mapping_version": mapping["mapping_version"], "mapping_sha256": mapping_hash(mapping),
        "mapping": deepcopy(dict(mapping)), "source_sha256": source_sha256,
        "form_bindings": deepcopy(dict(form_bindings)),
        "source_scores": deepcopy(sorted(sources, key=lambda s: s["source_row"])), "observations": observations,
        "bands": list(BANDS),
        "diagnostics": [{"source_row": s["source_row"], "component": k, "status": c["status"], "precedence_applied": c["precedence_applied"]}
                        for s in sorted(sources, key=lambda s: s["source_row"]) for k,c in s["components"].items()
                        if c["status"] != "scored" or c["precedence_applied"]],
        "main": {"observations": len(observations), "complete_pairs": len(accepted), "matrix": matrix,
                 "conflicting_observations": sum(g["status"] == "conflicting" for g in observations),
                 "incomplete_observations": sum(g["status"] == "incomplete" for g in observations)},
        "source_view": reference_view(sources, mapping, source_sha256),
    }


def validate_readiness_model(
    model: Mapping[str, Any],
    source_sha256: str | None = None,
    observation_sources: Sequence[Mapping[str, Any]] | None = None,
    source_records: Sequence[Mapping[str, Any]] | None = None,
    questions: Sequence[Mapping[str, Any]] | None = None,
    form_sha256: str | None = None,
    authoritative_form_structure: Mapping[str, Any] | None = None,
) -> None:
    """Recompute a saved scoring model before using it for figures or tables.

    Args:
        model: Serialized readiness_scores object; all contributions and rules
            must be present, with unique and exhaustive observation membership.
        source_sha256: Optional enclosing descriptive report's original workbook
            checksum; the readiness model must be bound to the same source.
        observation_sources: Optional enclosing Responses Summary observation
            groups; both source-row partitions and biobank identities must agree.
        source_records: Optional independently preserved raw response records
            from Responses Summary; all seven literal answers must match exactly.
        questions: Enclosing report/schema question dictionaries providing source
            columns for cross-checks; required whenever source_records are supplied.
        form_sha256: Optional enclosing report's authoritative manifest checksum;
            retained field binding evidence must reference the same manifest.
        authoritative_form_structure: Optional independently preserved actual
            manifest fields and checksum from the enclosing report; embedded
            binding UIDs, choices, types and requiredness must match them exactly.

    Returns:
        None. Every derived score, count, band, override, and checksum must agree.

    Raises:
        ValueError: If any required field or derived value is missing or inconsistent.
    """
    try:
        if source_sha256 is not None and model["source_sha256"] != source_sha256:
            raise ValueError("Readiness source checksum differs from the enclosing report.")
        if form_sha256 is not None and model["form_bindings"]["source_sha256"] != form_sha256:
            raise ValueError("Readiness form checksum differs from the enclosing report.")
        if authoritative_form_structure is not None:
            expected_bindings = bind_form_fields(model["mapping"], authoritative_form_structure)
            if json.dumps(expected_bindings,sort_keys=True) != json.dumps(model["form_bindings"],sort_keys=True):
                raise ValueError("Readiness bindings differ from independent authoritative form evidence.")
        if observation_sources is not None:
            expected = sorted((tuple(sorted(g["source_rows"])), g["biobank_id"]) for g in observation_sources)
            actual = sorted((tuple(sorted(g["source_rows"])), g["biobank_id"]) for g in model["observations"])
            if expected != actual:
                raise ValueError("Readiness observation membership differs from the enclosing report.")
        records = [{"source_row": s["source_row"], "answers": {k:s["components"][k]["raw_answer"] for k in COMPONENTS}}
                   for s in model["source_scores"]]
        if source_records is not None:
            if questions is None:
                raise ValueError("Readiness raw answer cross-check requires source question columns.")
            by_question = {q["question_id"]:q for q in questions}
            original = {s["source_row"]:s["answers"] for s in source_records}
            if len(original) != len(source_records) or set(original) != {s["source_row"] for s in records}:
                raise ValueError("Readiness raw answer source coverage differs from the report.")
            for record in records:
                for key,definition in model["mapping"]["components"].items():
                    column = by_question[definition["question_id"]]["column"]
                    if original[record["source_row"]][column] != record["answers"][key]:
                        raise ValueError(f"Readiness raw answer differs from preserved source row {record['source_row']}, {key}.")
        sources = score_sources(records, model["mapping"])
        groups = [{k: g[k] for k in ("source_rows", "institution", "country", "biobank_id")} for g in model["observations"]]
        rebuilt = build_readiness_model(sources, groups, model["mapping"], model["source_sha256"], model["form_bindings"])
        if json.dumps(rebuilt, sort_keys=True, allow_nan=False) != json.dumps(model, sort_keys=True, allow_nan=False):
            raise ValueError("Stored readiness scores or aggregates differ from their source evidence.")
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"Invalid saved readiness model: {exc}") from exc


def heatmap_fragment(view: Mapping[str, Any], title: str, unit: str) -> str:
    """Render native vector five-band counts with the reference axis orientation.

    Args:
        view: Validated matrix and complete_pairs count from either scoring view.
        title: TeX-safe chart heading identifying reference or deduplicated cohort.
        unit: TeX-safe observation-unit label for the colour scale.

    Returns:
        PGFPlots/TikZ fragment using Viridis and a shared 0..35 colour scale;
        larger future cohorts extend the scale rather than clipping counts.
    """
    maximum = max(35, max(map(max, view["matrix"])))
    labels = ",".join("{"+v+"}" for v in BANDS)
    table = "\n".join(f"{x} {y} {n}" for y,row in enumerate(view["matrix"]) for x,n in enumerate(row))
    nodes = "\n".join(rf"\node[text={'white' if n < maximum*.48 else 'black'},font=\sffamily\small] at (axis cs:{x},{y}) {{{n}}};"
                      for y,row in enumerate(view["matrix"]) for x,n in enumerate(row))
    return "\n".join([
        rf"\noindent\textbf{{{title}}}\par",
        rf"Complete score pairs: {view['complete_pairs']}.\par",
        r"\begin{center}\begin{tikzpicture}",
        rf"\begin{{axis}}[width=0.65\linewidth,height=0.65\linewidth,scale only axis,",
        r"xmin=-0.5,xmax=4.5,ymin=-0.5,ymax=4.5,y dir=reverse,axis on top,",
        rf"xtick={{0,1,2,3,4}},ytick={{0,1,2,3,4}},xticklabels={{{labels}}},yticklabels={{{labels}}},",
        r"x tick label style={font=\sffamily\small},y tick label style={font=\sffamily\small},",
        r"xticklabel pos=upper,xlabel={QM readiness level},ylabel={Traceability readiness level},",
        rf"colormap/viridis,point meta min=0,point meta max={maximum},colorbar,",
        rf"colorbar style={{ylabel={{{unit}}},yticklabel style={{font=\sffamily\small,/pgf/number format/assume math mode=true}}}}]",
        r"\addplot[matrix plot*,mesh/cols=5,point meta=explicit] table[x=x,y=y,meta=count] {",
        "x y count", table, r"};", nodes, r"\end{axis}\end{tikzpicture}\end{center}",
    ])


def readiness_section(model: Mapping[str, Any], escape: Callable[[str], str]) -> tuple[str, dict[str, str]]:
    """Compose the final scoring section and reusable native chart fragments.

    Args:
        model: Validated scoring payload retaining source and deduplicated audit data.
        escape: Existing report's LaTeX-escaping function for all human input text.

    Returns:
        Methodology and country-grouped repeated-header score-table TeX, plus
        only the deduplicated heatmap fragment for standalone publication.

    Raises:
        ValueError: If the stored model cannot be reproduced from its contributions.
    """
    validate_readiness_model(model)
    mapping = model["mapping"]
    text = [r"\clearpage", r"\section{QM vs traceability readiness}",
            r"These exploratory questionnaire-derived scores are not validated quality certifications. Scores use original submissions, never a union of conflicting answers.\par",
            r"\[T=\frac{d+(a+c+l+u)/4}{2}=\frac{4d+a+c+l+u}{8},\qquad Q=\frac{2r+p}{3}.\]",
            r"Technical self-assessment carries 50\% of traceability; each operational component carries 12.5\%. QMS self-assessment carries two-thirds of QM readiness. The digital-manual and paper QMS scores are literal 0.66 and 0.33, not exact thirds.\par",
            r"Custody selections use the first applicable rule in the order below; differing selections are flagged. ``Don't know'' scores zero by convention, not as proof of absent tracking. Missing or unrecognised answers are unscorable.\par",
            r"Bands: $[0,.2)$, $[.2,.4)$, $[.4,.6)$, $[.6,.8)$, $[.8,1]$. Exact internal boundaries enter the higher band.\par",
            rf"Scoring mapping: {escape(mapping['mapping_version'])}.\par",
            r"\subsection{Scoring rules}", r"\begingroup\smaller[2]",
            r"\begin{longtable}{@{}p{.19\linewidth}p{.65\linewidth}r@{}}",
            r"\toprule Component & Answer (custody precedence order) & Score \\ \midrule\endfirsthead",
            r"\toprule Component & Answer (custody precedence order) & Score \\ \midrule\endhead"]
    for key in COMPONENTS:
        component = mapping["components"][key]
        for index,rule in enumerate(component["rules"]):
            selector = "_".join(component["question_id"].split("_")[:2])
            label = escape(f"{key} ({selector}): {component['label']}") if index == 0 else ""
            text.append(f"{label} & {escape(rule['answer'])} & {rule['score']:g}" + r" \\")
        text.append(r"\midrule")
    text.extend([r"\bottomrule\end{longtable}\endgroup", r"\clearpage\subsection{Deduplicated observations}"])
    main = model["main"]
    text.append(rf"{main['observations']} observations; {main['complete_pairs']} complete pairs; {main['conflicting_observations']} conflicting groups and {main['incomplete_observations']} incomplete observations excluded from this heatmap. Agreeing score vectors count once. All alternatives remain in the table below. Unresolved identities remain separate observations.\par")
    fragments = {"readiness-main": heatmap_fragment(main, "Deduplicated, conflict-aware analysis", "Observations")}
    text.append("%% readiness-main")
    text.extend([r"\clearpage\subsection{Scores by institution and country}",
                 r"Component letters refer to the scoring rules above. A dash means unscorable. Totals are printed to four decimals; calculations and bands use full precision. Rows identify original worksheet submissions.\par",
                 r"\begingroup\smaller[3]\setlength{\tabcolsep}{2pt}",
                 r"\begin{longtable}{@{}>{\raggedright\arraybackslash}p{.26\linewidth}>{\raggedright\arraybackslash}p{.11\linewidth}*{7}{r}rr@{}}",
                 r"\toprule Institution / CC & Source rows / status & $a$ & $c$ & $l$ & $u$ & $d$ & $p$ & $r$ & $T$ & $Q$ \\ \midrule\endfirsthead",
                 r"\toprule Institution / CC & Source rows / status & $a$ & $c$ & $l$ & $u$ & $d$ & $p$ & $r$ & $T$ & $Q$ \\ \midrule\endhead",
                 r"\midrule\multicolumn{11}{r}{Continued on next page}\\\endfoot",
                 r"\bottomrule\endlastfoot"])
    country = None
    source_index = {s["source_row"]:s for s in model["source_scores"]}
    for group in model["observations"]:
        if country != group["country"]:
            country = group["country"]
            text.append(rf"\midrule\multicolumn{{11}}{{c}}{{\textbf{{{escape(country)}}}}}\\*\midrule")
        for index, alternative in enumerate(group["alternatives"]):
            first = escape(group["institution"] + " (" + country + ")") if index == 0 else ""
            rows = alternative["source_rows"]
            status = group["status"]
            precedence = [str(row) for row in rows if source_index[row]["components"]["c"]["precedence_applied"]]
            if precedence:
                status += "; custody precedence: " + ", ".join(precedence)
            values = [alternative["scores"][k] for k in COMPONENTS] + [alternative["traceability"], alternative["qm"]]
            cells = [first, escape(", ".join(map(str, rows)) + ": " + status)]
            cells += ["---" if v is None else f"{v:.4f}".rstrip("0").rstrip(".") for v in values]
            text.append(" & ".join(cells) + (r" \\*" if index < len(group["alternatives"])-1 else r" \\"))
        text.append(r"\midrule")
    text.extend([r"\end{longtable}\endgroup"])
    return "\n".join(text), fragments
