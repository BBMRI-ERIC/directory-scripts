from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


GENERATOR_PATH = (
    Path(__file__).resolve().parents[2]
    / "BBMRI-ERIC-Directory-Data-Manager-Manual"
    / "scripts"
    / "generate_checks_docs.py"
)
CHECKS_DIR = Path(__file__).resolve().parents[1] / "checks"


@pytest.mark.skipif(not GENERATOR_PATH.exists(), reason="manual generator not available")
def test_check_docs_metadata_matches_all_plugins():
    spec = spec_from_file_location("generate_checks_docs", GENERATOR_PATH)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    cache = module.build_cache(CHECKS_DIR)
    assert cache.get("doc_mismatches", []) == []

    for plugin_name, plugin in cache["plugins"].items():
        assert plugin["doc_mismatches"] == [], plugin_name
        for check in plugin["checks"]:
            doc = check.get("doc", {})
            assert doc, check["check_id"]
            assert doc["severity"] == check["level"]
            assert doc["entity"] == check["entity"]
            assert isinstance(doc["fields"], list)

    documented_checks = {
        check["check_id"]: check.get("doc", {})
        for plugin in cache["plugins"].values()
        for check in plugin["checks"]
    }
    assert documented_checks[
        "MAC:MemberNonMember"
    ]["severity"] == "WARNING"
    assert documented_checks[
        "MAC:MemberDupOtherArea"
    ]["entity"] == "BIOBANK"
    assert documented_checks["BBF:JuridicalMissing"][
        "fields"
    ] == ["juridical_person"]
