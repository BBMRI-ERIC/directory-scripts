# R-Maps Workflows

This file records repeatable map-development workflows specific to `R-maps/`.
It is not a duplicate of the root repository skills/guidance.

## 1. Render One Map

Run from `/home/hopet/codex/directory-scripts`.

### `nolabels`

```bash
Rscript R-maps/render_bbmri_members_nolabels.R \
  --input=/home/hopet/codex/directory-scripts/bbmri-directory-pilot.geojson \
  --iarc=/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

### `sized`

```bash
Rscript R-maps/render_bbmri_members_sized.R \
  --input=/home/hopet/codex/directory-scripts/bbmri-directory-pilot.geojson \
  --iarc=/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

For temporary overlap tuning in the sized map, add
`--biobank-label-layout-variant=spread`.

### `OEC-all`

```bash
Rscript R-maps/render_bbmri_members_oec_all.R \
  --input=/home/hopet/codex/directory-scripts/bbmri-directory-members-pilot.geojson \
  --iarc=/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson \
  --node-points=/home/hopet/codex/directory-scripts/R-maps/data/HQlineNN.geojson \
  --node-lines=/home/hopet/codex/directory-scripts/R-maps/data/onlyLinesHQlineNN.geojson \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

### `global-nolabels`

```bash
Rscript R-maps/render_global_nolabels.R \
  --input=/home/hopet/codex/directory-scripts/bbmri-directory-pilot.geojson \
  --iarc=/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

### `covid-nolabels`

```bash
Rscript R-maps/render_covid_nolabels.R \
  --input=/home/hopet/codex/directory-scripts/bbmri-directory-covid-pilot.geojson \
  --iarc=/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

### `global-labels` / `global-sized`

```bash
Rscript R-maps/render_global_labels.R \
  --input=/home/hopet/codex/directory-scripts/bbmri-directory-pilot.geojson \
  --iarc=/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

```bash
Rscript R-maps/render_global_sized.R \
  --input=/home/hopet/codex/directory-scripts/bbmri-directory-pilot.geojson \
  --iarc=/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

### `covid-labels` / `covid-sized`

```bash
Rscript R-maps/render_covid_labels.R \
  --input=/home/hopet/codex/directory-scripts/bbmri-directory-covid-pilot.geojson \
  --iarc=/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

```bash
Rscript R-maps/render_covid_sized.R \
  --input=/home/hopet/codex/directory-scripts/bbmri-directory-covid-pilot.geojson \
  --iarc=/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

### `quality_maps-nolabels`

```bash
Rscript R-maps/render_quality_maps_nolabels.R \
  --input=/home/hopet/codex/directory-scripts/bbmri-directory-quality-pilot.geojson \
  --iarc=/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

### `strategic-objectives`

```bash
Rscript R-maps/render_strategic_objectives.R \
  --input=/home/hopet/codex/directory-scripts/R-maps/data/strategic-objectives-template.toml \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

For interactive work in RStudio, source `R-maps/strategic_objectives_common.R`
from either the repository root or from `R-maps/` directly. The helper now
finds the folder in both cases.

### `federated-platform`

```bash
Rscript R-maps/render_federated_platform.R \
  --input=/home/hopet/codex/directory-scripts/R-maps/data/federated-platform.geojson \
  --iarc=/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

### `CRC-cohort-sized`

```bash
Rscript R-maps/render_crc_cohort_sized.R \
  --input=/home/hopet/codex/directory-scripts/R-maps/data/CRC-Cohort.geojson \
  --imaging=/home/hopet/codex/directory-scripts/R-maps/data/CRC-Cohort-imaging.geojson \
  --iarc=/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

### `rare-diseases-*`

```bash
./.venv-maps/bin/python R-maps/prepare_rare_diseases_geojson.py \
  --input=/home/hopet/codex/directory-scripts/bbmri-directory-pilot.geojson \
  --output=/home/hopet/codex/directory-scripts/bbmri-directory-rare-diseases-pilot.geojson
```

```bash
Rscript R-maps/render_rare_diseases_labels.R \
  --input=/home/hopet/codex/directory-scripts/bbmri-directory-rare-diseases-pilot.geojson \
  --iarc=/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

```bash
Rscript R-maps/render_rare_diseases_sized.R \
  --input=/home/hopet/codex/directory-scripts/bbmri-directory-rare-diseases-pilot.geojson \
  --iarc=/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

`rare-diseases-nolabels` and `rare-diseases-labels` keep fixed-size circles; `rare-diseases-sized` is the only rare-disease variant that scales circles by biobank size.

## 2. Regenerate The Full Pilot Set

### Bash wrapper

```bash
sh R-maps/export.sh
```

```bash
sh R-maps/export.sh global-nolabels global-labels global-sized covid-nolabels covid-labels covid-sized quality_maps-nolabels federated-platform CRC-cohort-sized rare-diseases-nolabels rare-diseases-labels rare-diseases-sized strategic-objectives
```

```bash
sh R-maps/export.sh
```

### Direct R entry point

```bash
Rscript R-maps/render_pilot_maps.R \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

What it does:

- runs `geocoding_2022.py` through the local pilot Python env
- writes `bbmri-directory-pilot.geojson`
- derives `bbmri-directory-members-pilot.geojson`
- derives `bbmri-directory-covid-pilot.geojson` when extras are requested
- derives `bbmri-directory-quality-pilot.geojson` when extras are requested
- renders the requested map set

### RStudio-friendly walkthrough

Open `R-maps/README.Rmd` in RStudio for the narrative guide and open the
scripts in `R-maps/examples/` for short runnable recipes. The scripts are
intended to be read and executed interactively, not just from the shell.

Useful starting points:

- `R-maps/examples/00_setup.R`
- `R-maps/examples/01_render_existing_map.R`
- `R-maps/examples/02_country_labels_and_coloring.R`
- `R-maps/examples/03_legends_and_overlays.R`
- `R-maps/examples/04_complex_overlay_template.R`

The biobank label helpers strip the `bbmri-eric:ID:` prefix before rendering.
That is the expected behavior for all label-bearing maps.

### Built-in Map Sets

The R runner also understands named sets:

```bash
Rscript R-maps/render_pilot_maps.R --map-set=core
Rscript R-maps/render_pilot_maps.R --map-set=extras
Rscript R-maps/render_pilot_maps.R --map-set=all
```

## 3. Run Prep Helpers Directly

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

## 4. Fast Parse Check

```bash
Rscript -e 'for (f in c("R-maps/map_config.R","R-maps/map_common.R","R-maps/render_bbmri_members_nolabels.R","R-maps/render_bbmri_members_sized.R","R-maps/render_bbmri_members_labels.R","R-maps/render_bbmri_members_oec_all.R","R-maps/render_global_nolabels.R","R-maps/render_global_labels.R","R-maps/render_global_sized.R","R-maps/render_covid_nolabels.R","R-maps/render_covid_labels.R","R-maps/render_covid_sized.R","R-maps/render_quality_maps_nolabels.R","R-maps/render_federated_platform.R","R-maps/render_crc_cohort_sized.R","R-maps/render_rare_diseases_common.R","R-maps/render_rare_diseases_nolabels.R","R-maps/render_rare_diseases_labels.R","R-maps/render_rare_diseases_sized.R","R-maps/render_pilot_maps.R")) parse(file=f)'
```

## 5. Verify Output Presence

```bash
ls -1 R-maps/pilot-output/*
```

## 6. Verify Raster Sizes

```bash
python3 - <<'PY'
from PIL import Image
from pathlib import Path
for p in sorted(Path("R-maps/pilot-output").glob("*small.png")):
    print(p.name, Image.open(p).size)
PY
```

## 7. Compare Against Published Tilemill References

Published references live at:

- `https://web.bbmri-eric.eu/Directory-files/`

Key filenames used so far:

- `directory-map-5-0-small-nolabels.png`
- `directory-map-5-0-small-sized.png`
- `directory-map-5-0-small-OEC-all.png`

Local temporary comparison material has been kept under:

- `R-maps/compare-temp/`

That folder is for disposable reference and side-by-side images only.

Useful current references:

- `directory-map-5-0-small-nolabels.png`
- `directory-map-5-0-small-sized.png`
- `directory-map-5-0-small-OEC-all.png`

For `OEC-all`, do not rely only on abstract reasoning. Open the local render
image and compare it visually after each material geometry/layout change.
When reviewing `OEC-all`, treat surrounding white border as an independent
quality criterion. The published original is not the source of truth for that
one detail, because its border is also too generous.

Before and after a material visual change, snapshot the current rendered
outputs so evolution can be reviewed:

```bash
bash R-maps/archive-visual-history.sh --label before-oec-tune
bash R-maps/archive-visual-history.sh --label after-oec-tune
```

These snapshots are kept locally under `R-maps/compare-temp/history/` with a
small rolling retention and are not meant to be committed.

## 8. Shadowtext Setup

The renderers automatically prepend `R-maps/r-lib` to `.libPaths()` if that
directory exists.

To verify `shadowtext`:

```bash
Rscript -e 'script_dir <- normalizePath("R-maps", winslash="/", mustWork=TRUE); source(file.path(script_dir, "map_common.R")); cat(requireNamespace("shadowtext", quietly=TRUE), "\n")'
```

Expected result:

```text
TRUE
```

## 9. Known Safe Edit Boundaries

- adjust palette/extent/offset constants in `map_config.R`
- adjust shared placement or halo behavior in `map_common.R`
- keep the Python prep helpers focused on data derivation only
- keep renderer scripts focused on map-specific layer composition only
- for `OEC-all`, keep normal visible symbols on `geom_sf(...)`

## 10. Known Risky Areas

- changing export logic in `bbmri_save_plot_formats(...)`
- changing the OEC projection or bbox
- changing label placement logic without rechecking Tilemill parity
- changing the halo helper without checking `nolabels`, `sized`, and `OEC-all`
  together
- switching `OEC-all` symbol layers back to manual projected `x/y`
- trying to infer HQ/NN node positions from `onlyLinesHQlineNN.geojson` without
  first checking the existing `HQlineNN.geojson` point anchors
- guessing live replacements for `federated-platform` or `CRC-cohort-sized`
  instead of using explicit snapshot inputs

## 11. Multi-Agent Review Pattern

When a map problem is ambiguous rather than purely mechanical, use this split:

- Agent 1: implementation quality
  Focus on correctness, compactness, assertive validations, and safe code.
- Agent 2: maintainability review
  Focus on modularity, human manageability, and long-term sustainability.
- Agent 3: visual review
  Focus on compactness, legibility, and parity with published Tilemill output.

This pattern worked well for OEC inset/layout work. The main agent should still
keep the actual geometry debugging local if the next edit depends immediately on
the result.

## 12. OEC Geometry Checklist

Before trusting an `OEC-all` change, verify:

- countries are clipped, not merely bbox-filtered
- the main OEC bbox still matches the original Tilemill `project.mml` bounds
- the composed main/inset boxes preserve projected aspect instead of stretching
  the plot to arbitrary page rectangles
- node lines look correct
- node squares sit on the expected line endpoints
- biobank dots are not drifting relative to countries
- `IARC` anchor, sub-symbols, and label all move consistently
- QA inset is small, near Europe, and not unintentionally magnified
- QA inset geography includes neighboring-state context, not only the masked
  partner country polygon
- HQ inset connector anchor is resolved on the actual rendered main-map panel,
  not from generic outer-box math
- the resolved HQ anchor remains effectively identical for `small`, `med`, and
  `big` exports
