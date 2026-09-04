# Development Notes

This document is the canonical maintainer reference for architecture, detailed
functionality specifications, invariants, code organization, and testing. It
also serves as the project's functionality-specification mechanism until a
dedicated specification system replaces it.

## Documentation ownership

- [`README.md`](README.md) is a concise landing page for discovery and first
  steps. It must link outward rather than accumulate per-script manuals.
- `docs/` contains user/operator documentation: installation, commands, inputs,
  outputs, workflow examples, deployment notes, and operational safety.
- `DEVELOPMENT.md` contains canonical behavioral and architectural contracts,
  including rationale needed to maintain them correctly.
- [`AGENTS.md`](AGENTS.md) contains concise, non-negotiable implementation
  guardrails. It should point here instead of duplicating detailed
  specifications.
- Every topic should have one canonical home. Cross-links and short summaries
  are preferable to copied sections that can drift.
- An interface or behavior change is incomplete until the relevant operator
  guide and this specification are both updated. Update `AGENTS.md` when the
  change also affects an enforceable repository-wide rule.
- User documentation explains how to operate current behavior; it is not, by
  itself, the authoritative definition of internal behavior.

Start from [README.md](README.md) for the documentation index and from
[`docs/setup.md`](docs/setup.md) for user-facing installation and common CLI
operation.

## Architecture

### Repository structure

- Top-level scripts are CLIs for validation, export, search, and maintenance.
- Every production Python module at the repository root, in `checks/`, or in
  `R-maps/` must state its purpose in a concise module-level docstring.
- Every `exporter-*.py` module must have both a summary-table entry and a detailed operator section in
  `docs/exporters.md`. The table is only an index; inputs, outputs, selection
  behavior, important options, and runnable examples belong in the detailed
  section.
- `checks/` contains Yapsy plugins only. Files there should be warning-producing checks, plus their matching `*.yapsy-plugin` descriptors.
- Plugin imports must distinguish hard dependencies from optional runtime helpers. Missing optional packages must not prevent the whole plugin from loading; degrade gracefully and keep the deterministic/local part of the check active when possible.
- Reusable infrastructure belongs outside `checks/` in top-level helper modules.
- Contact-assignment heuristics should reuse `contact_assignment_utils.py`; keep simple “contact reused across biobanks” visibility checks separate from stronger “likely foreign-institution contact” warnings so the informational signal can be disabled without losing the warning-level logic.
- `checks/ContactReuse.py` must not emit `CTR:CrossBiobankReuse` for a contact that already qualifies for `CTA:CrossBiobankInstitutionContact`; stronger warning-level ownership evidence supersedes the weaker INFO for the same contact. Contacts serving as main biobank contacts for multiple biobanks should remain shared cross-institution INFO-only cases, not WARNINGs.
- `checks/AccessPolicies.py` follows the current schema and must use only the generic `access_*` collection fields. Do not revive legacy modality-specific `sample_access_*`, `data_access_*`, or `image_access_*` field checks; regression tests should fail if those old check IDs or field names creep back in.

### Core module boundaries

- `directory.py`
  - single shared abstraction for Directory / Molgenis access
  - owns shared data retrieval, schema handling, withdrawal scoping, and graph helpers
  - Services and Studies are first-class cached/traversable entities there too: keep biobank<->service traversal and biobank->collection->study traversal logic in `directory.py` instead of reconstructing parentage ad hoc in exporters
  - for study linkage, treat `Collections.studies` as the authoritative relationship source; use `getCollectionStudies(...)`, `getCollectionStudyIds(...)`, `getStudyCollectionIds(...)`, and `getStudyCountries(...)` rather than reconstructing study membership from stale or partial `Studies.collections` payloads in scripts
  - owns shared quality-information access too: new code should prefer `getBiobankQualityInfo(...)`, `getCollectionQualityInfo(...)`, `getBiobankQualityInfoWide(...)`, `getCollectionQualityInfoWide(...)`, and `getQualityStandardsOntology(...)` over ad hoc DataFrame filtering/pivoting in exporters
- `geojsonutils.py`
  - shared coordinate parsing and GeoJSON feature-writing helpers
  - reuse it from exporters/tools that expose mapped entities instead of duplicating DMS/DMM/decimal coordinate normalization or ad hoc GeoJSON serialization
- `directory_session_compat.py`
  - compatibility wrapper for write-capable Molgenis sessions
  - provides the repository-local `DirectorySession` context-manager surface on top of `molgenis_emx2_pyclient.Client`
  - use this from maintenance CLIs instead of importing the removed legacy `molgenis_emx2.directory_client...` path directly
- `checks/`
  - owns actual QC logic that emits `DataCheckWarning(...)`
  - keep the easy-to-disable `INFO` plugin `checks/ContactReuse.py` separate from the warning-level probabilistic plugin `checks/ContactAssignments.py`
- helper modules such as `nncontacts.py`, `warningscontainer.py`, `warning_suppressions.py`, `orphacodes.py`, `oomutils.py`, `text_consistency.py`, `fact_descriptor_sync.py`
- `R-maps/`
  - shared home for the emerging `ggplot2` + `sf` replacement of legacy
    Tilemill renderers
  - keep shared palettes, projections, Natural Earth layer loading, and output
    size presets in common R helpers there rather than duplicating them between
    map scripts
- `checks/CollectionContent.py` now owns conservative ORPHA/ICD diagnosis crosswalk completion too when an `OrphaCodes` mapper is loaded: keep exact mappings highest-confidence, allow narrower-to-broader crosswalk fixes only in the accepted direction, and suppress duplicate legacy informational warnings when a newer concrete append fix already covers the same source diagnosis.
- `warningscontainer.py` should write XLSX cells by actual value type; withdrawn flags may be real booleans in warning/entity listings and must not be forced through string-only worksheet APIs.
  - own reusable logic that can be consumed by multiple scripts or plugins
- `xlsxutils.py` must disable automatic URL conversion and enforce Excel
  worksheet hyperlink limits: write explicit links only up to the limit, retain
  plain display values thereafter, and report omitted links once per sheet.

### Directory cache scope

- The shared `data-check-cache/directory` cache is keyed by entity class/table, not by target URL.
- This is acceptable for the current operating model, but it means alternate Directory targets share the same cache namespace.
- When switching a tool to a non-default Directory instance, purge the `directory` cache before switching back or comparing runs across targets.

### Scoped local validation

A lightweight in-repo validation layer is used narrowly in this repository.

- Use it for local inputs and repository-owned artifacts:
  - tool/runtime settings
  - shareable AI-cache payloads
  - warning-suppression JSON
- Do not use it as a full wrapper around live Molgenis Directory entities.
  - Molgenis already enforces much of the structural validity for stored data.
  - wrapping the whole live payload graph would add brittleness and duplicate validation noise.
- Non-fatal validation problems must not crash the tool:
  - QC path: log script-level validation warnings and continue
  - maintenance CLIs: raise user-facing input errors only when the tool cannot proceed safely
- Validation warnings should be suppressible via `--suppress-validation-warnings` where supported.

### Deterministic text checks vs AI-reviewed findings

Narrative-vs-structure checks are split into two categories:

- Deterministic checks
  - implemented directly as plugins
  - current example: `checks/TextConsistency.py`
  - use regexes / heuristics / explicit code logic
  - run directly on live Directory data during `data-check.py`
  - emit stable deterministic IDs such as:
    - `TXT:AgeRange`
    - `TXT:StudyType`
    - `TXT:FFPEMaterial`
    - `TXT:CovidDiag`

- AI-reviewed findings
  - stored in `ai-check-cache/`
  - reserved only for findings that genuinely need full AI-model review on live data and cannot be expressed robustly as deterministic logic
  - emitted at runtime by `checks/AIFindings.py` as `AI:Curated`
  - current rule families cover:
    - access-governance metadata gaps
    - participant phenotypic/clinical-profile gaps
    - data-category gaps
    - material-metadata gaps

Rule of thumb:
- if a rule can be implemented with regexes, heuristics, or ordinary Python logic, it should be a deterministic plugin
- `ai-check-cache/` is only for the residual fuzzy cases

### Fact-sheet alignment helpers vs runtime checks/tools

- `fact_descriptor_sync.py`
  - shared derivation/comparison logic for collection descriptors vs fact sheets
  - used by both `checks/FactTables.py` and `collection-factsheet-descriptor-updater.py`
  - owns special handling such as:
    - ignoring `*` fact-sheet aggregate values for descriptor comparison
    - treating `NAV` material as ambiguous/non-authoritative when richer materials may be hidden by k-anonymity suppression
    - preserving broader ICD-10 metadata codes when they already cover more specific fact-sheet diagnoses

- Design note for material updates:
  - NAV-only fact output is not definitive evidence that collection-level materials are wrong.
  - Fact rows can be suppressed by k-anonymity, so richer metadata may still be valid.
  - Treat such cases as review-required and document the ambiguity clearly in user-facing tooling/docs.
- Design note for age updates:
  - preserve fact-sheet month/day/week/year units when they can be inferred consistently
  - do not auto-update age metadata when fact rows mix incompatible units
  - when facts use one consistent unit, age proposals should cover the full min..max span represented by the fact rows even if the fact table has gaps between age buckets

- `checks/FactTables.py`
  - runtime QC warning producer
  - uses the shared helper logic to avoid reporting known deterministic false positives

- `collection-factsheet-descriptor-updater.py`
  - explicit maintenance CLI
  - uses the same shared helper logic to propose and optionally apply descriptor updates to staging-area `Collections`

- `qcheck-updater.py`
  - explicit maintenance CLI for QC-derived fix plans
  - consumes structured `fix_proposals` exported from `data-check.py`
  - supports human-readable listing, dry-run, interactive apply, and forced batch apply
- `directory-tables-modifier.py`
  - for `CollectionFacts` k-anonymity filtering in import/sync, keep semantics aligned with `FT:KAnonViolation`: skip only rows with `0 < number_of_donors < k` / `0 < number_of_samples < k` (do not auto-drop zero-valued rows)
- `k_anonymity.py`
  - shared helper for the `0 < value < k` rule; use it from both check code (`checks/FactTables.py`, fix proposals) and table tooling (`directory-tables-modifier.py`) to prevent semantic drift

If descriptor-alignment logic changes, keep both the check and the updater behavior consistent.

### `ai_cache.py` vs `checks/AIFindings.py`

These two files serve different layers:

- `ai_cache.py`
  - helper/infrastructure module
  - loads JSON files from `ai-check-cache/`
  - validates payload structure
  - computes and compares checksums
  - reports stale-cache issues back to the caller
  - does not emit `DataCheckWarning(...)` itself

- `checks/AIFindings.py`
  - actual Yapsy plugin
  - consumes `ai_cache.py`
  - turns cache records into runtime `DataCheckWarning(...)`
  - logs script warnings when cache entries are stale
  - supports both `COLLECTION` and `BIOBANK` AI-reviewed findings
  - owns the manual-facing `CHECK_DOCS` for the cache-backed check

So:
- `ai_cache.py` is infrastructure
- `checks/AIFindings.py` is a check

That is why `ai_cache.py` stays outside `checks/`.

### Check documentation metadata

Checks can carry machine-readable `CHECK_DOCS` metadata directly in plugin source.

Use `CHECK_DOCS` for:
- developer/manual-facing summaries
- explicit field declarations
- business-context explanations that cannot be reconstructed reliably from AST parsing alone

Keep `CHECK_DOCS` aligned with the emitted `DataCheckWarning(...)` calls.

### Warning suppressions

- `warning-suppressions.json`
  - reviewed false-positive suppressions
  - supports legacy map format and structured v2 list format with metadata
  - canonical v2 fields: `check_id`, `entity_id`, optional `entity_type`, `suppress_warning`, `suppress_fix`, `reason`, `added_by`, `added_on`, `expires_on`, `ticket`
  - a single structured entry can suppress the runtime warning, the exported QC fixes, or both; default is both
  - warning IDs (`FT:KAnonViolation`) suppress attached fixes too when `suppress_fix` is left enabled; module/update IDs (`FT/facts.k_anonymity.drop_rows_k10`) still suppress only the matching fix proposal path
  - used only to hide known residual false positives from QC output
- exported QC update-plan JSON
  - checksum-signed fix-plan artifact produced by `data-check.py -U/--export-update-plan ...`
  - consumed by `qcheck-updater.py`
  - carries both per-update integrity checksums and expected current field values
  - omits fix proposals that match configured warning suppressions
- `warning_suppressions.py`
  - loader/normalizer for suppression JSON
  - provides diagnostics for unknown check IDs, stale entity IDs, and expired suppressions
- `warning-suppressions-manage.py`
  - CLI for add/list/validate/prune-stale management of suppression entries
- `warningscontainer.py`
  - applies suppressions before warnings are written to stdout/XLSX
  - debug mode can print suppressed warning details for runtime traceability

Suppressions are not a substitute for fixing deterministic logic. Prefer code fixes first; keep suppressions for reviewed residual cases.

After changing check docs metadata, validate with:

```bash
python3 ../BBMRI-ERIC-Directory-Data-Manager-Manual/scripts/generate_checks_docs.py
```

## Fact-sheet aggregation specification

Status: Normative project specification

Provenance: user request, 2026-08-31

### Row classification

#### FS-ROW-001: Tracked dimensions

Fact-sheet aggregation MUST use the tracked dimensions `sex`, `age_range`,
`sample_type`, and `disease`.

#### FS-ROW-002: Aggregate row classes

An all-star row MUST contain `*` in every tracked dimension. An
all-but-one-star row MUST contain exactly one concrete tracked-dimension value
and `*` in every other tracked dimension. A no-star fallback row MUST contain a
concrete, non-empty, non-`*` value in every tracked dimension.

Rows with one or more missing tracked-dimension values MUST NOT be treated as
no-star fallback rows.

### Authoritative reporting

#### FS-AGG-001: Aggregation levels are non-additive

Sample and donor counts from all-star, all-but-one-star, and no-star rows MUST
NOT be added across aggregation levels. Multiple all-but-one-star values within
one fact sheet MUST NOT be summed to reconstruct an all-star total because
values can overlap.

#### FS-AGG-002: Authoritative marginal contribution

For one collection, dimension, and value, exactly one populated
all-but-one-star row MUST be treated as the authoritative marginal
contribution. If multiple matching all-but-one-star rows exist, the contribution
MUST be treated as ambiguous and excluded from aggregate reporting.

#### FS-AGG-003: Cross-collection aggregation

An exporter MAY sum one selected contribution per collection, dimension, and
value across collections. It MUST retain the number of contributing collections
and contribution provenance.

Authoritative all-but-one-star contributions and assumption-violating no-star
fallback contributions MUST be reported as separate statistics. Their counts,
observations, or contributing-collection totals MUST NOT be combined, even when
they come from different collections.

### Unsafe no-star fallback

#### FS-FALLBACK-001: Explicit opt-in

No-star fallback MUST be disabled by default. Collection-based exporters that
expose fact-sheet distributions MUST provide the long option
`--allow-no-star-fact-sums` to enable it.

Enabling the option MUST produce a visible warning explaining that no-star rows
are not guaranteed to be disjoint or complete and that derived sums may
double-count or undercount records.

#### FS-FALLBACK-002: Per-missing-value substitution

When fallback is enabled and a collection has no matching all-but-one-star row
for a dimension and value, the exporter MAY sum populated fully concrete
no-star rows matching that value as an assumption-violating substitute.

Fallback MUST NOT be used when an authoritative all-but-one-star row exists or
when multiple matching all-but-one-star rows make the contribution ambiguous. A
collection MUST NOT contribute both authoritative and fallback counts to the
same dimension and value. Fallback contributions MUST NOT be added to
authoritative cross-collection distribution totals.

#### FS-FALLBACK-003: No synthetic all-star totals

No-star fallback MUST NOT contribute to all-star sample totals, all-star donor
totals, collection-level aggregate comparisons, or statistics claiming
authoritative all-but-one-star coverage.

#### FS-FALLBACK-004: Provenance

Stdout and XLSX distribution output MUST place authoritative all-but-one-star
contributions and no-star fallback contributions in separate sections or
tables. Summary output MUST state whether fallback was enabled and how many
collections, values, and rows used it. When fallback is enabled, both stdout and
XLSX output MUST contain a visible warning that no-star sums violate aggregation
assumptions.

### Quality and consistency

#### FS-QC-001: Aggregate-row presence

Fact-sheet statistics and QC MUST report whether a fact sheet containing at
least one row has exactly one all-star row and whether it has all-but-one-star
rows covering each concrete dimension value represented by any fact row,
including a value represented only by no-star rows. A fact row is populated for
count reporting when at least one sample or donor count is a non-boolean integer;
zero is a populated count.

Missing and duplicate all-but-one-star rows MUST remain distinguishable.

#### FS-QC-002: Individual marginal bounds

When exactly one all-star row is available, each individual all-but-one-star
sample or donor count MUST NOT exceed the corresponding all-star count. Values
within a dimension MUST NOT be summed for this comparison.

#### FS-QC-003: Exact collection aggregates

When collection `size` or `number_of_donors` is an integer and the corresponding
all-star count is an integer, QC MUST compare them for equality.

#### FS-QC-004: Order-of-magnitude aggregates

When sample or donor order-of-magnitude metadata and the corresponding all-star
count are available, QC MUST verify that the exact all-star count lies in the
interval represented by the order of magnitude. This consistency check MUST use
the interval itself, not the configurable point-estimate coefficient used for
exporter totals.

### Verification

The implementation MUST have automated tests for row classification, fallback
selection and exclusion, provenance, warning output, all-but-one presence and
duplicate detection, individual marginal bounds, exact aggregate comparison,
OoM interval comparison, directory statistics, and common exporter CLI wiring.

## Fact-sheet emulation analysis specification

`exporter-fact-sheet-emulation.py` and `fact_sheet_emulation.py` provide a
read-only analysis of collection families that may have been created
historically to characterize samples, donors, or data before CollectionFacts
were available. This analysis is a migration aid, not a migration mechanism.

### FS-EMU-001: Operational identity versus characterization

A collection MUST be treated as operationally distinct when evidence shows a
different purpose, SOP, storage lifecycle, quality requirement, access or
governance regime, study relationship, network role, location, or responsible
organization. Differences that primarily describe the contents of a holding,
such as sex, material, diagnosis, age, anatomical site, imaging modality, or
data category, are characterization evidence and may indicate fact-sheet
emulation. A varying field MUST NOT be classified as characterization merely
because it is convenient for a proposed migration.
When a structured `purpose` field is present it is operational evidence.
Conflicting populated descriptions MUST block automatic readiness and be sent
for expert review because they may reveal different purposes or protocols.

The detector MUST distinguish required equality from contextual evidence. The
following fields MUST be excluded from the non-dimension equality signature:
collection `id`, `name`, descriptive text, sample/donor counts,
order-of-magnitude counts, and administrative timestamps or audit fields. Their
differences MUST NOT by themselves establish operational independence. Names,
IDs, and descriptions MUST nevertheless be retained as contextual evidence for
conceptual identity and operational-boundary markers. All other compared fields
MUST preserve missingness and be classified as same, unknown, or conflicting
under FS-EMU-003. Recorded metadata equality is evidence, not proof, when
fields are missing, copied, generic, or boilerplate.

### FS-EMU-002: Candidate-family boundaries

The detector MUST identify direct sibling families under the same parent when
they share a plausible conceptual identity. Top-level families MUST be formed
conservatively within one biobank, using exact non-dimension equivalence plus
variation in at least one current fact-sheet dimension (`age`, `diagnosis`,
`sample_type`/material, or `sex`). This exact-equivalence path is the primary
deterministic discovery rule and MUST require at least two members and at
least two distinct populated dimension values. Exact equivalence MUST be
calculated without treating names, IDs, descriptions, counts, or audit fields
as required equal fields.

Differently named top-level diagnosis partitions MAY be discovered only with a
strong additional anchor: an identical informative description, a specific
delimited ID/name series, or a sufficiently long shared description frame with
a diagnosis-derived difference. Generic names, generic materials, a shared
biobank, or a placeholder description MUST NOT be an anchor. Diagnosis-family
anchors MUST corroborate, not override, conflicting operational evidence.

A biobank MUST NOT, by itself, be a reason to group all of its collections.
Families MUST NOT cross biobanks or cross unrelated parent collections. A
top-level family without an existing umbrella collection is a candidate for
one new target collection, not a request to select an arbitrary source as the
target.

Name and ID evidence MUST be compared contextually, including differences
around phase, wave, round, visit, baseline, follow-up, re-examination, pilot,
eligibility/inclusion/exclusion criteria, site/centre, recruitment or collection
period, prospective/retrospective, autopsy/post-mortem, intervention, and
acquisition terms. A marker is operational-boundary evidence only when the
member-specific qualifier or surrounding text differs in a way that indicates
a separate protocol, acquisition round, lifecycle, governance arrangement, or
operational cohort.

Marker presence in shared study background is neutral. Ambiguous uses such as
disease stage, laboratory phase, anatomical "part", or publication language
MUST be sent to review rather than treated as a boundary or removed during
normalization.

The detector MUST NOT merge transitively through a weak intermediate match.
Each proposed family boundary requires auditable identity evidence and a
comparison of operational fields for the actual members.

Sibling families without either an umbrella-name/dimension-suffix relationship
or varying structured characterization evidence MUST remain unresolved and
MUST NOT receive fact-row migration previews. Before an existing parent or
top-level umbrella is recommended as a target, its operational metadata MUST
also be compared with the source members; conflicts or material unknowns block
target reuse.

### FS-EMU-003: Field comparison states

For every compared field, the detector MUST distinguish:

- **same:** all populated values agree after documented normalization;
- **unknown:** one or more values are missing, while no populated values
  conflict; and
- **conflicting:** two or more populated values differ.

Missing values are not evidence of equality. Conflicting operational fields
MUST lower emulation confidence and block automatic migration readiness.
Characterization conflicts SHOULD increase the evidence for a virtual
partition, but MUST NOT override an operational conflict.

Complete absence is reported as unknown. A partially populated operational
field blocks readiness because the members cannot be compared. Complete
absence of critical collection identity fields (`contact`, `license`,
`storage_temperatures`, or `type`) also blocks readiness; complete absence of
other optional fields remains visible for expert review but is not by itself a
hard blocker. `network` and `networks` input shapes MUST be compared as one
canonical network-membership field.

Descriptions MUST additionally have one of these evidence states:

- **informative-equal:** normalized informative descriptions agree;
- **dimension-derived difference:** the differing bounded text is a current
  fact-sheet value such as diagnosis, age, material/sample type, or sex;
- **operational-boundary difference:** the differing text identifies a phase,
  lifecycle, protocol, recruitment/acquisition period, site, intervention, or
  other operational separation;
- **placeholder/uninformative:** the text is empty, generic, or boilerplate
  such as a missing-description response; or
- **ambiguous:** the difference cannot be assigned safely to a dimension or an
  operational boundary.

The original descriptions and bounded differing sentence or snippet MUST be
retained for audit. Description markers MUST be evaluated from differences
between members, not from keyword presence alone. Shared background language
MUST NOT be treated as a boundary, and a dimension-derived description
difference MUST NOT override an operational conflict.

### FS-EMU-004: Schema-coupled type exception

The Directory schema may require collection type `IMAGE` when
`body_part_examined` is populated. A type difference that is explained solely
by this schema coupling MUST be reported as a mechanical exception and MUST
NOT be treated as an operational distinction. Any other type difference
remains operational evidence and requires review.

### FS-EMU-005: Separate confidence and readiness

The report MUST expose two independent assessments:

- **emulation confidence:** how strongly the available records support the
  interpretation that a family is a historical fact-sheet substitute; and
- **migration readiness:** whether the evidence is sufficient to represent the
  family safely using the current fact-sheet schema.

A family can have high emulation confidence but low migration readiness, for
example when its varying attribute is anatomical site and the current schema
has no such fact dimension, or when exact counts are unavailable. Operational
conflicts, blocking unknown fields, incompatible target metadata, unsupported
dimensions, ambiguous multi-valued attributes, insufficient conceptual
identity, and missing source mappings are migration blockers.

Diagnosis-based fact previews MUST also be blocked when source diagnoses are
multi-valued, incomplete, duplicated across collection strata, represented only
as coarse ranges, or paired with negation/control language that cannot be
represented as an unambiguous disease marginal.

Anatomical-site, organ, imaging-modality, image-dataset, timepoint,
recruitment-site, data-category, and similar partitions are unsupported or
future dimensions unless the current schema explicitly represents them. A
strongly patterned anatomy or imaging family MAY be emitted as `review-only`;
it MUST NOT be counted as current fact-sheet emulation or receive a fact
preview when acquisition, SOP, lifecycle, or operational identity is unknown
or conflicting. Scientific-question, data-element, or variable catalogues
MUST be excluded from positive fact-sheet classification when their members
represent different research questions rather than a supported distribution
dimension.

### FS-EMU-006: Counts and fact-row construction

Only exact integer sample and donor counts MAY be used in a proposed fact-row
preview. Order-of-magnitude values MUST remain explicitly marked as estimates
and MUST NOT be converted into exact counts. For every complete, single-valued
current fact-sheet dimension whose values are unique across the source members,
the exporter MUST copy each source collection's exact aggregate counts unchanged
into an independent all-but-one-star row for the target: that dimension is fixed
and every other fact dimension is `*`. If several dimensions independently meet
these requirements, each dimension receives its own marginal rows. Proposed
marginals MUST NOT be added, either within one dimension or across dimensions.

The exporter MUST NOT emit no-star intersection previews from collection-level
aggregates. Incomplete, multi-valued, or duplicate source mappings MUST NOT be
summed to manufacture a missing marginal. An absent target collection ID MAY
block migration readiness, but MUST NOT suppress an otherwise unambiguous
advisory marginal preview. Existing target all-star rows or collection-level
totals MAY be cited as provenance evidence, but MUST NOT be emitted as proposed
facts. Every proposed fact row MUST retain its source collection ID.

### FS-EMU-007: Current and future dimensions

The detector MUST distinguish dimensions representable by the current
fact-sheet schema from dimensions that are only candidates for future
extension. Current dimensions include the supported sex, material/sample-type,
and diagnosis mappings. Existing Directory attributes such as
`body_part_examined`, imaging modality, image dataset type, data category, and
collection category MAY be reported as future-dimension candidates with their
source field, values, ontology, coverage, representability, and provenance.
The report MUST NOT relabel an anatomical or organ partition as a disease
partition without disease-specific evidence. Candidate dimensions should be
assessed for generalizability across sample, image, and data modalities and
for whether they describe contents rather than operations.

### FS-EMU-008: Advisory AI packets

For unresolved or migration-blocked cases, the exporter MUST be able to emit
JSON and Markdown review packets from the same structured analysis. Each packet
MUST include instructions, expected outputs, suspect family and collection
IDs, field-level comparisons, dimension candidates, blockers, provenance, and
the rules against summing counts or converting OoM values. AI output is
advisory only: it MUST be returned for expert review and MUST NOT be treated
as a qcheck update or executable Directory mutation. Deterministic comparison
and ontology matching MUST precede any optional AI interpretation.

Prompt packet values MUST be bounded: strings longer than 1,000 characters
retain beginning and ending evidence plus original length and a checksum, and
long sequences retain bounded edge items plus their count and checksum. Full
source values remain available through the Directory and workbook traceability
references rather than being duplicated into an unbounded model prompt.
Identical fields and fields unknown for every member MUST be represented as
compact per-role summaries; detailed comparison rows remain required for
variation, conflict, and partial missingness.


Review instructions MUST tell the reviewer to distinguish collection-boundary
language from shared study background, to treat phase/re-examination and
acquisition markers as possible operational boundaries, and not to interpret
scientific questions or data-element catalogues as fact-sheet strata. The
expected response MUST separately state emulation confidence, migration
readiness, operational-boundary evidence, unsupported/future dimensions, and
required follow-up.

The default XLSX report MUST omit the verbose `Boundary evidence` table intended
for diagnostic processing. `--advanced-reporting` MUST include that worksheet;
JSON and Markdown AI-review packets MUST retain the same boundary evidence
regardless of the XLSX setting.

### FS-EMU-009: Privacy and expert review

Reports MUST contain only the minimum Directory evidence needed to assess a
family. Proposed dimensions and counts require expert review for semantic
validity, privacy or re-identification risk, k-anonymity implications, and
source completeness. A high-confidence family is not automatically safe to
publish or collapse.

Every family report MUST expose, at minimum, the discovery rule, parent and
biobank boundary, member IDs, identity anchor, varied current dimensions,
field-level equality states, description evidence state, marker category and
qualifier where present, bounded evidence snippet, operational conflicts and
unknowns, unsupported-dimension candidates, abstention reason, emulation
confidence, migration readiness, and source/provenance references. These
fields are evidence for review and MUST NOT be interpreted as a recommendation
to collapse without expert sign-off.

### FS-EMU-010: No writes or updater payloads

The exporter and helper MUST be read-only with respect to Directory entities.
They MUST NOT modify Directory tables, cached entity records, source
collections, or CollectionFacts, and MUST NOT emit payloads intended for direct
consumption by `qcheck-updater.py`. The shared Directory loader MAY perform its
normal cache refresh or an explicitly requested cache purge. Any later collapse,
target creation, fact-sheet generation, or source-ID redirect MUST be
implemented as a separately approved workflow with its own validation and
human sign-off.

## Coding Style

- Python 3, 4-space indentation, keep existing vim modelines intact.
- Prefer `snake_case` names and small reusable helpers.
- Keep exporters thin: CLI + orchestration only.
- Keep shared Directory logic in `directory.py`.
- When code needs parent/context data for an entity already selected by the
  current withdrawn scope, use scope-independent loaded lookups
  (`getLoadedBiobankById(...)`, `getLoadedCollectionById(...)`) rather than
  user-facing scope-filtered lookups. Whole-snapshot analysis may use
  `getLoadedCollections()` but must treat its shared record mappings as
  read-only. This prevents withdrawn-only exports and ancestor counting from
  dropping active parents or double-counting children.
- Implement fact-sheet summaries through `fact_sheet_summary.py` and follow the [fact-sheet aggregation specification](#fact-sheet-aggregation-specification); exporters must not define alternate aggregation semantics.
- `exporter-all.py` is the broad entity dump: when its sheet layout changes, keep the workbook tabs and stdout sections aligned across biobanks, collections, services, studies, contacts, and networks, and keep any withdrawn-in-main-workbook option additive rather than replacing the existing separate-workbook path.
- Put cross-cutting reusable logic in helper modules, not duplicated across scripts.
- Keep CLI help output consistent across scripts: standard options first (`-h`, `-v`, `-d`, then Directory target/auth options), then tool-specific options.
- Keep short options globally consistent inside one CLI: do not reuse `-t` for tool-specific meanings in scripts that already expose `-t/--token` via shared auth helpers.
- Use explicit runtime validation for assumptions that depend on input/data/config.
- Prefer clear exceptions and actionable messages over silent fallback.
- For reusable/public Python APIs, keep docstrings complete and consistent.
- For helper entry points that may be called from tests with ad hoc `argparse.Namespace` objects, access optional CLI attributes defensively with `getattr(..., None)` instead of assuming every parser-added attribute is present.

## Testing

### Fast checks

```bash
python3 -m py_compile <changed-python-files>
pytest -q
```

### Focused tests

Examples:

```bash
pytest -q tests/test_directory.py
pytest -q tests/test_text_consistency.py tests/test_text_consistency_check.py
pytest -q tests/test_ai_cache.py tests/test_ai_findings_check.py
```

### Live Directory tests

```bash
pytest -q tests/test_directory_live_cache_modes.py --live-directory --live-directory-mode both
```

Optional live settings:
- `--live-directory-schema <SCHEMA>`
- env `DIRECTORY_TEST_SCHEMA`
- env `DIRECTORYUSERNAME`
- env `DIRECTORYPASSWORD`

### When changing checks

At minimum, run:

```bash
pytest -q tests/test_check_docs_metadata.py
python3 ../BBMRI-ERIC-Directory-Data-Manager-Manual/scripts/generate_checks_docs.py
```

If deterministic text checks changed, also run:

```bash
pytest -q tests/test_text_consistency.py tests/test_text_consistency_check.py
```

If AI cache handling changed, also run:

```bash
pytest -q tests/test_ai_cache.py tests/test_ai_findings_check.py
```

## AI review workflow

Use the Codex skill `run-ai-checks` when you need full AI-model review of live data.

That workflow should:
- use the strongest available model
- review live current data
- avoid duplicating deterministic checks
- update `ai-check-cache/` only for genuinely AI-only findings
- keep checksum metadata current
- re-run the normal QC path after cache updates

Typical follow-up validation:

```bash
python3 data-check.py -N | rg 'AI:Curated'
```

## Codex skills workflow

Use repository skills from `skills/` (and installed global skills) as operational guardrails, not optional hints.

- `review-and-commit` (default pre-commit workflow):
  - use before every commit in this repository
  - enforces scope review, correctness/safety review, required tests, and documentation sync
  - ensures only required files are staged (no local artifacts/caches)
  - requires comprehensive commit message body (behavior changes, safety implications, tests run, deferred limits)
  - when both repositories are touched (`directory-scripts` and `../BBMRI-ERIC-Directory-Data-Manager-Manual`), prepare separate commits unless explicitly requested otherwise
- `assertive-quality-gate`:
  - required before push, and whenever code review/testing is requested
  - focuses on assertive programming, API docstrings, and regression-oriented tests
- `review-check-redundancy`:
  - required when touching `checks/`, `text_consistency.py`, `checks/AIFindings.py`, `ai_cache.py`, or `ai-check-cache/`
  - verifies no duplicate/overlapping checks are introduced without justification
- `run-ai-checks`:
  - only when live AI-reviewed findings are intentionally refreshed
  - keeps deterministic rules out of AI cache and validates checksum/cache freshness

Practical rule: if you are going to commit, start with `review-and-commit`; this keeps commit quality and cross-file consistency stable over time.

## QC-derived update workflow

- `DataCheckWarning` may carry structured `fix_proposals` alongside the human warning text.
- `data-check.py -U/--export-update-plan ...` serializes those proposals into a JSON fix plan.
- `qcheck-updater.py` reads that file, filters it, lists it in a human-readable form, and can dry-run or apply the updates to a staging schema.
- Dry-run must follow the same interactive per-update review path as a real apply; the only behavioral difference is that it stops before `save_table(...)`.
- Interactive review must accept `y` to apply, `n` to skip, and `i` to ignore as false positive; the ignore path writes canonical coupled suppressions for the update's source check IDs into `warning-suppressions.json` and then continues with the next update.
- Interactive maintenance CLIs should treat Ctrl+C as a normal user abort: catch `KeyboardInterrupt` in `main()`, log a short interruption message naming the script/action, and return the script's abort/runtime exit code instead of dumping a traceback.
- The updater is intentionally a consumer of exported QC evidence, not a second implementation of the QC logic.
- The current updater apply path supports both biobank-scoped and collection-scoped fixes: biobank metadata updates in `Biobanks`, collection metadata updates in `Collections`, and explicit row deletions in `CollectionFacts` (for example k-anonymity cleanup). Contact/network fixes are still out of scope until there is explicit support for them.
- Current default QC baseline for fact-row donor k-anonymity is `k=10` (`FT:KAnonViolation`) for public aggregated data; any lower/waived threshold should be an explicitly documented exception (for example pre-anonymized source data).
- `--list` is the non-writing inspection mode and should use the same canonical multi-value formatting as interactive review so order-only differences are not presented as live mismatches.
- Checksums are advisory integrity markers: warn on mismatch, but keep an override path so deliberate user edits remain possible.
- Every update also carries `expected_current_value`; apply logic must compare it with the live staging-area value and warn before writing when the values diverge.
- In interactive mode, expected-current-value mismatches must be handled per update during review; declining one mismatched proposal must not abort unrelated updates.
- Unordered multi-value fields must be compared canonically; order-only differences in `data_use`, `type`, `diagnosis_available`, `materials`, or `sex` are not meaningful.
- Review output must show the real effect of append updates: the final target value plus the incremental addition, not a replacement-looking payload.
- `uncertain` proposals are still exported because they can represent genuine alternative curator choices; do not auto-merge or auto-apply them blindly.
- Ontology-backed fixes such as DUO terms must carry explanations validated against the official ontology source during development; do not improvise ontology descriptions at runtime.
- DUO terms must be normalized across `DUO_0000000` and `DUO:0000000` forms before comparison and duplicate detection.
- This workflow only makes sense when the staging area is the authoritative editable source. If a node imports/synchronizes data from another primary system, fix that primary source instead.

### SO2 survey analysis tool

- `survey-so2-directory.py` is a one-off survey-analysis CLI that still follows the repository's shared infrastructure rules:
- Technology-modality UpSet exports treat the required `Other` survey checkbox as non-positive unless `Technologies` free text says something concrete; the current graph uses direct-field NGS/proteomics/metabolomics, dedicated radiology/pathology questions, a separate `Genotyping / panels` bucket inferred from positive `Technologies` text, and `Other technology` only for the remaining positive `Technologies` details.
  - the generated R artifacts should include three coordinated outputs from the same CSV payload: the UpSet plot, the observed-minus-expected deviation plot, and a respondent-by-modality matrix plot
  - the matrix plot should label rows as `survey_row (CC): institution`, keep a white plot/panel background for export readability, and sort countries ascending with `A...` countries at the top of the plot
  - use `directory.py` for Directory access/cache/auth instead of ad hoc API calls
  - keep the survey-to-Directory mapping in editable JSON (`survey-mappings/so2_2025_directory_mapping.json`) so humans can correct Codex-produced assumptions
  - keep the survey-question to strategic-objective mapping in editable JSON (`survey-mappings/so2_2025_question_to_strategic_objectives.json`) so the report can aggregate findings by BBMRI SO2 objective without baking those assumptions into code
  - generate a machine-readable findings JSON first; treat TeX/PDF rendering as a second step that can render an edited findings JSON without re-reading the survey workbook
  - generate XeLaTeX builds in a temporary working directory and write only the designated `.tex` / `.pdf` outputs into the repository or user-selected paths
  - prefer `latexmk -pdfxe` for PDF builds when available; fall back to direct `xelatex` only when `latexmk` is unavailable
- Resolution logic for survey respondents is intentionally conservative:
  - exact via biobank ID or collection ID when the survey provides them
  - certain via institution-name match when the normalized name, alias/acronym, or ID alias maps uniquely
  - approximate via institution-name similarity when there is no exact ID anchor; fuzzy matching should be accent-insensitive and robust to small typos
  - unresolved/missing when the respondent does not map cleanly into the Directory
- `directory.py` should stay cache-first for read workflows: when a complete schema snapshot is already cached, reuse it without forcing a live API session; if live refresh fails, fall back to the cached snapshot when it is complete and otherwise raise a clear runtime error.
- The same cache-first rule applies to quality metadata: `directory.py` should backfill missing optional `QualityInfoBiobanks` / `QualityInfoCollections` tables into an otherwise-complete schema cache when live access is available, and `QualityStandards` ontology caching must be keyed by Directory base URL.
- Do not invert the workflow by reporting every Directory biobank missing from the survey; only analyze survey respondents and their matched/missing Directory scope.
- WSI can currently only be analyzed through generic imaging signals (`type=IMAGE`, `data_categories=IMAGING_DATA`, imaging metadata, and free text). Do not invent a fake WSI-specific structured field until the Directory schema grows one.
- Survey-derived update plans may target both `BIOBANK` and `COLLECTION` entities; keep update generation conservative and avoid auto-writing free-text rewrites.
- Keep the findings JSON self-contained for later rendering: it should carry any derived strategic-objective tags needed for the PDF so `render-report` can work from the JSON alone.
- Keep repeated methodology text out of the main report body:
  - the main report should use short issue summaries plus compact concrete values for non-consistent findings
  - one canonical description per finding type belongs in the appendix, with clickable links from the summary/status tables
  - `Mapping` and `Entity` cells should remain breakable enough for PDF readability (`.` / `_` for mapping IDs; `-` / `:` / `_` / `.` for entity identifiers)

### Current fix-producing module labels

- exported `module` values intentionally match the visible QC check-prefix family that users see in warning IDs
- current labels:
  - `AP`
    - DUO/access-policy proposals from `checks/AccessPolicies.py`
  - `CC`
    - collection-content/type fixes from `checks/CollectionContent.py`
  - `C19`
    - COVID-specific fixes from `checks/COVID.py`
  - `FT`
    - fact-sheet-derived diagnosis/material/sex/age/count fixes from `checks/FactTables.py`
  - `TXT`
    - deterministic narrative-to-structure fixes from `checks/TextConsistency.py`
- keep the semantic category in `update_id`; do not overload `module` with a second naming scheme
- keep field-specific rationale specific: notes from one domain (for example age-range caveats) must not leak into unrelated diagnosis/material/count proposals
- when an ontology-backed value is already present under an equivalent storage form (for example `DUO_0000007` vs `DUO:0000007`), both the checks and the updater must treat the proposal as a no-op rather than prompting for a duplicate addition

### Confidence handling

- `certain`
  - deterministic, directly implied by structured source data
- `almost_certain`
  - still deterministic, but with a small policy/curation assumption that must stay visible to the user
- `uncertain`
  - export and list these proposals, but treat them as curator-choice candidates rather than safe batch updates

### Selection and conflict handling

- Filters combine as `AND`; comma-separated/repeated values within the same filter combine as `OR`.
- Supported selectors:
  - exact entity id
  - hierarchy root id
  - staging area
  - `check_id`
  - `update_id`
  - `module`
  - `confidence`
- Use `exclusive_group` for mutually exclusive alternatives in one field; the updater must not auto-merge those proposals.
- If multiple updates for the same entity/field disagree on mode or target value, keep them as conflicts and skip automatic apply.

## Withdrawal scope

Directory-backed tools exclude withdrawn biobanks/collections by default.
Directory cache directories are schema-qualified (`directory-ERIC`, `directory-BBMRI-EU`, ...). Cache purging for `directory` must affect only the currently selected schema cache; target-URL separation is still not provided.

For `data-check.py` and similar read/check entrypoints, non-`ERIC` staging schemas must be selected only after authentication. The user-facing behavior should be:
- read credentials from CLI or `.env`
- fail early with a clear input/configuration error if a non-`ERIC` schema is requested without credentials
- authenticate first, then set the target schema, so private staging areas do not fail with a misleading low-level schema-not-found exception
- treat quality-info tables as optional for non-`ERIC` schemas and degrade to empty DataFrames instead of failing when those tables are absent

Collection withdrawal is logically inherited:
- withdrawn collection -> withdrawn
- biobank withdrawn -> all child collections treated as withdrawn
- ancestor collection withdrawn -> descendant collection treated as withdrawn

Use:
- `-w` / `--include-withdrawn` to include withdrawn content
- `--only-withdrawn` to restrict the run to withdrawn content

Node/staging-area scope and reported country must stay distinct:
- `Directory.get*NN(...)` is for BBMRI node / staging-area routing and workbook grouping, derived from entity IDs via `nncontacts.py`
- `Directory.get*Country(...)` is for actual reported country values
- non-member biobanks hosted in countries such as `US` or `VN` must still route/group under `EXT`, not under country-specific tabs
