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
    """The XLSX summary must use Directory coverage instead of re-deriving it.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. The XLSX summary must use Directory coverage instead of re-deriving it.
    """
    script_path = Path(__file__).parents[1] / "exporter-negotiator-orphans.py"
    input_xlsx = tmp_path / "representatives.xlsx"
    output_xlsx = tmp_path / "orphans.xlsx"
    input_xlsx.touch()

    class FakeDirectory:
        """Serve Czech biobanks, direct Negotiator coverage, and empty quality tables without workbook I/O.
        """
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
            """Accept CLI construction without fetching or altering the class-level fixture records.

            Args:
                **_kwargs: Additional keyword arguments accepted to preserve the patched call signature.
            """
            pass

        @staticmethod
        def getEntityAttributeId(value):
            """Return canonical identifier extracted from the fixture attribute value.

            Args:
                value: Fixture attribute value whose identifier form this stub normalizes.

            Returns:
                The canonical identifier extracted from the fixture attribute value.
            """
            return value.get("id") if isinstance(value, dict) else value

        def getBiobanksCount(self):
            """Return number of synthetic biobank records visible in the selected scope.

            Returns:
                Number of biobank records exposed by this stub.
            """
            return len(self.biobanks)

        def getCollectionsCount(self):
            """Return number of synthetic collection records visible in the selected scope.

            Returns:
                Number of collection records exposed by this stub.
            """
            return len(self.collections)

        def getCollectionQualityInfo(self, **_kwargs):
            """Return fixture collection-quality DataFrame used by the exporter.

            Args:
                **_kwargs: Keyword options accepted while returning the empty quality-info fixture.

            Returns:
                The fixture collection-quality DataFrame used by the exporter.
            """
            return pd.DataFrame(columns=["collection", "assess_level_col"])

        def getBiobankQualityInfo(self, **_kwargs):
            """Return fixture biobank-quality DataFrame used by the exporter.

            Args:
                **_kwargs: Keyword options accepted while returning the empty quality-info fixture.

            Returns:
                The fixture biobank-quality DataFrame used by the exporter.
            """
            return pd.DataFrame(columns=["biobank", "assess_level_bio"])

        def loadNegotiatorRepresentatives(self, _path):
            """Record representative-XLSX loading on the Directory double.

            Args:
                _path: Raw representative workbook path, ignored because registrations are already in the stub.

            Returns:
                None. Record representative-XLSX loading on the Directory double.
            """
            pass

        def getNegotiatorResources(self):
            # Empty direct assignments deliberately disagree with coverage.
            """Return fixture Negotiator registration resources.

            Returns:
                Collection-ID-to-resource dictionary with empty labels and no representatives.
            """
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
            """Return fixture Negotiator coverage classification mapping.

            Returns:
                The fixture Negotiator coverage classification mapping.
            """
            return self.coverage

        def getCollections(self):
            """Return synthetic collection records available to the code under test.

            Returns:
                The synthetic collection records available to the code under test.
            """
            return list(self.collections)

        def getBiobanks(self):
            """Return synthetic biobank records available to the code under test.

            Returns:
                The synthetic biobank records available to the code under test.
            """
            return list(self.biobanks)

        def isCollectionWithdrawn(self, _collection_id):
            """Report the fixture marks the requested collection as withdrawn.

            Args:
                _collection_id: Collection identifier whose fixture withdrawal status this stub reports.

            Returns:
                Whether the fixture marks the requested collection as withdrawn.
            """
            return False

        def isBiobankWithdrawn(self, _biobank_id):
            """Report the fixture marks the requested biobank as withdrawn.

            Args:
                _biobank_id: Biobank identifier whose fixture withdrawal status this stub reports.

            Returns:
                Whether the fixture marks the requested biobank as withdrawn.
            """
            return False

        def getCollectionCountry(self, _collection_id):
            """Return fixture country code for the requested collection.

            Args:
                _collection_id: Collection identifier whose fixture country code this stub returns.

            Returns:
                The fixture country code for the requested collection.
            """
            return "CZ"

        def getBiobankCountry(self, _biobank_id):
            """Return fixture country code for the requested biobank.

            Args:
                _biobank_id: Biobank identifier whose fixture country code this stub returns.

            Returns:
                The fixture country code for the requested biobank.
            """
            return "CZ"

        def getBiobankById(self, biobank_id):
            """Return synthetic biobank record selected by the requested identifier, or `None` when absent.

            Args:
                biobank_id: Biobank identifier whose fixture record this stub returns or omits.

            Returns:
                The synthetic biobank record selected by the requested identifier, or `None` when absent.
            """
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
