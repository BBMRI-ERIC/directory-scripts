"""Tests for the Node biobank statistics exporter policy core."""
import importlib.util
from pathlib import Path
import sys
import io

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


def test_report_model_keeps_federated_platform_unavailable():
    module = _module()

    class Directory:
        def getNegotiatorCoverage(self):
            return {"bb": type("Coverage", (), {"status": "fully"})()}
        def getBiobanks(self): return [{"id": "bb"}]
        def getBiobankNN(self, _): return "CZ"
        def getCollections(self): return [{"id": "c", "biobank": {"id": "bb"}, "type": {"id": "HOSPITAL"}}]
        def getBiobankServices(self, _): return []
        def getBiobankQualityInfo(self): return __import__("pandas").DataFrame()
        def getCollectionQualityInfo(self): return __import__("pandas").DataFrame()

    model = module.build_report_model(Directory())
    assert model["federated_platform"].available is False
    assert model["nodes"]["CZ"]["hospital-integrated"]["negotiator_fully"] == 1


def test_stdout_marks_unavailable_federated_platform():
    module = _module()
    model = {"nodes": {"EXT": {"total biobanks": {metric: 0 for metric in module.METRICS}}}, "problems": {"EXT": ["bb"]}}
    buffer = io.StringIO()
    module.render_stdout(model, buffer)
    assert "Node EXT" in buffer.getvalue()
    assert "N/A" in buffer.getvalue()
