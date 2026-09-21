#!/usr/bin/env python3
"""Export per-National-Node biobank statistics from Directory evidence."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import logging

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
METRICS = ("total_biobanks", "directory_biobanks", "federated_platform_biobanks",
           "negotiator_fully", "negotiator_partially", "negotiator_missing",
           "q_org_eric", "q_org_accredited", "q_collection_eric", "q_collection_accredited")

@dataclass(frozen=True)
class BiobankClassification:
    category: str
    votes: dict[str, int]
    frontier_ids: tuple[str, ...]
    mixed: bool
    tie: bool
    provisional: bool = False

@dataclass(frozen=True)
class SourceResult:
    """Availability and provenance of one report source."""
    available: bool
    reason: str

def _ids(value):
    if isinstance(value, dict): value = value.get("id")
    if isinstance(value, list): return {str(item.get("id", item)) for item in value}
    return {str(value)} if value else set()

def classify_biobank_collections(collections):
    """Classify a biobank from its top-most supported collection frontier."""
    by_id = {item["id"]: item for item in collections}
    children = defaultdict(list)
    roots = set(by_id)
    for item in collections:
        parent = item.get("parent_collection", {}).get("id")
        if parent:
            if parent not in by_id: return BiobankClassification("others", {}, (), False, False, True)
            children[parent].append(item["id"]); roots.discard(item["id"])
    mapped = {typ: rule.name for rule in CATEGORY_POLICY for typ in rule.types}
    votes, frontier = Counter(), []
    def walk(cid, stack):
        if cid in stack: raise ValueError("cycle")
        item = by_id[cid]; categories = sorted({mapped[t] for t in _ids(item.get("type")) if t in mapped})
        if categories:
            votes.update(categories); frontier.append(cid); return
        for child in sorted(children[cid]): walk(child, stack | {cid})
    try:
        for root in sorted(roots): walk(root, set())
    except ValueError:
        return BiobankClassification("others", dict(votes), tuple(sorted(frontier)), bool(votes), False, True)
    if not votes: return BiobankClassification("others", {}, (), False, False)
    order = [rule.name for rule in CATEGORY_POLICY]
    highest = max(votes.values()); winners = [name for name in order if votes[name] == highest]
    return BiobankClassification(winners[0], dict(votes), tuple(sorted(frontier)), len(votes) > 1, len(winners) > 1)

def build_report_model(directory):
    """Build Node/category metrics using only active Directory and loaded Negotiator data."""
    coverage = directory.getNegotiatorCoverage()
    result = defaultdict(lambda: defaultdict(lambda: {metric: 0 for metric in METRICS}))
    problems = defaultdict(list)
    classifications = {}
    for biobank in directory.getBiobanks():
        bid = biobank["id"]; node = directory.getBiobankNN(bid) or "UNKNOWN"
        collections = [c for c in directory.getCollections() if c["biobank"]["id"] == bid]
        if not collections and not directory.getBiobankServices(bid): problems[node].append(bid)
        category = classify_biobank_collections(collections).category
        classifications[bid] = (node, category)
        for row in ("total biobanks", category):
            values = result[node][row]; values["total_biobanks"] += 1; values["directory_biobanks"] += 1
            status = coverage[bid].status
            if status in {"fully", "partially", "missing"}: values["negotiator_" + status] += 1
    for table, entity_column, level_column, prefix in (
        (directory.getBiobankQualityInfo(), "biobank", "assess_level_bio", "q_org_"),
        (directory.getCollectionQualityInfo(), "collection", "assess_level_col", "q_collection_"),
    ):
        if not {entity_column, level_column}.issubset(table.columns):
            continue
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
    return {"nodes": result, "federated_platform": SourceResult(False, "Locator/Finder inventory API unavailable"), "problems": problems}

def main(argv=None, directory_factory=Directory):
    parser = build_parser(description="Export per-Node biobank statistics.")
    add_logging_arguments(parser); add_directory_auth_arguments(parser); add_xlsx_output_argument(parser)
    add_no_stdout_argument(parser); add_directory_schema_argument(parser, default="ERIC"); add_purge_cache_arguments(parser, ["directory"])
    parser.add_argument("input_xlsx", help="Negotiator representatives XLSX")
    args = parser.parse_args(argv); configure_logging(args)
    directory = directory_factory(**build_directory_kwargs(args)); directory.loadNegotiatorRepresentatives(args.input_xlsx)
    model = build_report_model(directory)
    if not args.nostdout:
        for node in sorted(model["nodes"]):
            print("Node", node, pd.DataFrame(model["nodes"][node]).T.to_string())
            print("Biobanks without collections or services:", len(model["problems"][node]))
    if args.outputXLSX:
        with pd.ExcelWriter(args.outputXLSX[0], engine="xlsxwriter") as writer:
            for node in sorted(model["nodes"]):
                pd.DataFrame(model["nodes"][node]).T.reindex(ROWS).to_excel(writer, sheet_name=node[:31])

if __name__ == "__main__": main()
