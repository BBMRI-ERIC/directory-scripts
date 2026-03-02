# AI Check Cache

This folder stores shareable AI-curated findings that can be committed to Git.

Purpose:
- keep a reviewable repository of issues spotted by Codex or other models
- avoid coupling AI-assisted checks to private runtime caches such as `data-check-cache/`
- let teams without direct access to the same models still run the resulting checks

Layout:
- one subdirectory per Directory schema/staging area, for example `ERIC/`
- one or more JSON files per schema

JSON format:

```json
{
  "schema": "ERIC",
  "generator": "codex-heuristic-v1",
  "generated_on": "2026-03-01",
  "findings": [
    {
      "rule": "StudyText",
      "entity_id": "bbmri-eric:ID:XX_NODE:collection:123",
      "entity_type": "COLLECTION",
      "severity": "WARNING",
      "fields": ["COLLECTION.name", "COLLECTION.description", "COLLECTION.type"],
      "message": "Collection text suggests a structured type that is missing.",
      "action": "Review the text and add the structured type if appropriate."
    }
  ]
}
```

Rules:
- regular `data-check.py` runs only read these files; they do not call an AI model
- entries should describe concrete entity-level findings, not vague prompts
- when a finding is superseded or disproved, delete or update the corresponding record
- prefer conservative `WARNING` findings unless the AI-reviewed issue is unambiguous
