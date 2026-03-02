# AI Check Cache

This folder stores shareable AI-reviewed findings that can be committed to Git.

Purpose:
- keep a reviewable repository of issues spotted by Codex or other strong models on live Directory data
- avoid coupling AI-assisted checks to private runtime caches such as `data-check-cache/`
- let teams without direct access to the same models still run the resulting cache-backed warnings

Important boundary:
- deterministic regex/heuristic checks do **not** belong here
- those checks must be implemented directly as regular plugins (for example `TextConsistency`)
- this cache is reserved for findings that genuinely require full AI-model review and cannot be expressed robustly as deterministic logic

Reuse rules:
- regular `data-check.py` runs only read these JSON files; they do not call an AI model
- cache reuse is checksum-based: each file stores checksums for all source fields used by the finding and for every reviewed entity covered by that cache file
- timestamps and `mg_*` runtime metadata are excluded from the checksum, so pure metadata churn does not invalidate the cache
- if live Directory data changes, the `AIFindings` plugin emits a script warning listing the changed entity IDs and skips stale findings until the live AI-review workflow refreshes the cache

How to refresh it:
- run the Codex skill `run-ai-checks`
- that skill reviews live Directory data with the strongest available model, updates `ai-check-cache/` only for genuinely AI-only findings, and then validates the refreshed `AI:Curated` warnings through the normal QC pipeline

JSON format:

```json
{
  "schema": "ERIC",
  "generator": "codex-live-review-v1",
  "generated_on": "2026-03-02",
  "withdrawn_scope": "active-only",
  "checked_fields": [
    "COLLECTION.name",
    "COLLECTION.description"
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
      "rule": "NarrativeReuseBarrier",
      "entity_id": "bbmri-eric:ID:XX_NODE:collection:123",
      "entity_type": "COLLECTION",
      "severity": "WARNING",
      "fields": [
        "COLLECTION.name",
        "COLLECTION.description"
      ],
      "entity_checksum": "...",
      "source_checksum": "...",
      "message": "The narrative says the collection is available only through a bespoke bilateral process that is not reflected in the structured metadata.",
      "action": "Review the narrative and the structured access metadata, and align them so reuse expectations are clear."
    }
  ]
}
```

Rules:
- entries must describe concrete entity-level findings, not vague prompts
- keep findings conservative enough that they can be reviewed and committed
- when a finding is superseded or disproved, update or delete the JSON record and keep the checksum metadata current
- if a finding can be expressed robustly as deterministic logic, move it into a regular plugin instead of keeping it here
