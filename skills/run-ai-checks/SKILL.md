---
name: run-ai-checks
description: "Use when the user asks to run or refresh true AI-reviewed checks on live Directory data. This skill performs a strongest-model review on current data, keeps regex/heuristic checks out of the AI cache, updates `ai-check-cache/` only for genuinely AI-only findings, and validates the refreshed cache before commit."
---

# Run AI Checks

Use this skill when the user asks to run full AI checks, refresh `ai-check-cache/`, validate stale AI-cache warnings, or prepare AI-cache updates for review.

## Required workflow

1. Confirm model strength first:
   - if the current model is not the strongest available, tell the user and recommend switching before interpreting results, unless the user explicitly wants to continue
2. Refresh or inspect current live Directory data:
   - use `Directory(...)` directly from Codex or a small local Python helper
   - keep withdrawn scope explicit; active-only is the default unless the user explicitly asks otherwise
3. Review current deterministic coverage first:
   - inspect `checks/`, especially `text_consistency.py` and the existing deterministic plugins
   - do not put regex-like findings into `ai-check-cache/`
4. Run the full AI review on the live data in Codex:
   - identify only findings that cannot be expressed robustly as deterministic checks
   - check current `ai-check-cache/` entries for overlap before adding anything new
5. Update `ai-check-cache/` entries only for the residual AI-only findings:
   - keep JSON stable and commit-friendly
   - include current `entity_checksum` and `source_checksum`
   - include enough message/action detail that non-experts can understand the issue
6. Re-run the normal QC path after updating the cache:
   - `python3 data-check.py -N`
   - inspect emitted `AI:Curated` warnings and confirm they match the intended refreshed findings

## Required checks

- Do not trust stale AI-cache findings. If `AIFindings` reports changed entity IDs, refresh the live AI review before using or editing those entries.
- Keep the AI cache focused on genuinely AI-only findings. If a pattern is deterministic, move it into a regular plugin instead.
- Do not commit private runtime caches or ad-hoc local outputs outside `ai-check-cache/`.

## Validation expectations

After updating the AI cache, validate at least:

- `python3 -m py_compile ai_cache.py checks/AIFindings.py <changed deterministic helpers/plugins/tests>`
- `pytest -q tests/test_ai_cache.py tests/test_ai_findings_check.py <changed deterministic test subsets>`
- `python3 data-check.py -N`
- `python3 ../BBMRI-ERIC-Directory-Data-Manager-Manual/scripts/generate_checks_docs.py` if documentation metadata changed

## Output format

Report in this order:

1. Live-data scope reviewed
2. AI-only findings added/updated/removed
3. Deterministic findings that should become or remain regular plugin checks instead
4. Validation status
5. Whether the cache is ready to commit
