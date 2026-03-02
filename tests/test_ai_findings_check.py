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
        "checks.AIFindings.load_ai_findings",
        lambda schema: [
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
    )

    warnings = AIFindings().check(AIFindingsDirectoryStub(), args=None)

    assert [(warning.directoryEntityID, warning.dataCheckID) for warning in warnings] == [
        ("col1", "AI:StudyText"),
        ("col1", "AI:AgeText"),
    ]
