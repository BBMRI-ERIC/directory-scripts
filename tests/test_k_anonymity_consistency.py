#!/usr/bin/python3

"""Regression tests for shared k-anonymity semantics across checks and tooling."""

from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd

from check_fix_helpers import build_fact_k_anonymity_drop_fixes
from k_anonymity import positive_below_k_mask


REPO_ROOT = Path(__file__).resolve().parents[1]


def _parse_module(module_path: Path) -> ast.AST:
    """Parse a repository module into an abstract syntax tree.

    Args:
        module_path: Python source file read as UTF-8, without executing its imports.

    Returns:
        The parsed AST used to inspect duplicated k-anonymity predicates.
    """
    return ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))


def _has_import_from(tree: ast.AST, module: str, name: str) -> bool:
    """Return whether an AST imports a named symbol from a module.

    Args:
        tree: Parsed abstract syntax tree inspected by the static-analysis helper.
        module: Dotted import-source name to match in an ImportFrom node.
        name: Unqualified Python symbol sought in the parsed source.

    Returns:
        True if any from-import names the requested module and symbol, regardless of alias.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            for imported_name in node.names:
                if imported_name.name == name:
                    return True
    return False


def _count_named_calls(tree: ast.AST, name: str) -> int:
    """Count calls to a named function in an abstract syntax tree.

    Args:
        tree: Parsed abstract syntax tree inspected by the static-analysis helper.
        name: Unqualified Python symbol sought in the parsed source.

    Returns:
        Number of direct calls using that simple name; attribute calls such as obj.name() are excluded.
    """
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name:
            count += 1
    return count


def test_fact_fix_proposal_matches_modifier_k_anonymity_semantics():
    """Verify fact fix proposal matches modifier k anonymity semantics.

    Returns:
        None. Verifies fact fix proposal matches modifier k anonymity semantics.
    """
    facts = [
        {"id": "row-none", "number_of_donors": None},
        {"id": "row-0", "number_of_donors": 0},
        {"id": "row-1", "number_of_donors": 1},
        {"id": "row-9", "number_of_donors": 9},
        {"id": "row-10", "number_of_donors": 10},
        {"id": "row-11", "number_of_donors": 11},
    ]
    k_limit = 10

    proposal = build_fact_k_anonymity_drop_fixes(
        {"id": "bbmri-eric:ID:EU_demo:collection:col1"},
        facts,
        k_limit=k_limit,
    )
    proposal_ids = proposal[0].proposed_value if proposal else []

    df = pd.DataFrame(facts)
    numeric_donors = pd.to_numeric(df["number_of_donors"], errors="coerce")
    modifier_ids = sorted(df.loc[positive_below_k_mask(numeric_donors, k_limit), "id"].astype(str))

    assert proposal_ids == modifier_ids
    assert "row-0" not in proposal_ids
    assert "row-10" not in proposal_ids
    assert proposal_ids == ["row-1", "row-9"]


def test_modifier_and_facttables_use_shared_k_anonymity_helpers():
    """Verify modifier and facttables use shared k anonymity helpers.

    Returns:
        None. Verifies modifier and facttables use shared k anonymity helpers.
    """
    modifier_tree = _parse_module(REPO_ROOT / "directory-tables-modifier.py")
    assert _has_import_from(modifier_tree, "k_anonymity", "positive_below_k_mask")
    assert _count_named_calls(modifier_tree, "positive_below_k_mask") >= 2

    facttables_tree = _parse_module(REPO_ROOT / "checks" / "FactTables.py")
    assert _has_import_from(facttables_tree, "k_anonymity", "donor_value_violates_k")
    assert _count_named_calls(facttables_tree, "donor_value_violates_k") >= 1
