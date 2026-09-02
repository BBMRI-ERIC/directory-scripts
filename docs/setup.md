# Setup and common operation

## Requirements

- Python 3
- Runtime dependencies from [`requirements.txt`](../requirements.txt)
- Test dependencies from [`requirements-test.txt`](../requirements-test.txt)

Install the runtime dependencies from the repository root:

```bash
python3 -m ensurepip
pip3 install -r requirements.txt
```

For development and testing, also install:

```bash
pip3 install -r requirements-test.txt
```

If Directory GraphQL requests fail after a server upgrade, update the EMX2
client:

```bash
pip3 install --upgrade molgenis-emx2-pyclient
```

Refresh root certificates when HTTPS certificate verification fails:

```bash
pip3 install --upgrade certifi
python3 install_certifi.py
```

DNS-dependent checks require a working resolver configuration, normally
`/etc/resolv.conf`. Do not replace a working system-managed configuration. On
minimal environments where the file is absent, configure it according to the
operating system or Termux installation.

After changing Python versions, reinstall `requirements.txt`. This restores
plugin dependencies such as `validate_email`. Older Yapsy releases may not be
compatible with newer Python versions; use the version constrained by this
repository first and consult upstream Yapsy if the interpreter reports import
errors.

ORPHA/ICD-10 crosswalk checks require an Orphadata `en_product1.xml` download.
Pass it to supporting tools with `-O`.

## Authentication

The public `ERIC` schema can normally be read anonymously. Private staging
schemas require credentials supplied through CLI options or a local `.env`:

```text
DIRECTORYTARGET=https://directory.bbmri-eric.eu
DIRECTORYUSERNAME=your-user
DIRECTORYPASSWORD=your-password
```

Keep credentials and diagnostic logs containing credentials out of version
control. If federated login is used in the browser, configure a local Directory
password for API access.

## Common CLI options

Options vary by script; use `--help` for the authoritative interface. Shared
conventions include:

- `-v` / `--verbose`: progress and operational detail
- `-d` / `--debug`: detailed diagnostics
- `-X` / `--output-xlsx`: XLSX output where supported
- `-N` / `--no-stdout`: suppress normal stdout output
- `-P` / `--schema`: select a Directory schema; read tools default to `ERIC`
- `-w` / `--include-withdrawn`: include withdrawn entities
- `--only-withdrawn`: restrict processing to withdrawn entities
- `--purge-cache NAME` / `--purge-all-caches`: discard selected caches
- `--suppress-validation-warnings`: hide non-fatal local validation warnings
- `--emergency-skip-dag-checks`: bypass hierarchy acyclicity checks at your own
  risk when malformed Directory relationships would otherwise stop a read-only
  task

The emergency option does not repair cycles. Hierarchy traversal and inherited
withdrawal results may be incomplete or unreliable while it is enabled.

## Cache behavior

Directory caches are schema-specific, for example
`data-check-cache/directory-ERIC` and
`data-check-cache/directory-BBMRI-EU`. They are not separated by target URL.
Purge the `directory` cache when switching a schema between Directory server
instances.

Read-only tools can reuse a complete cached schema while offline. If no complete
cache is available, they fail with a user-facing connectivity error. Quality
metadata and the `QualityStandards` ontology are cached through `directory.py`
as well. Schemas outside `ERIC` may omit quality-information tables; shared
tools treat those tables as optional rather than failing the whole operation.

Cache availability differs by tool:

- read-only exporters expose the `directory` cache
- `full-text-search.py` exposes `directory` and `index`
- `geocoding_2022.py` exposes `directory` and `geocoding`
- `data-check.py` exposes the full QC cache and plugin-control surface

Scoped input validation covers repository-owned configuration and JSON/cache
artifacts. Non-fatal issues are reported as validation warnings and may be
hidden with `--suppress-validation-warnings`; live Directory entities continue
to use explicit runtime checks and the normal QC framework.

## Entity scope

Directory-backed tools exclude withdrawn biobanks and collections by default.
A collection is logically withdrawn if the collection, its parent biobank, or
an ancestor collection is withdrawn.

Node/staging-area grouping is derived from entity IDs and differs from reported
country. For example, a non-member biobank in the `EXT` staging area remains in
the `EXT` node group even if its reported country is `US`.
