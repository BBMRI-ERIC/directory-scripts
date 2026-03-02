---
name: run-ai-checks
description: "Use when the user asks to run or refresh true AI-reviewed checks on live Directory data. This skill performs a strongest-model review on a fresh Directory snapshot, keeps regex/heuristic checks out of `ai-check-cache/`, reuses checksum-stable AI findings when source content is unchanged, refreshes changed entities, and validates the refreshed cache before commit."
---

# Run AI Checks

Use this skill when the user asks to run full AI checks, refresh `ai-check-cache/`, validate stale AI-cache warnings, or prepare AI-cache updates for review.

## Required workflow

1. Start from a fresh live Directory snapshot:
   - use `Directory(schema=..., purgeCaches=['directory'])` for the AI-review run
   - keep withdrawn scope explicit; active-only is the default unless the user explicitly asks otherwise
   - reminder: use the strongest available model in the current session when possible
2. Review current deterministic coverage first:
   - inspect `checks/`, especially `text_consistency.py` and the existing deterministic plugins
   - do not put regex-like findings into `ai-check-cache/`
3. Compute checksums for all reviewed entities before trusting the existing AI cache:
   - compute canonical checksums on the live entities first, before deciding what can be reused
   - checksums must be based only on relevant content fields
   - exclude volatile/runtime-only fields such as timestamps and `mg_*`
4. Compare the live checksum map with the existing AI cache:
   - if an entity is already in the AI cache and the checksum is unchanged, keep its existing AI findings intact
   - if an entity is already in the AI cache and the checksum changed, rerun all AI-only checks for that entity and replace its old findings
   - if an entity is not yet in the AI cache, run all AI-only checks for that entity
   - if new AI rules are introduced, run only those additional rules on unchanged entities
5. Preserve explicit “no finding” coverage:
   - keep checksum metadata for all reviewed entities, including entities that currently produce no AI findings
   - unchanged entities with no findings can be skipped on later runs
   - changed entities with no findings must be fully re-reviewed, then kept in the checked-entity list even if they still produce no findings
6. Run the full AI review on the live data in Codex:
   - identify only findings that cannot be expressed robustly as deterministic checks
   - check current `ai-check-cache/` entries for overlap before adding anything new
7. Update `ai-check-cache/` entries only for the residual AI-only findings:
   - keep JSON stable and commit-friendly
   - include current `entity_checksum` and `source_checksum`
   - keep `checked_entities` complete enough to represent both positive findings and reviewed-no-finding entities
   - include enough message/action detail that non-experts can understand the issue
8. Validate the refreshed AI cache on a clean `Directory(...)` load first:
   - confirm that `load_ai_findings_for_directory(...)` reports reusable findings and no stale-cache issues for the fresh live snapshot
   - do this before relying on the full QC pipeline, because earlier checks may mutate in-memory entity objects and can create false stale-cache warnings
9. Re-run the normal QC path after updating the cache:
   - run `python3 data-check.py -N -r`
   - do not purge the Directory cache for this validation run
   - inspect emitted `AI:Curated` warnings and confirm they match the intended refreshed findings and do not contain garbage

## Required checks

- Do not trust stale AI-cache findings. If `AIFindings` reports changed entity IDs, refresh the live AI review before using or editing those entries.
- Keep the AI cache focused on genuinely AI-only findings. If a pattern is deterministic, move it into a regular plugin instead.
- Do not commit private runtime caches or ad-hoc local outputs outside `ai-check-cache/`.
- When validating reuse, distinguish real source-data drift from false stale-cache warnings caused by in-memory mutation during a full QC run.

## Validation expectations

After updating the AI cache, validate at least:

- `python3 -m py_compile ai_cache.py checks/AIFindings.py <changed deterministic helpers/plugins/tests>`
- `pytest -q tests/test_ai_cache.py tests/test_ai_findings_check.py <changed deterministic test subsets>`
- a clean-snapshot cache-load check using `Directory(..., purgeCaches=['directory'])` plus `load_ai_findings_for_directory(...)`
- `python3 data-check.py -N -r` without purging the Directory cache
- `python3 ../BBMRI-ERIC-Directory-Data-Manager-Manual/scripts/generate_checks_docs.py` if documentation metadata changed

## Output format

Report in this order:

1. Live-data scope reviewed
2. AI-only findings added/updated/removed
3. Deterministic findings that should become or remain regular plugin checks instead
4. Cache reuse summary:
   - unchanged entities reused
   - changed entities re-reviewed
   - new entities reviewed
   - reviewed entities with no findings retained in checksum metadata
5. Validation status
6. Whether the cache is ready to commit
