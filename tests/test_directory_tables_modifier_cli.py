#!/usr/bin/python3

"""CLI regression tests for directory-tables-modifier validation paths."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "directory-tables-modifier.py"


def _run_modifier(*args: str) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(SCRIPT_PATH), *args]
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )


def _base_auth_args() -> list[str]:
    return [
        "--directory-target",
        "https://example.org",
        "--directory-username",
        "test-user",
        "--directory-password",
        "test-password",
    ]


def test_k_anonymity_rejected_for_non_collectionfacts_table() -> None:
    result = _run_modifier(
        *_base_auth_args(),
        "-s",
        "BBMRI-EU",
        "-T",
        "Collections",
        "-i",
        "nonexistent.tsv",
        "-k",
        "5",
    )
    assert result.returncode == 2
    assert "--k-donors/--k-samples can only be used with -T/--table CollectionFacts." in result.stderr


def test_k_anonymity_rejected_for_delete_action() -> None:
    result = _run_modifier(
        *_base_auth_args(),
        "-s",
        "BBMRI-EU",
        "-T",
        "CollectionFacts",
        "-x",
        "--delete-filter-only",
        "-R",
        "^fact:",
        "-k",
        "5",
    )
    assert result.returncode == 2
    assert "--k-donors/--k-samples are only supported for import (-i) and sync (-y) operations." in result.stderr


def test_k_anonymity_requires_positive_threshold() -> None:
    result = _run_modifier(
        *_base_auth_args(),
        "-s",
        "BBMRI-EU",
        "-T",
        "CollectionFacts",
        "-i",
        "nonexistent.tsv",
        "-K",
        "0",
    )
    assert result.returncode == 2
    assert "--k-samples must be a positive integer." in result.stderr


def test_k_anonymity_help_documents_positive_range_only() -> None:
    result = _run_modifier("-h")
    assert result.returncode == 0
    assert "number_of_donors is >0 and <k" in result.stdout
    assert "number_of_samples is >0 and <k" in result.stdout
