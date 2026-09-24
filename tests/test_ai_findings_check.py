"""Test ai findings check behavior."""

import logging
from pathlib import Path

from ai_cache import AICacheIssue, AICacheLoadResult
from checks.AIFindings import AIFindings


class AIFindingsDirectoryStub:
    """Expose only col1 and bb1 as visible cached-finding targets, routed to CZ and NL.
    """
    def getSchema(self):
        """Return schema string selected for the fake Directory session.

        Returns:
            The schema string selected for the fake Directory session.
        """
        return "ERIC"

    def getCollectionById(self, collection_id):
        """Return synthetic collection record selected by the requested identifier, or `None` when absent.

        Args:
            collection_id: Collection identifier whose fixture record this stub returns or omits.

        Returns:
            The synthetic collection record selected by the requested identifier, or `None` when absent.
        """
        return {"id": collection_id} if collection_id == "col1" else None

    def getBiobankById(self, biobank_id):
        """Return synthetic biobank record selected by the requested identifier, or `None` when absent.

        Args:
            biobank_id: Biobank identifier whose fixture record this stub returns or omits.

        Returns:
            The synthetic biobank record selected by the requested identifier, or `None` when absent.
        """
        return {"id": biobank_id} if biobank_id == "bb1" else None

    def getCollectionNN(self, collection_id):
        """Return fixture national-node code for the requested collection.

        Args:
            collection_id: Collection identifier whose fixture national-node code this stub returns.

        Returns:
            The fixture national-node code for the requested collection.
        """
        return "CZ"

    def getBiobankNN(self, biobank_id):
        """Return fixture national-node code for the requested biobank.

        Args:
            biobank_id: Biobank identifier whose fixture national-node code this stub returns.

        Returns:
            The fixture national-node code for the requested biobank.
        """
        return "NL"


def test_ai_findings_plugin_emits_only_findings_for_entities_in_scope(monkeypatch):
    """Verify ai findings plugin emits only findings for entities in scope.

    Args:
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. Verifies ai findings plugin emits only findings for entities in scope.
    """
    monkeypatch.setattr(
        "checks.AIFindings.load_ai_findings_for_directory",
        lambda directory: AICacheLoadResult(
            findings=[
                {
                    "rule": "NarrativeReuseBarrier",
                    "entity_id": "col1",
                    "entity_type": "COLLECTION",
                    "severity": "WARNING",
                    "message": "Narrative describes a missing reuse restriction.",
                    "action": "Review the narrative.",
                },
                {
                    "rule": "NarrativeReuseBarrier",
                    "entity_id": "missing_collection",
                    "entity_type": "COLLECTION",
                    "severity": "WARNING",
                    "message": "Should be skipped",
                    "action": "Skip",
                },
            ],
            issues=[],
        ),
    )

    warnings = AIFindings().check(AIFindingsDirectoryStub(), args=None)

    assert [(warning.directoryEntityID, warning.dataCheckID) for warning in warnings] == [
        ("col1", "AI:Curated"),
    ]
    assert warnings[0].message.startswith("[NarrativeReuseBarrier] ")


def test_ai_findings_plugin_supports_biobank_findings(monkeypatch):
    """Verify ai findings plugin supports biobank findings.

    Args:
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. Verifies ai findings plugin supports biobank findings.
    """
    monkeypatch.setattr(
        "checks.AIFindings.load_ai_findings_for_directory",
        lambda directory: AICacheLoadResult(
            findings=[
                {
                    "rule": "NarrativeBiobankProfileGap",
                    "entity_id": "bb1",
                    "entity_type": "BIOBANK",
                    "severity": "INFO",
                    "message": "Biobank narrative and structured profile diverge.",
                    "action": "Review the biobank metadata.",
                }
            ],
            issues=[],
        ),
    )

    warnings = AIFindings().check(AIFindingsDirectoryStub(), args=None)

    assert len(warnings) == 1
    assert warnings[0].directoryEntityID == "bb1"
    assert warnings[0].dataCheckID == "AI:Curated"
    assert warnings[0].NN == "NL"


def test_ai_findings_plugin_logs_script_warning_for_stale_cache(monkeypatch, caplog):
    """Verify ai findings plugin logs script warning for stale cache.

    Args:
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.
        caplog: Pytest log-capture fixture used to inspect emitted log records.

    Returns:
        None. Verifies ai findings plugin logs script warning for stale cache.
    """
    monkeypatch.setattr(
        "checks.AIFindings.load_ai_findings_for_directory",
        lambda directory: AICacheLoadResult(
            findings=[],
            issues=[
                AICacheIssue(
                    path=Path("ai-check-cache/ERIC/reuse-barriers.json"),
                    rule="NarrativeReuseBarrier",
                    withdrawn_scope="active-only",
                    reason="changed-entities",
                    entity_ids=("col1", "col2"),
                )
            ],
        ),
    )

    with caplog.at_level(logging.WARNING):
        warnings = AIFindings().check(AIFindingsDirectoryStub(), args=None)

    assert warnings == []
    assert "Changed entities: col1, col2" in caplog.text
    assert "live AI-review workflow" in caplog.text
