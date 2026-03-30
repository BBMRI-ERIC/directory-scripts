# R-Maps Agent Notes

This file is intentionally local to `R-maps/`. It supplements the root
repository guidance in `/home/hopet/codex/directory-scripts/AGENTS.md` and
should not repeat the general Directory/QC/exporter rules from there.

## Scope

This folder contains the in-progress R replacement for the legacy Tilemill map
pipeline. The current target maps are:

- `bbmri-members-nolabels`
- `bbmri-members-sized`
- `bbmri-members-OEC-all`
- `global-nolabels`
- `covid-nolabels`
- `quality_maps-nolabels`
- `federated-platform`
- `CRC-cohort-sized`

The R code is responsible for rendering plus a small amount of map-specific
GeoJSON derivation. The base full-Directory point export still starts from
`geocoding_2022.py`.

## Legacy Baseline That Still Matters

Tilemill is no longer the implementation target, but some legacy map semantics
are still the parity baseline and should remain documented here:

- `bbmri-members-nolabels`
  - standard Europe map
  - no rivers or lakes
  - fixed-size biobank dots
  - no biobank labels
  - country labels still exist
- `bbmri-members-sized`
  - same standard Europe map and country palette as `nolabels`
  - no rivers or lakes
  - biobank dot size follows `biobankSize`
  - biobank labels use `biobankID`
- `bbmri-members-OEC-all`
  - custom `tmerc` projection
  - white background
  - dark-blue member countries
  - light-blue observer countries
  - orange HQ / node / biobank language
  - simplified base map
  - uses the member/observer GeoJSON subset, not the full directory point set
- `global-nolabels`
  - standard Mercator map
  - world viewport
  - classic Tilemill geography layers, including lakes/rivers
  - fixed-size biobank dots
  - no biobank labels
  - country labels and `IARC` still exist
- `covid-nolabels`
  - same world viewport and classic geography as `global-nolabels`
  - fixed-size dots
  - point set is the COVID subset only
- `quality_maps-nolabels`
  - Europe viewport with classic geography layers
  - one point per rendered quality designation
  - `biobankType='biobank'` uses large translucent circles
  - `biobankType='collection'` uses small circles
  - `qual_id='eric'` is orange
  - `qual_id='accredited'` is dark blue
  - `qual_id='Other'` must remain explicit in the GeoJSON contract
- `federated-platform`
  - Europe viewport with classic geography layers
  - country palette differs from standard maps
  - `biobankType='LocatorBiobank'` is orange-brown
  - `biobankType='FinderBiobank'` is magenta
  - point labels use `biobankLabel`
  - `IARC` is a plain observer circle, not the standard observer-plus-biobank composite
- `CRC-cohort-sized`
  - world viewport from the legacy export script
  - classic geography layers
  - main cohort points are red and size-scaled by `contribSize`
  - imaging contributions are separate green points
  - no point labels

Keep those semantics in AGENTS rather than in the README. The README should
explain how to run and maintain the R pipeline, not serve as a Tilemill study
document.

## Files And Ownership

- `map_config.R`
  Central place for palette choices, projections, extents, export sizes, and
  manual label offsets.
- `map_common.R`
  Shared helpers for:
  - package loading
  - Natural Earth caching/downloading
  - projection-aware bbox helpers
  - GeoJSON reading/writing
  - shared text halo logic
  - local label placement logic
  - output export
- `render_bbmri_members_nolabels.R`
  Standard map without biobank labels.
- `render_bbmri_members_sized.R`
  Standard map with size-scaled biobank dots and local biobank ID labels.
- `render_bbmri_members_oec_all.R`
  OEC map with custom projection and overlay inputs.
- `render_global_nolabels.R`
  World standard map.
- `render_covid_nolabels.R`
  World COVID subset map.
- `render_quality_maps_nolabels.R`
  Quality map renderer from derived quality GeoJSON.
- `render_federated_platform.R`
  Federated-platform renderer from snapshot-backed GeoJSON.
- `render_crc_cohort_sized.R`
  CRC cohort renderer from snapshot-backed main/imaging GeoJSON.
- `prepare_covid_geojson.py`
  Helper that derives the COVID subset from the full pilot GeoJSON plus live Directory metadata.
- `prepare_quality_geojson.py`
  Helper that derives the quality-map GeoJSON from current Directory quality metadata.
- `render_pilot_maps.R`
  End-to-end runner from cached Directory GeoJSON generation to the requested
  map set (`core`, `extras`, or `all`).
- `README.md`
  Human-oriented overview and dependency notes.
- `SKILLS.md`
  Folder-local workflows and commands.
- `TRANSFER.md`
  Current state, open issues, and handoff notes.

## Non-Negotiable Design Decisions

- Keep `geocoding_2022.py` as the GeoJSON producer unless there is an explicit
  decision to replace it.
- `geocoding_2022.py` must stay lazy and cache-backed:
  - no unconditional startup probe against the live geocoder
  - only still-unresolved coordinate cases may hit the live geocoder
  - successful and stable negative geocoder results should be persisted in the
    geocoding cache so repeated runs on the same Directory snapshot do not
    re-query the same contacts
  - the geocoding cache should be global, not schema-scoped
- Keep `prepare_covid_geojson.py` and `prepare_quality_geojson.py` thin and
  data-contract oriented. Shared map rendering logic still belongs in the R
  helpers.
- Keep map-specific scripts thin. Shared style/placement/export logic belongs
  in `map_common.R` and `map_config.R`.
- Do not hardcode machine-specific legacy output paths into the renderers.
  External Tilemill-era overlays are passed as explicit inputs.
- `global-nolabels`, `covid-nolabels`, `quality_maps-nolabels`,
  `federated-platform`, and `CRC-cohort-sized` intentionally keep the classic
  Tilemill geography layers. Do not apply the standard-map “no lakes/rivers”
  simplification to those maps.
- Do not reintroduce rivers or lakes into `nolabels` and `sized`.
- `sized` biobank labels should use constrained local placement only. No long
  repel shifts and no connector lines.
- `sized` biobank labels are plain black text. They do not use the white halo.
- Country labels are uppercase and use the shared white halo treatment.
- `nolabels` may optimize country-label positions locally to avoid biobank-dot
  overlap. `sized` currently does not.
- `OEC-all` uses a materially different projection and style. Do not force it
  to share the standard-map geography or palette rules.
- External/non-European OEC partner areas should be handled through the
  config-driven `oec_insets` list in `map_config.R`, not through hardcoded
  renderer branches. Qatar is only the first configured inset.
- `federated-platform` and `CRC-cohort-sized` are snapshot-backed in v1. Do
  not silently replace them with guessed live derivations.
- `quality_maps-nolabels` and `covid-nolabels` are derived from current data
  and should stay reproducible from the current cache/Directory state.
- For `OEC-all`, country polygons, HQ/NN boxes, and biobank dots must share the
  same `sf` geometry rendering path. Do not reintroduce manual projected `x/y`
  plotting for normal symbols in that map.

## Current Labeling Rules

- Shared halo logic lives in `bbmri_geom_text_halo(...)` in `map_common.R`.
- The current intended halo style is:
  - inner ring: `1px` opaque white
  - outer ring: `3px` semi-transparent white
- Outer ring opacity is currently `0.25`.
- `nolabels` country labels and `IARC` use that explicit halo setup.
- `sized` country labels use the same halo setup.
- `OEC-all` `IARC` uses the same halo setup.
- `OEC-all` `IARC` label now uses shifted `sf` geometry rather than a manual
  `x/y` nudge path, because the latter produced projection drift.
- `OEC-all` HQ anchoring for inset connectors must be resolved from the
  actually rendered main-map panel on the target output device. Generic
  plot-box math was not reliable enough and produced visible west/east drift.

## OEC HQ Overlay Anchor Algorithm

### Purpose

For the current `OEC-all` layout, the purpose of the HQ anchor algorithm is:

- place the inset connector for HQ-sourced insets so that it starts at the
  same visual HQ location already rendered on the main OEC map
- redraw the HQ square on top of that connector so the connector disappears
  under the HQ symbol, just like the normal HQ-to-node links
- keep that coincidence true across `small`, `med`, `big`, and vector exports

This purpose is intentionally narrow. The current proof covers the present
`HQ -> QA` inset path. It does not prove correctness for arbitrary future
non-HQ connector sources.

### Algorithm

1. Build the main `OEC-all` map as a normal `geom_sf(...)` plot in
   `cfg$oec_crs`, with the real HQ symbol already present in the layer stack.
2. Fit that plot into `main_box` with `bbmri_fit_box_to_aspect(...)`, so the
   composed page preserves the projected map aspect ratio instead of stretching
   the map into an arbitrary `cowplot` rectangle.
3. Resolve the HQ location from the rendered main plot, not from raw overlay
   coordinates:
   - `bbmri_oec_hq_anchor_npc(...)` inspects the built ggplot layers
   - it finds the rendered HQ square layer
   - it converts that rendered HQ geometry into panel-local normalized
     coordinates (`panel NPC`)
4. Convert that panel-local HQ anchor into page/canvas coordinates by drawing
   the same plot grob into a temporary device with the exact target export
   width/height and using `grid::deviceLoc(...)` inside the real panel
   viewport. This yields `hq_overlay_xy` in page-normalized coordinates
   (`page NPC`).
5. For the current Qatar inset, require:
   - `connector.source_node_type = "HQ"`
   - `connector.source_dx = 0`
   - `connector.source_dy = 0`
   Then the connector source is exactly `hq_overlay_xy`.
6. Draw the inset and its connector line.
7. Redraw the HQ square at exactly the same `hq_overlay_xy`, with the same HQ
   symbol style, so the connector terminates under the HQ symbol instead of
   striking visibly through it.
8. Recompute this anchor separately for each export size. Do not reuse one
   anchor across `small`, `med`, `big`, and vector outputs.

### Why This Is Correct For Its Purpose

The purpose is to make three visible objects coincide:

- the HQ square already present on the main OEC map
- the source point of the HQ-to-inset connector
- the final HQ square redrawn over that connector

The current implementation satisfies that purpose because:

- the anchor is taken from the rendered HQ square in the main plot, so it is
  tied to the actual visible HQ position rather than to approximate bbox math
- the page anchor is resolved through the real panel viewport on a device with
  the same width/height as the final export, so panel margins and layout
  effects are accounted for
- the Qatar connector starts from that exact resolved page anchor because its
  current config keeps both HQ-source shims at zero
- the overlay HQ square is redrawn at that exact same resolved page anchor

Therefore, for the current HQ-sourced inset case, the underlying HQ symbol, the
connector source, and the overlay HQ redraw share one canonical anchor point in
the final page coordinate system. Any remaining visual difference should be
limited to normal device rasterization or antialiasing, not to coordinate
drift.

### Important Limits And Guardrails

- This proof is for the current HQ special case. It does not justify using
  bbox-derived `bbmri_project_point_to_npc(...)` math for future non-HQ inset
  anchors. If future insets need other source nodes, resolve those anchors from
  the rendered panel too.
- Do not go back to naive page placement such as
  `main_box$x + main_box$width * hq_npc$x`; that old approach caused visible
  west/east drift.
- The current HQ lookup depends on the HQ remaining identifiable in the built
  plot as the intended single HQ square layer. If future styling adds another
  competing one-row square layer, revisit `bbmri_oec_hq_anchor_npc(...)` and
  make the HQ match more explicit.
- Keep the export-size-specific anchor recomputation. The anchor is part of the
  rendering pipeline, not a static geometry constant.
- When anchor math depends on the export device, keep the temporary-device size
  and the final raster `ggsave(...)` DPI as one explicit contract. Do not rely
  on implicit device defaults if export DPI behavior changes.

## Current Placement Rules

- Shared manual country-label shims live in `map_config.R` under
  `standard_label_offsets`.
- Current manual shims include at least:
  - `CH`
  - `CZ`
  - `GB`
  - `MT`
  - `CY`
  - `NL`
  - `BE`
- `MT` and `CY` are both shifted downward to clear the islands.
- `nolabels` additionally runs `bbmri_place_country_labels(...)` to minimize
  overlap with biobank dots while staying close to the base position.
- `sized` biobank IDs run `bbmri_place_local_labels(...)`, which prefers
  positions close to the dot and expands outward only when overlap forces it.
- `OEC-all` `IARC` label currently has an explicit northwest shim:
  - `nudge_x = -20000`
  - `nudge_y = 22000`
- `OEC-all` main geography now uses the original Tilemill `project.mml`
  bounds again. External partner areas configured in `oec_insets` are removed
  from the main canvas and rendered in floating inset windows linked back to
  HQ.
- `OEC-all` Qatar is now handled as a repositioning inset, not as a magnified
  map. The inset is deliberately small and should stay close to southeastern
  Europe/Turkey while keeping Qatar itself geographically proportionate.
- The QA connector landing point may need a tiny inset-local correction even
  when the base node geometry is correct. Treat that as an inset-composition
  detail, not as evidence that the QA node geometry itself is wrong.
- The current local overlay data now place the Slovakia node in Martin rather
  than Bratislava. If the Slovakia node moves again, update both
  `HQlineNN.geojson` and the matching endpoint in `onlyLinesHQlineNN.geojson`.

## Extra-Map Data Contracts

- `prepare_covid_geojson.py`
  - input: full pilot GeoJSON with `biobankID`
  - output: subset GeoJSON with the same point schema as the full pilot export
  - COVID membership is inferred from current live/cached biobank metadata, not
    from a `biobankCOVID` property in the full pilot GeoJSON
- `prepare_quality_geojson.py`
  - output properties:
    - `biobankID`
    - `biobankName`
    - `biobankType`
    - `qual_id`
  - `qual_id` values should be normalized to `eric`, `accredited`, or `Other`
  - collection points should use collection coordinates when available and fall
    back to the parent biobank coordinates otherwise
- `render_federated_platform.R`
  - requires `biobankType` and `biobankLabel`
  - currently accepted `biobankType` values are `LocatorBiobank` and `FinderBiobank`
- `render_crc_cohort_sized.R`
  - both input GeoJSONs require:
    - `biobankID`
    - `biobankName`
    - `biobankType`
    - `contribSize`

## Current OEC Projection Findings

- The early OEC parity failures were caused by projection-path mismatches.
- The custom Transverse Mercator bbox must be projected by sampling the bbox
  boundary densely. Transforming only the four corner points is not sufficient.
- Even with the correct CRS and bbox, the composed `cowplot` placement must
  preserve the projected aspect ratio. Stretching the OEC panel into an
  arbitrary page box makes it look like a cylindrical projection.
- The current `oec_bbox` should stay aligned with the original Tilemill
  `project.mml` bounds unless there is a deliberate visual redesign.
- For OEC countries, bbox-hit filtering was not enough because overseas
  territories from countries such as France distorted the projected extents.
  Use real clipping for OEC country and OEC line layers.
- For OEC inset geography, clipping only the masked country was also wrong:
  it prevented any neighboring-state context from appearing. Inset geography
  should clip the full country layer to the inset bbox, while points/nodes stay
  filtered to the inset partner mask.
- The legacy `HQlineNN.geojson` node points already sit on the correct line
  endpoints. A later experiment that tried to "realign" them from line strings
  was wrong and was removed.
- `HQlineNN.geojson` uses plain country names such as `Belgium`, while
  `onlyLinesHQlineNN.geojson` uses names such as
  `BelgiumConnecting LineString`. If those files are ever matched by name
  again, normalize that suffix explicitly.

## Current OEC Symbol Rules

- `OEC-all` country polygons, node squares, biobank dots, and the base `IARC`
  observer circle are now rendered through `geom_sf(...)`.
- This change materially fixed the earlier drift where OEC boxes and dots were
  visibly off while the lines themselves were correct.
- `IARC` remains a composite symbol:
  - observer circle
  - internal node square
  - internal biobank dot
- The internal `IARC` sub-symbols still use projected local offsets relative to
  the `IARC` anchor point. That is acceptable because the anchor itself now
  follows the `sf` geometry path.
- OEC lines now use a white under-stroke plus the orange top stroke. This acts
  as a lightweight halo and is visually preferable to simply making the lines
  thicker.

## Multi-Agent Review Pattern

When OEC visual tuning becomes ambiguous, the useful multi-agent setup was:

- implementation agent
  Focus: computational correctness, compact/safe code, assertive validations.
- modularity reviewer
  Focus: maintainability, edit boundaries, sustainability of config and helper
  abstractions.
- visual reviewer
  Focus: compactness, clarity, parity against published Tilemill outputs, and
  whether the layout is actually pleasant rather than merely technically valid.

For OEC visual review, surrounding white border / dead whitespace is a
separate quality criterion. Do not force it to match the published original on
that point, because the original OEC render also leaves too much white space.
Prefer a tighter, visually balanced border even when that diverges from the
reference image.

This worked best when the main agent kept the critical-path rendering work local
 and delegated only sidecar review/critique. The subagents were useful for:

- challenging inset placement and Europe sizing
- identifying abstraction problems in the first OEC inset implementation
- catching visually broken "technically correct" states

Do not delegate the actual last-mile geometry debugging if the next action is
blocked on the answer; that part was faster locally.

## Visual History Rule

- The visual-review agent should keep several prior rendered states, not only
  the latest file.
- Use `archive-visual-history.sh` before and after material visual changes to
  snapshot the current rendered outputs under `R-maps/compare-temp/history/`.
- Keep the history local and ignored by Git. It is for short-term comparison,
  not for committed artifacts.
- Default retention should stay small and rolling (currently `--keep 8`) unless
  a specific review session needs more.
- For OEC inset anchor debugging, verify the resolved HQ page anchor against
  all three raster export sizes (`small`, `med`, `big`). The intended behavior
  is effectively identical normalized page coordinates across sizes.

## Export Rules

- `bbmri_save_plot_formats(...)` writes:
  - `*-small.png`
  - `*-med.png`
  - `*-big.png`
  - `*-small.pdf`
  - `*-med.pdf`
  - `*-big.pdf`
  - default `<prefix>.pdf`
  - default `<prefix>.svg` when `svglite` is available
- Raster exports are generated with fixed physical size plus varying DPI, not
  by changing the physical page size. This is intentional so dots/text stay
  visually proportional across `small`/`med`/`big`.
- Because raster device math rounds at the pixel level, a configured size can
  occasionally land one pixel off in height on a specific output. Treat that as
  a rendering-device artifact unless it becomes materially visible.
- `render_pilot_maps.R` must use the dedicated
  `bbmri_save_members_oec_all_formats(...)` path for `OEC-all`, not the generic
  `bbmri_save_plot_formats(...)` path. Otherwise the size-specific HQ-anchor
  resolution is bypassed.

## External Inputs

The current OEC renderer expects these explicit external inputs:

- `/home/hopet/codex/directory-scripts/R-maps/data/IARC.geojson`
- `/home/hopet/codex/directory-scripts/R-maps/data/HQlineNN.geojson`
- `/home/hopet/codex/directory-scripts/R-maps/data/onlyLinesHQlineNN.geojson`

These are repo-local working copies of the legacy Tilemill overlay files. Do
not move these assumptions into root-level repo guidance. They are specific to
the current map migration work.

Current extra-map local inputs:

- `/home/hopet/codex/directory-scripts/R-maps/data/federated-platform.geojson`
- `/home/hopet/codex/directory-scripts/R-maps/data/CRC-Cohort.geojson`
- `/home/hopet/codex/directory-scripts/R-maps/data/CRC-Cohort-imaging.geojson`

Keep these defaults repo-local. They replace direct reads from the legacy
Tilemill tree.

## Practical Review Standard

When changing map code, validate at least:

- the script parses with `Rscript -e 'parse(file=...)'`
- the relevant renderer completes successfully
- the expected output files are regenerated
- the visual change is checked against the published Tilemill references when
  the change affects proportions, label placement, framing, or symbol sizes

## What Not To Change Casually

- `standard_bbox` and `oec_bbox`
- `oec_insets`
- `oec_crs`
- `biobank_size_widths`
- the `OEC-all` member/observer palette split
- the decision to exclude `bbmri-eric:ID:EXT_NASBIO` from `OEC-all`

Any change to those should be recorded in `TRANSFER.md`, because they are part
of the current parity baseline.
