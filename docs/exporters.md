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
