# Reusable Python libraries

Scripts remain runnable directly from the cloned repository. Shared behavior is
implemented in top-level modules so commands and checks use the same Directory
cache, entity semantics, validation, and output rules without installing this
repository as a package.

## Directory access and identity

- `geocoding_utils.py`: importable coordinate precedence, authoritative local
  location inputs, address-cache provenance, institution-research packets and
  reconciled statistics; used by `geocoding.py`. See [map workflows](maps.md).

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

### Software, model and vocabulary versions

Inspect versions without loading biobanks, collections or other entity records:

```python
from directory import get_directory_versions, compare_directory_versions

versions = get_directory_versions()
print(versions["software"])
print(versions["model"])
print(versions["vocabularies"])

comparison = compare_directory_versions(
    expected_software_commit="573baa460ebed8ac8d3af37b22124ff7f7be96de",
    expected_model_commit="0aac60c44c68ff1733c3d10f3669ec9967951872",
)
print(comparison["comparisons"]["software"])
print(comparison["comparisons"]["schema"])
print(comparison["comparisons"]["vocabularies"])
print(comparison["model_overall"])
```

These example SHAs are fixed reference points, not automatically current
production versions. Supply the commits against which your application was
developed. Software releases and schema/vocabulary migrations are independent:
a software commit cannot establish the installed model or vocabulary revision.

Both functions accept `directory_url`, `schema`, `username`, `password`, `token`,
`refresh`, `offline` and `ontology_tables`. Credentials are explicit for private
schemas and are never stored or sent to GitHub. Existing `Directory` instances
offer `getVersions(**options)` and
`compareVersions(software_commit, model_commit, **options)` using their configured
target/schema. They require explicit credentials for private live metadata reads;
they do not retain the credentials used to load entity data. Prefer the standalone
functions when only version information is needed.

- `ontology_tables=None` (default) discovers all vocabularies referenced by the
  selected schema, including transitive references between ontology tables.
- An explicit tuple, such as `("DataCategories", "ServiceTypes")`, inspects only
  those vocabularies. An empty tuple inspects model metadata only. Restricted
  results never claim whole-model equality: inspect `model_overall.scoped_status`.
- `refresh=True` (default) attempts a fresh Directory observation. A failed or
  partial refresh retains a usable previous snapshot, marks `cache_fallback`
  and records the refresh diagnostic. Reference and software observation times
  remain separate.
- `refresh=False` uses a usable metadata cache first. `offline=True` forbids both
  Directory and GitHub requests, including when `refresh=True` is supplied. Warm
  the exact target/schema/scope and required source caches online first.

Results are dictionaries suitable for JSON serialization. `software` contains
the reported release/commit and a commit link. Inspection preserves a short
reported commit honestly; comparison resolves it to an immutable full SHA.
`model.reported_commit` remains null when the server exposes no deployment
commit. Model and vocabulary fingerprints are content evidence, not proof that
a particular migration was deployed.

Component comparisons return `older`, `equal`, `newer`, `diverged` or `unknown`.
Software direction uses Git ancestry. Schema/vocabulary direction uses matching
source contents and ancestry, independently of the binary. `model_overall` may
also be `mixed` when assessed schema/vocabulary migrations point in opposing
directions. An unknown component prevents an unqualified overall conclusion;
available components are still returned.

Schema comparison assesses business column types, required/key flags and
references. Descriptions, defaults, validation and read-only properties are not
assessed. Missing observed properties are listed in `missing_properties` and
make that schema comparison unknown: omitted flags are not silently treated as
false. The production API currently omits some of these flags. Ontology schema
comparison covers definitions explicitly present in the source model CSV;
software-generated ontology definitions remain unverified. Vocabulary comparison
includes custom business properties, excluding runtime `mg_*`, display `order`
and derived inverse references. Missing or unsupported components remain unknown.

Comparison uses pinned files in `molgenis/molgenis-emx2` (public ERIC model or
staging-area model, plus ontology contents). Exact assessed-content equality
needs no history search. Otherwise it searches file history, including renames,
at an independent upstream `master` tip. It records that immutable tip and lookup
time; the tip is not a deployment claim. Freeze `history_tip` to a full SHA for
repeatable searches. `max_history_versions=100` bounds each file search; capped,
incomplete or ambiguous reverted histories remain unknown. History scans can
require many GitHub requests, and rate limits are reported as unknown evidence.

Metadata caches live under `data-check-cache/directory-metadata-v1` and include
target URL and schema in their identity. GitHub sources use the separate
`data-check-cache/directory-version-sources` cache by default; override with
`source_cache_dir=Path(...)`. `DIRECTORY_CACHE_ROOT` relocates the default caches.
No entity cache is purged or loaded. An offline repeat can use:

```python
cached = compare_directory_versions(
    "573baa460ebed8ac8d3af37b22124ff7f7be96de",
    "0aac60c44c68ff1733c3d10f3669ec9967951872",
    offline=True,
)
```

These APIs return evidence, not per-entity QC findings or a compatibility policy.
Existing QC one-message version reporting remains unchanged.

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

## Single-purpose auxiliary tools

EOSC identity matching and its workbook/review helpers live together in
`eosc-organisation-matcher.py`, not in shared library modules. See the
[EOSC matcher guide](eosc-organisation-matcher.md) for the incremental operator
workflow. Registry decisions and human approval are separate from membership
eligibility and the current biobank inventory.

## Module contracts

Public APIs and behavioral constraints are maintained in
[DEVELOPMENT.md](../DEVELOPMENT.md). Non-negotiable change rules are summarized
in [AGENTS.md](../AGENTS.md). User-facing commands belong in the relevant guide
under `docs/`, not in library docstrings or implementation specifications.
