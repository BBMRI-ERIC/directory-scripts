# R Maps

This folder contains the active R-based Directory map pipeline.

## Supported Maps

Core maps:

- `bbmri-members-nolabels`
- `bbmri-members-sized`
- `bbmri-members-OEC-all`

Extra maps:

- `global-nolabels`
- `covid-nolabels`
- `quality_maps-nolabels`
- `federated-platform`
- `CRC-cohort-sized`

## Quick Start

Render the core maps:

```bash
bash R-maps/export-all.sh
```

Render only the extra maps:

```bash
bash R-maps/export-all.sh --map-set extras
```

Render everything:

```bash
bash R-maps/export-all.sh --map-set all
```

## How The Pipeline Works

`export-all.sh` drives `render_pilot_maps.R`.

Shared inputs:

1. `geocoding_2022.py` writes the full pilot GeoJSON
2. helper prep scripts derive map-specific GeoJSONs when needed
3. renderer scripts write `small` / `med` / `big` PNG and PDF outputs

`geocoding_2022.py` is expected to be cache-backed for both Directory data and
live geocoding. Only entities still missing usable coordinates should trigger a
live geocoder lookup, and successful or stable negative lookup results should
be written into the shared global geocoding cache for reuse on later runs.

Derived GeoJSONs:

- `bbmri-directory-pilot.geojson`
  Full Directory biobank point export from `geocoding_2022.py`
- `bbmri-directory-members-pilot.geojson`
  Member/observer subset for `bbmri-members-OEC-all`
- `bbmri-directory-covid-pilot.geojson`
  COVID subset derived from the full pilot GeoJSON plus live Directory network metadata
- `bbmri-directory-quality-pilot.geojson`
  Quality-map points derived from current Directory quality metadata

## Data Sources

Generated from current Directory/cache state:

- `bbmri-members-nolabels`
- `bbmri-members-sized`
- `bbmri-members-OEC-all`
- `global-nolabels`
- `covid-nolabels`
- `quality_maps-nolabels`

Snapshot-backed local inputs:

- `R-maps/data/federated-platform.geojson`
- `R-maps/data/CRC-Cohort.geojson`
- `R-maps/data/CRC-Cohort-imaging.geojson`

OEC overlays:

- `R-maps/data/IARC.geojson`
- `R-maps/data/HQlineNN.geojson`
- `R-maps/data/onlyLinesHQlineNN.geojson`

## Direct Commands

Render one map directly:

```bash
Rscript R-maps/render_global_nolabels.R \
  --input=/home/hopet/codex/directory-scripts/bbmri-directory-pilot.geojson \
  --iarc=/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

```bash
Rscript R-maps/render_quality_maps_nolabels.R \
  --input=/home/hopet/codex/directory-scripts/bbmri-directory-quality-pilot.geojson \
  --iarc=/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

```bash
Rscript R-maps/render_federated_platform.R \
  --input=/home/hopet/codex/directory-scripts/R-maps/data/federated-platform.geojson \
  --iarc=/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

Prep helpers can also be run directly:

```bash
./.venv-maps/bin/python R-maps/prepare_covid_geojson.py \
  --input=/home/hopet/codex/directory-scripts/bbmri-directory-pilot.geojson \
  --output=/home/hopet/codex/directory-scripts/bbmri-directory-covid-pilot.geojson
```

```bash
./.venv-maps/bin/python R-maps/prepare_quality_geojson.py \
  --output=/home/hopet/codex/directory-scripts/bbmri-directory-quality-pilot.geojson
```

## Important Files

- `map_config.R`
  Central map configuration: bboxes, export sizes, palettes, country groups, and inset settings
- `map_common.R`
  Shared helpers for Natural Earth loading, projections, label placement, and output export
- `prepare_covid_geojson.py`
  COVID subset derivation helper
- `prepare_quality_geojson.py`
  Quality-map GeoJSON derivation helper
- `render_pilot_maps.R`
  End-to-end runner used by `export-all.sh`

## Outputs

Generated outputs go to `R-maps/pilot-output/` and include:

- `*-small.png`
- `*-med.png`
- `*-big.png`
- `*-small.pdf`
- `*-med.pdf`
- `*-big.pdf`
- `<prefix>.pdf`
- `<prefix>.svg` when `svglite` is available

Generated output and derived pilot GeoJSON files are ignored by Git.

## Dependencies

Required R packages include:

- `ggplot2`
- `sf`
- `cowplot`
- `ggrepel`
- `svglite`

Optional:

- `shadowtext`

The renderers automatically prepend `R-maps/r-lib` to `.libPaths()` if that
directory exists.

To install `shadowtext` locally:

```bash
sudo apt-get update
sudo apt-get install -y \
  build-essential \
  pkg-config \
  libfontconfig1-dev \
  libfreetype6-dev \
  libcairo2-dev
mkdir -p R-maps/r-lib
Rscript -e '.libPaths(c(normalizePath("R-maps/r-lib", mustWork = TRUE), .libPaths())); install.packages("shadowtext", repos = "https://cloud.r-project.org")'
```

## Further Guidance

Use these folder-local files for deeper maintenance guidance:

- [AGENTS.md](/home/hopet/codex/directory-scripts/R-maps/AGENTS.md)
- [SKILLS.md](/home/hopet/codex/directory-scripts/R-maps/SKILLS.md)
- [TRANSFER.md](/home/hopet/codex/directory-scripts/R-maps/TRANSFER.md)
