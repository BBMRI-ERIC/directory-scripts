# Data quality checks

`data-check.py` is the repository's primary tool. It loads the Directory,
runs checks from `checks/`, and writes warnings to stdout and optionally XLSX.

## Data-quality framework and Data Manager Manual

The executable framework in this repository and the published
[BBMRI-ERIC Directory Data Manager's Manual](https://zenodo.org/doi/10.5281/zenodo.2583446)
serve different, connected purposes. The manual is also available through the
[Help page in the BBMRI-ERIC Directory](https://directory.bbmri-eric.eu/ERIC/pages/#/Help),
which is the normal public entry point.

- `data-check.py`, the plugins in `checks/`, and their tests define and execute
  the actual validation behavior. The implementation is authoritative for what
  is checked, which warning IDs are emitted, and which fix proposals are
  generated.
- The Data Manager Manual explains the Directory fields and the checks to data
  managers. Its "Data quality framework" chapter is generated from plugin code
  and `CHECK_DOCS` metadata, then combined with reviewed manual overrides.
- The documentation generator also adds references from Directory attributes
  in the manual to the checks that use them. This connects field-entry guidance
  with the relevant validation rules.
- The manual does not run checks or modify Directory data. Conversely, adding
  or changing a check here does not update the published manual automatically.

When check behavior, warning text, fields, severity, or remediation guidance
changes, update the implementation and `CHECK_DOCS` here, regenerate the manual
from the sibling `BBMRI-ERIC-Directory-Data-Manager-Manual` repository, inspect
the generated chapter and field references, and only then synchronize the
reviewed manual sources and publish the updated PDF. For BBMRI-ERIC internal
editors, the
[Overleaf authoring project](https://www.overleaf.com/project/697dfc6afe719b05d2c3c35b)
is used to maintain and synchronize the manual sources; access is restricted to
authorized collaborators.

## Running checks

Run the default suite:

```bash
python3 data-check.py
```

Purge all QC caches and write an XLSX report:

```bash
python3 data-check.py --purge-all-caches -X results.xlsx
```

Refresh only the Directory cache and suppress normal stdout:

```bash
python3 data-check.py -v --purge-cache directory -N -X results.xlsx
```

Inspect only withdrawn content:

```bash
python3 data-check.py --only-withdrawn -X withdrawn.xlsx
```

Enable ORPHA/ICD-10 crosswalk checks:

```bash
python3 data-check.py -O en_product1.xml
```

Use `--disable-checks-all-remote` or `--disable-checks-remote emails` when
remote validation must be disabled. Local syntax, placeholder-domain, and
country-suffix email checks remain active.

For common authentication, cache, scope, and emergency options, see
[Setup and common operation](setup.md).

## Warning suppressions

Reviewed false positives can be recorded in `warning-suppressions.json`. The
recommended structured entries contain `check_id`, `entity_id`, optional
`entity_type`, warning/fix suppression flags, a reason, ownership metadata, and
optional expiry or ticket information.

Manage entries through the CLI rather than editing them casually:

```bash
python3 warning-suppressions-manage.py list
python3 warning-suppressions-manage.py add --check-id FT:KAnonViolation \
  --entity-id ENTITY_ID --entity-type COLLECTION --reason "..." \
  --added-by USER
python3 warning-suppressions-manage.py validate
python3 warning-suppressions-manage.py prune-stale --dry-run
```

Suppressions can hide warnings, attached fix proposals, or both. Debug mode
lists suppressed warning IDs, entity IDs, and available reasons. Prefer fixing
a deterministic check over suppressing a reproducible logic error.

## QC-derived updates

Some warnings carry structured fix proposals. Export, inspect, dry-run, and
apply them with:

```bash
python3 data-check.py -U qc-updates.json -r -N
python3 qcheck-updater.py -i qc-updates.json -s BBMRI-CZ --list
python3 qcheck-updater.py -i qc-updates.json -s BBMRI-CZ -n --module AP
python3 qcheck-updater.py -i qc-updates.json -s BBMRI-CZ --module AP --force
```

Dry-run follows the same per-update review path as apply but stops before
writing. During interactive review, `y` approves, `n` skips, and `i` records the
proposal as a reviewed false positive. The updater verifies advisory checksums
and compares the live value with the value observed when the plan was created.

Apply updates only when the Directory staging area is the authoritative source.
If it is synchronized from another system, fix that primary system instead.

## Fact-sheet checks

Fact-sheet QC reports:

- presence and uniqueness of all-star aggregate rows
- presence, completeness, and duplication of all-but-one-star marginal rows
- individual marginal bounds against the all-star row
- exact all-star comparisons with collection sample and donor totals
- all-star comparisons with sample and donor order-of-magnitude intervals
- donor k-anonymity warnings using the current public-data baseline of `k=10`

Marginal rows are compared independently and are never summed to reconstruct a
collection total. The normative behavior is in the
[fact-sheet aggregation specification](../DEVELOPMENT.md#fact-sheet-aggregation-specification).

## AI-reviewed findings

Normal QC runs consume committed findings from `ai-check-cache/`; they do not
call a model. Deterministic regex and heuristic checks belong in normal plugins,
not in that cache. Use the repository's `run-ai-checks` skill only when a live,
model-assisted review and cache refresh is intentionally requested.

## Check documentation

Checks with non-obvious behavior carry `CHECK_DOCS` metadata in their plugin
source. After changing check behavior or metadata, regenerate and inspect the
[Directory Data Manager's Manual](https://zenodo.org/doi/10.5281/zenodo.2583446)
source output as described in
[DEVELOPMENT.md](../DEVELOPMENT.md#check-documentation-metadata).
