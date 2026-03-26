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

### `OEC-all`

```bash
Rscript R-maps/render_bbmri_members_oec_all.R \
  --input=/home/hopet/codex/directory-scripts/bbmri-directory-members-pilot.geojson \
  --iarc=/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson \
  --node-points=/home/hopet/codex/directory-scripts/R-maps/data/HQlineNN.geojson \
  --node-lines=/home/hopet/codex/directory-scripts/R-maps/data/onlyLinesHQlineNN.geojson \
  --output-dir=/home/hopet/codex/directory-scripts/R-maps/pilot-output
```

## 2. Regenerate The Full Pilot Set

### Bash wrapper

```bash
./R-maps/export-all.sh
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
- renders all three maps

## 3. Fast Parse Check

```bash
Rscript -e 'parse(file="R-maps/map_config.R"); parse(file="R-maps/map_common.R"); parse(file="R-maps/render_bbmri_members_nolabels.R"); parse(file="R-maps/render_bbmri_members_sized.R"); parse(file="R-maps/render_bbmri_members_oec_all.R")'
```

## 4. Verify Output Presence

```bash
ls -1 R-maps/pilot-output/bbmri-members-*
```

## 5. Verify Raster Sizes

```bash
python3 - <<'PY'
from PIL import Image
from pathlib import Path
for p in sorted(Path("R-maps/pilot-output").glob("*small.png")):
    print(p.name, Image.open(p).size)
PY
```

## 6. Compare Against Published Tilemill References

Published references live at:

- `https://web.bbmri-eric.eu/Directory-files/`

Key filenames used so far:

- `directory-map-5-0-small-nolabels.png`
- `directory-map-5-0-small-sized.png`
- `directory-map-5-0-small-OEC-all.png`

Local temporary comparison material has been kept under:

- `R-maps/compare-temp/`

That folder is for disposable reference and side-by-side images only.

## 7. Shadowtext Setup

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

## 8. Known Safe Edit Boundaries

- adjust palette/extent/offset constants in `map_config.R`
- adjust shared placement or halo behavior in `map_common.R`
- keep renderer scripts focused on map-specific layer composition only

## 9. Known Risky Areas

- changing export logic in `bbmri_save_plot_formats(...)`
- changing the OEC projection or bbox
- changing label placement logic without rechecking Tilemill parity
- changing the halo helper without checking `nolabels`, `sized`, and `OEC-all`
  together
