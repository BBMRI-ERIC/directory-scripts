"""Tests for the Node biobank statistics exporter policy core."""
import importlib.util
from pathlib import Path
import sys

def _module():
    path = Path(__file__).parents[1] / "exporter-nn-biobank-stats.py"
    spec = importlib.util.spec_from_file_location("nn_stats", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

def test_policy_has_only_initial_supported_mappings():
    module = _module()
    assert module.POLICY_VERSION
    assert {rule.name for rule in module.CATEGORY_POLICY if rule.types} == {"hospital-integrated", "population-based"}

def test_frontier_prunes_mapped_parent_and_tie_uses_row_priority():
    module = _module()
    result = module.classify_biobank_collections([
        {"id": "hospital", "type": {"id": "HOSPITAL"}},
        {"id": "population", "type": {"id": "POPULATION_BASED"}},
        {"id": "child", "parent_collection": {"id": "hospital"}, "type": {"id": "POPULATION_BASED"}},
    ])
    assert result.category == "hospital-integrated"
    assert result.votes == {"hospital-integrated": 1, "population-based": 1}
    assert result.tie and result.mixed
