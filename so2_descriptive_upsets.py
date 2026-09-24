"""Create and validate optional external ComplexUpset assets for SO2 reports."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import csv
import json
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Mapping, Sequence


class InputError(Exception):
    """Raised when an UpSet registry, payload, or asset bundle is invalid."""


@dataclass(frozen=True)
class UpSetDefinition:
    """One approved report figure definition.

    Attributes:
        definition_id: Stable safe filename and report identifier.
        question_selectors: Numeric IDs resolved against payload question identifiers.
        title: Human-readable report title.
    """

    definition_id: str
    question_selectors: tuple[str, ...]
    title: str


@dataclass(frozen=True)
class UpSetFigure:
    """Validated relative filenames for one rendered figure pair.

    Attributes:
        upset_pdf: Relative UpSet PDF filename.
        deviation_pdf: Relative deviation PDF filename.
    """

    upset_pdf: str
    deviation_pdf: str


@dataclass(frozen=True)
class ValidatedUpSetAssets:
    """Validated optional asset state passed to the TeX renderer.

    Attributes:
        state: Asset availability: ``empty`` when omitted, ``complete`` after bundle validation.
        figures: Figure pairs keyed by definition ID.
    """

    state: str
    figures: Mapping[str, UpSetFigure]


_SAFE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_SELECTOR = re.compile(r"^q_[0-9]{3}$")
_BUNDLE_VERSION = "1"
_MAX_UPSET_LABEL_LENGTH = 52


def _short_display_label(label: str, maximum: int = _MAX_UPSET_LABEL_LENGTH) -> str:
    """Create a readable bounded UpSet set label while retaining its source prefix.

    Args:
        label: Full ``q_NNN::category`` label for combined definitions, or a
            category label for a single-question definition.
        maximum: Maximum display-label length including the source prefix.

    Returns:
        Deterministically shortened label that retains the source question prefix.

    Raises:
        InputError: If the label lacks the required source/category separator.
    """
    if maximum < 12:
        raise InputError("UpSet display label maximum must allow readable text.")
    prefix, value = label.split("::", 1) if "::" in label else ("", label)
    value = " ".join(value.rstrip(": ").split())
    marker = "(please specify)"
    if marker in value.casefold():
        value = f"{value.split('(', 1)[0].rstrip(' (:')} (please specify)"
    available = maximum - (len(prefix) + 2 if prefix else 0)
    if len(value) > available:
        words = value.split()
        compact: list[str] = []
        for word in words:
            candidate = " ".join([*compact, word])
            if len(candidate) + 3 > available:
                break
            compact.append(word)
        value = (" ".join(compact) or value[: max(1, available - 3)]).rstrip() + "..."
    return f"{prefix}::{value}" if prefix else value


def load_upset_registry(path: str | Path) -> tuple[UpSetDefinition, ...]:
    """Load a versioned ordered registry of approved descriptive UpSet figures.

    Args:
        path: JSON registry path.

    Returns:
        Immutable definitions in configured order.

    Raises:
        InputError: If the file is unreadable, malformed, or has invalid entries.
    """
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"Could not read UpSet registry {path}: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("registry_version") != "1":
        raise InputError("UpSet registry must have supported registry_version '1'.")
    entries = raw.get("definitions")
    if not isinstance(entries, list) or not entries:
        raise InputError("UpSet registry definitions must be a nonempty array.")
    result: list[UpSetDefinition] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise InputError(f"UpSet registry definitions[{index}] must be an object.")
        definition_id = entry.get("id")
        selectors = entry.get("question_selectors")
        title = entry.get("title")
        if not isinstance(definition_id, str) or not _SAFE_ID.fullmatch(definition_id):
            raise InputError(f"UpSet registry definitions[{index}].id must be a safe identifier.")
        if definition_id in seen:
            raise InputError(f"UpSet registry has duplicate definition id {definition_id!r}.")
        if not isinstance(selectors, list) or not selectors or len(set(selectors)) != len(selectors) or not all(
            isinstance(item, str) and _SELECTOR.fullmatch(item) for item in selectors
        ):
            raise InputError(f"UpSet registry definitions[{index}].question_selectors must be unique q_NNN values.")
        if not isinstance(title, str) or not title.strip():
            raise InputError(f"UpSet registry definitions[{index}].title must be nonblank text.")
        seen.add(definition_id)
        result.append(UpSetDefinition(definition_id, tuple(selectors), title))
    return tuple(result)


def _canonical_json(value: Any) -> bytes:
    """Encode JSON-compatible data deterministically.

    Args:
        value: JSON-compatible value.

    Returns:
        Canonical UTF-8 JSON bytes.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def resolve_payload_questions(payload: Mapping[str, Any], selectors: Sequence[str]) -> tuple[Mapping[str, Any], ...]:
    """Resolve each numeric selector to exactly one multi-choice payload question.

    Args:
        payload: Descriptive-statistics payload.
        selectors: Registry selectors in required order.

    Returns:
        Resolved question mappings in selector order.

    Raises:
        InputError: If a selector is unresolved, ambiguous, or non-multi-choice.
    """
    questions = payload.get("questions")
    if not isinstance(questions, list):
        raise InputError("Descriptive payload questions must be an array for UpSet export.")
    resolved: list[Mapping[str, Any]] = []
    for selector in selectors:
        matches = [item for item in questions if isinstance(item, Mapping) and str(item.get("question_id", "")).startswith(f"{selector}_")]
        if len(matches) != 1:
            raise InputError(f"UpSet selector {selector!r} must resolve to exactly one descriptive question, found {len(matches)}.")
        if matches[0].get("question_type") != "multi_choice":
            raise InputError(f"UpSet selector {selector!r} resolves to a non-multi-choice question.")
        resolved.append(matches[0])
    return tuple(resolved)


def canonical_upset_material(payload: Mapping[str, Any], definitions: Sequence[UpSetDefinition]) -> dict[str, Any]:
    """Extract the source-of-truth vectors and resolved definitions for hashing.

    Args:
        payload: Validated descriptive-statistics payload.
        definitions: Approved definitions in report order.

    Returns:
        Canonical JSON-compatible vector and definition material.

    Raises:
        InputError: If a configured question has no retained canonical vectors.
    """
    vectors = payload.get("upset_vectors")
    if not isinstance(vectors, Mapping):
        raise InputError("Descriptive payload lacks canonical upset_vectors.")
    material: dict[str, Any] = {"definitions": [], "vectors": {}}
    for definition in definitions:
        questions = resolve_payload_questions(payload, definition.question_selectors)
        ids = [str(question["question_id"]) for question in questions]
        material["definitions"].append({"id": definition.definition_id, "questions": ids})
        for question_id in ids:
            if not isinstance(vectors.get(question_id), list):
                raise InputError(f"Descriptive payload lacks vectors for {question_id!r}.")
            material["vectors"][question_id] = vectors[question_id]
    return material


def canonical_upset_sha256(payload: Mapping[str, Any], definitions: Sequence[UpSetDefinition]) -> str:
    """Calculate the content hash which binds a bundle to a payload.

    Args:
        payload: Validated descriptive-statistics payload.
        definitions: Approved definitions in report order.

    Returns:
        Lowercase SHA-256 digest.

    Raises:
        InputError: If canonical material cannot be extracted.
    """
    return sha256(_canonical_json(canonical_upset_material(payload, definitions))).hexdigest()


def _matrix_rows(payload: Mapping[str, Any], definition: UpSetDefinition) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    """Build one answered-only Boolean matrix, inner joining combined questions.

    Args:
        payload: Validated descriptive-statistics payload.
        definition: Approved definition to materialize.

    Returns:
        ASCII-safe set-column names, their display labels, and CSV rows in source-row order.

    Raises:
        InputError: If vector identities are malformed or duplicate answered rows exist.
    """
    questions = resolve_payload_questions(payload, definition.question_selectors)
    vectors = payload["upset_vectors"]
    joins: list[tuple[Mapping[str, Any], dict[int, Mapping[str, Any]]]] = []
    columns: list[str] = []
    labels: list[str] = []
    for question in questions:
        question_id = str(question["question_id"])
        prefix = "_".join(question_id.split("_", 2)[:2])
        categories = [str(value["value"]) for value in question["categories"] if value["value"] != "Missing"]
        labels.extend(
            f"{prefix}::{category}" if len(questions) > 1 else category
            for category in categories
        )
        answered: dict[int, Mapping[str, Any]] = {}
        for vector in vectors[question_id]:
            source_row = vector.get("source_row") if isinstance(vector, Mapping) else None
            if isinstance(source_row, bool) or not isinstance(source_row, int) or source_row < 1:
                raise InputError(f"Invalid canonical vector source_row for {question_id!r}.")
            if vector.get("state") == "answered":
                if source_row in answered:
                    raise InputError(f"Duplicate answered source row {source_row} for {question_id!r}.")
                answered[source_row] = vector
        joins.append((question, answered))
    source_rows = set.intersection(*(set(answered) for _, answered in joins)) if joins else set()
    rows: list[dict[str, Any]] = []
    for source_row in sorted(source_rows):
        first = joins[0][1][source_row]
        row: dict[str, Any] = {"source_row": source_row, "country": first["country"], "institution": first["institution"]}
        for question, answered in joins:
            prefix = "_".join(str(question["question_id"]).split("_", 2)[:2])
            selected = set(answered[source_row].get("selected_categories", []))
            for category in [str(value["value"]) for value in question["categories"] if value["value"] != "Missing"]:
                label = f"{prefix}::{category}" if len(questions) > 1 else category
                row[label] = category in selected
        rows.append(row)
    columns = [f"set_{index:03d}" for index in range(1, len(labels) + 1)]
    for row in rows:
        selected_values = {
            key: value for key, value in row.items()
            if key not in {"source_row", "country", "institution"}
        }
        for column, label in zip(columns, labels, strict=True):
            row[column] = selected_values[label]
        for label in labels:
            del row[label]
    return columns, [_short_display_label(label) for label in labels], rows


def _renderer_source() -> str:
    """Generate R source that renders all CSV definitions in one bundle.

    Returns:
        R source text requiring ComplexUpset, ggplot2, and jsonlite.
    """
    return """required <- c(\"ComplexUpset\", \"ggplot2\", \"jsonlite\")
missing <- required[!vapply(required, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) stop(\"Install required R packages: \", paste(missing, collapse = \", \"))
get_script_dir <- function() {
  file_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
  if (length(file_arg)) return(dirname(normalizePath(sub("^--file=", "", file_arg[[1]]))))
  getwd()
}
bundle_dir <- if (length(commandArgs(trailingOnly = TRUE))) commandArgs(trailingOnly = TRUE)[[1]] else get_script_dir()
manifest <- jsonlite::fromJSON(file.path(bundle_dir, \"input-manifest.json\"), simplifyVector = FALSE)
sha256 <- function(path) {
  output <- system2(\"sha256sum\", path, stdout = TRUE, stderr = TRUE)
  status <- attr(output, \"status\")
  if (!is.null(status) && status != 0) stop(\"sha256sum failed for \", path)
  strsplit(output[[1]], \" +\")[[1]][[1]]
}
outputs <- list()
for (definition in manifest$definitions) {
  data <- utils::read.csv(file.path(bundle_dir, definition$csv), check.names = FALSE)
  sets <- unlist(definition$sets, use.names = FALSE)
  labels <- unlist(definition$set_labels, use.names = FALSE)
  for (set in sets) data[[set]] <- as.logical(data[[set]])
  max_set_count <- max(vapply(sets, function(set) sum(data[[set]]), numeric(1)))
  plot_data <- data
  names(plot_data)[match(sets, names(plot_data))] <- labels
  plot <- ComplexUpset::upset(plot_data, labels, sort_intersections_by = \"cardinality\", min_size = 1, width_ratio = 0.2,
    set_sizes = (
      ComplexUpset::upset_set_size() +
      ggplot2::geom_text(ggplot2::aes(label = ggplot2::after_stat(count)), hjust = 1.1, stat = \"count\") +
      ggplot2::expand_limits(y = max_set_count * 1.15)
    ),
    matrix = ComplexUpset::intersection_matrix(geom = ggplot2::geom_point(size = 2.3)))
  ggplot2::ggsave(file.path(bundle_dir, definition$upset_pdf), plot, width = 10, height = 7, units = \"in\")
  probabilities <- vapply(sets, function(set) mean(data[[set]]), numeric(1))
  observed_table <- table(apply(data[sets], 1, paste, collapse = \"|\"))
  keys <- names(observed_table)
  observed <- as.integer(observed_table)
  expected <- vapply(strsplit(keys, \"|\", fixed = TRUE), function(bits) {
    nrow(data) * prod(ifelse(bits == \"TRUE\", probabilities, 1 - probabilities))
  }, numeric(1))
  deviation <- data.frame(intersection = seq_along(observed), deviation = observed - expected)
  dev_plot <- ggplot2::ggplot(deviation, ggplot2::aes(intersection, deviation)) +
    ggplot2::geom_col(fill = \"#C43C35\") + ggplot2::geom_hline(yintercept = 0) +
    ggplot2::labs(x = \"Intersection\", y = \"Observed minus expected\") + ggplot2::theme_minimal()
  ggplot2::ggsave(file.path(bundle_dir, definition$deviation_pdf), dev_plot, width = 10, height = 5, units = \"in\")
  outputs[[definition$id]] <- list(upset_pdf = definition$upset_pdf, deviation_pdf = definition$deviation_pdf, upset_sha256 = sha256(file.path(bundle_dir, definition$upset_pdf)), deviation_sha256 = sha256(file.path(bundle_dir, definition$deviation_pdf)))
}
jsonlite::write_json(list(bundle_version = \"1\", canonical_sha256 = manifest$canonical_sha256, outputs = outputs), file.path(bundle_dir, \"output-manifest.json\"), auto_unbox = TRUE, pretty = TRUE)
"""


def write_upset_r_bundle(payload: Mapping[str, Any], registry_path: str | Path, output_dir: str | Path, overwrite: bool = False) -> Path:
    """Transactionally write CSV inputs, manifest, and an external R renderer.

    Args:
        payload: Validated descriptive-statistics payload with canonical vectors.
        registry_path: Approved figure-registry JSON path.
        output_dir: Requested bundle directory.
        overwrite: Whether an existing directory may be replaced after staging succeeds.

    Returns:
        Published bundle directory.

    Raises:
        InputError: If the target is unsafe or bundle files cannot be created.
    """
    definitions = load_upset_registry(registry_path)
    canonical_hash = canonical_upset_sha256(payload, definitions)
    target = Path(output_dir)
    if target.exists() and not overwrite:
        raise InputError(f"UpSet bundle output directory already exists: {target}. Use --overwrite to replace it.")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.stage-", dir=target.parent))
    try:
        records = []
        for definition in definitions:
            sets, set_labels, rows = _matrix_rows(payload, definition)
            csv_name = f"{definition.definition_id}.csv"
            with (staging / csv_name).open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["source_row", "country", "institution", *sets])
                writer.writeheader()
                writer.writerows(rows)
            records.append({"id": definition.definition_id, "title": definition.title, "csv": csv_name, "sets": sets, "set_labels": set_labels, "upset_pdf": f"{definition.definition_id}-upset.pdf", "deviation_pdf": f"{definition.definition_id}-deviation.pdf"})
        manifest = {"bundle_version": _BUNDLE_VERSION, "canonical_sha256": canonical_hash, "source_payload_sha256": sha256(_canonical_json(payload)).hexdigest(), "definitions": records}
        (staging / "input-manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (staging / "render-descriptive-upsets.R").write_text(_renderer_source(), encoding="utf-8")
        if target.exists():
            shutil.rmtree(target)
        staging.replace(target)
    except OSError as exc:
        raise InputError(f"Could not write UpSet bundle {target}: {exc}") from exc
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    return target


def validate_upset_asset_bundle(payload: Mapping[str, Any], registry_path: str | Path, assets_dir: str | Path) -> ValidatedUpSetAssets:
    """Validate an explicitly supplied external asset directory before TeX embedding.

    Args:
        payload: Fresh descriptive-statistics payload to bind to the assets.
        registry_path: Approved registry used to calculate the expected hash.
        assets_dir: Existing external bundle directory, which may be intentionally empty.

    Returns:
        Empty or complete immutable asset state for the report renderer.

    Raises:
        InputError: If the directory is absent, stale, incomplete, or unsafe.
    """
    directory = Path(assets_dir)
    if not directory.is_dir():
        raise InputError(f"UpSet asset directory does not exist or is not a directory: {directory}.")
    if not any(directory.iterdir()):
        return ValidatedUpSetAssets("empty", {})
    try:
        input_manifest = json.loads((directory / "input-manifest.json").read_text(encoding="utf-8"))
        output_manifest = json.loads((directory / "output-manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"UpSet asset directory lacks readable bundle manifests: {exc}") from exc
    definitions = load_upset_registry(registry_path)
    expected_hash = canonical_upset_sha256(payload, definitions)
    if input_manifest.get("bundle_version") != _BUNDLE_VERSION or output_manifest.get("bundle_version") != _BUNDLE_VERSION:
        raise InputError("UpSet asset bundle has an unsupported manifest version.")
    if input_manifest.get("canonical_sha256") != expected_hash or output_manifest.get("canonical_sha256") != expected_hash:
        raise InputError("UpSet asset bundle canonical SHA-256 does not match the current descriptive payload.")
    expected_ids = [definition.definition_id for definition in definitions]
    input_definitions = input_manifest.get("definitions")
    outputs = output_manifest.get("outputs")
    if not isinstance(input_definitions, list) or not isinstance(outputs, dict) or [item.get("id") for item in input_definitions if isinstance(item, dict)] != expected_ids:
        raise InputError("UpSet asset bundle definitions do not match the approved registry.")
    figures: dict[str, UpSetFigure] = {}
    for item in input_definitions:
        definition_id = item["id"]
        output = outputs.get(definition_id)
        if not isinstance(output, dict):
            raise InputError(f"UpSet asset bundle lacks output manifest entry for {definition_id!r}.")
        paths = (item.get("upset_pdf"), item.get("deviation_pdf"))
        if not all(isinstance(path, str) and Path(path).name == path and path.endswith(".pdf") for path in paths):
            raise InputError(f"UpSet asset bundle has unsafe PDF path for {definition_id!r}.")
        if output.get("upset_pdf") != paths[0] or output.get("deviation_pdf") != paths[1] or not all((directory / path).is_file() for path in paths):
            raise InputError(f"UpSet asset bundle is incomplete for {definition_id!r}.")
        hashes = (output.get("upset_sha256"), output.get("deviation_sha256"))
        if not all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) for value in hashes):
            raise InputError(f"UpSet asset bundle lacks SHA-256 values for {definition_id!r}.")
        if tuple(sha256((directory / path).read_bytes()).hexdigest() for path in paths) != hashes:
            raise InputError(f"UpSet asset bundle PDF SHA-256 mismatch for {definition_id!r}.")
        figures[definition_id] = UpSetFigure(
            (directory / paths[0]).resolve().as_posix(),
            (directory / paths[1]).resolve().as_posix(),
        )
    return ValidatedUpSetAssets("complete", figures)
