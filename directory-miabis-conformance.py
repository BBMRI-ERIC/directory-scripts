#!/usr/bin/env python3
"""Compare Directory schema/reference vocabularies with pinned MIABIS sources."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import tempfile

from cli_common import add_directory_auth_arguments, add_logging_arguments, build_parser, configure_logging
from cli_interrupts import log_keyboard_interrupt
from directory import get_directory_metadata_snapshot
from miabis_conformance import compare_reference, render_comparison
from vocabulary_guidance import DEFAULT_GUIDANCE_PATH, load_guidance
from vocabulary_sources import MIABIS_REVISION, load_directory_history, load_miabis_reference


def build_cli():
    """Construct the standalone read-only metadata comparison parser.

    Returns:
        Argument parser following common logging/auth/schema option conventions.
    """
    parser = build_parser(description=__doc__)
    add_logging_arguments(parser)
    add_directory_auth_arguments(parser)
    parser.add_argument("--directory-url", default=os.getenv("DIRECTORYTARGET", "https://directory.bbmri-eric.eu"),
                        help="Directory base URL; model and vocabularies are checked independently of software")
    parser.add_argument("-P", "--schema", default="ERIC", help="schema whose metadata is inspected (no entity records)")
    parser.add_argument("--miabis-revision", default=MIABIS_REVISION, help="full immutable official MIABIS commit")
    parser.add_argument("--directory-revision", default="0aac60c44c68ff1733c3d10f3669ec9967951872", help="full immutable upstream Directory history endpoint")
    parser.add_argument("--history-start-revision", default="843af5c2af4ee681e700f2a149213199b40919df", help="ancestral baseline before network inheritance removal")
    parser.add_argument("--guidance", type=Path, default=DEFAULT_GUIDANCE_PATH, help="reviewed migration/comparison JSON")
    parser.add_argument("--cache-dir", type=Path,
                        default=Path(os.getenv("DIRECTORY_CACHE_ROOT", ".")) / "data-check-cache" / "vocabulary-sources",
                        help="immutable upstream source cache, separate from entity snapshots")
    parser.add_argument("--offline", action="store_true", help="forbid network activity; require all reference inputs cached")
    parser.add_argument("--refresh", action="store_true", help="refresh live Directory metadata, preserving cached fallback")
    for name in ("json", "markdown", "tex"):
        parser.add_argument("--output-" + name, type=Path, help=f"write {name} report (TeX is an optional fragment)")
    parser.add_argument("--overwrite", action="store_true", help="allow replacing existing report files")
    return parser


def publish_reports(outputs: dict[Path, str]) -> None:
    """Stage report text and restore prior outputs if final replacement fails.

    Args:
        outputs: Distinct local destinations mapped to fully rendered UTF-8 text.

    Returns:
        None. Publishes each prepared file without writing partial report contents.

    Raises:
        OSError: If staging/publication fails; earlier destinations are restored.
    """
    staged = {}
    previous = {}
    published = []
    try:
        for destination, text in outputs.items():
            previous[destination] = destination.read_bytes() if destination.exists() else None
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".miabis-", delete=False) as temporary:
                staged[destination] = Path(temporary.name)
                temporary.write(text.encode("utf-8"))
        for destination, source in staged.items():
            os.replace(source, destination)
            published.append(destination)
    except OSError:
        for destination in reversed(published):
            if previous[destination] is None:
                destination.unlink()
            else:
                destination.write_bytes(previous[destination])
        raise
    finally:
        for path in staged.values():
            path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    """Run the separate metadata-only comparison with safe output preflight.

    Args:
        argv: Explicit argument tokens for tests/embedding, or None for process CLI.

    Returns:
        0 for complete reviewed comparison, 1 for complete comparison needing review,
        2 for unavailable/invalid/incomplete inputs, or 3 for user interruption.
    """
    args = build_cli().parse_args(argv)
    configure_logging(args)
    try:
        destinations = {kind: getattr(args, "output_" + kind) for kind in ("json", "markdown", "tex")}
        paths = [path.resolve() for path in destinations.values() if path is not None]
        if len(paths) != len(set(paths)) or args.guidance.resolve() in paths:
            raise ValueError("Report outputs must be distinct and must not replace the guidance input")
        for path in paths:
            if path.exists() and not args.overwrite:
                raise ValueError(f"Report already exists: {path}; use --overwrite to replace it")
            if path.exists() and not path.is_file():
                raise ValueError(f"Report destination is not a file: {path}")
            if not path.parent.is_dir():
                raise ValueError(f"Report parent directory does not exist: {path.parent}")
        guidance = load_guidance(args.guidance)
        reference = load_miabis_reference(revision=args.miabis_revision, cache_dir=args.cache_dir, offline=args.offline)
        history = load_directory_history(
            repository="molgenis/molgenis-emx2", start_revision=args.history_start_revision,
            end_revision=args.directory_revision, paths=(
                "data/biobank-directory/molgenis.csv", "data/biobank-directory/stagingArea/molgenis.csv",
                "data/biobank-directory/ontologies/DataCategories.csv", "data/biobank-directory/ontologies/ServiceTypes.csv",
            ), cache_dir=args.cache_dir, offline=args.offline,
        )
        snapshot = get_directory_metadata_snapshot(
            directory_url=args.directory_url, schema=args.schema,
            ontology_tables=("DataCategories", "ServiceTypes"), refresh=args.refresh, offline=args.offline,
            username=args.username, password=args.password, token=args.token,
        )
        report = compare_reference(reference, snapshot, guidance, history)
        outputs = {path: render_comparison(report, format=kind) for kind, path in destinations.items() if path is not None}
        publish_reports(outputs)
        if not outputs:
            print(render_comparison(report, format="markdown"), end="")
        else:
            count = report["review_count"]
            print(f"Comparison complete: {report['complete']}; items needing review: {count}; exit status: {report['exit_status']}")
        return report["exit_status"]
    except KeyboardInterrupt:
        log_keyboard_interrupt("directory-miabis-conformance.py", action="metadata comparison")
        return 3
    except (ValueError, RuntimeError, OSError) as exc:
        logging.error("No complete conformance conclusion: %s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
