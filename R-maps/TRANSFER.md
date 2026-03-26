# R-Maps Transfer Note

This is the current handoff state for the Tilemill-to-R migration work in
`R-maps/`.

## Goal

Replace the current Tilemill rendering of selected BBMRI maps with maintainable
R scripts built on `ggplot2` and `sf`, while keeping `geocoding_2022.py` as the
GeoJSON source.

## Current Implemented Scope

Implemented renderers:

- `bbmri-members-nolabels`
- `bbmri-members-sized`
- `bbmri-members-OEC-all`

Implemented outputs:

- raster PNGs at `small` / `med` / `big`
- matching size-specific PDFs
- default PDF
- default SVG when `svglite` is available

Current pilot outputs live in:

- `/home/hopet/codex/directory-scripts/R-maps/pilot-output`

## Current Data Inputs

Pilot GeoJSON inputs:

- `/home/hopet/codex/directory-scripts/bbmri-directory-pilot.geojson`
- `/home/hopet/codex/directory-scripts/bbmri-directory-members-pilot.geojson`

Current OEC overlay inputs:

- `/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson`
- `/home/hopet/codex/directory-scripts/R-maps/data/HQlineNN.geojson`
- `/home/hopet/codex/directory-scripts/R-maps/data/onlyLinesHQlineNN.geojson`

## Important Technical Decisions Already Made

### GeoJSON / Python Boundary

- `geocoding_2022.py` stays in place.
- It was already patched so invalid cached decimal coordinates are range-checked
  before export.
- The bad cached coordinates for `ES_BV` and `ES_IMIB` were explicitly handled
  during this work and should not silently reappear.

### Standard Maps

- `nolabels` and `sized` do not render lakes or waterways.
- Both use `EPSG:3857`.
- Observer color in standard maps is light blue.
- Country labels are uppercase.

### `sized`

- Dot size follows the Tilemill bucket widths from `biobankSize`.
- Biobank labels are rendered.
- Biobank labels use local constrained placement only.
- Biobank labels do not use a white halo.
- No connector lines are drawn.

### `nolabels`

- Country labels can locally shift to reduce overlap with biobank dots.
- This optimization is intentionally limited to nearby candidate positions.

### `OEC-all`

- Uses the custom Transverse Mercator projection from the legacy project.
- Uses the member/observer/gray country grouping from current `map_config.R`.
- Observer color is light blue, not orange.
- HQ and nodes use squares, with HQ larger than node squares.
- `IARC` is rendered as a larger light-blue observer circle.
- `IARC` label is shimmed northwest to avoid the nearby node.

### Halo Rendering

Current halo implementation is manual in `bbmri_geom_text_halo(...)`:

- inner ring: `1px` opaque white
- outer ring: `3px` semi-transparent white
- outer ring opacity: `0.25`

This is expressed in output-pixel terms and converted to map units using the
 projected bbox.

This manual approach is currently preferred because:

- it gives tighter control over ring widths than the previous experiments
- it avoids the earlier misalignment bug where `nudge_y` was applied
  inconsistently between halo and text layers

### Export Scaling

`bbmri_save_plot_formats(...)` was changed so raster outputs keep a constant
physical layout and vary DPI by target size. This matters because the earlier
approach made symbols appear disproportionately smaller on `med` and `big`
outputs.

Practical consequence:

- the same dot/text sizes now stay visually comparable across `small`, `med`,
  and `big`
- size-specific PDFs are also written

## Current Visual State

Based on local comparison work against published Tilemill PNGs:

- `bbmri-members-nolabels` is the closest to parity
- `bbmri-members-sized` is broadly good, but still benefits from incremental
  label and proportion tuning
- `bbmri-members-OEC-all` is still the furthest from parity and needs the most
  future tuning

## Known Remaining Issues / Open Work

1. `OEC-all` still needs focused visual tuning for:
   - framing tightness
   - HQ/node square prominence
   - connector line weight
   - final `IARC` and node interaction spacing

2. `sized` may still need:
   - final biobank label font-size tuning
   - some cluster-by-cluster local placement tuning

3. Country-label offsets remain partly manual. `MT` and `CY` were already
   shimmed downward, but more country-specific nudges may still be needed.

4. Raster height can occasionally round by one pixel because of device math
   after DPI-based export scaling. Treat this as cosmetic unless it causes a
   visible mismatch.

## Known Harmless Warnings

Renders commonly emit:

- `GDAL Message 1: Non closed ring detected`
- `st_point_on_surface assumes attributes are constant over geometries`

These warnings have been observed repeatedly without blocking successful
rendering.

## Files That Matter Most For Future Work

- `/home/hopet/codex/directory-scripts/R-maps/map_config.R`
- `/home/hopet/codex/directory-scripts/R-maps/map_common.R`
- `/home/hopet/codex/directory-scripts/R-maps/render_bbmri_members_nolabels.R`
- `/home/hopet/codex/directory-scripts/R-maps/render_bbmri_members_sized.R`
- `/home/hopet/codex/directory-scripts/R-maps/render_bbmri_members_oec_all.R`

## Recommended Next Steps

1. Do a dedicated `OEC-all` parity pass against the published references.
2. Decide whether the current halo should remain fully manual or eventually be
   reimplemented with a better blur-like text effect.
3. Keep the root repository docs unchanged unless the change is truly global.
   R-map-specific operational knowledge belongs in this folder.
