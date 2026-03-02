import logging
from pathlib import Path

from ai_cache import AICacheIssue, AICacheLoadResult
from checks.AIFindings import AIFindings


class AIFindingsDirectoryStub:
    def getSchema(self):
        return "ERIC"

    def getCollectionById(self, collection_id):
        return {"id": collection_id} if collection_id == "col1" else None

    def getCollectionNN(self, collection_id):
        return "CZ"


def test_ai_findings_plugin_emits_only_findings_for_entities_in_scope(monkeypatch):
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


def test_ai_findings_plugin_logs_script_warning_for_stale_cache(monkeypatch, caplog):
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
