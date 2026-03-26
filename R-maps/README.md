# R Map Migration

This directory contains the initial `ggplot2` + `sf` replacement work for the
legacy Tilemill-based Directory maps.

## Current Pipeline

The current production flow is:

1. [`geocoding_2022.py`](/home/hopet/codex/directory-scripts/geocoding_2022.py)
   generates a GeoJSON `FeatureCollection` of biobank points.
2. The legacy shell pipeline in
   `~/codex/geocoding_python/tilemill/mapsGeneration.sh` creates derived
   GeoJSON variants such as `bbmri-directory-members.geojson`.
3. Tilemill projects render final PNG/PDF/SVG outputs via
   `export-directory-5-0_python.sh`.

The Python GeoJSON generator is expected to stay in place for now. The R
replacement should therefore consume GeoJSON and focus on rendering rather than
re-implementing geocoding.

## Tilemill Analysis

### `bbmri-members-nolabels`

- Projection: Web Mercator-like (`+proj=merc ...`), replace with `EPSG:3857`.
- Data layers:
  - Natural Earth countries, rivers, lakes, admin lines, glaciers, geo-lines
  - `country-interaction.geojson`
  - `IARC.geojson`
  - `bbmri-directory.geojson`
- Visual logic:
  - member / observer country fills from `common-styles/rainbow.mss`
  - blue water background
  - fixed-size biobank circles
  - no biobank labels
  - country labels and IARC label still exist through `labels.mss`

### `bbmri-members-sized`

- Same base map and projection as `bbmri-members-nolabels`.
- Same country fill palette.
- Biobank circles vary by `biobankSize`:
  - `0 -> 5`
  - `1 -> 6`
  - `2 -> 8`
  - `3 -> 12`
  - `4 -> 20`
  - `5 -> 32`
  - `6 -> 48`
  - `7 -> 64`
  - `8 -> 72`
- Biobank labels are enabled and use `biobankID`.

### `bbmri-members-OEC-all`

- Projection: custom Transverse Mercator:
  `+proj=tmerc +lon_0=10 +lat_0=-10 +k=1 ...`
- Uses a different visual language from `rainbow-eleanor.mss`:
  - white background
  - dark blue member countries
  - orange observer countries and orange biobank markers
  - simplified base map without rivers/lakes
- Uses `bbmri-directory-members.geojson` rather than the full Directory
  GeoJSON.
- Adds external overlay data:
  - `IARC.geojson`
  - `HQlineNN.geojson`
  - `onlyLinesHQlineNN.geojson`
- Excludes one specific biobank:
  - `bbmri-eric:ID:EXT_NASBIO`

## External OEC Inputs

The OEC project depends on three overlay GeoJSON files. For this migration
work, the currently used copies are stored locally in `R-maps/data/`:

- `IARC.geojson`
- `HQlineNN.geojson`
- `onlyLinesHQlineNN.geojson`

These were copied from the legacy Tilemill data area and are still treated as
explicit renderer inputs rather than being hardcoded into plotting logic.

## R Dependencies

The map scripts rely on base R packages already available in this environment
such as `ggplot2`, `sf`, `ggrepel`, and `svglite`.

If you want proper text glow/halo rendering through
`shadowtext::geom_shadowtext()` instead of the current manual fallback, install
the `shadowtext` package into the repo-local R library under `R-maps/r-lib`.

On Debian/Ubuntu, install the required system development packages first:

```bash
sudo apt-get update
sudo apt-get install -y \
  build-essential \
  pkg-config \
  libfontconfig1-dev \
  libfreetype6-dev \
  libcairo2-dev
```

Then install `shadowtext` into the local library used by the map tooling:

```bash
mkdir -p R-maps/r-lib
Rscript -e '.libPaths(c(normalizePath("R-maps/r-lib", mustWork = TRUE), .libPaths())); install.packages("shadowtext", repos = "https://cloud.r-project.org")'
```

Verify the installation:

```bash
Rscript -e '.libPaths(c(normalizePath("R-maps/r-lib", mustWork = TRUE), .libPaths())); print(requireNamespace("shadowtext", quietly = TRUE))'
```

Expected result:

```text
[1] TRUE
```

If installation fails with missing `fontconfig`, `freetype`, or `cairo`
headers, the Debian/Ubuntu package command above has not been applied yet.

## Migration Strategy

1. Keep `geocoding_2022.py` as the GeoJSON producer.
2. Replace Tilemill rendering with thin R entry scripts in this directory.
3. Keep all shared logic in `map_config.R` and `map_common.R`:
   - projections
   - palette rules
   - output sizes
   - Natural Earth layer loading
   - shared `ggplot2` theme helpers
4. Keep map-specific scripts small and readable:
   - `render_bbmri_members_nolabels.R`
   - `render_bbmri_members_sized.R`
   - `render_bbmri_members_oec_all.R`
   - `render_pilot_maps.R`
5. Avoid machine-specific hardcoded paths. All external inputs should be passed
   in explicitly or resolved from repo-relative defaults.
6. Prefer stable, explicit labeling over clever automation. For country labels,
   use deterministic centroids plus a small hand-maintained offset table where
   needed. For dense biobank labels, use a deterministic local-placement pass
   that allows only small shifts around each point instead of long-distance
   repel layouts.

## Initial Scope

The scripts added now are scaffolding plus first-pass rendering logic. The next
implementation steps should be:

1. Document how the OEC overlay GeoJSON files are generated and who owns them.
2. Compare the first R renders visually against the current Tilemill outputs.
3. Tune label offsets and stroke/fill values until the outputs are stable across
   the standard export sizes.
4. Decide whether SVG export should be mandatory or optional via `svglite`.
