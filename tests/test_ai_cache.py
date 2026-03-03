import json
import copy
from pathlib import Path

import ai_cache
from ai_cache import load_ai_findings_for_directory


class DirectoryStub:
    def __init__(self, collections, *, include_withdrawn=False, only_withdrawn=False):
        self._collections = list(collections)
        self.include_withdrawn_entities = include_withdrawn or only_withdrawn
        self.only_withdrawn_entities = only_withdrawn
        self._ai_checksum_snapshot = {}

    def getSchema(self):
        return "ERIC"

    def getCollections(self):
        return list(self._collections)

    def getBiobanks(self):
        return []

    def prepare_ai_cache_checksum_state(self):
        if self._ai_checksum_snapshot:
            return
        self._ai_checksum_snapshot = {
            "COLLECTION": {
                collection["id"]: copy.deepcopy(collection)
                for collection in self._collections
            }
        }

    def get_ai_checksum_entity(self, entity_type, entity_id):
        if not self._ai_checksum_snapshot:
            self.prepare_ai_cache_checksum_state()
        return self._ai_checksum_snapshot.get(entity_type, {}).get(entity_id)


def build_collection(collection_id, **overrides):
    collection = {
        "id": collection_id,
        "name": "Collection",
        "description": "",
        "type": [],
        "materials": [],
        "diagnosis_available": [],
        "age_low": None,
        "age_high": None,
        "withdrawn": False,
    }
    collection.update(overrides)
    return collection


def write_payload(root, payload):
    schema_dir = root / "ERIC"
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "study-text.json").write_text(json.dumps(payload), encoding="utf-8")


def test_load_ai_findings_for_directory_filters_stale_entities(monkeypatch, tmp_path):
    original = build_collection("col1", description="Baseline follow-up visit", type=["SAMPLE"])
    changed = build_collection("col2", description="Original description", type=["SAMPLE"])
    fields = ["COLLECTION.name", "COLLECTION.description", "COLLECTION.type"]
    payload = {
        "schema": "ERIC",
        "rule": "StudyText",
        "generator": "test",
        "generated_on": "2026-03-02",
        "withdrawn_scope": "active-only",
        "checked_fields": fields,
        "checked_entities": [
            {
                "entity_id": "col1",
                "entity_type": "COLLECTION",
                "entity_checksum": ai_cache.compute_entity_checksum(original),
                "source_checksum": ai_cache.compute_source_checksum("COLLECTION", original, fields),
            },
            {
                "entity_id": "col2",
                "entity_type": "COLLECTION",
                "entity_checksum": ai_cache.compute_entity_checksum(changed),
                "source_checksum": ai_cache.compute_source_checksum("COLLECTION", changed, fields),
            },
        ],
        "findings": [
            {
                "rule": "StudyText",
                "entity_id": "col1",
                "entity_type": "COLLECTION",
                "severity": "WARNING",
                "message": "follow-up",
                "action": "review",
                "fields": fields,
                "entity_checksum": ai_cache.compute_entity_checksum(original),
                "source_checksum": ai_cache.compute_source_checksum("COLLECTION", original, fields),
            },
            {
                "rule": "StudyText",
                "entity_id": "col2",
                "entity_type": "COLLECTION",
                "severity": "WARNING",
                "message": "follow-up",
                "action": "review",
                "fields": fields,
                "entity_checksum": ai_cache.compute_entity_checksum(changed),
                "source_checksum": ai_cache.compute_source_checksum("COLLECTION", changed, fields),
            },
        ],
    }
    write_payload(tmp_path, payload)
    monkeypatch.setattr(ai_cache, "AI_CACHE_ROOT", tmp_path)

    directory = DirectoryStub(
        [
            original,
            build_collection("col2", description="Changed description", type=["SAMPLE"]),
            build_collection("col3", description="New collection", type=["SAMPLE"]),
        ]
    )
    result = load_ai_findings_for_directory(directory)

    assert [finding["entity_id"] for finding in result.findings] == ["col1"]
    assert {issue.reason for issue in result.issues} == {"changed-entities", "new-entities"}
    changed_issue = next(issue for issue in result.issues if issue.reason == "changed-entities")
    assert changed_issue.entity_ids == ("col2",)
    new_issue = next(issue for issue in result.issues if issue.reason == "new-entities")
    assert new_issue.entity_ids == ("col3",)


def test_load_ai_findings_for_directory_reports_scope_mismatch(monkeypatch, tmp_path):
    collection = build_collection("col1")
    fields = ["COLLECTION.name", "COLLECTION.description", "COLLECTION.type"]
    payload = {
        "schema": "ERIC",
        "rule": "StudyText",
        "generator": "test",
        "generated_on": "2026-03-02",
        "withdrawn_scope": "active-only",
        "checked_fields": fields,
        "checked_entities": [
            {
                "entity_id": "col1",
                "entity_type": "COLLECTION",
                "entity_checksum": ai_cache.compute_entity_checksum(collection),
                "source_checksum": ai_cache.compute_source_checksum("COLLECTION", collection, fields),
            }
        ],
        "findings": [],
    }
    write_payload(tmp_path, payload)
    monkeypatch.setattr(ai_cache, "AI_CACHE_ROOT", tmp_path)

    directory = DirectoryStub([collection], include_withdrawn=True)
    result = load_ai_findings_for_directory(directory)

    assert [issue.reason for issue in result.issues] == ["scope-mismatch"]


def test_load_ai_findings_for_directory_uses_pristine_checksum_snapshot(monkeypatch, tmp_path):
    collection = build_collection(
        "col1",
        description="Narrative access conditions",
        access_description="Structured access description",
    )
    fields = ["COLLECTION.name", "COLLECTION.description", "COLLECTION.access_description"]
    payload = {
        "schema": "ERIC",
        "rule": "NarrativeAccessMetadataGap",
        "generator": "test",
        "generated_on": "2026-03-03",
        "withdrawn_scope": "active-only",
        "checked_fields": fields,
        "checked_entities": [
            {
                "entity_id": "col1",
                "entity_type": "COLLECTION",
                "entity_checksum": ai_cache.compute_entity_checksum(collection),
                "source_checksum": ai_cache.compute_source_checksum("COLLECTION", collection, fields),
            }
        ],
        "findings": [
            {
                "rule": "NarrativeAccessMetadataGap",
                "entity_id": "col1",
                "entity_type": "COLLECTION",
                "severity": "WARNING",
                "message": "Narrative access conditions are only in free text.",
                "action": "Review access metadata.",
                "fields": fields,
            }
        ],
    }
    write_payload(tmp_path, payload)
    monkeypatch.setattr(ai_cache, "AI_CACHE_ROOT", tmp_path)

    directory = DirectoryStub([collection])
    directory.prepare_ai_cache_checksum_state()
    directory.getCollections()[0]["derived_runtime_flag"] = True
    directory.getCollections()[0]["access_description"] = "Mutated by earlier plugin"

    result = load_ai_findings_for_directory(directory)

    assert [finding["entity_id"] for finding in result.findings] == ["col1"]
    assert result.issues == []
