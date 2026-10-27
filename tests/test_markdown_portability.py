"""Keep tracked Markdown free of personal notes and machine-specific home paths."""

from pathlib import Path
import re
import subprocess


def test_tracked_markdown_uses_shared_names_and_portable_paths():
    """Scan published Markdown without touching private or generated local files.

    Returns:
        None. Documents contain neither person-specific scoring references nor
        absolute home paths that expose local account names or installations.
    """
    root = Path(__file__).resolve().parents[1]
    paths = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "*.md", "*.Rmd"], cwd=root
    ).decode().split("\0")
    forbidden = re.compile(
        r"\bjosephine\b|/(?:home|Users)/[^/\s`]+|/data/data/com\.termux/files/home",
        re.IGNORECASE,
    )
    findings = []
    for name in filter(None, paths):
        for number, line in enumerate((root / name).read_text(encoding="utf-8").splitlines(), 1):
            if forbidden.search(line):
                findings.append(f"{name}:{number}")
    assert not findings, "Personal references or home paths: " + ", ".join(findings)
