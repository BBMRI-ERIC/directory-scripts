---
name: propose-ai-checks
description: "Use when the user explicitly asks to review current Directory data and propose new AI-assisted checks. This skill reviews real up-to-date data and current AI-check results with the strongest available model, proposes only non-duplicative additions or refinements, prefers deterministic checks where possible, and implements changes only after explicit user approval."
---

# Propose AI Checks

Use this skill only when the user explicitly asks to review current data and propose new AI checks or AI-check refinements.

## Core rules

- Use the strongest model available in the current session for the review.
- If the current model is not the strongest available, say so immediately and recommend switching before doing the review, unless the user explicitly wants to continue.
- Preserve backward compatibility of existing checks, check IDs, and existing AI cache findings unless the user approves a compatibility break.
- Avoid duplicating current deterministic checks in `checks/` and current AI findings/checks in `ai-check-cache/`.
- Prefer deterministic, explainable checks over AI checks whenever a robust rule can be implemented.
- Treat current live-data failures as evidence, not as proof that a new check is needed; first rule out overlap with existing checks.

## Required two-step workflow

### Step 1: proposal only

Do all of the following before proposing anything:

- Refresh the live data view first:
  - run `python3 run-ai-checks.py --purge-cache directory --report ai-checks-results-current.txt`
  - if withdrawn content is in scope, pass `-w/--include-withdrawn` or `--only-withdrawn` explicitly
- Inspect existing relevant checks in `checks/`, `ai_cache.py`, `checks/AIFindings.py`, `ai_check_generation.py`, and `ai-check-cache/`.
- Review the current manual-facing documentation where helpful (`README.md`, `CHECK_DOCS`, and the manual repo if needed).
- Review the freshly generated `ai-checks-results-current.txt` with the strongest available model and look explicitly for false positives, false negatives, and duplicate coverage.
- Group findings into:
  - already covered by deterministic checks
  - already covered by AI cache findings
  - partially covered / overlapping
  - genuinely new
  - existing AI checks that should be narrowed, split, or retired
- For each proposed new or changed check, provide:
  - the user-facing problem
  - why current checks do not already cover it
  - whether it should be deterministic or AI-assisted
  - expected entity scope and fields
  - estimated hit counts from real current data
  - false-positive / false-negative risks and why the rule is still justified
  - how non-experts should fix it

Do not implement anything in this step.

### Step 2: implementation only after approval

After the user approves specific proposals:

- Implement deterministic checks first where feasible.
- For AI-assisted checks, use the shareable repository-backed cache model under `ai-check-cache/`, not private runtime caches.
- Regenerate AI findings from current data with `python3 run-ai-checks.py --purge-cache directory --report ai-checks-results-current.txt`.
- Re-review the refreshed result set with the strongest available model and refine any obvious false positives/false negatives before committing.
- Keep AI findings commit-friendly:
  - stable JSON structure
  - checksum metadata for checked entities and source fields
  - clear rationale text
  - no secrets or private runtime artifacts
- Ensure `CHECK_DOCS` fully explains the check for non-experts.
- Add or update tests.
- Re-run overlap review so the new check does not duplicate an existing one.

## AI-cache design constraints

- Do not use `data-check-cache/` or other private/local caches for shareable AI findings.
- Treat `ai-check-cache/` as a versioned empirical repository of reviewed "no-no" patterns.
- The cache is reusable only while current live entity/source checksums match the committed JSON payloads.
- If `data-check.py` or `AIFindings` reports stale AI-cache warnings, rerun `run-ai-checks.py` before trusting or editing AI findings.
- New AI findings must be explainable enough that a later deterministic check can replace them when feasible.
- If a proposed AI check mostly encodes a stable heuristic, recommend converting it into a deterministic check instead of expanding AI usage.

## Output format for step 1

Report in this order:

1. Candidate checks/refinements worth adding
2. Existing checks or AI findings that already overlap
3. Real-data counts/examples from the refreshed run
4. Recommended implementation order
5. Risks or open questions

Be explicit about what should *not* be implemented because it would duplicate existing coverage.
