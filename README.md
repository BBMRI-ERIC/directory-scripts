# BBMRI-ERIC Directory Scripts

This repository contains the BBMRI-ERIC Directory data-quality checker and a
collection of exporters, reports, map generators, maintenance tools, analyses,
and reusable Python libraries built around the Directory.

The original and primary entry point is the data-quality checker:

```bash
python3 data-check.py
```

## Quick Start

```bash
pip3 install -r requirements.txt
python3 data-check.py
```

For authentication, cache behavior, Python compatibility, and common command
line options, see [Setup and common operation](docs/setup.md).

## Tool Families

| Family | Main entry points | Documentation |
|---|---|---|
| Data quality | `data-check.py`, `checks/`, `qcheck-updater.py` | [Data quality](docs/data-quality.md) |
| Exports and reports | `exporter-*.py` | [Exporters](docs/exporters.md) |
| Maps and geospatial output | `geocoding_2022.py`, `R-maps/` | [Maps](docs/maps.md) |
| Data maintenance and synchronization | `directory-tables-modifier.py`, updater/importer/sync tools | [Maintenance tools](docs/maintenance-tools.md) |
| Auxiliary analyses and utilities | `survey-so2-directory.py`, search, statistics, conversion helpers | [Auxiliary tools](docs/auxiliary-tools.md) |
| Reusable Python modules | `directory.py` and focused helper modules | [Libraries](docs/libraries.md) |

## Common Examples

Run the default quality checks and write an XLSX report:

```bash
python3 data-check.py -X results.xlsx
```

Export the main Directory entities:

```bash
python3 exporter-all.py -X directory.xlsx
```

Generate the GeoJSON used by the map framework:

```bash
python3 geocoding_2022.py geocoding.config -o bbmri-directory-geojson
```

Every CLI provides its authoritative option list through `-h` or `--help`.

## Documentation Model

- `docs/` is user-facing documentation: installation, commands, inputs,
  outputs, examples, and operational safety warnings.
- [DEVELOPMENT.md](DEVELOPMENT.md) contains architecture and detailed
  functionality specifications for maintainers.
- [AGENTS.md](AGENTS.md) contains concise, non-negotiable implementation
  guardrails derived from those specifications.
- [R-maps/README.md](R-maps/README.md) contains the detailed R map workflow.

User documentation explains how to operate the current implementation. It is
not the canonical location for internal behavioral contracts.

## Development

Install test dependencies and run the suite:

```bash
pip3 install -r requirements-test.txt
pytest -q
```

See [DEVELOPMENT.md](DEVELOPMENT.md) for architecture, module boundaries,
testing expectations, and functionality specifications.
