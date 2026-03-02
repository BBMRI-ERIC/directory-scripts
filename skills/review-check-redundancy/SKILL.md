---
name: review-check-redundancy
description: "Use before committing or pushing changes to `checks/` or `ai-check-cache/`, and when the user asks to review check overlap. This skill critically reviews deterministic and AI-assisted checks for redundancy, prefers cheaper deterministic checks when functionality overlaps, and proposes safe consolidations without losing coverage."
---

# Review Check Redundancy

Use this skill before commit/push when `checks/`, `checks/AIFindings.py`, `ai_cache.py`, or `ai-check-cache/` changed, and when the user asks to review check overlap.

## Review goals

- Detect redundant coverage across deterministic checks and AI-assisted findings/checks.
- Preserve functionality and backwards compatibility of check outputs as far as practical.
- Prefer deterministic checks over AI checks when both cover the same user problem.
- Keep AI coverage only for cases that remain materially fuzzy after deterministic rules are exhausted.

## Required workflow

### Step 1: inventory

- List changed checks and nearby related checks.
- Review matching `CHECK_DOCS`, tests, and README/manual references.
- Inspect `ai-check-cache/` categories and finding rationales when AI checks are involved.

### Step 2: overlap analysis

For each changed or candidate check:

- Identify the user-facing problem it detects.
- Identify the entity/fields it relies on.
- Identify every existing deterministic or AI check that overlaps with that problem.
- Classify overlap as:
  - exact duplicate
  - deterministic superset
  - AI superset
  - partial overlap
  - complementary

### Step 3: resolution proposal

When redundancy exists, propose the cheapest safe resolution:

- keep the deterministic check and retire or narrow the AI check
- keep both, but clearly separate scopes
- merge check logic while preserving IDs/messages if stability matters
- convert stable AI findings into deterministic logic

Each proposal must state:

- what functionality is preserved
- what check IDs/messages would change, if any
- migration or compatibility risk
- required test/doc updates

## Decision rules

- Do not remove a check only because it looks similar; prove that coverage is preserved.
- If deterministic and AI checks overlap, the deterministic rule is the default owner.
- If AI coverage catches broader but noisy cases, keep it only for the residual fuzzy area and document that boundary.
- If live data still triggers an older check, treat that as active coverage, not dead code.

## Output format

Report in this order:

1. Redundant or overlapping checks
2. Gaps where overlap is only partial
3. Recommended consolidations
4. Compatibility and testing implications

Do not implement the consolidation unless the user asks.
