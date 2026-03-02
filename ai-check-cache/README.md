# AI Check Cache

This folder stores shareable AI-curated findings that can be committed to Git.

Purpose:
- keep a reviewable repository of issues spotted by Codex or other models
- avoid coupling AI-assisted checks to private runtime caches such as `data-check-cache/`
- let teams without direct access to the same models still run the resulting checks

Layout:
- one subdirectory per Directory schema/staging area, for example `ERIC/`
- one or more JSON files per schema, one file per public AI rule

Generation and reuse:
- refresh the cache with `./run-ai-checks.py`
- regular `data-check.py` runs only read these JSON files; they do not call an AI model
- cache reuse is checksum-based: each file stores checksums for all source fields used by the rule and for every entity that was reviewed by that rule
- timestamps and `mg_*` runtime metadata are excluded from the checksum, so pure metadata churn does not invalidate the cache
- if live Directory data changes, the `AIFindings` plugin emits a script warning listing the changed entity IDs and skips stale findings until `./run-ai-checks.py` is rerun

JSON format:

```json
{
  "schema": "ERIC",
  "rule": "CovidText",
  "generator": "codex-ai-review-v2",
  "generated_on": "2026-03-02",
  "withdrawn_scope": "active-only",
  "checked_fields": [
    "COLLECTION.name",
    "COLLECTION.description",
    "COLLECTION.diagnosis_available"
  ],
  "checked_entities": [
    {
      "entity_id": "bbmri-eric:ID:XX_NODE:collection:123",
      "entity_type": "COLLECTION",
      "entity_checksum": "...",
      "source_checksum": "..."
    }
  ],
  "findings": [
    {
      "rule": "CovidText",
      "entity_id": "bbmri-eric:ID:XX_NODE:collection:123",
      "entity_type": "COLLECTION",
      "severity": "WARNING",
      "fields": [
        "COLLECTION.name",
        "COLLECTION.description",
        "COLLECTION.diagnosis_available"
      ],
      "entity_checksum": "...",
      "source_checksum": "...",
      "message": "Collection text suggests post-/long-COVID context (matched 'long COVID'), but diagnosis_available does not contain U09.9.",
      "action": "Review whether the collection really targets post-/long-COVID cases. If yes, add U09.9 or the relevant structured post-COVID diagnosis; otherwise reword the narrative."
    }
  ]
}
```

Rules:
- entries must describe concrete entity-level findings, not vague prompts
- entries should remain conservative enough that they can be reviewed and committed
- when a finding is superseded or disproved, rerun `./run-ai-checks.py` and review the diff before committing
- prefer deterministic checks whenever the rule can be expressed robustly without model-assisted review
