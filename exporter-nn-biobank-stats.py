#!/usr/bin/env python3
"""Export per-National-Node biobank statistics from Directory evidence."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping

import pandas as pd

from cli_common import (add_directory_auth_arguments, add_directory_schema_argument,
                        add_logging_arguments, add_no_stdout_argument,
                        add_purge_cache_arguments, add_xlsx_output_argument,
                        build_directory_kwargs, build_parser, configure_logging)
from directory import Directory

log = logging.getLogger(__name__)
POLICY_VERSION = "1"

@dataclass(frozen=True)
class CategoryRule:
    """One versioned biobank-category mapping rule."""

    name: str
    types: frozenset[str]
    supported: bool

CATEGORY_POLICY = (
    CategoryRule("hospital-integrated", frozenset({"HOSPITAL"}), True),
    CategoryRule("population-based", frozenset({"POPULATION_BASED"}), True),
    CategoryRule("human biomonitoring", frozenset(), False),
    CategoryRule("environmental", frozenset(), False),
    CategoryRule("plant biodiversity", frozenset(), False),
    CategoryRule("domestic animals", frozenset(), False),
    CategoryRule("wildlife animals", frozenset(), False),
    CategoryRule("museum", frozenset(), False),
    CategoryRule("others", frozenset(), True),
)
ROWS = ("total biobanks",) + tuple(rule.name for rule in CATEGORY_POLICY)
METRICS = (
    "total_biobanks", "directory_biobanks", "federated_platform_biobanks",
    "negotiator_fully", "negotiator_partially", "negotiator_missing",
    "q_org_eric", "q_org_accredited", "q_collection_eric", "q_collection_accredited",
)
METRIC_COLUMNS = (
    ("Biobanks", "Total", "total_biobanks", "unique biobanks"),
    ("Biobanks", "Directory", "directory_biobanks", "unique biobanks"),
    ("Biobanks", "Federated Platform", "federated_platform_biobanks", "unique biobanks"),
    ("Negotiator: biobanks", "Fully represented", "negotiator_fully", "unique biobanks"),
    ("Negotiator: biobanks", "Partially represented", "negotiator_partially", "unique biobanks"),
    ("Negotiator: biobanks", "Missing", "negotiator_missing", "unique biobanks"),
    ("Q-labels: organizations", "ERIC", "q_org_eric", "unique biobanks"),
    ("Q-labels: organizations", "Accredited", "q_org_accredited", "unique biobanks"),
    ("Q-labels: collections", "ERIC", "q_collection_eric", "unique collections"),
    ("Q-labels: collections", "Accredited", "q_collection_accredited", "unique collections"),
)
EXCEL_INVALID_SHEET_CHARS = "[]:*?/\\"

@dataclass(frozen=True)
class BiobankClassification:
    """Classification result and frontier evidence for one biobank."""

    category: str
    votes: dict[str, int]
    frontier_ids: tuple[str, ...]
    mixed: bool
    tie: bool
    provisional: bool = False
    fallback_reason: str | None = None

@dataclass(frozen=True)
class SourceResult:
    """Availability and provenance of one report source."""
    available: bool
    reason: str

def classify_biobank_collections(collections):
    """Classify a biobank from its top-most supported collection frontier.

    Args:
        collections: Active collection mappings belonging to one biobank.

    Returns:
        Selected category, votes, frontier identifiers, mixed/tie and
        provisional-hierarchy indicators, and a reason whenever the result
        falls back to ``others``.
    """
    by_id = {item["id"]: item for item in collections}
    if not by_id:
        return BiobankClassification(
            "others", {}, (), False, False,
            fallback_reason="no active collections",
        )
    children = defaultdict(list)
    roots = set(by_id)
    for item in collections:
        parent = item.get("parent_collection", {}).get("id")
        if parent:
            if parent not in by_id:
                return BiobankClassification(
                    "others", {}, (), False, False,
                    provisional=True,
                    fallback_reason=(
                        f"parent collection {parent!r} is absent from biobank collection set"
                    ),
                )
            children[parent].append(item["id"]); roots.discard(item["id"])
    # Validate every component before pruning the supported voting frontier.
    states = {}
    def validate(cid):
        state = states.get(cid, 0)
        if state == 1:
            raise ValueError(f"collection hierarchy cycle detected at {cid!r}")
        if state == 2: return
        states[cid] = 1
        parent = by_id[cid].get("parent_collection", {}).get("id")
        if parent: validate(parent)
        states[cid] = 2
    try:
        for cid in sorted(by_id): validate(cid)
    except ValueError as error:
        return BiobankClassification(
            "others", {}, (), False, False,
            provisional=True,
            fallback_reason=str(error),
        )
    mapped = {typ: rule.name for rule in CATEGORY_POLICY for typ in rule.types}
    votes, frontier = Counter(), []
    def walk(cid, stack):
        if cid in stack:
            raise ValueError(f"collection hierarchy cycle detected at {cid!r}")
        item = by_id[cid]
        collection_types = Directory.getListOfEntityAttributeIds(item, "type")
        normalized_types = {str(value) for value in collection_types}
        categories = sorted({
            mapped[value] for value in normalized_types if value in mapped
        })
        if categories:
            votes.update(categories); frontier.append(cid); return
        for child in sorted(children[cid]): walk(child, stack | {cid})
    try:
        for root in sorted(roots): walk(root, set())
    except ValueError as error:
        return BiobankClassification(
            "others", dict(votes), tuple(sorted(frontier)), bool(votes),
            False, provisional=True, fallback_reason=str(error),
        )
    if not votes:
        return BiobankClassification(
            "others", {}, (), False, False,
            fallback_reason="no supported category votes",
        )
    order = [rule.name for rule in CATEGORY_POLICY]
    highest = max(votes.values()); winners = [name for name in order if votes[name] == highest]
    return BiobankClassification(winners[0], dict(votes), tuple(sorted(frontier)), len(votes) > 1, len(winners) > 1)

def build_report_model(directory):
    """Build Node/category metrics using only active Directory and Negotiator data.

    Args:
        directory: Initialized ``Directory`` with a loaded Negotiator resource
            dataset and active-scope entity access.

    Returns:
        Aggregate Node metrics, source availability states, resource problems,
        and rendering metadata shared by stdout and XLSX output.
    """
    coverage = directory.getNegotiatorCoverage()
    result = defaultdict(lambda: defaultdict(lambda: {metric: 0 for metric in METRICS}))
    problems = defaultdict(list)
    classifications = {}
    for biobank in directory.getBiobanks():
        bid = biobank["id"]; node = directory.getBiobankNN(bid) or "UNKNOWN"
        collections = [c for c in directory.getCollections() if c["biobank"]["id"] == bid]
        if not collections and not directory.getBiobankServices(bid): problems[node].append(bid)
        classification = classify_biobank_collections(collections)
        category = classification.category
        if classification.mixed:
            log.info("Mixed biobank %s: votes=%s, selected=%s, tie=%s, frontier=%s", bid, classification.votes, category, classification.tie, classification.frontier_ids)
        if classification.provisional:
            log.warning(
                "Provisional fallback to others for biobank %s: %s.",
                bid,
                classification.fallback_reason,
            )
        classifications[bid] = (node, category)
        for row in ("total biobanks", category):
            values = result[node][row]; values["total_biobanks"] += 1; values["directory_biobanks"] += 1
            status = coverage[bid].status
            if status in {"fully", "partially", "missing"}: values["negotiator_" + status] += 1
    for node in tuple(result):
        for row in ROWS:
            result[node][row]
    quality_sources = {}
    for table, entity_column, level_column, prefix, source_name in (
        (directory.getBiobankQualityInfo(), "biobank", "assess_level_bio", "q_org_", "Biobank quality table"),
        (directory.getCollectionQualityInfo(), "collection", "assess_level_col", "q_collection_", "Collection quality table"),
    ):
        required_columns = {entity_column, level_column}
        if not required_columns.issubset(table.columns):
            quality_sources[prefix] = SourceResult(
                False,
                f"{source_name} unavailable: missing required columns",
            )
            continue
        quality_sources[prefix] = SourceResult(True, f"{source_name} available")
        levels = defaultdict(set)
        for _, record in table.iterrows():
            entity = Directory.getEntityAttributeId(record.get(entity_column))
            level = Directory.getEntityAttributeId(record.get(level_column))
            if entity and level in {"eric", "accredited"}: levels[entity].add(level)
        for entity, levels_for_entity in levels.items():
            bid = entity if prefix == "q_org_" else (directory.getParentBiobank(entity) or {}).get("id")
            if bid not in classifications: continue
            node, category = classifications[bid]
            level = "accredited" if "accredited" in levels_for_entity else "eric"
            for row in ("total biobanks", category): result[node][row][prefix + level] += 1
    return {
        "nodes": result,
        "federated_platform": SourceResult(False, "Locator/Finder inventory API unavailable"),
        "quality_sources": quality_sources,
        "problems": problems,
        "metadata": {
            "Directory schema": directory.getSchema(),
            "Emergency DAG checks skipped": bool(
                getattr(directory, "skip_graph_dag_validation", False)
            ),
        },
    }

def _unsupported_rows() -> frozenset[str]:
    """Return report rows whose version-one values are unavailable."""
    return frozenset(rule.name for rule in CATEGORY_POLICY if not rule.supported)


def _rendered_cell_value(
    model: Mapping[str, Any],
    row_name: str,
    metric: str,
    value: Any,
    *,
    for_xlsx: bool,
) -> Any:
    """Return a display value while preserving unavailable-versus-zero semantics."""
    unavailable = (
        row_name in _unsupported_rows()
        or (
            metric == "federated_platform_biobanks"
            and not model.get(
                "federated_platform",
                SourceResult(False, "Federated Platform source unavailable"),
            ).available
        )
    )
    if metric.startswith("q_"):
        prefix = "q_org_" if metric.startswith("q_org_") else "q_collection_"
        quality_source = model.get("quality_sources", {}).get(prefix)
        unavailable = unavailable or (
            quality_source is not None and not quality_source.available
        )
    if unavailable:
        return None if for_xlsx else "N/A"
    return value if value is not None else (None if for_xlsx else "N/A")


def _node_table_values(model: Mapping[str, Any], node: str, *, for_xlsx: bool) -> list[list[Any]]:
    """Return fixed-order rendered values for one Node without recalculating metrics."""
    rows = model["nodes"][node]
    return [
        [
            row_name,
            *(
                _rendered_cell_value(
                    model,
                    row_name,
                    metric,
                    rows.get(row_name, {}).get(metric),
                    for_xlsx=for_xlsx,
                )
                for _, _, metric, _ in METRIC_COLUMNS
            ),
        ]
        for row_name in ROWS
    ]


def _format_stdout_table(model: Mapping[str, Any], node: str) -> list[str]:
    """Format one Node table with deterministic two-line grouped headers."""
    values = _node_table_values(model, node, for_xlsx=False)
    groups = ["Category", *(group for group, _, _, _ in METRIC_COLUMNS)]
    labels = ["", *(label for _, label, _, _ in METRIC_COLUMNS)]
    widths = [
        max(len(str(row[column])) for row in values + [groups, labels])
        for column in range(len(groups))
    ]

    def line(row: list[Any]) -> str:
        return " | ".join(str(value).ljust(widths[index]) for index, value in enumerate(row))

    separator = "-+-".join("-" * width for width in widths)
    return [line(groups), line(labels), separator, *(line(row) for row in values)]


def render_stdout(model: Mapping[str, Any], stream=sys.stdout) -> None:
    """Render deterministic, aligned Node statistics to a text stream.

    Args:
        model: Precomputed report model returned by :func:`build_report_model`.
        stream: Text stream that receives the report, normally standard output.

    Returns:
        ``None`` after writing all Node blocks in normalized alphabetical order.
    """
    for node in sorted(model["nodes"]):
        print(f"Node {node}", file=stream)
        for line in _format_stdout_table(model, node):
            print(line, file=stream)
        print(
            f"Biobanks without collections or services: {len(model['problems'].get(node, []))}",
            file=stream,
        )
        print(file=stream)


def _safe_sheet_name(node: str) -> str:
    """Return the deterministic Excel-compatible name for one normalized Node."""
    sanitized = "".join("_" if character in EXCEL_INVALID_SHEET_CHARS else character for character in node)
    sanitized = sanitized.strip().strip("'") or "UNKNOWN"
    return sanitized[:31].rstrip("'") or "UNKNOWN"


def _sheet_names(nodes) -> dict[str, str]:
    """Map report Nodes to unique safe worksheet names.

    Args:
        nodes: Iterable of normalized report Node values.

    Returns:
        Mapping from each Node to its Excel-safe worksheet name.

    Raises:
        ValueError: Two distinct Node names sanitize to the same worksheet name.
    """
    result = {}
    reverse = {}
    for node in sorted(nodes):
        sheet_name = _safe_sheet_name(node)
        collision_key = sheet_name.casefold()
        prior = reverse.get(collision_key)
        if prior is not None and prior != node:
            raise ValueError(
                f"Worksheet name collision: Nodes {prior!r} and {node!r} both map to {sheet_name!r}."
            )
        result[node] = sheet_name
        reverse[collision_key] = node
    return result


def _write_node_sheet(workbook, sheet, model: Mapping[str, Any], node: str) -> None:
    """Write one grouped Node report sheet from already aggregated values."""
    title_format = workbook.add_format({"bold": True, "align": "center", "valign": "vcenter", "border": 1, "bg_color": "#D9EAF7"})
    header_format = workbook.add_format({"bold": True, "align": "center", "text_wrap": True, "border": 1, "bg_color": "#EDF3F8"})
    row_format = workbook.add_format({"border": 1})
    number_format = workbook.add_format({"border": 1, "num_format": "0"})
    sheet.write(0, 0, "Category", title_format)
    group_start = 1
    metric_index = 0
    while metric_index < len(METRIC_COLUMNS):
        group = METRIC_COLUMNS[metric_index][0]
        group_end_index = metric_index
        while (
            group_end_index + 1 < len(METRIC_COLUMNS)
            and METRIC_COLUMNS[group_end_index + 1][0] == group
        ):
            group_end_index += 1
        group_end = group_start + (group_end_index - metric_index)
        sheet.merge_range(0, group_start, 0, group_end, group, title_format)
        metric_index = group_end_index + 1
        group_start = group_end + 1
    for column, (_, label, _, _) in enumerate(METRIC_COLUMNS, start=1):
        sheet.write(1, column, label, header_format)
    for row_index, values in enumerate(_node_table_values(model, node, for_xlsx=True), start=2):
        sheet.write(row_index, 0, values[0], row_format)
        for column, value in enumerate(values[1:], start=1):
            if value is None:
                sheet.write_blank(row_index, column, None, row_format)
            else:
                sheet.write_number(row_index, column, value, number_format)
    sheet.set_column(0, 0, 26)
    sheet.set_column(1, len(METRIC_COLUMNS), 17)
    sheet.freeze_panes(2, 1)

    problem_row = 2 + len(ROWS) + 2
    sheet.write(problem_row, 0, "Problems: biobanks without collections or services", title_format)
    sheet.write(problem_row + 1, 0, "Count", header_format)
    sheet.write_number(problem_row + 1, 1, len(model["problems"].get(node, [])), number_format)

    legend_row = problem_row + 4
    sheet.write(legend_row, 0, "Legend", title_format)
    legends = (
        ("Biobanks and Negotiator", "unique biobanks"),
        ("Q-labels: organizations", "unique biobanks; accredited takes precedence over ERIC"),
        ("Q-labels: collections", "unique collections grouped by parent-biobank category"),
        ("Blank cells", "unavailable or unsupported, not zero"),
        ("Negotiator", "actual representatives only; displayed states exclude biobanks without active collections"),
        ("Unsupported categories", "currently fall into others"),
        ("Problems", "active biobanks without collections or services"),
    )
    for offset, (label, meaning) in enumerate(legends, start=1):
        sheet.write(legend_row + offset, 0, label, header_format)
        sheet.write(legend_row + offset, 1, meaning)

    metadata_row = legend_row + len(legends) + 3
    metadata = {
        "Policy version": POLICY_VERSION,
        "Federated Platform source": model.get(
            "federated_platform",
            SourceResult(False, "Federated Platform source unavailable"),
        ).reason,
        **model.get("metadata", {}),
    }
    for offset, (label, value) in enumerate(metadata.items()):
        sheet.write(metadata_row + offset, 0, label, header_format)
        sheet.write(metadata_row + offset, 1, value)


def write_xlsx_report(model: Mapping[str, Any], path) -> None:
    """Atomically write grouped per-Node statistics sheets.

    Args:
        model: Precomputed report model returned by :func:`build_report_model`.
        path: Destination XLSX path. Existing output is replaced only after a
            complete workbook is successfully written.

    Returns:
        ``None`` after atomically publishing the workbook.

    Raises:
        ValueError: A Node cannot be mapped to a unique Excel worksheet name.
        OSError: The destination directory or final atomic replacement fails.
    """
    destination = Path(path)
    sheet_names = _sheet_names(model["nodes"])
    temporary_file = None
    try:
        descriptor, temporary_file = tempfile.mkstemp(
            prefix=f".{destination.stem}.", suffix=".xlsx", dir=destination.parent or Path(".")
        )
        os.close(descriptor)
        with pd.ExcelWriter(
            temporary_file,
            engine="xlsxwriter",
            engine_kwargs={"options": {"strings_to_urls": False}},
        ) as writer:
            for node in sorted(model["nodes"]):
                sheet = writer.book.add_worksheet(sheet_names[node])
                writer.sheets[sheet_names[node]] = sheet
                _write_node_sheet(writer.book, sheet, model, node)
        os.replace(temporary_file, destination)
        temporary_file = None
    finally:
        if temporary_file is not None:
            try:
                os.unlink(temporary_file)
            except FileNotFoundError:
                pass


def build_argument_parser():
    """Build the import-safe command-line parser for this exporter.

    Returns:
        Parser with standard Directory, XLSX, logging, and cache arguments plus
        explicit Negotiator registration-source options and a deprecated
        positional alias for the representatives workbook.
    """
    parser = build_parser(description="Export per-Node biobank statistics.")
    add_logging_arguments(parser)
    add_directory_auth_arguments(parser)
    add_xlsx_output_argument(parser)
    add_no_stdout_argument(parser)
    add_directory_schema_argument(parser, default="ERIC")
    add_purge_cache_arguments(parser, ["directory"])
    parser.add_argument(
        "input_xlsx",
        nargs="?",
        help=(
            "deprecated positional alias for --negotiator-representatives-xlsx"
        ),
    )
    source_group = parser.add_argument_group(
        "Negotiator registration source (choose exactly one)"
    )
    source_group.add_argument(
        "--negotiator-representatives-xlsx",
        metavar="FILE",
        help="current Negotiator representatives XLSX",
    )
    source_group.add_argument(
        "--negotiator-orphans-xlsx",
        metavar="FILE",
        help=(
            "XLSX produced by exporter-negotiator-orphans.py; reads the "
            "negotiator_collection_stats worksheet"
        ),
    )
    source_group.add_argument(
        "--negotiator-api",
        action="store_true",
        help="future Negotiator API source (not implemented)",
    )
    return parser


def _select_negotiator_source(args, parser):
    """Validate and return the single configured Negotiator source.

    Args:
        args: Parsed command-line namespace.
        parser: Argument parser used to report actionable usage errors.

    Returns:
        A ``(source_kind, path, legacy_alias)`` tuple. ``path`` is ``None``
        only for the reserved API source, which currently raises a parser error.
    """
    sources = []
    if args.input_xlsx:
        sources.append(("representatives", args.input_xlsx, True))
    if args.negotiator_representatives_xlsx:
        sources.append(("representatives", args.negotiator_representatives_xlsx, False))
    if args.negotiator_orphans_xlsx:
        sources.append(("orphans", args.negotiator_orphans_xlsx, False))
    if args.negotiator_api:
        sources.append(("api", None, False))
    if len(sources) != 1:
        parser.error("select exactly one Negotiator registration source")
    source_kind, path, legacy_alias = sources[0]
    if source_kind == "api":
        parser.error("Negotiator API registration source is not implemented yet")
    return source_kind, path, legacy_alias

def main(argv=None, directory_factory=Directory):
    """Run the Node statistics exporter.

    Args:
        argv: Optional command-line argument sequence; ``None`` reads process arguments.
        directory_factory: Callable constructing the Directory implementation.

    Returns:
        ``None`` after successful report rendering.
    """
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    source_kind, source_path, legacy_alias = _select_negotiator_source(args, parser)
    configure_logging(args)
    if legacy_alias:
        log.warning(
            "The positional Negotiator workbook is deprecated; use "
            "--negotiator-representatives-xlsx instead."
        )
    unsupported = ", ".join(rule.name for rule in CATEGORY_POLICY if not rule.supported)
    log.warning("Unsupported biobank categories currently fall into others: %s", unsupported)
    directory = directory_factory(**build_directory_kwargs(args))
    if source_kind == "representatives":
        directory.loadNegotiatorRepresentatives(source_path)
    else:
        directory.loadNegotiatorOrphansReport(source_path)
    model = build_report_model(directory)
    for node in sorted(model["problems"]):
        problem_ids = sorted(model["problems"][node])
        if problem_ids:
            log.warning(
                "Node %s has %d active biobank(s) without collections or services.",
                node,
                len(problem_ids),
            )
    if args.verbose or args.debug:
        for node in sorted(model["problems"]):
            problem_ids = sorted(model["problems"][node])
            if problem_ids:
                log.info(
                    "Biobanks without collections or services for Node %s: %s",
                    node,
                    ", ".join(problem_ids),
                )
    if not args.nostdout: render_stdout(model)
    if args.outputXLSX:
        write_xlsx_report(model, args.outputXLSX[0])

if __name__ == "__main__": main()
