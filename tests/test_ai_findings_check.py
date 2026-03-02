import logging
from pathlib import Path

from ai_cache import AICacheIssue, AICacheLoadResult
from checks.AIFindings import AIFindings


class AIFindingsDirectoryStub:
    def getSchema(self):
        return "ERIC"

    def getBiobankById(self, biobank_id):
        return {"id": biobank_id} if biobank_id == "bb1" else None

    def getCollectionById(self, collection_id):
        return {"id": collection_id} if collection_id == "col1" else None

    def getBiobankNN(self, biobank_id):
        return "CZ"

    def getCollectionNN(self, collection_id):
        return "CZ"


def test_ai_findings_plugin_emits_only_findings_for_entities_in_scope(monkeypatch):
    monkeypatch.setattr(
        "checks.AIFindings.load_ai_findings_for_directory",
        lambda directory: AICacheLoadResult(
            findings=[
                {
                    "rule": "StudyText",
                    "entity_id": "col1",
                    "entity_type": "COLLECTION",
                    "severity": "WARNING",
                    "message": "Study text mismatch",
                    "action": "Review collection type",
                },
                {
                    "rule": "CovidText",
                    "entity_id": "missing_collection",
                    "entity_type": "COLLECTION",
                    "severity": "WARNING",
                    "message": "Should be skipped",
                    "action": "Skip",
                },
                {
                    "rule": "AgeText",
                    "entity_id": "col1",
                    "entity_type": "COLLECTION",
                    "severity": "WARNING",
                    "message": "Age text mismatch",
                    "action": "Review",
                },
            ],
            issues=[],
        ),
    )

    warnings = AIFindings().check(AIFindingsDirectoryStub(), args=None)

    assert [(warning.directoryEntityID, warning.dataCheckID) for warning in warnings] == [
        ("col1", "AI:StudyText"),
        ("col1", "AI:AgeText"),
    ]


def test_ai_findings_plugin_logs_script_warning_for_stale_cache(monkeypatch, caplog):
    monkeypatch.setattr(
        "checks.AIFindings.load_ai_findings_for_directory",
        lambda directory: AICacheLoadResult(
            findings=[],
            issues=[
                AICacheIssue(
                    path=Path("ai-check-cache/ERIC/study-text.json"),
                    rule="StudyText",
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
