"""Regression coverage for Negotiator-orphans summary delegation."""

from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

from openpyxl import load_workbook
import pandas as pd

import directory as directory_module


def test_orphan_summary_uses_shared_coverage_and_omits_no_collections(
    tmp_path,
    monkeypatch,
):
    """The XLSX summary must use Directory coverage instead of re-deriving it."""
    script_path = Path(__file__).parents[1] / "exporter-negotiator-orphans.py"
    input_xlsx = tmp_path / "representatives.xlsx"
    output_xlsx = tmp_path / "orphans.xlsx"
    input_xlsx.touch()

    class FakeDirectory:
        biobanks = [
            {"id": "bbmri-eric:ID:CZ_full", "name": "Full"},
            {"id": "bbmri-eric:ID:CZ_partial", "name": "Partial"},
            {"id": "bbmri-eric:ID:CZ_missing", "name": "Missing"},
            {"id": "bbmri-eric:ID:CZ_empty", "name": "Empty"},
        ]
        collections = [
            {"id": "full", "biobank": {"id": "bbmri-eric:ID:CZ_full"}},
            {"id": "partial-one", "biobank": {"id": "bbmri-eric:ID:CZ_partial"}},
            {"id": "partial-two", "biobank": {"id": "bbmri-eric:ID:CZ_partial"}},
            {"id": "missing", "biobank": {"id": "bbmri-eric:ID:CZ_missing"}},
        ]
        coverage = {
            "bbmri-eric:ID:CZ_full": SimpleNamespace(status="fully"),
            "bbmri-eric:ID:CZ_partial": SimpleNamespace(status="partially"),
            "bbmri-eric:ID:CZ_missing": SimpleNamespace(status="missing"),
            "bbmri-eric:ID:CZ_empty": SimpleNamespace(status="no_collections"),
        }

        def __init__(self, **_kwargs):
            pass

        @staticmethod
        def getEntityAttributeId(value):
            return value.get("id") if isinstance(value, dict) else value

        def getBiobanksCount(self):
            return len(self.biobanks)

        def getCollectionsCount(self):
            return len(self.collections)

        def getCollectionQualityInfo(self, **_kwargs):
            return pd.DataFrame(columns=["collection", "assess_level_col"])

        def getBiobankQualityInfo(self, **_kwargs):
            return pd.DataFrame(columns=["biobank", "assess_level_bio"])

        def loadNegotiatorRepresentatives(self, _path):
            pass

        def getNegotiatorResources(self):
            # Empty direct assignments deliberately disagree with coverage.
            return {
                collection["id"]: SimpleNamespace(
                    network_name="",
                    biobank_name="",
                    resource_name="",
                    representatives=frozenset(),
                )
                for collection in self.collections
            }

        def getNegotiatorCoverage(self):
            return self.coverage

        def getCollections(self):
            return list(self.collections)

        def getBiobanks(self):
            return list(self.biobanks)

        def isCollectionWithdrawn(self, _collection_id):
            return False

        def isBiobankWithdrawn(self, _biobank_id):
            return False

        def getCollectionCountry(self, _collection_id):
            return "CZ"

        def getBiobankCountry(self, _biobank_id):
            return "CZ"

        def getBiobankById(self, biobank_id):
            return next(
                biobank for biobank in self.biobanks if biobank["id"] == biobank_id
            )

    monkeypatch.setattr(directory_module, "Directory", FakeDirectory)
    monkeypatch.setattr(
        sys,
        "argv",
        [str(script_path), str(input_xlsx), "-X", str(output_xlsx), "-N"],
    )

    runpy.run_path(str(script_path), run_name="__main__")

    sheet = load_workbook(output_xlsx, data_only=True)["nn_summary"]
    headers = [cell.value for cell in sheet[2]]
    values_by_node = {
        row[0]: dict(zip(headers, row))
        for row in sheet.iter_rows(min_row=3, values_only=True)
    }
    summary = values_by_node["CZ"]
    assert summary["Number of biobanks completely represented in the Negotiator"] == 1
    assert summary["Number of biobanks partially represented in the Negotiator"] == 1
    assert summary["Number of biobanks not represented in the Negotiator at all"] == 1
    assert summary["Number of biobanks without collections"] == 1
