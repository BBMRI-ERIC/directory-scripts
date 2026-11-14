# Survey Participation Maps Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline or bounded
> superpowers:subagent-driven-development after approval. Track steps below.

**Goal:** Generate reproducible SO2 participation and MuCP/SO2 comparison maps in
both existing geographic layouts, with safe platform helpers and PDF inclusion.

**Architecture:** Python prepares source-bound country counts and a frozen
Directory inventory. R reuses existing geographic components, places measured
country glyphs and writes verified PDF/PNG bundles. Existing report pipelines
validate and publish those assets without needing R or Directory access.

**Tech Stack:** Existing Python survey/Directory APIs, pytest/hypothesis, shell,
R ggplot2/sf/cowplot/jsonlite/digest, XeLaTeX and existing PDF staging.

**Spec:** [Participation-map design](../participation-maps-design.md).
**Status:** Implementation and Termux/Debian geographic/report validation complete
(2026-11-14). Scoped commit and push authorized. Windows dispatch is mock-tested,
not field-tested.

## Global Constraints

- Work on `survey-analysis`; do not merge survey features into master.
- Include unresolved individual respondents; retain available reviewed deduplication.
- Never equate a submission, collection scope or national summary with a distinct
  biobank without the identity/provisional-unit rules in the design.
- A national summary itself always adds zero biobanks. Count only identifiable
  individual biobanks obtained through decomposition, deduplicated against other
  responses; an undecomposed summary or residual adds zero.
- Directory access is exclusively through `directory.py`; `describe` and
  `render-descriptive-report` remain Directory-free and R-free.
- Preserve above-100% results and undefined zero-denominator ratios honestly.
- All absolute bars within each figure share one linear scale, including insets.
- No bar/label group overlaps at the physical output size; no hidden omissions.
- Termux uses Debian proot, Cygwin uses automatic Rscript.exe, otherwise Rscript.
- No auto-installation, personal source data in Git, live writes, commits or pushes
  without separate authorization. All Python contracts include args/return semantics.

## Review Focus

1. Unresolved/duplicate/projected responses inflate counts or manufacture overlap.
   Task 1 tests source ownership, reviewed identities, repeated scopes and B bounds.
2. A selected combined cohort drops SO2-only/MuCP-only contributors. Task 1 tests
   all four joins against the same full participation inventory.
3. Small-country glyphs, long counts and inset transforms collide or change scale.
   Task 3 tests measured boxes at final dimensions with dense synthetic countries.
4. Platform paths contain spaces, quotes or Windows drive syntax. Task 4 uses fake
   executables and argument capture, plus real platform smoke tests where available.
5. Stale assets or interrupted rendering replace good reports. Tasks 2 and 5 test
   hash mismatch, nonempty partial bundles, cross-device stages and rollback.

## Existing Integration Points

- `survey-so2-directory.py`: `build_cli`, `_add_common_cli`, `build_directory`,
  `run_describe`, `_render_descriptive_payload`, `run_merge_mucp`, main dispatch.
- `so2_response_merging.py:merge_descriptive_responses`: original source rows,
  reviewed deduplication and `observation_sources`; do not change answer merging.
- `survey_combined.py:build_combined_payload` and `execute_merge`: selected banks
  plus unmatched/review/excluded inventories retain source identity information.
- `survey_identity.py:build_identity_catalogue` and `resolve_scoped_sources`:
  accepted Directory ownership and reviewed projection provenance.
- `so2_descriptive_upsets.py:write_upset_r_bundle` and asset validators: reuse
  staging/hash conventions, not UpSet-specific row semantics or R code.
- `so2_descriptive_report.py:render_descriptive_tex`, `render_descriptive_pdf`,
  `RenderedDescriptiveReport`: extend for external binary figure staging.
- `survey_combined_report.py:render_combined_tex`, `publish_combined_outputs`:
  insert maps in overview and use existing transactional output handling.
- `R-maps/map_common.R`: country loading/cache, fills, projections, fonts and labels.
- `R-maps/map_config.R`: layout membership colours, extents, coastline scaling,
  country offsets and OEC insets.
- `R-maps/render_bbmri_members_oec_all.R`: existing panel/inset transforms and
  geometry masking; its public builder currently requires point/HQ/route files.
- `R-maps/strategic_objectives_common.R`: frame-box placement is useful precedent,
  but assumes objective-role counts and standard CRS. Do not call it unchanged
  for survey glyphs or claim it guarantees collision-free OEC placement.

## Task 1: Canonical Participation And Directory Counts

**Files:** create `survey_participation.py`,
`survey-mappings/survey_participation_identities.example.json`,
`tests/test_survey_participation.py`, synthetic fixtures under
`tests/fixtures/so2_mucp/participation/`.

**Interfaces:**
- `directory_inventory(directory) -> dict`: freeze sorted IDs, normalized country,
  withdrawn state, scope, target/schema, timestamp evidence and content digest.
- `collect_participation(so2_payload, combined_payload=None, identities=None) -> dict`:
  immutable full-source unit roster, source links, survey flags, country decisions,
  provisional status and explicit national/unknown-country audit entries.
- `build_country_counts(participation, inventory) -> dict`: ordered rows containing
  `country`, `directory_count`, `so2_count`, `mucp_count`, `shared_count`,
  `so2_percent` (number/null), per-survey provisional counts and diagnostics.
- `participation_binding(...) -> dict`: canonical source/identity material used
  for repeatable hashes, independent of chart paths, report timestamps and join.

- [ ] Write failing synthetic tests: Directory D=5, SO2 S=3, MuCP M=2, shared B=1;
  SO2 duplicate submissions and MuCP scopes/projections do not add extra units.
- [ ] Add unresolved examples: D=2/S=3 gives 150%, D=0/S=2 gives null percentage,
  D=4/S=0 gives 0%; unknown country remains in audit, never in invented geography.
- [ ] Add tests for reviewed non-Directory cross-survey groups, conflicting country
  evidence, source-hash mismatches, distinct biobanks sharing a response file,
  national summaries and named reviewed projections without double counting.
  Assert that an undecomposed summary adds zero; decomposition identifying two
  biobanks adds exactly two, and if one already responded separately, that
  separate response does not add a third. Unassigned residual summary adds zero.
- [ ] Test all join modes, including SO2 respondents outside selected MuCP banks;
  repeated records appearing in review and bank arrays are counted exactly once.
  Reject inconsistent duplicate record IDs. Country mappings include EXT->reported
  country and MNE->ME; differing answer content does not change participation.
  Require the same SO2 participation hash/counts in SO2 and MuCP exports using
  the same descriptive JSON and reviewed identity file; extra combined resolver
  matches must not silently regroup standalone SO2 respondents.
- [ ] Run `pytest -q tests/test_survey_participation.py`; confirm failures before code.
- [ ] Implement these pure adapters, reusing retained source/grouping decisions.
  Do not infer identities from names or blindly collapse by original filename.
  Inventory scope never filters respondents, and missing cache dates stay unknown.
- [ ] Rerun the file, including hypothesis cases for duplicate/order invariance;
  expected PASS and stable sorted serialization across input permutations.

## Task 2: Map Bundles And Peer Export Commands

**Files:** create `survey_map_assets.py`, `tests/test_survey_map_assets.py`;
modify `survey-so2-directory.py`, `tests/test_survey_branch_boundary.py`.

**Interfaces:**
- `write_map_bundle(participation, inventory, output_dir, *, kind, layouts,
  overwrite=False) -> Path`: sibling-staged map counts, render spec, identity audit,
  inventory and input manifest. Kind is `so2` or `mucp`; no R execution.
- `validate_map_assets(participation, assets_dir, *, expected_kind) -> ValidatedMapAssets`:
  typed absent/empty/ready state, figures and frozen denominator provenance;
  nonempty invalid bundles raise InputError.
- New peers: `export-so2-map-r -i DESCRIPTIVE.json --output-dir DIR` and
  `export-mucp-map-r -i COMBINED.json --so2-json DESCRIPTIVE.json --output-dir DIR`.
- Shared flags: `--map-layout {bbmri-members,oec,both}` (default both),
  `--directory-inventory JSON`, `--participation-identities JSON`, `--overwrite`,
  existing Directory authentication/schema/cache/withdrawn options.

- [ ] Write failing parser/help and bundle tests before implementing the commands.
  Assert frozen-inventory mode never constructs Directory; normal export uses
  `build_directory`/shared CLI helpers, including non-ERIC authentication semantics.
- [ ] Test overwrite/input collisions, partial failures and existing sentinel
  preservation. A user inventory must match its declared target/schema/scope;
  explicit conflicting options fail rather than silently override provenance.
- [ ] Test SO2 source-hash agreement between the two JSON inputs. A combined
  payload lacking a reconstructable full inventory fails with regeneration advice;
  do not pretend an old inner-cohort payload represents the complete surveys.
- [ ] Run `pytest -q tests/test_survey_map_assets.py tests/test_survey_branch_boundary.py`;
  verify RED, then implement the interfaces and dispatch.
- [ ] Use input-manifest schema version 1: kind, layouts, canonical participation
  hash, survey hashes, inventory hash/scope, aggregate CSV hash and render spec.
  Do not include large raw survey bodies in bundles; keep identity audits local.
  Output manifest records file hashes, dimensions, per-country counts, collision
  diagnostics, basemap/config/renderer hashes and R/package versions.
  Carry frozen source-bound SO2 grouping and explicit additional review decisions
  in the input manifest. R validates file bytes and propagates Python's canonical
  participation hash; do not rely on Python/jsonlite producing identical JSON bytes.
- [ ] Rerun tests for GREEN; preserve existing commands' no-input help and defaults.

## Task 3: Both R Layouts And Collision-Checked Rendering

**Files:** create `R-maps/render_survey_participation.R`,
`R-maps/survey_participation_common.R`, `tests/test_survey_maps_rendering.py`,
`tests/r/test_survey_participation.R`; extend `R-maps/map_common.R` and
`render_bbmri_members_oec_all.R` only for a small tested country-panel extraction.

**Interfaces:**
- R CLI: `Rscript R-maps/render_survey_participation.R --bundle=ABS_DIR
  --kind=so2|mucp [--overwrite]`.
- `bbmri_survey_country_panels(layout, cfg, canvas_mm)`: country geometry,
  membership-fill layers, geographic-to-page transforms and inset obstacles.
- `bbmri_survey_glyphs(counts, kind, scale, device)`: measured atomic country
  groups including all labels, not independently repelled text.
- `bbmri_place_survey_glyphs(groups, panels, reserved_boxes)`: deterministic
  positions, leader lines, complete bounding boxes and zero-collision diagnostics.

- [ ] Write R fixture assertions for exact bar heights/fills/outlines and common
  scale: S>D, D=0, S=0, shared base B in both bars, large digit labels, and a
  choropleth legend extending to 150 rather than capping at 100.
- [ ] Add dense BE/NL/DE/CH/AT/CZ/SI/IT/MT examples plus CY/QA/insets and
  outside-extent respondents. Validate every measured box is on-canvas, outside
  reserved areas and disjoint from others at the final physical page size.
  Validate intended internal text/bar separation within each group as well,
  especially M/S and numeric labels for zero-height bars.
- [ ] Run the R tests and Python wrapper to establish RED. Use real R/grid font
  measurement, not Python guessed text widths or source-string-only assertions.
- [ ] Extract only the geographic panel assembly needed to reuse existing OEC
  clipping/insets without fake point files or unwanted HQ routes. Old builders'
  defaults and membership/geography outputs must remain unchanged.
- [ ] Implement the 240x135 mm PDFs and 300 dpi PNGs specified by the design.
  Render both SO2 figures and the paired MuCP figure for every selected layout.
  Layout-specific measured placement uses bounded displacement and reserved
  callout rows; if audit cannot reach zero overlaps, fail without publication.
- [ ] Stage all figure files and output-manifest before promotion; include hashes,
  exact count rows, source/config/basemap evidence and collision boxes. Failed
  rendering, missing packages or locked target files must preserve prior outputs.
- [ ] Run R tests and relevant existing map geometry/inset tests; inspect rendered
  PDFs/PNGs at report size, especially dense central Europe and zero denominators.
  Save review evidence locally; conditional skips are not proof of R correctness.

## Task 4: SO2/MuCP Cross-Platform Shell Helpers

**Files:** create `scripts/render-so2-maps.sh`, `scripts/render-mucp-maps.sh`,
`scripts/survey-map-runtime.sh`, `tests/test_survey_map_helpers.py`.

**Interfaces:** each entry helper takes `[--rscript PATH] [--overwrite] BUNDLE_DIR`,
validates its own kind and delegates one quoted argument vector to the runtime
helper. Shell scripts locate the checkout through their own location, not cwd.

- [ ] Write failing subprocess tests with fake uname/proot-distro/cygpath/Rscript
  executables. Capture exact arguments and exit status; require no real R, Windows
  or proot in these portable dispatcher tests.
- [ ] Include paths with spaces, apostrophes, non-ASCII characters and leading
  hyphens; verify no eval or shell/R-code interpolation and no argument splitting.
- [ ] Test Termux binding of repository and external bundle paths, nested path
  consolidation, missing Debian/R/packages and propagation of renderer failure.
- [ ] Test Cygwin R_HOME/PATH/Program Files discovery and explicit --rscript/RSCRIPT
  precedence, numeric version sorting, native path conversion and absence of any
  RStudio launch. Test direct Linux/macOS Rscript dispatch and missing-runtime errors.
- [ ] Run `pytest -q tests/test_survey_map_helpers.py`; verify RED, implement the
  three helpers according to the design, and require GREEN plus `bash -n` on all.
- [ ] Perform an actual Termux/Debian smoke render and direct-R render if available.
  Run a real Cygwin/Windows smoke test on a suitable host before claiming that
  platform is field-validated; mocks alone establish dispatch, not Windows R health.

## Task 5: Validated Inclusion And Atomic Publication

**Files:** modify `survey-so2-directory.py`, `so2_descriptive_report.py`,
`survey_combined.py`, `survey_combined_report.py`; extend
`tests/test_so2_descriptive_report.py`, `tests/test_survey_merge_mucp_cli.py`,
`tests/test_survey_combined_publication.py`,
`tests/test_survey_map_assets.py` and `tests/test_survey_map_report_integration.py`.

**Interfaces:** `--map-assets-dir` on describe, render-descriptive-report and
merge-mucp; optional `map_assets` on both TeX composers. Extend
`RenderedDescriptiveReport` with a default-empty external-figure mapping, so old
callers remain compatible. Stage those binary assets through both existing
publication functions rather than running R or embedding temporary paths.

- [ ] Write failing tests for offline SO2 inclusion with Directory/R constructors
  forbidden. Missing option leaves current output unchanged; a supplied empty
  bundle gives an explicit omitted-map note; stale/tampered/partial bundles fail.
- [ ] Verify figure counts/order: both layouts yield four SO2 maps after Responses
  Summary, two comparison maps in MuCP overview; selected one-layout bundles work.
  Captions disclose unresolved units, confirmed overlap, frozen inventory and
  full-survey versus selected-report cohort. Every map uses a landscape page.
- [ ] Add failures for kind mismatch, changed dedup/country/identity source hashes,
  changed aggregate CSV, missing PDFs, path traversal and image-hash mismatch.
  Reject differing render spec/count audit rather than trusting valid filenames.
- [ ] Test portable TeX-only assets and --output-chart-dir binary copies, invalid
  output/input nesting, paths needing LaTeX escaping, and map copy/compile failure
  rollback with pre-existing JSON/TeX/PDF/chart sentinels on separate target dirs.
- [ ] Run the affected tests for RED, then implement validation, map provenance in
  JSON and binary staging. Renderers must recompute participation binding from
  current retained survey sources and explicit bundled review decisions, not
  trust a stale embedded geographic block. SO2 checks its current observation
  grouping; MuCP checks source workbook hashes and its full identity inventory
  against the frozen SO2 grouping. No silently guessed replacement registry is used.
  MuCP uses the same original SO2 source binding as the prepared bundle; no new
  Directory session or R process is needed just to verify imported map figures.
- [ ] Rerun tests and existing SO2/combined publication suites for GREEN; compile
  synthetic end-to-end PDFs with two XeLaTeX passes/convergence as appropriate.
  Delete/move the original bundle and verify published TeX/assets remain usable.

## Task 6: Operator Documentation And Final Validation

**Files:** create `docs/surveys/maps.md`; update `docs/surveys/README.md`,
`so2.md`, `mucp.md`, `DEVELOPMENT.md`, `AGENTS.md`; adjust ignore rules and
distribution-boundary tests only for newly introduced survey-specific artifacts.
Do not put detailed survey instructions into the master-facing docs/maps.md.

- [ ] Document prepare -> helper -> ordinary report commands, both layouts,
  actual declared R dependencies, first-use basemap downloads, offline cache
  expectations, identity review, Directory date/scope and above-100% interpretation.
- [ ] Document explicit unresolved/national/unknown-country treatment, confirmed
  overlap limitations and the distinction from the selected combined cohort.
  Keep real survey identity files, input/output bundles and generated reports local.
- [ ] Add exact input/return semantics to every new Python definition and update
  survey specifications/guardrails, especially Directory-free rendering and source
  ownership. Existing README remains a short navigation page.
- [ ] Run `python3 -m py_compile` on changed Python, `bash -n` on the helpers,
  `pytest -q tests/test_survey_participation.py tests/test_survey_map_assets.py
  tests/test_survey_maps_rendering.py tests/test_survey_map_helpers.py
  tests/test_survey_map_report_integration.py` and `pytest -q`.
- [ ] Run real R render assertions, compare CSV/manual country counts, ensure
  `shared_count <= min(S, M)` everywhere and inspect all final map pages at
  printable size. Verify labels and bars do not overlap in either layout.
- [ ] Obtain one independent scoped Sol review of original requirements, full
  delta, counting and output safety. Fix material findings and rerun affected tests.
- [ ] Report actual per-platform verification; flag unavailable real Cygwin tests
  as outstanding rather than completed. Do not auto-install to force a pass.
  No commit, merge or push without explicit separate authorization.

## Proposed Operator Workflow

SO2, after generating the existing descriptive JSON:

```sh
python3 survey-so2-directory.py export-so2-map-r \
  -i so2-2025-20260916-descriptive.json --output-dir so2-participation-maps
bash scripts/render-so2-maps.sh so2-participation-maps
# Add to the existing describe command, retaining its other options:
# --map-assets-dir so2-participation-maps --overwrite
```

MuCP, after generating the existing combined JSON:

```sh
python3 survey-so2-directory.py export-mucp-map-r \
  -i so2-mucp-readable.json --so2-json so2-2025-20260916-descriptive.json \
  --directory-inventory so2-participation-maps/directory-inventory.json \
  --output-dir mucp-participation-maps
bash scripts/render-mucp-maps.sh mucp-participation-maps
# Add to the existing merge-mucp command, retaining its other options:
# --map-assets-dir mucp-participation-maps --overwrite
```

These interfaces are implemented. Full geographic validation remains pending. Helper
--overwrite applies only to rendered assets, while export --overwrite replaces
the prepared bundle after validation; both preserve old artifacts on failure.

## Execution Ledger

- Publication authorized after completion: commit and push only the survey-map
  source, tests, data-free example, guides, design/plan and privacy ignores.
  Exclude private survey inputs, real reviewed identities, caches, generated
  reports/maps and unrelated local artifacts. Reuse the recorded independent
  reviews and full-suite evidence; recheck the staged inventory and affected tests.
- Pre-push gate: 91 scoped tests passed with all 30 intended files staged,
  including real six-variant R rendering, KOMA page-fit, distribution boundaries
  and tracked Python documentation contracts. Python compilation, shell syntax,
  staged whitespace and privacy-inventory checks pass. No generated data or
  unrelated files are staged. The remote survey-analysis baseline was unchanged.

- Final completion audit (authoritative over the historical action lists):
  - Task 1: full-source identity ownership/counts, unresolved individuals, national
    summaries, projections, country corrections and all four join partitions
    verified. The actual two bundles have identical SO2 and Directory bindings.
  - Task 2: both peer commands prepared real frozen bundles; hash/count/render
    audits and source-contract replay pass without Directory/R during inclusion.
  - Task 3: all six real-data PDF/PNG variants rendered, visually inspected and
    validated; twelve device collision audits are zero. Real six-variant synthetic
    rendering, repeating percentages, polygon repair, internal backing clearance,
    extreme counts and outside-panel packing are covered by regressions.
  - Task 4: actual Termux/Debian helpers rendered both bundles. Portable native
    and Cygwin dispatch/discovery/error/quoting tests pass, including missing
    runtimes and relative leading-hyphen paths. Real Windows field execution is
    unavailable and is not claimed; no automatic installation was added.
  - Task 5: complete real SO2 and MuCP report copies published with verified maps
    and existing validated UpSet assets. SO2: 165 pages, maps 10-13. MuCP: 480
    pages, maps 13-14. Captions stay with the maps; actual KOMA page-fit tests
    cover both kinds and nonzero country conflicts. Original reports untouched.
  - Task 6: guides/specifications/guardrails and privacy ignores updated. Final
    full suite: 1322 passed, 39 skipped, the same eight unrelated baseline failures.
    Six additional test-only join/runtime cases passed afterwards; the affected
    participation/helper subset has 35 passing tests. No production changes after
    the full run. Python contracts/compilation, shell syntax and whitespace pass.
- Local report copies: so2-2025-20260916-descriptive-with-maps.pdf and
  so2-mucp-readable-with-maps.pdf, with portable ignored map-assets companions.
  Both map bundles and report outputs remain ignored/private. Current R source
  hashes match the manifests; strict offline replay accepts both rendered bundles.
- Final geographic review found a 0.255 mm backing/bar overlap at an extreme
  synthetic count ratio. A padded-bounds regression reproduced RED, then passed
  after both neighbour-bar and top-label separation included backing width.
  Independent review otherwise found no material issues in the geographic fixes;
  latest real-data figures and embedded report pages were visually checked by
  the controller. No commits or pushes performed or authorized.

- Approval received for Debian sf/cowplot/digest and required dependencies.
  Installation resumed with --no-install-recommends. The first attempt hit stale
  security-package URLs (404); refreshing package metadata succeeded and the
  same approved installation is now running. No commits or pushes authorized.
  This removes the previous permission blocker, not the remaining validation gates.
- Approved packages installed after metadata refresh: sf 1.0-19, cowplot 1.1.3,
  digest 0.6.37; existing ggplot2 4.0.3 and jsonlite 2.0.0 remain active. Natural
  Earth downloaded into the ignored cache. The first full geographic test found
  malformed source rings (RU) and self-intersections (RO/SK). In-memory closure
  plus st_make_valid fixes these; synthetic holes/islands area and metadata tests
  observed RED then GREEN, and the initial six-variant real rendering test passed.
- Real-data rendering then exposed percentage rounding in jsonlite and greedy
  off-map packing failure for VN. The test denominator now uses seven to exercise
  repeating percentages; the strict audit reproduced RED. Output serialization
  uses 17-digit precision. A seven-country MuCP callout regression reproduced
  VN placement failure, then passed with edge-first packing. Configured standard
  label seeds and an outside-extent heading are applied; label-seed regression
  observed RED then GREEN. Final six-variant and real-data renders are rerunning.

- Blocked audit: the same missing-dependency approval condition persisted across
  three consecutive goal turns. The previous continuation made concrete progress
  by repairing the producer contract; this recheck confirms sf/cowplot/digest
  remain absent and neither prepared bundle has rendered PDFs. No further
  required geographic validation can proceed without an external change.
  No test/reviewer/renderer process is still running. Mark the active goal blocked,
  not complete. Resume with approval to install Debian r-cran-sf,
  r-cran-cowplot and r-cran-digest plus required dependencies, then follow the
  rendering/inspection/report-compilation steps below. No installation,
  commitment, push or weakening of acceptance criteria is authorized by this state.

- Latest checkpoint (supersedes the earlier chronological entries): Tasks 1, 2,
  4 and 5 are implemented and covered by portable tests. Task 3's real R/grid
  geometry and rollback tests pass, but real sf maps/visual inspection are not
  verified. Task 6 docs and scoped review are implemented; final full-suite
  evidence is recorded below. No commits, pushes or installs performed.
- Independent review repair verification: initial eight findings repaired;
  follow-up caught rejected-only projection root loss and MuCP-only country
  overrides leaking into SO2. Both reproduced RED, repaired and independently
  confirmed by the same Sol-medium reviewer (37 participation/assets/report
  tests passed). No remaining findings in that focused scope; geographic
  verification remains blocking, not waived.
- Counting decisions: retain an unresolved individual root if all scope identity
  proposals are rejected. Only accepted identified owners suppress that root;
  national summaries still count zero. Reviewed country corrections apply only
  to surveys explicitly named by source references. Differing shared placements
  go in shared_country_conflicts, separately from all country/unknown count rows.
- Safety evidence: actual R/grid tests force both promotion failure and failed
  restoration, proving old backups survive. Both Python report publishers restore
  JSON/TeX/charts/maps after promotion starts. PDF and PNG audits are distinct;
  generated companion paths cannot overlap input bundles. Empty-country geometry
  and extreme-count label/bar separation are covered.
- Final integration subset: 82 passed, 1 skipped (real geospatial render).
  Stable final full rerun including the producer-contract repair: 1318 passed, 40 skipped,
  eight unchanged failures
  (legacy Yapsy imp imports, exporter docs index, existing proot cwd map tests).
  Broader SO2/combined report regressions: 222 passed. New/changed Python
  documentation contracts, Python compilation, shell syntax and R parsing pass.
  Logs are local temporary artifacts: survey-maps-producer-contract-pytest.log and
  survey-maps-producer-targeted.log. No in-scope test failed in those runs.
- Actual SO2 and MuCP CLI preparation succeeded with the shared active cached
  inventory. Both ignored bundles contain no rendered maps. The Termux helper
  selected Debian correctly and failed clearly at missing sf/cowplot/digest,
  without publishing files. The two bundles have equal SO2 participation and
  inventory hashes; offline combined-report replay succeeds. No inputs changed.
- Continuation corrected the earlier false diagnosis of mismatched source files:
  the map adapter expected survey_file_sha256/mucp_json_sha256, but the actual
  merge producer emits so2_sha256/mucp_sha256. Corrected fixtures reproduced RED,
  adapter now uses the real contract, and 24 participation/assets tests passed.
  A separate synthetic regression exercises actual execute_merge, descriptive
  parsing/merging, bundle preparation and replay rather than invented metadata.
  Existing source hashes were equal; regeneration of source reports is not needed.
  Same independent reviewer confirmed this correction with 25 participation/asset
  tests passing and no findings in scope. A Debian installation simulation changed
  nothing; required packages are still absent and approval is still pending.
- Genuine remaining environment gates: Debian sf/cowplot/digest installation
  needs approval (requested; no approval received), then first-use Natural Earth
  basemap fetch/cache and rendering of all six map variants. Inspect all output
  PDFs/PNGs at report size before claiming collision-free geographic output.
  Windows/Cygwin field smoke needs a suitable host; portable argv/discovery,
  R_HOME/Program Files, explicit/env overrides and numeric version selection
  are tested but are not real Windows execution.
- Resume after dependency approval: install only approved Debian packages;
  prepare the basemap cache through the documented renderer; run
  tests/test_survey_maps_rendering.py, render dense real-data bundles for both
  surveys/layouts, visually inspect them and compile the reports with assets.
  Reuse the now-validated local descriptive/combined pair and prepared bundles.
  Their SO2 hashes match. Never patch input hashes to bypass validation. Keep
  all real source/review/output artifacts local and uncommitted.

- Independent Sol-medium audit completed: 27 focused tests independently GREEN,
  eight material findings require repairs (not a completion approval): R backup
  cleanup ordering; residual/scope double counting; map input output protection;
  within-glyph label/bar overlap; MuCP changing frozen SO2 country bindings;
  optional full-inventory evidence; incomplete OEC geometry reuse; PNG audit
  overwriting PDF evidence. One TDD repair pass is in progress; no findings waived.

- Execution baseline: survey-analysis at d338dfd304efef184dbff4f9c4ba4f8e94d2f9c4.
  Tracked worktree initially clean; planning files and private artifacts preserved.
  Execute inline, TDD per task, one independent final audit, no commits/pushes.
- Ruling: use the existing dedicated survey-analysis checkout rather than another
  worktree; it is already separate from master and has no conflicting tracked edits.
- Environment: Debian proot R 4.5.0 and ggplot2/jsonlite are available; sf,
  cowplot and digest are missing. Native Rscript and a Windows/Cygwin host are
  unavailable. No dependencies installed; real rendering needs those packages.
- Task 1 core adapters: 8 tests GREEN after observing missing-module RED. Includes
  unresolved counts, unclamped ratios, zero national summaries with reviewed
  decomposition, full inventory independence and order-invariant bindings.
  Remaining hardening is included in subsequent integration/final audit.
- Task 2 implementation in progress; four new tests observed RED. Frozen export
  and tamper checks pass; CLI regression exposed a missing cache_choices argument,
  now corrected to the existing helper's explicit directory cache choice.
- Tasks 1/2 initial integration: 22 targeted participation/bundle/peer-regression
  tests GREEN. Added subsequent RED->GREEN coverage for partial source inventories
  and missing Montenegro/Qatar country aliases.
- Task 4 portable dispatch tests: 4 GREEN after missing-script RED. Native,
  Termux/proot and Windows/Cygwin argv handling, quoted paths, kind errors and
  propagated renderer failures verified; shell syntax passes. Real Windows absent.
- Task 3 pure R/grid tests: GREEN on actual Debian R after missing-file RED.
  Device-measured text extents, dense-country separation, common scale, >100%
  bar geometry, zero responses and deterministic placement verified. Full sf
  basemaps still blocked by unapproved missing Debian packages; no installs made.
- Task 5 binary asset replay/publication tests: 9 GREEN after missing-module RED.
  SO2 and MuCP TeX-only publication, sentinel preservation, stale data, count/hash
  checking and country/obstacle collision audits covered. Broader existing report
  publication/CLI tests: 30 GREEN. More failure-path and compile coverage pending.
- Current new-feature suite: 27 GREEN, including canonical-ID review consistency,
  zero national-summary counting, real R/grid geometry and actual XeLaTeX map-PDF
  compilation. Combined new/existing publication, merging and CLI regression subset:
  57 GREEN. All new/changed Python docstring contracts, compilation, bash syntax
  and R parsing pass. Runtime verification of final reviewer confirms
  gpt-6.1-sol / medium from child turn_context (not agent self-identification).
- Task 6 operator/spec/guardrail docs written under docs/surveys; final review and
  stable full rerun pending. No shared master map source or Directory data changed.
- Initial local replay failed with a hash-mismatch message; the later continuation
  traced this to incorrect adapter field names, not different source bytes.
  The producer-contract correction and successful replay supersede that hypothesis.
- First exploratory full run: 1289 passed, 39 skipped, 9 failed. Eight failures
  concern unchanged legacy Yapsy/imp, exporter docs index and proot-cwd tests;
  the new unusual-country test was RED while that run was in progress and is
  now fixed. Final stable full-suite run remains required.
- Ruling: reuse existing bbmri_oec_panel_plot and panel transforms with typed
  empty sf layers, rather than extract them again or introduce fake point files.
  Existing map implementations remain untouched; direct wrapper tests/render
  evidence must establish compatibility once sf/cowplot become available.
- Ruling: implement Task 4 before Task 3's full render, since runtime dispatch is
  independently testable while the required R geospatial packages are unavailable.

- User-approved: include unresolved individual respondents; keep x>y and >100%;
  undefined ratios when D=0; external-R workflow; separate automatic helpers;
  Termux Debian proot, Cygwin Windows Rscript.exe, otherwise direct Rscript.
- User-approved clarification: national summaries never count as biobanks;
  only identifiable individual biobanks extracted from them may count, once each
  after deduplication against all other responses. Without decomposition, zero.
- Proposed defaults explicitly recorded in the design: both layouts, adjacent
  paired bars, full survey populations, physical canvas and collision/callout
  policy. Accepted with the instruction to pursue this plan as a goal.
- Existing integration points inspected on survey-analysis. Current standalone
  describe remains offline, while combined JSON retains complete matching
  inventories beyond selected banks. Existing OEC builder is not a drop-in
  point-free background and existing bar placement is not layout-independent.
- No production implementation, data refresh, package installation, source
  modification, report regeneration, commit or push performed during planning.
- Plan self-review completed: corrected the CLI entry-point reference to
  `build_cli`; pinned consistent SO2 grouping across both exports, explicit
  source-bound review replay and cross-language hash handling; added both
  within-group and between-country placement checks. National-summary counting
  and the remaining design defaults are now approved by the goal instruction.
