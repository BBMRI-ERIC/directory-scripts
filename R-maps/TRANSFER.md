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
- `global-nolabels`
- `covid-nolabels`
- `quality_maps-nolabels`
- `federated-platform`
- `CRC-cohort-sized`

Implemented outputs:

- raster PNGs at `small` / `med` / `big`
- matching size-specific PDFs
- default PDF
- default SVG when `svglite` is available

Current wrapper:

- `/home/hopet/codex/directory-scripts/R-maps/export.sh`
  Main POSIX-shell entry point that exports all maps by default or only the
  explicitly named map ids.

Human-facing docs now live in:

- `/home/hopet/codex/directory-scripts/R-maps/README.md`
- `/home/hopet/codex/directory-scripts/R-maps/README.Rmd`
- `/home/hopet/codex/directory-scripts/R-maps/examples/`

Use `README.Rmd` and the example scripts for RStudio-driven maintenance and
framework walkthroughs.

Current pilot outputs live in:

- `/home/hopet/codex/directory-scripts/R-maps/pilot-output`

## Current Data Inputs

Pilot GeoJSON inputs:

- `/home/hopet/codex/directory-scripts/bbmri-directory-pilot.geojson`
- `/home/hopet/codex/directory-scripts/bbmri-directory-members-pilot.geojson`
- `/home/hopet/codex/directory-scripts/bbmri-directory-covid-pilot.geojson`
- `/home/hopet/codex/directory-scripts/bbmri-directory-quality-pilot.geojson`

Current OEC overlay inputs:

- `/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson`
- `/home/hopet/codex/directory-scripts/R-maps/data/HQlineNN.geojson`
- `/home/hopet/codex/directory-scripts/R-maps/data/onlyLinesHQlineNN.geojson`

Current snapshot-backed extra-map inputs:

- `/home/hopet/codex/directory-scripts/R-maps/data/federated-platform.geojson`
- `/home/hopet/codex/directory-scripts/R-maps/data/CRC-Cohort.geojson`
- `/home/hopet/codex/directory-scripts/R-maps/data/CRC-Cohort-imaging.geojson`

Local visual-review snapshots should be stored under
`R-maps/compare-temp/history/` via `archive-visual-history.sh`. This is a
rolling ignored workspace for comparing successive render states during visual
tuning and should not be committed.

For OEC visual review, surrounding white border is now treated as its own
quality target rather than something to match exactly against the published
Tilemill output. The original OEC render also leaves too much border, so future
review should prefer tighter and better-balanced whitespace.

## Important Technical Decisions Already Made

### GeoJSON / Python Boundary

- `geocoding_2022.py` stays in place.
- It was already patched so invalid cached decimal coordinates are range-checked
  before export.
- It now also uses a persistent global geocoding cache and no longer
  performs an unconditional startup probe against the live geocoder. Repeated
  runs on the same Directory snapshot should therefore reuse cached geocoding
  results instead of touching the live geocoder again for already-seen
  unresolved contacts.
- The bad cached coordinates for `ES_BV` and `ES_IMIB` were explicitly handled
  during this work and should not silently reappear.
- `prepare_covid_geojson.py` derives the COVID subset from the full pilot
  GeoJSON plus live Directory metadata. It does not depend on `biobankCOVID`
  being present in the full pilot GeoJSON.
- `prepare_quality_geojson.py` derives quality-map points from current
  Directory metadata. It uses raw quality references when available and falls
  back to `combined_quality` for collection coverage.

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
- `IARC` label is now anchored from shifted `sf` geometry rather than manual
  projected `x/y` text placement.
- External non-European partner areas are now handled through the generic
  `oec_insets` config list. The first configured inset is Qatar (`QA`), which
  is removed from the main map and drawn in a floating inset window linked
  back to HQ.
- The main OEC bbox is back on the original Tilemill `project.mml` bounds.
  This matters visually: the tighter experimental bbox made Norway/Finland too
  large and caused Turkey/Scandinavia clipping relative to the published map.
- A second independent OEC issue was page composition: the main map and inset
  must be fitted into `cowplot` boxes while preserving their projected aspect
  ratios. Otherwise the correct `tmerc` CRS still looks visually cylindrical.
- A later OEC framing bug turned out to be `coord_sf(...)` order, not
  projection math: if extra `geom_sf(...)` layers were added after the custom
  `coord_sf(...)`, ggplot replaced the coordinate system with a default one and
  silently discarded the intended projected bbox.
- The current main OEC frame is now derived from the projected mainland-country
  extent itself, not from crop fractions on the broad legacy OEC bbox and not
  from the mixed point/line cloud. The renderer applies explicit geographic
  exclusions first, then expands that mainland bbox to the target page aspect.
- The current OEC sheet is also deliberately wider than the old portrait
  experiments: `med` is now `4800 x 2800`, with proportional `small` / `big`
  and vector sizes.
- The current OEC mainland frame has two explicit high-north controls:
  - `oec_main_north_cap_lat` caps the top around Mageroya rather than farther
    north
  - `oec_geographic_exclusions$arctic_islands` removes Bear Island / Bjornoya
    and other remote Norway Arctic polygons from the base map
- The QA inset is intentionally small and geographically proportionate to the
  main OEC extent. It is for repositioning closer to Europe, not for
  magnifying Qatar.
- Inset geography now clips the full country layer to the inset bbox, not only
  Qatar itself. Without that, neighboring-state context can never be visible.
- OEC lines now use a white under-stroke plus orange top stroke.
- OEC node squares and biobank dots now render through `geom_sf(...)`, which
  fixed the earlier symbol projection drift.

### New Extra Maps

- `global-nolabels`
  - world viewport
  - classic geography layers
  - full pilot GeoJSON input
- `covid-nolabels`
  - world viewport
  - classic geography layers
  - COVID subset from `prepare_covid_geojson.py`
- `quality_maps-nolabels`
  - Europe viewport
  - classic geography layers
  - quality points from `prepare_quality_geojson.py`
  - collection points are usually more numerous than biobank points
- `federated-platform`
  - Europe viewport
  - snapshot-backed local GeoJSON input
  - custom fedplat country palette and point labels from `biobankLabel`
- `CRC-cohort-sized`
  - world viewport from the legacy export script
  - snapshot-backed local main/imaging GeoJSON inputs
  - main cohort points are size-scaled by `contribSize`
  - imaging points are a separate green overlay

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
- `bbmri-members-OEC-all` improved materially after the OEC projection-path
  fixes, especially once country clipping and `geom_sf` symbol rendering were
  applied
- the five newly added extra-map renderers pass direct smoke-render checks, but
  they have not yet gone through the same detailed visual tuning loop as the
  original three migrated maps

## Key OEC Debugging Lessons

These findings mattered and should not be rediscovered the hard way:

1. OEC projected bbox math:
   - projecting only bbox corners was wrong
   - sampling the bbox boundary densely fixed main-map extent math

2. OEC country extents:
   - filtering intersecting countries was insufficient
   - real clipping was required so overseas territories did not collapse the
     Europe panel into a tiny area

3. OEC symbols vs lines:
   - lines could look correct while node boxes and biobank dots were still off
   - the root cause was manual projected `x/y` plotting for symbols under the
     custom OEC projection
   - switching normal OEC symbols to `geom_sf(...)` fixed this

4. `HQlineNN` vs `onlyLinesHQlineNN`:
   - node points already sat on the correct line endpoints
   - an attempted re-alignment from line endpoints was incorrect and removed
   - line feature names append `Connecting LineString`, so naive name matching
     is wrong

5. QA inset:
   - the purpose of the inset is repositioning, not enlargement
   - QA should stay geographically proportionate and simply move closer to
     Europe
   - the QA connector endpoint may still need tiny visual tuning in inset space
     even when the underlying node geometry is correct

6. HQ anchor for inset connectors:
   - generic plot-box or panel-box math was not reliable enough
   - the stable solution was to render the main OEC plot into a temporary
     device at the real target output size, enter the actual panel viewport,
     and resolve the HQ page anchor from that rendered panel
   - that resolved page anchor is then reused for both the QA connector source
     and the overlay HQ box
   - this was validated across `small`, `med`, and `big` and should remain the
     pattern for future additional inset windows

7. OEC main framing:
   - using `oec_projected_crop` against the broad legacy OEC bbox was the
     wrong abstraction because large numeric crop changes often had weak or
     misleading visible effects
   - the current stable frame is driven by the projected mainland-country
     extent after explicit geographic exclusions, then expanded to the target
     page aspect
   - this only became visibly effective after moving `coord_sf(...)` to the
     end of the OEC panel plot layer stack so later `geom_sf(...)` layers could
     no longer replace the custom projected bbox with a default one
   - the last important refinement was to stop the far north around Mageroya
     and explicitly remove Bear Island / Bjornoya and the other remote Arctic
     Norway polygons from the base geometry
   - future OEC framing work should tune the dedicated OEC page size,
     `oec_content_margins`, `oec_main_north_cap_lat`, and
     `oec_geographic_exclusions`, not reintroduce broad-window crop fractions
     or point-cloud auto-fit

## Multi-Agent Setup That Was Used

During the OEC parity work, a useful three-agent split was:

- implementation/correctness
- modularity/maintainability review
- visual clarity/parity review

This helped challenge bad inset layouts and overcomplicated abstractions, but
the actual geometry/projection debugging was still best done locally by the
main agent.

## Known Remaining Issues / Open Work

1. `OEC-all` may still need focused visual tuning for:
   - final QA inset placement
   - exact QA connector landing point
   - final perceived prominence of HQ/node squares
   - any remaining `IARC` micro-spacing
   - final tuning of the new content-derived Europe framing through
     `oec_content_margins` and `oec_content_trim_bias`

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
- `/home/hopet/codex/directory-scripts/R-maps/prepare_covid_geojson.py`
- `/home/hopet/codex/directory-scripts/R-maps/prepare_quality_geojson.py`
- `/home/hopet/codex/directory-scripts/R-maps/render_bbmri_members_nolabels.R`
- `/home/hopet/codex/directory-scripts/R-maps/render_bbmri_members_sized.R`
- `/home/hopet/codex/directory-scripts/R-maps/render_bbmri_members_oec_all.R`
- `/home/hopet/codex/directory-scripts/R-maps/render_global_nolabels.R`
- `/home/hopet/codex/directory-scripts/R-maps/render_covid_nolabels.R`
- `/home/hopet/codex/directory-scripts/R-maps/render_quality_maps_nolabels.R`
- `/home/hopet/codex/directory-scripts/R-maps/render_federated_platform.R`
- `/home/hopet/codex/directory-scripts/R-maps/render_crc_cohort_sized.R`

## Recommended Next Steps

1. Do a dedicated `OEC-all` parity pass against the published references.
2. Decide whether the current halo should remain fully manual or eventually be
   reimplemented with a better blur-like text effect.
3. Keep the root repository docs unchanged unless the change is truly global.
   R-map-specific operational knowledge belongs in this folder.
4. Do a visual-tuning pass for the five extra maps once the user starts
   reviewing them side-by-side against the legacy Tilemill outputs.
