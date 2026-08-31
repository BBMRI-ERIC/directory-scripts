# Fact-sheet aggregation specification

Status: Normative project specification (focused; no repository-wide specification-assurance baseline)

Provenance: user request, 2026-08-31

## Row classification

### FS-ROW-001: Tracked dimensions

Fact-sheet aggregation MUST use the tracked dimensions `sex`, `age_range`, `sample_type`, and `disease`.

### FS-ROW-002: Aggregate row classes

An all-star row MUST contain `*` in every tracked dimension. An all-but-one-star row MUST contain exactly one concrete tracked-dimension value and `*` in every other tracked dimension. A no-star fallback row MUST contain a concrete, non-empty, non-`*` value in every tracked dimension.

Rows with one or more missing tracked-dimension values MUST NOT be treated as no-star fallback rows.

## Authoritative reporting

### FS-AGG-001: Aggregation levels are non-additive

Sample and donor counts from all-star, all-but-one-star, and no-star rows MUST NOT be added across aggregation levels. Multiple all-but-one-star values within one fact sheet MUST NOT be summed to reconstruct an all-star total because values can overlap.

### FS-AGG-002: Authoritative marginal contribution

For one collection, dimension, and value, exactly one populated all-but-one-star row MUST be treated as the authoritative marginal contribution. If multiple matching all-but-one-star rows exist, the contribution MUST be treated as ambiguous and excluded from aggregate reporting.

### FS-AGG-003: Cross-collection aggregation

An exporter MAY sum one selected contribution per collection, dimension, and value across collections. It MUST retain the number of contributing collections and contribution provenance.

Authoritative all-but-one-star contributions and assumption-violating no-star fallback contributions MUST be reported as separate statistics. Their counts, observations, or contributing-collection totals MUST NOT be combined, even when they come from different collections.

## Unsafe no-star fallback

### FS-FALLBACK-001: Explicit opt-in

No-star fallback MUST be disabled by default. Collection-based exporters that expose fact-sheet distributions MUST provide the long option `--allow-no-star-fact-sums` to enable it.

Enabling the option MUST produce a visible warning explaining that no-star rows are not guaranteed to be disjoint or complete and that derived sums may double-count or undercount records.

### FS-FALLBACK-002: Per-missing-value substitution

When fallback is enabled and a collection has no matching all-but-one-star row for a dimension and value, the exporter MAY sum populated fully concrete no-star rows matching that value as an assumption-violating substitute.

Fallback MUST NOT be used when an authoritative all-but-one-star row exists or when multiple matching all-but-one-star rows make the contribution ambiguous. A collection MUST NOT contribute both authoritative and fallback counts to the same dimension and value. Fallback contributions MUST NOT be added to authoritative cross-collection distribution totals.

### FS-FALLBACK-003: No synthetic all-star totals

No-star fallback MUST NOT contribute to all-star sample totals, all-star donor totals, collection-level aggregate comparisons, or statistics claiming authoritative all-but-one-star coverage.

### FS-FALLBACK-004: Provenance

Stdout and XLSX distribution output MUST place authoritative all-but-one-star contributions and no-star fallback contributions in separate sections or tables. Summary output MUST state whether fallback was enabled and how many collections, values, and rows used it. When fallback is enabled, both stdout and XLSX output MUST contain a visible warning that no-star sums violate aggregation assumptions.

## Quality and consistency

### FS-QC-001: Aggregate-row presence

Fact-sheet statistics and QC MUST report whether a fact sheet containing at least one row has exactly one all-star row and whether it has all-but-one-star rows covering each concrete dimension value represented by any fact row, including a value represented only by no-star rows. A fact row is populated for count reporting when at least one sample or donor count is a non-boolean integer; zero is a populated count.

Missing and duplicate all-but-one-star rows MUST remain distinguishable.

### FS-QC-002: Individual marginal bounds

When exactly one all-star row is available, each individual all-but-one-star sample or donor count MUST NOT exceed the corresponding all-star count. Values within a dimension MUST NOT be summed for this comparison.

### FS-QC-003: Exact collection aggregates

When collection `size` or `number_of_donors` is an integer and the corresponding all-star count is an integer, QC MUST compare them for equality.

### FS-QC-004: Order-of-magnitude aggregates

When sample or donor order-of-magnitude metadata and the corresponding all-star count are available, QC MUST verify that the exact all-star count lies in the interval represented by the order of magnitude. This consistency check MUST use the interval itself, not the configurable point-estimate coefficient used for exporter totals.

## Verification

The implementation MUST have automated tests for row classification, fallback selection and exclusion, provenance, warning output, all-but-one presence and duplicate detection, individual marginal bounds, exact aggregate comparison, OoM interval comparison, directory statistics, and common exporter CLI wiring.
