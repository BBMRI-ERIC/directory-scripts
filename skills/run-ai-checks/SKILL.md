---
name: run-ai-checks
description: "Use when the user asks to run or refresh true AI-reviewed checks on live Directory data. This skill performs a strongest-model review on a fresh Directory snapshot, keeps regex/heuristic checks out of `ai-check-cache/`, validates cache reuse against a pristine pre-plugin checksum baseline, refreshes changed entities, and requires clean end-to-end validation before commit."
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
   - review the full existing check surface before proposing anything new, so existing deterministic and AI-backed checks are not forgotten
   - document any newly introduced AI-only check type in this skill so future runs know that the category exists and how it should be reviewed
   - do not put regex-like findings into `ai-check-cache/`
3. Compute checksums for all reviewed entities before trusting the existing AI cache:
   - compute canonical checksums on the live entities first, before deciding what can be reused
   - capture checksums from a pristine pre-plugin Directory snapshot, not after QC plugins mutate in-memory entities during a run
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
   - review consistency between unstructured descriptions and structured metadata for both biobanks and collections
   - explicitly cover at least these topic groups:
     - phenotypic and clinical profile of donors/research participants:
       - age groups and age-range implications
       - clinically actionable biological sex
       - diagnosis and clinically relevant disease framing
       - stated inclusion criteria and special population statements
     - collected data:
       - whether narrative claims about clinical, imaging, omics, registry, follow-up, questionnaire, or similar data are reflected in structured metadata
     - collected biological material:
       - whether narrative claims about FFPE, tissue, blood derivatives, swabs, DNA/RNA, or similar materials are reflected in structured metadata
     - access conditions:
       - whether narrative access/governance/restriction statements are reflected in structured access metadata
       - consider whether the evidence would support proposing richer structured access profiling, including DUC/CCE-style profiles, when that would materially improve reuse
   - prefer findings that affect meaningful advertisement, discoverability, or reuse of collections/biobanks
7. Update `ai-check-cache/` entries only for the residual AI-only findings:
   - keep JSON stable and commit-friendly
   - include current `entity_checksum` and `source_checksum`
   - ensure `checked_fields` still match the actual live Directory field names used by the rule; if the field model changed, rebaseline `checked_entities` for the full reviewed scope
   - keep `checked_entities` complete enough to represent both positive findings and reviewed-no-finding entities
   - include enough message/action detail that non-experts can understand the issue
8. Validate the refreshed AI cache on a clean `Directory(...)` load first:
   - confirm that `load_ai_findings_for_directory(...)` reports reusable findings and no stale-cache issues for the fresh live snapshot
   - if the clean load shows stale-cache issues, refresh or fix the cache before doing anything else
9. Re-run the normal QC path after updating the cache:
   - run `python3 data-check.py -N -r`
   - do not purge the Directory cache for this validation run
   - use this run to confirm there are no stale AI-cache warnings in the full QC path
   - inspect the actual `AI:Curated` warnings separately, either by running `python3 data-check.py -r | rg 'AI:Curated'` without `-N` or by calling `AIFindings().check(...)` directly in a short Python snippet
   - if this full QC run emits stale AI-cache warnings, treat that as a checksum/runtime bug and fix it before committing

## Current AI-only categories

Keep this list current when adding a new AI-only rule:

- `NarrativeAccessMetadataGap`
  - concrete access/governance conditions are present in the narrative but missing from structured access metadata
- `NarrativeParticipantClinicalProfileGap`
  - narrative describes participant phenotype or clinical profile that is materially relevant for discovery/reuse, but the structured sex/age/diagnosis profile does not reflect it
- `NarrativeDataCategoryGap`
  - narrative advertises clinically relevant data modalities or follow-up/registry/questionnaire content that is not reflected in `data_categories`
- `NarrativeMaterialMetadataGap`
  - narrative advertises concrete stored biomaterials that are not reflected in `materials`

## Required checks

- Do not trust stale AI-cache findings. If `AIFindings` reports changed entity IDs, refresh the live AI review before using or editing those entries.
- Keep the AI cache focused on genuinely AI-only findings. If a pattern is deterministic, move it into a regular plugin instead.
- Before keeping any AI-reviewed finding, check for redundancy against all existing programmatic checks in `checks/`; prefer the non-AI check whenever the rule can be expressed and tested deterministically.
- Do not commit private runtime caches or ad-hoc local outputs outside `ai-check-cache/`.
- Keep ad-hoc review dumps such as `ai-checks-results-current.txt` out of commits; they are local review artifacts, not framework inputs.
- Treat clean-load cache validation as the source of truth for reuse, but require the full QC path to stay clean too; the runtime must preserve the pristine checksum baseline.

## Validation expectations

After updating the AI cache, validate at least:

- `python3 -m py_compile ai_cache.py checks/AIFindings.py <changed deterministic helpers/plugins/tests>`
- `pytest -q tests/test_ai_cache.py tests/test_ai_findings_check.py <changed deterministic test subsets>`
- a clean-snapshot cache-load check using `Directory(..., purgeCaches=['directory'])` plus `load_ai_findings_for_directory(...)`
- `python3 data-check.py -N -r` without purging the Directory cache
- `python3 ../BBMRI-ERIC-Directory-Data-Manager-Manual/scripts/generate_checks_docs.py` if documentation metadata changed

The update is not ready to commit unless both validation paths are clean:

- clean live cache load: reusable findings, zero stale-cache issues
- full `data-check.py -N -r` path: no stale AI-cache warnings

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
