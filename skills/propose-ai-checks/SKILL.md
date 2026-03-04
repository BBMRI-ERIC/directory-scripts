---
name: propose-ai-checks
description: "Use when the user explicitly asks to review current Directory data and propose new AI-assisted checks. This skill reviews real up-to-date data with the strongest available model, separates deterministic regex/heuristic checks from true AI-only findings, and proposes only non-duplicative additions or refinements before any implementation."
---

# Propose AI Checks

Use this skill only when the user explicitly asks to review current data and propose new AI checks or AI-check refinements.

## Core rules

- Use the strongest model available in the current session for the review.
- If the current model is not the strongest available, say so immediately and recommend switching before doing the review, unless the user explicitly wants to continue.
- Preserve backward compatibility of existing checks and AI cache findings unless the user approves a compatibility break.
- Avoid duplicating current deterministic checks in `checks/` and current AI findings in `ai-check-cache/`.
- Prefer deterministic, explainable checks over AI checks whenever a robust rule can be implemented.
- Regex-like or heuristic text checks belong in regular plugins, not in `ai-check-cache/`.
- Reserve `ai-check-cache/` for findings that need full AI-model review on live data and cannot be expressed robustly as deterministic logic.

## Required two-step workflow

### Step 1: proposal only

Do all of the following before proposing anything:

- Inspect existing relevant checks in `checks/`, `text_consistency.py`, `ai_cache.py`, `checks/AIFindings.py`, and `ai-check-cache/`.
- Review the current manual-facing documentation where helpful (`README.md`, `CHECK_DOCS`, and the manual repo if needed).
- Use real Directory data or a current cache snapshot to collect evidence.
- Review the current live findings with the strongest available model and look explicitly for false positives, false negatives, and duplicate coverage.
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
- Refresh the relevant live data, update `ai-check-cache/` entries with current checksums, and re-review the resulting findings with the strongest available model before committing.
- Keep AI findings commit-friendly:
  - stable JSON structure
  - checksum metadata for checked entities and source fields
  - clear rationale text
  - no secrets or private runtime artifacts
- Ensure `CHECK_DOCS` fully explains deterministic checks for non-experts.
- Add or update tests.
- Re-run overlap review so the new check does not duplicate an existing one.

## AI-cache design constraints

- Do not use `data-check-cache/` or other private/local caches for shareable AI findings.
- Treat `ai-check-cache/` as a versioned empirical repository of reviewed "no-no" patterns.
- The cache is reusable only while current live entity/source checksums match the committed JSON payloads.
- If `data-check.py` or `AIFindings` reports stale AI-cache warnings, refresh the live AI-review workflow before trusting or editing AI findings.
- New AI findings must be explainable enough that a later deterministic check can replace them when feasible.
- If a proposed AI check mostly encodes a stable heuristic, recommend converting it into a deterministic check instead of expanding AI usage.

## Output format for step 1

Report in this order:

1. Candidate checks/refinements worth adding
2. Existing checks or AI findings that already overlap
3. Real-data counts/examples from the current review
4. Recommended implementation order
5. Risks or open questions

Be explicit about what should *not* be implemented because it would duplicate existing coverage.
