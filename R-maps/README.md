# R Maps

This folder contains the active R-based Directory map pipeline.

The current supported outputs are:

- `bbmri-members-nolabels`
- `bbmri-members-sized`
- `bbmri-members-OEC-all`

The R code is responsible for rendering. GeoJSON generation still starts from
[`geocoding_2022.py`](/home/hopet/codex/directory-scripts/geocoding_2022.py).

## Quick Start

Render all three maps from the current Directory cache:

```bash
bash R-maps/export-all.sh
```

Render a single map directly:

```bash
Rscript R-maps/render_bbmri_members_nolabels.R \
  --input=/home/hopet/codex/directory-scripts/bbmri-directory-pilot.geojson \
  --iarc=/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

```bash
Rscript R-maps/render_bbmri_members_sized.R \
  --input=/home/hopet/codex/directory-scripts/bbmri-directory-pilot.geojson \
  --iarc=/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

```bash
Rscript R-maps/render_bbmri_members_oec_all.R \
  --input=/home/hopet/codex/directory-scripts/bbmri-directory-members-pilot.geojson \
  --iarc=/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson \
  --node-points=/home/hopet/codex/directory-scripts/R-maps/data/HQlineNN.geojson \
  --node-lines=/home/hopet/codex/directory-scripts/R-maps/data/onlyLinesHQlineNN.geojson \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

## Pipeline

`export-all.sh` runs the full local workflow:

1. generate `bbmri-directory-pilot.geojson` from the Directory cache
2. derive `bbmri-directory-members-pilot.geojson`
3. render `nolabels`, `sized`, and `OEC-all`

For `OEC-all`, the export path is size-specific on purpose. `small`, `med`,
and `big` are built separately so the HQ anchor used by inset connectors is
resolved against the actual target output size.

## Important Files

- `map_config.R`
  Central configuration for projections, extents, palettes, export sizes, and
  inset settings.
- `map_common.R`
  Shared helpers for loading data, projection-aware geometry logic, label
  helpers, and generic export support.
- `render_bbmri_members_nolabels.R`
  Standard map without biobank labels.
- `render_bbmri_members_sized.R`
  Standard map with size-scaled biobank dots and local biobank labels.
- `render_bbmri_members_oec_all.R`
  OEC map with custom projection and inset support.
- `render_pilot_maps.R`
  End-to-end local runner used by `export-all.sh`.
- `data/`
  Repo-local overlay GeoJSON inputs used by `OEC-all`.

## Inputs

Standard maps use:

- full biobank GeoJSON from `geocoding_2022.py`
- `R-maps/data/IARC.geojson`

`OEC-all` uses:

- member/observer subset GeoJSON
- `R-maps/data/IARC.geojson`
- `R-maps/data/HQlineNN.geojson`
- `R-maps/data/onlyLinesHQlineNN.geojson`

These overlay files are now local project inputs. They are part of the R map
workflow and should be updated here when node geometry changes.

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

`pilot-output/` is ignored by Git.

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

## Visual Review Helpers

For local before/after snapshots during visual tuning:

```bash
bash R-maps/archive-visual-history.sh --label before-change
bash R-maps/archive-visual-history.sh --label after-change
```

Snapshots are stored under `R-maps/compare-temp/history/` and are ignored by
Git.

## Further Guidance

Use these folder-local files for deeper maintenance guidance:

- [AGENTS.md](/home/hopet/codex/directory-scripts/R-maps/AGENTS.md)
- [SKILLS.md](/home/hopet/codex/directory-scripts/R-maps/SKILLS.md)
- [TRANSFER.md](/home/hopet/codex/directory-scripts/R-maps/TRANSFER.md)
