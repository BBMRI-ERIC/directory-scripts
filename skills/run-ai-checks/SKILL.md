---
name: run-ai-checks
description: "Use when the user asks to rerun, refresh, or validate the shareable AI checks. This skill regenerates `ai-check-cache/` from current Directory data, produces a human-reviewable AI findings report, and requires a strongest-model review of the refreshed results before committing AI-check changes."
---

# Run AI Checks

Use this skill when the user asks to rerun AI checks, refresh `ai-check-cache/`, validate stale AI-cache warnings, or prepare AI-check updates for review.

## Required workflow

1. Refresh the data source first:
   - default active content: `python3 run-ai-checks.py --purge-cache directory --report ai-checks-results-current.txt`
   - include withdrawn: add `-w/--include-withdrawn`
   - withdrawn only: add `--only-withdrawn`
2. Inspect the script summary counts and the generated `ai-checks-results-current.txt`.
3. Review the refreshed result set with the strongest available model in the current session.
4. Identify obvious false positives, false negatives, and deterministic overlaps before committing any cache changes.
5. Re-run `python3 data-check.py -N` (or a focused equivalent) after the cache refresh if the user wants to confirm the emitted `AI:*` warnings in the normal QC pipeline.

## Required checks

- If the current model is not the strongest available, tell the user and recommend switching before interpreting the refreshed AI findings, unless the user explicitly wants to continue.
- If `data-check.py` or `AIFindings` reports AI-cache staleness warnings, do not trust the old cache; rerun `run-ai-checks.py` first.
- Keep withdrawn scope explicit. The committed cache is normally generated for active content only unless the user explicitly asks otherwise.
- Do not commit private runtime caches or ad-hoc local outputs outside `ai-check-cache/`.

## Validation expectations

After rerunning the cache, validate at least:

- `python3 -m py_compile ai_cache.py ai_check_generation.py run-ai-checks.py checks/AIFindings.py <changed tests>`
- `pytest -q tests/test_ai_check_generation.py tests/test_ai_cache.py tests/test_ai_findings_check.py`
- the relevant broader test subset or full `pytest -q` when AI-check logic changed materially

## Output format

Report in this order:

1. Refresh command used
2. Counts per AI rule
3. Notable false positives/false negatives found in the refreshed run
4. Whether the cache is ready to commit
5. Any follow-up deterministic checks or refinements that should replace AI coverage later
