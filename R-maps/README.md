# R Maps

This folder contains the active R-based Directory map pipeline.

For a narrative, RStudio-friendly walkthrough, open
[README.Rmd](README.Rmd). For runnable recipes, open the scripts in
[examples/](examples/).

## Supported Maps

Core maps:

- `bbmri-members-nolabels`
- `bbmri-members-labels`
- `bbmri-members-sized`
- `bbmri-members-OEC-all`

Extra maps:

- `global-nolabels`
- `global-labels`
- `global-sized`
- `covid-nolabels`
- `covid-labels`
- `covid-sized`
- `quality_maps-nolabels`
- `federated-platform`
- `CRC-cohort-sized`
- `rare-diseases-nolabels`
- `rare-diseases-labels`
- `rare-diseases-sized`
- `strategic-objectives`

Notes:
- `rare-diseases-nolabels` and `rare-diseases-labels` use fixed-size circles; only `rare-diseases-sized` scales circles by biobank size.
- global/covid country labels use a wider placement search on small/med variants to reduce overlap.

## Quick Start

Render all maps (default):

```bash
sh R-maps/export.sh
```

Render only the extra maps:

```bash
sh R-maps/export.sh global-nolabels global-labels global-sized covid-nolabels covid-labels covid-sized quality_maps-nolabels federated-platform CRC-cohort-sized rare-diseases-nolabels rare-diseases-labels rare-diseases-sized strategic-objectives
```

Render everything:

```bash
sh R-maps/export.sh
```

Render only specific maps:

```bash
sh R-maps/export.sh bbmri-members-OEC-all global-nolabels
```

Render a named set directly through the R runner:

```bash
Rscript R-maps/render_pilot_maps.R --map-set=core
Rscript R-maps/render_pilot_maps.R --map-set=extras
Rscript R-maps/render_pilot_maps.R --map-set=all
```

## How The Pipeline Works

`export.sh` drives `render_pilot_maps.R`.

If you prefer working interactively in RStudio, open `R-maps/README.Rmd` and
the scripts in `R-maps/examples/`. They show the same shared helpers that the
production renderers use, but in smaller recipe-sized pieces.

Shared inputs:

1. `geocoding_2022.py` writes the full pilot GeoJSON
2. helper prep scripts derive map-specific GeoJSONs when needed
3. renderer scripts write `small` / `med` / `big` PNG, PDF, and SVG outputs

`bbmri-members-OEC-all` uses a dedicated page size instead of the standard
landscape exporter sheet. The current target `med` page is approximately
`20.3 x 11.9 cm` (`2400 x 1400 px` at `300 dpi`, `4800 x 2800 px` at
`600 dpi` raster), with proportional `small` and `big` variants.

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
- `bbmri-directory-rare-diseases-pilot.geojson`
  Rare-disease subset derived from current Directory collections/networks

Biobank label-bearing maps strip the `bbmri-eric:ID:` prefix from the visible
label text. For `bbmri-members-sized`, a temporary overlap-tuning pass can be
requested with `--biobank-label-layout-variant=spread`; for a wider temporary
shim spread, use `--biobank-label-layout-variant=spreadwide`.

Strategic-objectives maps use the TOML scaffold at
`R-maps/data/strategic-objectives-template.toml`. The renderer can generate:

- per-SG recolor views
- per-SO recolor or bars views
- global recolor or bars views

The shared implementation lives in `R-maps/strategic_objectives_common.R` and
is intentionally sourceable from either the repository root or `R-maps/`
itself, so it can be explored directly in RStudio without shell wrappers.
The bundled example script renders an SO2-only subset so you can inspect the
three supported levels without needing the full objective matrix first.

## Data Sources

Generated from current Directory/cache state:

- `bbmri-members-nolabels`
- `bbmri-members-labels`
- `bbmri-members-sized`
- `bbmri-members-OEC-all`
- `global-nolabels`
- `global-labels`
- `global-sized`
- `covid-nolabels`
- `covid-labels`
- `covid-sized`
- `quality_maps-nolabels`
- `rare-diseases-nolabels`
- `rare-diseases-labels`
- `rare-diseases-sized`

Snapshot-backed local inputs:

- `R-maps/data/federated-platform.geojson`
- `R-maps/data/CRC-Cohort.geojson`
- `R-maps/data/CRC-Cohort-imaging.geojson`
- `R-maps/data/strategic-objectives-template.toml`

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

The standalone renderer defaults now point to the current pilot GeoJSON files:

- `bbmri-directory-pilot.geojson`
- `bbmri-directory-covid-pilot.geojson`
- `bbmri-directory-rare-diseases-pilot.geojson`

That makes the scripts runnable directly from RStudio without manual path
fixups.

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

```bash
Rscript R-maps/render_strategic_objectives.R \
  --input=/home/hopet/codex/directory-scripts/R-maps/data/strategic-objectives-template.toml \
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

```bash
./.venv-maps/bin/python R-maps/prepare_rare_diseases_geojson.py \
  --input=/home/hopet/codex/directory-scripts/bbmri-directory-pilot.geojson \
  --output=/home/hopet/codex/directory-scripts/bbmri-directory-rare-diseases-pilot.geojson
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
- `prepare_rare_diseases_geojson.py`
  Rare-disease GeoJSON derivation helper
- `prepare_strategic_objectives_spec.py`
  TOML/JSON normalization helper for strategic-objectives maps
- `render_pilot_maps.R`
  End-to-end runner used by `export.sh`
- `strategic-objectives-template.toml`
  Scaffold for future strategic-objectives visualization data
- `strategic_objectives_common.R`
  Shared helpers for SO/SG map data loading, summarization, and rendering
- `render_strategic_objectives.R`
  CLI entrypoint for strategic-objectives maps

## Outputs

Generated outputs go to `R-maps/pilot-output/` and include:

- `*-small.png`
- `*-med.png`
- `*-big.png`
- `*-small.pdf`
- `*-med.pdf`
- `*-big.pdf`
- `*-small.svg`
- `*-med.svg`
- `*-big.svg`
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
