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

## Current Labeling Rules

- Shared halo logic lives in `bbmri_geom_text_halo(...)` in `map_common.R`.
- The current intended halo style is:
  - inner ring: `1px` opaque white
  - outer ring: `3px` semi-transparent white
- Outer ring opacity is currently `0.25`.
- `nolabels` country labels and `IARC` use that explicit halo setup.
- `sized` country labels use the same halo setup.
- `OEC-all` `IARC` uses the same halo setup.

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
- `oec_crs`
- `biobank_size_widths`
- the `OEC-all` member/observer palette split
- the decision to exclude `bbmri-eric:ID:EXT_NASBIO` from `OEC-all`

Any change to those should be recorded in `TRANSFER.md`, because they are part
of the current parity baseline.
