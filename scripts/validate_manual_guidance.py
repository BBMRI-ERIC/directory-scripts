#!/usr/bin/env python3
"""Check Manual section labels and reviewed guidance fingerprints across repositories."""

import argparse
from collections import Counter
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vocabulary_guidance import DEFAULT_GUIDANCE_PATH, content_hash, load_guidance


def validate_manual_references(guidance: dict, text: str) -> list[str]:
    """Check stable references without attempting to certify prose correctness.

    Args:
        guidance: Decoded guidance entries and their logical Manual section records.
        text: Combined root-level Manual TeX sources, including guidance annotations.

    Returns:
        Sorted unique diagnostics for missing/duplicate labels or annotations,
        undefined guidance IDs and changed entry fingerprints requiring prose review.
    """
    labels = Counter(re.findall(r"\\label\{([^{}]+)\}", text))
    annotations = {}
    diagnostics = []
    if "schema_version" in guidance:
        document_hashes = re.findall(r"%\s*directory-guidance-document:\s*sha256=([0-9a-f]{64})", text)
        if document_hashes != [content_hash(guidance)]:
            diagnostics.append("Manual version/source context review required: guidance document fingerprint changed or is missing")
    for entry_id, digest in re.findall(r"%\s*directory-guidance:\s*(\S+)\s+sha256=([0-9a-f]{64})", text):
        annotations.setdefault(entry_id, []).append(digest)
    entries = [entry for group in ("migrations", "miabis_bindings", "structural_changes") for entry in guidance[group]]
    expected = {entry["id"] for entry in entries}
    for unknown in annotations.keys() - expected:
        diagnostics.append(f"Manual references undefined guidance ID {unknown}")
    for entry in entries:
        observed = annotations.get(entry["id"], [])
        if len(observed) != 1:
            diagnostics.append(f"Manual needs exactly one annotation for {entry['id']}; found {len(observed)}")
        elif observed[0] != content_hash(entry):
            diagnostics.append(f"Manual prose review required: guidance {entry['id']} changed")
        for section_id in entry["manual_section_ids"]:
            label = guidance["manual_sections"][section_id]["label"]
            if labels[label] != 1:
                diagnostics.append(f"Manual section label {label} missing or duplicated ({labels[label]})")
    return sorted(set(diagnostics))


def main(argv: list[str] | None = None) -> int:
    """Validate explicit cross-repository annotations without writing either checkout.

    Args:
        argv: Explicit CLI tokens, or None to read the process command line.

    Returns:
        0 when references/fingerprints agree, 1 when prose review is required,
        or 2 when a required input cannot be read or validated.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guidance", type=Path, default=DEFAULT_GUIDANCE_PATH)
    parser.add_argument("--manual-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        paths = sorted(args.manual_root.glob("*.tex"))
        if not paths:
            raise ValueError("Manual root contains no TeX sources")
        text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        diagnostics = validate_manual_references(load_guidance(args.guidance), text)
        for diagnostic in diagnostics:
            print(diagnostic)
        if not diagnostics:
            print("Manual guidance references and fingerprints match; this is not a semantic review of the prose.")
        return 1 if diagnostics else 0
    except (OSError, ValueError) as exc:
        print(f"Cannot validate Manual guidance: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
