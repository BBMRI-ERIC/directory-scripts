# SO2 And MuCP Participation Maps

Status: Approved for implementation with the plan as a goal on 2026-11-14.
Branch: `survey-analysis`; commits and pushes require separate authorization.

## Agreed Requirements

- Support the existing `bbmri-members` and OEC geographic layouts.
- Include maps in their respective SO2 descriptive and MuCP-led combined PDFs.
- Country bars, count labels and country codes must not overlap other countries'
  groups. Nearby countries may use displaced groups with leader lines.
- SO2 has a membership-coloured map with outlined Directory totals, filled
  respondent counts, `x of y` above and a two-letter country code below.
- SO2 also has a green choropleth of `100 * respondents / Directory biobanks`.
- MuCP has two adjacent vertical bars per country: MuCP responses and SO2
  responses, with their intersection highlighted in both.
- Include unresolved individual respondents, using available reviewed
  deduplication. They are not silently excluded for lacking a Directory match.
- Preserve `x > y`: fills may exceed Directory outlines, and the percentage
  legend may exceed 100%. For `y = 0`, retain `x of 0` and show the percentage
  as unavailable rather than zero.
- Separate preparation, R rendering and report inclusion, like the UpSet workflow.
- Provide separate SO2/MuCP shell helpers. Termux uses Debian proot; Cygwin
  automatically uses Windows `Rscript.exe`, without opening RStudio; other
  systems use `Rscript`. No automatic installation.

## Counting Contract

Freeze a small Directory inventory through `directory.py`; count biobank IDs,
not collections, geocoded points or response documents. Group by reported country,
not staging prefix. EXT records contribute to their reported country. Default
denominator scope is active biobanks; shared withdrawn options explicitly change
the denominator, never remove survey responses. Record target, schema, scope,
inventory hash and original cache observation time when available. An unavailable
observation time remains unknown; export time is a separate field.

Build one local participation identity per known biobank. Reuse SO2
`responses_summary.observation_sources`, reviewed identities, and MuCP accepted
Directory identities. Resolve additional duplicate or cross-survey identities
only through explicit, source-bound local review. Names or email similarity
alone never merge records. Unlinked unresolved submissions remain provisional
individual reporting units and are counted, with that qualification beside maps.
Multiple collection scopes and internal projections of the same reporting unit
do not create extra biobanks. A source containing explicitly distinct reviewed
biobanks can legitimately contribute several units.
Only accepted individual owners suppress a decomposed source's provisional root.
When every scoped identity proposal is rejected, an individual response still
counts once as unresolved; a national summary still counts zero.

National summaries are not biobanks and contribute zero by themselves. Retain
them as evidence in the audit. They can contribute to participation counts only
after decomposition into identifiable individual biobanks with source-bound
evidence and ownership. Deduplicate those biobanks against all other submissions;
neither a collection nor an unassigned residual summary creates another biobank.
If decomposition cannot establish any individual biobank, the summary adds zero.
This counting rule is user-approved.

For country c, store Directory D, SO2 S, MuCP M and confirmed shared B. Enforce
`0 <= B <= min(S, M)`; do not enforce `S <= D`. Shared means the same accepted
Directory ID or an explicitly reviewed cross-survey identity. Unconfirmed
possible overlaps remain in S/M but not B; the caption states that B is confirmed
overlap, not necessarily all overlap. Membership maps use both full survey
populations independently of `merge-mucp --join`.

Use reviewed country corrections for the surveys explicitly named in their
source references, then Directory country for resolved identities, then consistent
country evidence within each survey. A MuCP-only correction cannot change SO2.
Within-survey conflicts remain in the unknown-country counts. When the surveys
place a shared identity differently, keep each source-survey placement and retain
the unresolved linkage in `shared_country_conflicts`, not in a guessed country's
shared segment. This keeps B<=min(S,M) for all count rows, including unknown.
Use ISO alpha-2 map codes, including ME, TR and GB, while preserving original
MNE/Turkey/UK wording in provenance. Unknown-country respondents are retained in
an explicitly labelled side summary, not placed at invented coordinates.

The standalone SO2 JSON is authoritative for SO2 grouping in both exports.
MuCP preparation must not silently re-group it using extra resolver matches from
the combined analysis. Additional cross-survey links and duplicate corrections
belong to the same optional reviewed identity file supplied to both exports.
Record a separate SO2 participation hash so the two map families can demonstrate
that their S counts and country assignments use the same observations.
The combined document must declare complete MuCP input-record coverage; a legacy
document without reconstructable full coverage needs regeneration.

The caption calls S/D a comparison with Directory inventory, not strict coverage
of Directory biobanks: S includes provisional/non-Directory respondents, and the
inventory may have a different reference date.

## Appearance And Placement

Render both layouts by default; an export option selects either one. Produce
two SO2 maps per layout and one MuCP comparison map per layout. Reuse country
membership colours, projection, coastline scaling, masks and island/inset
configuration from `R-maps/map_config.R`. Do not add biobank dots, HQ routes or
node-network decorations to these participation maps.

SO2: Directory outline height D, respondent fill height S, count label above
`max(D, S)` and CC below. A zero Directory denominator still has a visible
respondent bar; zero responses have a visible baseline/count label.

MuCP: left bar height M; right bar has the SO2 outline D and fill S. Both contain
an identically coloured base segment of height B. The left count is M; the right
is `S of D`. Small M/S labels identify the pair, with one CC beneath the pair.
All count bars within a map, including insets and off-map groups, share one
linear count-to-height scale. The overlap segment is part of each total, never
added above it. Use distinct MuCP/SO2 fills and one shared highlight colour.

Choropleth: a sequential green scale from 0 to at least 100, extending to the
actual maximum when necessary. Zero is a pale green, undefined ratios use a
separate grey/hatch legend, and countries without relevant observations are
distinct from measured zeroes. Legends state the denominator and its scope.

Render to a 240 x 135 mm landscape canvas with vector text and PNG previews.
Use 9 pt labels by default, never shrink below 8 pt to hide collisions. Preserve
geographic aspect ratio; spare canvas space can hold callouts. The report places
each figure on a landscape page without further text-shrinking. Keep map page
size configurable internally so the page-fit test can enforce actual TeX bounds.

Measure the complete country group on the actual graphics device: both bars,
numeric labels, M/S labels, CC, and padding. Place groups deterministically in
physical units, not by independently repelling labels. Treat legends, insets,
captions and page edges as obstacles. Reuse configured geographic seeds and
manual layout-specific overrides; use bounded displacement with leader lines.
If local placement fails, use reserved callout rows rather than accept overlap
or silently omit countries. Countries outside the geographic extent use an
explicitly titled outside-extent panel with the same bars and scale. The final
collision audit must contain zero group/group or group/obstacle intersections;
otherwise rendering fails and existing outputs remain intact.

## Preparation And Inclusion

Add peer commands `export-so2-map-r` and `export-mucp-map-r` to
`survey-so2-directory.py`. They prepare aggregate CSVs, a lightweight local
identity audit, frozen Directory inventory, render specification and hash-bound
input manifest. They do not run R. SO2 preparation consumes descriptive JSON;
MuCP preparation consumes combined JSON plus the full SO2 descriptive JSON.
Use the combined payload's complete matching inventories, not only its selected
`biobanks` array. Validate that both payloads refer to the same SO2 response file.
Allow reuse of a previously exported Directory inventory for identical denominators.

Add `--map-assets-dir` to `describe`, `render-descriptive-report` and `merge-mucp`.
No assets means unchanged operation and no R dependency. A supplied empty bundle
produces an explicit maps-not-rendered note. A nonempty stale, partial, wrong-kind
or tampered bundle blocks publication; it must never embed an unrelated map.
Place SO2 maps after Responses Summary and MuCP maps in Cohort overview before
question statistics. Explain that MuCP comparison maps use full survey inputs,
even when the surrounding report selects an inner or other restricted cohort.

Validate canonical participation/source hashes, output file hashes, chart kinds,
layout, numeric counts and zero-collision diagnostics. Store map-input provenance
in report JSON separately from question statistics. R runtime versions, relevant
R source/config hashes and basemap hashes belong to the output manifest.
Report rendering validates survey identity material offline; it does not refresh
the Directory or require the exporting R environment's source paths to exist.
The frozen, source-bound SO2 grouping and additional reviewed identity decisions
travel in the bundle. SO2 rendering checks its current responses_summary against
that grouping; MuCP rendering checks the original SO2 workbook hash and complete
MuCP source/identity inventory. It replays the bundled explicit map-review decisions,
not a newly guessed or implicit external mapping. A conflicting accepted identity
fails validation with regeneration advice. Changes to map-only review decisions
require re-exporting the bundle. Python computes canonical JSON hashes once; R
checks input file bytes and records that hash without reserializing JSON to
recompute a supposedly identical cross-language canonical encoding.

Publish aggregate map PDFs and PNGs as a complete validated render set. Copy
external PDF bytes into the existing report compilation/publication staging
pipeline, including standalone chart output, rather than leaking temporary or
machine-specific paths into TeX. A TeX-only result must retain a portable sibling
asset directory. Compilation or copying failures roll back all requested outputs.

## Shell Helpers

Provide tracked `scripts/render-so2-maps.sh` and `scripts/render-mucp-maps.sh`,
sharing `scripts/survey-map-runtime.sh`. Invocation is
`bash scripts/render-so2-maps.sh [--rscript PATH] [--overwrite] BUNDLE_DIR`
and equivalently for MuCP. Resolve the repository from the helper location and
the bundle from its argument, so arbitrary working directories are supported.

- Termux: detect the host environment and `proot-distro`; invoke Debian's Rscript
  noninteractively, binding absolute repository and bundle paths at the same
  guest paths. Consolidate redundant/nested binds. Print the command/runtime
  choice and a precise error if Debian, R or packages are missing.
- Cygwin: prefer explicit `--rscript`, then `RSCRIPT`, then `Rscript.exe` on PATH,
  then Windows R installations under Program Files/R. Prefer a configured
  `R_HOME` before scanning versioned installations; select the newest parsed
  numeric version deterministically. Use `cygpath` for Windows argument paths;
  retain the executable's shell-usable path. Never launch RStudio or interpolate
  user input through eval/constructed R code.
- Elsewhere: explicit `--rscript`, then `RSCRIPT`, then `Rscript` on PATH.

Check bundle kind before execution; pass only quoted argument-vector elements,
propagate R's exit status and preserve pre-existing results on failure. R checks
ggplot2, sf, cowplot, jsonlite and digest before rendering. Natural Earth data
reuse the existing map cache; document first-use download requirements. No
silent dependency installation, raw survey upload or remote model invocation.

## Scope And Approval

This work is confined to `survey-analysis`; survey-specific documentation stays
under `docs/surveys/`. It does not update the Directory, change questionnaire
statistics, introduce new fuzzy matching, or change existing map outputs.
Private identities, input data, manifests with source IDs, generated maps and
reports remain local/ignored. Only data-free examples and synthetic fixtures
are candidates for future commits.

The handling of unresolved respondents, values above 100%, zero denominators,
national-summary decomposition, external rendering, platform detection and
automatic Windows Rscript execution is user-approved. Concrete new CLI names,
adjacent MuCP bars, full-population comparison, map canvas and placement policy
above were accepted when the user requested pursuit of the plan as a goal.
