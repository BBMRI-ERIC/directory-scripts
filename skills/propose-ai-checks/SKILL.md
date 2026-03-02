---
name: propose-ai-checks
description: "Use when the user explicitly asks to review current Directory data and propose new AI-assisted checks. This skill compares live data findings against existing deterministic and AI checks, proposes only non-duplicative additions, prefers deterministic checks where possible, and implements new AI-cache checks only after explicit user approval."
---

# Propose AI Checks

Use this skill only when the user explicitly asks to review current data and propose new AI checks.

## Core rules

- Use the most advanced model available in the current session for the analysis step.
- If the current model is not the strongest available, say so immediately and recommend switching before doing the review, unless the user explicitly wants to continue.
- Preserve backward compatibility of existing checks, check IDs, and existing AI cache findings.
- Avoid duplicating current deterministic checks in `checks/` and current AI findings/checks in `ai-check-cache/`.
- Prefer deterministic, explainable checks over AI checks whenever a robust rule can be implemented.
- Treat current live-data failures as evidence, not as proof that a new check is needed; first rule out overlap with existing checks.

## Required two-step workflow

### Step 1: proposal only

Do all of the following before proposing anything:

- Inspect existing relevant checks in `checks/`, `ai_cache.py`, `checks/AIFindings.py`, and `ai-check-cache/`.
- Review the current manual-facing documentation where helpful (`README.md`, `CHECK_DOCS`, and the manual repo if needed).
- Use real Directory data or cached snapshots to collect evidence and counts.
- Group findings into:
  - already covered by deterministic checks
  - already covered by AI cache findings
  - partially covered / overlapping
  - genuinely new
- For each proposed new check, provide:
  - the user-facing problem
  - why current checks do not already cover it
  - whether it should be deterministic or AI-assisted
  - expected entity scope and fields
  - estimated hit counts from real data
  - false-positive risks and why the rule is still justified
  - how non-experts should fix it

Do not implement anything in this step.

### Step 2: implementation only after approval

After the user approves specific proposals:

- Implement deterministic checks first where feasible.
- For AI-assisted checks, use the shareable repository-backed cache model under `ai-check-cache/`, not private runtime caches.
- Keep AI findings commit-friendly:
  - stable JSON structure
  - deterministic IDs/versioning
  - clear rationale text
  - no secrets or private runtime artifacts
- Ensure `CHECK_DOCS` fully explains the check for non-experts.
- Add or update tests.
- Re-run overlap review so the new check does not duplicate an existing one.

## AI-cache design constraints

- Do not use `data-check-cache/` or other private/local caches for shareable AI findings.
- Treat `ai-check-cache/` as a versioned empirical repository of reviewed "no-no" patterns.
- New AI findings must be explainable enough that a later deterministic check can replace them when feasible.
- If a proposed AI check mostly encodes a stable heuristic, recommend converting it into a deterministic check instead of expanding AI usage.

## Output format for step 1

Report in this order:

1. Candidate checks worth adding
2. Existing checks or AI findings that already overlap
3. Real-data counts/examples
4. Recommended implementation order
5. Risks or open questions

Be explicit about what should *not* be implemented because it would duplicate existing coverage.
