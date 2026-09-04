# Exporters and reports

Exporters are standalone `exporter-*.py` commands. Run each command with
`--help` for its complete option list. They share the authentication, caching,
withdrawn-scope, and logging conventions documented in
[Setup and common operation](setup.md).

## Exporter catalog

| Script | Summary |
|---|---|
| `exporter-all.py` | Export all major Directory entity classes and aggregate collection statistics. |
| `exporter-bbmri-cohorts.py` | Report BBMRI Cohorts network statistics and associated QC findings. |
| `exporter-cMDR.py` | Export study-linked biobanks and collections, including geospatial output. |
| `exporter-cohorts.py` | Export cohort and population-based collections. |
| `exporter-country.py` | Report biobank and collection counts by country. |
| `exporter-covid.py` | Export COVID-relevant collections and biobanks. |
| `exporter-ecraid.py` | Export collections and institutions relevant to ECRAID. |
| `exporter-fact-sheet-emulation.py` | Identify collection families that may historically emulate fact sheets and report migration candidates. |
| `exporter-institutions.py` | Export juridical persons grouped by country. |
| `exporter-mission-cancer.py` | Export cancer and pediatric-cancer collections. |
| `exporter-negotiator-orphans.py` | Analyze Negotiator representative coverage and assignment candidates. |
| `exporter-obesity.py` | Export obesity and pediatric-obesity collections. |
| `exporter-pediatric.py` | Export pediatric and pediatric-only collections. |
| `exporter-quality-label.py` | Export quality assessments for biobanks and collections. |

## Exporter details

### `exporter-all.py`

- **Purpose:** Produce the broadest tabular export of Directory content and a
  high-level inventory of the selected scope.
- **Output:** Stdout entity listings and totals; XLSX sheets for `Biobanks`,
  `Collections`, `Services`, `Studies`, `Contacts`, and `Networks`. Entity IDs
  in the workbook link to the corresponding Directory web view.
- **Selection:** Active entities by default. Collection-type and material-type
  filters are available. `-w`, `--only-withdrawn`,
  `--include-withdrawn-sheets-in-output`, and `--output-xlsx-withdrawn` control
  withdrawn output.

```bash
python3 exporter-all.py -X all.xlsx
python3 exporter-all.py -w --include-withdrawn-sheets-in-output -X all.xlsx
```

Excel limits a cell to 32,767 characters. Long values are truncated by the
shared XLSX writer; verbose mode identifies affected cells and debug mode shows
the original and resulting values.

Excel also limits each worksheet to 65,530 hyperlinks. The shared writer
creates explicit links up to that limit, leaves additional display cells as
plain text, and emits one summary warning instead of thousands of per-cell
warnings.

### `exporter-bbmri-cohorts.py`

- **Purpose:** Analyze biobanks and collections participating in the BBMRI
  Cohorts networks.
- **Output:** Network/entity/country aggregates, collection facts and sample
  statistics, optional warning details, a statistics workbook, and an optional
  QC warning workbook.
- **Selection:** Aggregation dimensions can be selected with `--aggregator`.
  Plugin and remote-check controls allow the QC part of the run to be narrowed.

```bash
python3 exporter-bbmri-cohorts.py \
  -X bbmri-cohorts-stats.xlsx \
  -XWE bbmri-cohorts-warnings.xlsx
```

### `exporter-cMDR.py`

- **Purpose:** Show Directory study/trial linkage in both directions: from
  collections to studies and from studies to collections and biobanks.
- **Output:** Country-grouped text with per-country totals; XLSX `Biobanks`,
  `Collections`, and `Studies` sheets; optional GeoJSON point features.
- **Selection:** Only entities participating in at least one collection-study
  link are exported. GeoJSON uses entity coordinates where available and falls
  back to the parent biobank coordinates.

```bash
python3 exporter-cMDR.py -X cMDR.xlsx
python3 exporter-cMDR.py -G cMDR-map.geojson
```

### `exporter-cohorts.py`

- **Purpose:** Inventory `COHORT` and `POPULATION_BASED` collections.
- **Output:** Collection listings, countries, biobank/collection totals,
  explicit sample/donor totals, OoM-assisted estimates, and XLSX tables.
- **Selection:** Count totals use top-level collections to avoid double-counting
  holdings also represented by subcollections.

```bash
python3 exporter-cohorts.py -X cohorts.xlsx
```

### `exporter-country.py`

- **Purpose:** Provide a compact country-level overview of Directory coverage.
- **Output:** Biobank and collection counts by country, optional XLSX output,
  and fact-sheet summary tables for the selected collections.
- **Selection:** Uses the shared Directory schema and withdrawn-scope options.

```bash
python3 exporter-country.py
python3 exporter-country.py -X countries.xlsx
```

### `exporter-covid.py`

- **Purpose:** Identify collections relevant to COVID-19 through diagnoses,
  control/prospective characteristics, and COVID network membership.
- **Output:** Existing-sample, COVID-only, control, prospective, and other
  relevant collection groups; biobank counts; explicit and OoM-assisted sample
  and donor totals; XLSX tables.
- **Selection:** Uses structured Directory content rather than a free-text-only
  search.

```bash
python3 exporter-covid.py -X covid.xlsx
```

### `exporter-ecraid.py`

- **Purpose:** Identify collections and institutions relevant to ECRAID.
- **Output:** Separate BSL-2/BSL-3 and pathogen-material collection groups,
  participating biobank totals, fact-sheet summaries, and XLSX tables.
- **Selection:** Based on Directory biosafety and pathogen-related material
  metadata.

```bash
python3 exporter-ecraid.py -X ecraid.xlsx
```

### `exporter-fact-sheet-emulation.py`

- **Purpose:** Find sibling or conservatively grouped top-level collection
  families that may be historical substitutes for fact-sheet dimensions rather
  than genuinely different operational collections. The analysis is
  deterministic and read-only; it does not collapse collections or create
  updater payloads.
- **Output:** Text output groups candidate families by country and reports
  confidence, migration readiness, source IDs, blockers, and country/biobank
  totals. `-X` writes an XLSX workbook with `Candidate families`,
  `Source collections`, `Field comparison`, `Proposed facts`,
  `Unrepresentable data`, `Migration mapping`, `Dimension candidates`, and
  `Dimension values` sheets. `--advanced-reporting` additionally includes the
  verbose `Boundary evidence` diagnostic sheet. Entity IDs in the workbook
  link to the Directory web view.
- **Selection and options:** `--scope all` (default) considers sibling and
  conservative top-level families; `--scope siblings` or `--scope top-level`
  narrows the analysis. `--min-confidence low|medium|high` filters the
  deterministic result. `-c`/`--country` accepts one or more country codes.
  Shared authentication, schema, withdrawn-scope, cache, logging, `-X`, and
  `-N` options work as described in [Setup and common operation](setup.md).
- **Read-only and statistical warnings:** The exporter reports possible
  migration targets, but never edits Directory data and never invokes
  `qcheck-updater.py`. Exact source counts are evidence only. It does not sum
  source collections, fact rows, marginal rows, or order-of-magnitude values
  to manufacture totals. Missing values reduce confidence; conflicting
  operational values and conflicting populated descriptions block automatic
  migration. A schema-coupled `IMAGE` type difference caused only by
  `body_part_examined` is reported as an exception, not treated as proof of
  operational independence.
- **Proposed fact semantics:** Each eligible source collection aggregate is
  copied unchanged into an all-but-one-star row of the target collection. The
  split dimension is fixed and every other fact dimension is `*`. If multiple
  dimensions each form a complete one-to-one mapping, each gets an independent
  set of marginal rows. Never add proposed rows within or across dimensions.
  Incomplete, multi-valued, or duplicate mappings are not summed, and the
  exporter does not propose no-star intersections or target all-star totals.
  A missing target ID remains a migration blocker but does not hide an
  otherwise unambiguous advisory marginal preview.
- **How families are discovered:** The primary deterministic rule finds at
  least two collections within the same parent or biobank whose non-dimension
  metadata is exactly equivalent while current fact-sheet dimensions vary.
  IDs, names, descriptions, counts, order-of-magnitude values, and
  administrative timestamps are excluded from required equality, but names,
  IDs, and descriptions remain important contextual evidence. Differently
  named diagnosis partitions require an additional informative anchor, such as
  a specific ID series or a description that differs only around diagnosis.
  A shared biobank, generic material, or placeholder description is not enough.
- **Description and boundary evidence:** Descriptions are classified as
  informative-equal, dimension-derived difference,
  operational-boundary difference, placeholder/uninformative, or ambiguous.
  The analysis compares the differing sentence or bounded snippet, not merely
  keyword presence. Phase, wave, round, visit, baseline, follow-up,
  re-examination, eligibility/inclusion/exclusion criteria, pilot/site,
  recruitment or collection period, prospective/retrospective,
  autopsy/post-mortem, intervention, and acquisition language can indicate
  separate operational collections when their member-specific qualifiers
  differ. Shared study background is neutral; ambiguous uses such as disease
  stage, laboratory phase, or anatomical “part” are sent for review.
- **Review-only and exclusions:** Anatomy, organ, imaging modality,
  timepoint, recruitment site, data category, and similar partitions are
  reported as future-dimension candidates or `review-only` families unless the
  current schema and operational evidence support them. Scientific-question,
  data-element, and variable catalogues are not fact-sheet families merely
  because their collections look systematically named. Operational conflicts,
  missing comparison fields, unsupported dimensions, ambiguous values, and
  missing source mappings block migration readiness even when emulation
  confidence is high. Diagnosis previews are additionally blocked for
  multi-valued, incomplete, duplicated, or coarse-range mappings and for
  negated/control descriptions.
- **Audit and interpretation:** Results expose the discovery rule, family
  boundary, identity anchor, varied dimensions, field comparison states,
  description state, marker/qualifier and bounded evidence snippet, conflicts,
  unknowns, unsupported dimensions, abstention reason, confidence, readiness,
  and provenance. Treat these as review evidence, not an automatic instruction
  to collapse collections. A family may be a strong historical fact-sheet
  substitute while still being unsafe to migrate.
- **AI review workflow:** `--ai-review-prefix PREFIX` writes
  `PREFIX-ai-review.json` and `PREFIX-ai-review.md`. Both contain the same
  bounded suspect cases, field-level evidence, unresolved data, explicit
  review questions, and the expected JSON response schema. Feed either packet
  to a chatbot, Codex, or an API as an advisory review task. The AI must
  classify each family, explain the evidence, identify future dimensions, and
  list required follow-up; its response must be reviewed by an expert and is
  not an executable Directory update. Individual prompt strings longer than
  1,000 characters retain bounded leading and trailing evidence together with
  their original length and checksum; long sequences are similarly bounded so
  packets remain practical to review.
  Identical and universally unknown fields are summarized by role; detailed
  rows are retained for variation, conflict, and partial missingness.
  For direct model input, prefer country-scoped packets via `-c`; an unfiltered
  all-country packet is an archival review dataset and may exceed a model
  upload or context limit even though individual evidence values are bounded.

```bash
# Report all candidate families using the shared Directory cache when possible.
python3 exporter-fact-sheet-emulation.py -v

# Produce the analysis workbook and prompt-ready JSON/Markdown review packets.
python3 exporter-fact-sheet-emulation.py \
  -c AT UK \
  -X fact-sheet-emulation.xlsx \
  --ai-review-prefix fact-sheet-emulation

# Run offline against an already populated cache and suppress normal stdout.
python3 exporter-fact-sheet-emulation.py \
  --no-stdout \
  -X fact-sheet-emulation.xlsx

# Add the verbose boundary-evidence worksheet for diagnostic review.
python3 exporter-fact-sheet-emulation.py \
  --no-stdout \
  --advanced-reporting \
  -X fact-sheet-emulation-advanced.xlsx
```

### `exporter-institutions.py`

- **Purpose:** Extract the juridical persons responsible for Directory
  biobanks.
- **Output:** Country-grouped stdout listings and one XLSX `Institutions` sheet.
- **Selection:** Institutions are deduplicated within the selected Directory
  and withdrawn scope.

```bash
python3 exporter-institutions.py -X institutions.xlsx
```

### `exporter-mission-cancer.py`

- **Purpose:** Analyze cancer-relevant and pediatric-cancer Directory holdings.
- **Output:** Cancer-only, cancer-control, prospective, pediatric, and
  pediatric-only collection groups; country/institution/biobank totals;
  explicit and OoM-assisted sample/donor estimates; XLSX and fact-sheet tables.
- **Selection:** Uses ICD-10 cancer ranges and ORPHA mappings. Supply current
  Orphadata mappings with `-O` for reproducible ORPHA classification.

```bash
python3 exporter-mission-cancer.py \
  -O en_product1.xml -X mission-cancer.xlsx
```

### `exporter-negotiator-orphans.py`

- **Purpose:** Compare a Negotiator representative workbook with Directory
  collections and identify missing representative assignments.
- **Output:** TSV-style stdout plus XLSX collection, biobank, and national-node
  summaries, including safe parent/biobank auto-assignment candidates.
- **Input:** Requires the current Negotiator representative XLSX as a positional
  argument. The script reports all input rows and marks withdrawn entities.

```bash
python3 exporter-negotiator-orphans.py representatives.xlsx \
  -X negotiator-orphans.xlsx
```

### `exporter-obesity.py`

- **Purpose:** Analyze obesity-relevant collections and their pediatric
  subsets.
- **Output:** Obesity, pediatric-obesity, and pediatric-only obesity groups;
  biobank totals; explicit and OoM-assisted sample/donor totals; XLSX and
  fact-sheet tables.
- **Selection:** Uses obesity diagnosis mappings and age metadata. `-O` can
  select the Orphadata mapping file.

```bash
python3 exporter-obesity.py -O en_product1.xml -X obesity.xlsx
```

### `exporter-pediatric.py`

- **Purpose:** Analyze pediatric-relevant and pediatric-only collections from
  collection age ranges.
- **Output:** Collection and biobank totals, explicit sample/donor totals,
  OoM-assisted sample estimates, XLSX tables, and fact-sheet summaries.
- **Selection:** Distinguishes collections containing pediatric ages from those
  whose represented age range is exclusively pediatric. `-O` selects the
  optional Orphadata mapping file used by shared diagnosis logic.

```bash
python3 exporter-pediatric.py -X pediatric.xlsx
```

### `exporter-quality-label.py`

- **Purpose:** Export quality-standard assessments attached to biobanks and
  collections.
- **Output:** XLSX `Biobanks`, `Collections`, and `CombinedQuality` sheets. The
  default filename is `QualityLabelsExporter.xlsx`.
- **Selection:** Supports shared withdrawn scope and a separate
  `--output-xlsx-withdrawn` workbook. Quality information and
  `DirectoryOntologies/QualityStandards` use the cache-first `directory.py` API,
  allowing offline reruns after the required caches have been populated.

```bash
python3 exporter-quality-label.py
python3 exporter-quality-label.py -w \
  --output-xlsx-withdrawn withdrawn-quality.xlsx
```

## Shared fact-sheet summaries

Collection-based exporters include shared fact-sheet summary sheets and stdout
statistics where applicable. Authoritative distributions use all-but-one-star
rows and retain one unambiguous contribution per collection, dimension, and
value. Marginal rows within one fact sheet are not additive.

The affected exporters are `exporter-all.py`, `exporter-bbmri-cohorts.py`,
`exporter-cMDR.py`, `exporter-cohorts.py`, `exporter-country.py`,
`exporter-covid.py`, `exporter-ecraid.py`, `exporter-mission-cancer.py`,
`exporter-obesity.py`, and `exporter-pediatric.py`.

An explicit unsafe fallback is available when all-but-one-star rows are absent:

```bash
python3 exporter-cohorts.py --allow-no-star-fact-sums -X cohorts.xlsx
```

The fallback sums fully concrete no-star rows for a missing marginal value.
Those rows may overlap or omit records, so the result may double-count or
undercount. Fallback values remain separately labelled and are never combined
with authoritative distributions, all-star totals, coverage claims, or
collection-level consistency comparisons.

Order-of-magnitude count estimates use the shared policy in `oomutils.py`. The
default point estimate is the lower interval bound (`10**n`). Set
`DIRECTORY_OOM_UPPER_BOUND_COEFFICIENT` to change that policy consistently for
exporters and statistics tools; for example, `0.3` uses
`0.3 * 10**(n+1)`. QC comparisons against OoM metadata use the interval itself
and are unaffected by this point-estimate setting.

See the normative
[fact-sheet aggregation specification](../DEVELOPMENT.md#fact-sheet-aggregation-specification).
