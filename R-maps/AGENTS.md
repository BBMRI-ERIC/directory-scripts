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

The R code is responsible only for rendering. GeoJSON generation still starts
from `geocoding_2022.py`.

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
- `render_pilot_maps.R`
  End-to-end pilot runner from cached Directory GeoJSON generation to all three
  rendered outputs.
- `README.md`
  Human-oriented overview and dependency notes.
- `SKILLS.md`
  Folder-local workflows and commands.
- `TRANSFER.md`
  Current state, open issues, and handoff notes.

## Non-Negotiable Design Decisions

- Keep `geocoding_2022.py` as the GeoJSON producer unless there is an explicit
  decision to replace it.
- Keep map-specific scripts thin. Shared style/placement/export logic belongs
  in `map_common.R` and `map_config.R`.
- Do not hardcode machine-specific legacy output paths into the renderers.
  External Tilemill-era overlays are passed as explicit inputs.
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
