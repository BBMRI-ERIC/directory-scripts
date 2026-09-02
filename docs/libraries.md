# Reusable Python libraries

Scripts remain runnable directly from the cloned repository. Shared behavior is
implemented in top-level modules so commands and checks use the same Directory
cache, entity semantics, validation, and output rules without installing this
repository as a package.

## Directory access and identity

- `directory.py`: cache-first Directory loading, entity graphs, traversal,
  quality metadata, facts, and scope-aware accessors
- `directory_session_compat.py`: context-managed EMX2 client compatibility for
  write-capable tools
- `nncontacts.py`: node contacts, staging-area parsing, member-area rules, and
  escalation routing
- `contact_assignment_utils.py`: shared contact ownership and institution
  evidence helpers

Use `directory.py` rather than making ad hoc Directory API calls in scripts.
Keep node/staging-area identity separate from reported country.

## CLI, validation, and interruption handling

- `cli_common.py`: shared argument groups, logging, authentication, cache, schema,
  withdrawn scope, and Directory construction
- `cli_interrupts.py`: consistent Ctrl+C handling for interactive CLIs
- `validation_models.py`: lightweight structured validation models
- `validation_helpers.py`: non-fatal validation warning adapters

## Quality checks and fix plans

- `customwarnings.py`: warning levels, entity types, and warning records
- `warningscontainer.py`: warning collection, suppression, stdout, and XLSX output
- `warning_suppressions.py`: suppression loading, normalization, and diagnostics
- `fix_proposals.py`: structured fix proposals and checksummed update-plan JSON
- `check_fix_helpers.py`: shared check-side proposal construction
- `ai_cache.py`: validated, checksum-aware loading of committed AI-reviewed
  findings
- `text_consistency.py`: deterministic narrative-to-structure rules
- `duo_terms.py`: reviewed DUO metadata used in human-readable proposals

## Fact sheets and statistics

- `fact_sheet_utils.py`: row classification, values, completeness, bounds, and
  aggregate comparisons
- `fact_sheet_summary.py`: non-additive exporter summaries and explicit unsafe
  no-star fallback handling
- `fact_descriptor_sync.py`: collection descriptor derivation and comparison
- `directory_stats_utils.py`: per-biobank statistics shared by reports
- `k_anonymity.py`: canonical `0 < value < k` policy
- `oomutils.py`: shared order-of-magnitude intervals and point estimates

The detailed fact-sheet contract is in
[DEVELOPMENT.md](../DEVELOPMENT.md#fact-sheet-aggregation-specification).

## Ontologies and tabular output

- `orphacodes.py`: ORPHA/ICD-10 crosswalk parsing and mapping types
- `icd10codeshelper.py`: ICD-10 ranges and domain classification helpers
- `pddfutils.py`: shared pandas reshaping, flattening, and sorting
- `xlsxutils.py`: Excel-safe dataframe writing, long-cell truncation diagnostics,
  and hyperlinks
- `geojsonutils.py`: coordinate parsing and GeoJSON FeatureCollection writing

## Module contracts

Public APIs and behavioral constraints are maintained in
[DEVELOPMENT.md](../DEVELOPMENT.md). Non-negotiable change rules are summarized
in [AGENTS.md](../AGENTS.md). User-facing commands belong in the relevant guide
under `docs/`, not in library docstrings or implementation specifications.
