# Geocoding Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for native execution, or superpowers:subagent-driven-development if explicitly selected. Steps use checkbox syntax for tracking. Keep a single writer; independent final review does not edit code.

**Goal:** Rename the geocoder, make coordinate sources and summary statistics reliable, and support authoritative manual/researched locations with a portable Markdown research workflow.

**Architecture:** Keep `geocoding.py` as the standalone CLI and map-export orchestrator. Extract importable resolution, validation, cache, research-packet and statistics functions into `geocoding_utils.py`; reuse `Directory`, `cli_common.py` and `geojsonutils.py`. Every selected biobank gets one provenance-bearing result before GeoJSON generation and statistics.

**Tech Stack:** Existing Python, argparse, diskcache, geopy/Nominatim, pandas, pytest, JSON and Markdown; existing shell/R launchers. No new runtime dependency, model API or package installation.

**Spec:** [Approved design](geocoding-cleanup-design.md).

## Global Constraints

- Preserve INI dataset filters, country/name/ID exclusions and output-property selection. Exclusions precede every location source and research request.
- Two optional JSON inputs, each an authoritative snapshot: manual overrides and institution resolutions. Removed entries and omitted files cannot authorize cached positions.
- Institution fallback requires both unusable/missing Directory coordinates and missing street/address; city/postcode alone do not disqualify it. Newly added streets or coordinates supersede it.
- Manual policies are exactly `missing-location`, `missing-coordinates`, `always`. Research entries can use only `missing-location`.
- No AI runtime: optionally emit Markdown instructions/context; an external interface returns the complete institution-resolution JSON.
- Keep raw/researched local files, caches and outputs out of commits; invented schemas/examples/fixtures are shareable. Protect existing local artifacts and never purge a cache as a migration shortcut.
- Preserve GeoJSON feature properties, existing prefix-plus-`.geojson` behavior, address fallback order, negative caching and existing service retry/TLS policy.
- Count biobanks once per winning source, not queries or requests. Query specificity is not positional accuracy.
- Document every explicit Python definition, parameter, result and meaningful exception using repository Google-style contracts.
- This plan does not authorize a push, Directory write, map regeneration, new dependency or repair of unrelated baseline failures.

## Review Focus

1. A current street added under the same contact ID must defeat both old institution and stale address caches, even if current geocoding fails (Task 2).
2. Removed, changed or omitted input snapshots must not resurrect successful cached locations; malformed files must fail before API/output work (Tasks 1, 2 and 5).
3. INI-excluded biobanks must never reappear through `always` overrides, AI results, statistics or research packets (Tasks 3 and 5).
4. Repeated research must preserve the complete catalogue, including out-of-scope entries, without re-researching accepted entries; unresolved answers must validate without invented coordinates (Tasks 1 and 3).
5. Multiple biobanks and locations belonging to one named institution must not inflate its institution count or distort cache/API attribution (Tasks 2 and 4).

## Files And Interfaces

Create:
- `geocoding_utils.py`: context/result models, strict local JSON validation, address resolver/cache provenance, research Markdown and summary helpers.
- `schemas/geocoding-locations-v1.schema.json`: machine-readable common contract embedded into research instructions; no external schema service.
- `docs/examples/geocoding-manual-overrides.json` and `docs/examples/geocoding-institution-resolutions.json`: invented examples only.
- `tests/test_geocoding_locations.py`, `tests/test_geocoding_resolution.py`, `tests/test_geocoding_review.py`, `tests/test_geocoding_statistics.py`, `tests/test_geocoding_cli.py`.

Rename `geocoding_2022.py` to `geocoding.py` and
`tests/test_geocoding_2022_coordinates.py` to `tests/test_geocoding_coordinates.py`.
Update the caller/docs inventory in Task 6; do not leave an executable wrapper.

Define these documented dataclasses in `geocoding_utils.py`:
- `LocationContext`: `biobank_id`, `biobank_name`, `institution`, `institution_source`, `country`, `address`, `zip`, `city` (strings), `longitude_raw`, `latitude_raw` (raw objects). Missing text normalizes to empty strings; retain original organization text separately in evidence as needed. `institution_source` distinguishes `juridical_person` from the explicitly labelled biobank-name fallback.
- `LocationCatalogue`: `kind` (string), `entries` (ID-to-validated-entry mapping), `document` (complete validated JSON envelope). Empty catalogue represents an omitted file and authorizes nothing. Its entries contain only validated organizational/research fields, not full Directory records.
- `CoordinateResult`: `coordinates` (longitude/latitude tuple or None), `source` (`directory`, `manual`, `institution`, `address`, `unresolved`), `channel` (`input`, `cache`, `api`, `none`), `query_fields` (tuple), `reason` (string), `evidence` (mapping). Document ownership; results and contexts must not mutate Directory records.

Address/query signatures include current normalized field values; institution signatures include the exact current entry and its request context. No caller may infer provenance from the presence of a coordinate pair alone.

## Task 1: Freeze Baseline And Define Validated Location Inputs

**Files:** New helper, schema, examples and `tests/test_geocoding_locations.py`; existing design/plan evidence.

**Interfaces:** Produce the three dataclasses above; `make_location_context(biobank: Mapping, contact: Mapping | None) -> LocationContext`; `context_fingerprint(context: LocationContext) -> str`; `load_location_catalogue(path: Path | None, expected_kind: str) -> LocationCatalogue`; `parse_decimal_coordinates(longitude_raw: object, latitude_raw: object) -> list[float]`.

- [x] Record initial HEAD and tracked/untracked task scope. At execution time use the worktree skill, preserving the approved untracked design/plan by copying only those two documents into the execution worktree. Run baseline `pytest -q` there before source changes and record exact failures/skips, never in the user workspace where historical tests may overwrite reports. Keep this plan as the only execution ledger and store detailed logs privately.
- [x] Write location-contract tests for both file kinds, missing/empty catalogues, all three manual policies, forbidden research policy, duplicate JSON keys/IDs, unsupported versions, malformed files and exact case-preserving biobank IDs. A resolved entry requires valid finite coordinates; reject booleans as coordinates. Zero is valid.
- [x] Add `test_unresolved_research_does_not_require_address_or_coordinates`: invented unresolved/ambiguous entries validate with identity, context fingerprint, policy, status and explanation, while providing no usable position. Resolved entries missing evidence, address or coordinates fail clearly.
- [x] Run `pytest -q tests/test_geocoding_locations.py`; verify red failures identify the missing helper/contract rather than environment errors.
- [x] Implement a common envelope `schema_version="1.0"`, `kind`, `entries` list. Entry keys are `biobank_id`, `policy`, `status`, `explanation`, optional named `longitude`/`latitude`, optional `address` object. Institution entries additionally use `request_id`, `context_fingerprint`, `institution`, `country`; resolved entries require `evidence` (nonempty list of source/note objects), `confidence` (`high`, `medium`, `low`); optional `qualifier` retains qualifications. Define exactly these fields in schema and runtime validation, including status-dependent requirements and complete-catalogue preservation.
- [x] Implement strict local validation without adding `jsonschema` to core dependencies. Reject duplicate object keys during JSON parsing. Explicitly requested missing/unreadable files are errors; `None` yields an empty catalogue. Unknown schema/status/policy/kind/entry keys fail with path and entry context. Do not validate whole Directory payloads through these models.
- [x] Normalize only relevant context fields. Preserve IDs and source spelling; whitespace-canonicalize fingerprint components `(biobank_id, institution, country, city, zip)` deterministically. Treat absent/NaN contact fields as missing, not literal `nan`. Safely handle a missing contact or `juridical_person`; label fallback institution names without inventing legal ownership.
- [x] Move the existing two-component decimal diagnostic parser into the helper, retaining its combined error messages. Reuse `geojsonutils.get_entity_coordinates()` for supported numeric/decimal/DMS/DMM coordinate normalization, catching invalid input at the resolver boundary. Never classify valid numeric coordinates as invalid merely because they are not strings.
- [x] Run `pytest -q tests/test_geocoding_locations.py`; add schema/examples to the allowlisted commit only after tests pass. Record red/green evidence and commit the coherent input-contract checkpoint.

## Task 2: Implement One Source-Aware Resolver And Cache Contract

**Files:** `geocoding_utils.py`, `tests/test_geocoding_resolution.py`.

**Interfaces:** Consume Task 1 contracts. Produce `resolve_coordinates(context: LocationContext, manual: LocationCatalogue, institutions: LocationCatalogue, cache: MutableMapping, geocode: Callable[[str], tuple[str, object | None]]) -> CoordinateResult`. The injected geocoder returns existing `resolved`/`not_found`/`disabled` statuses and a geopy-compatible longitude/latitude object; no model APIs. Produce `resolve_address(context: LocationContext, cache: MutableMapping, geocode: Callable) -> CoordinateResult` for the address-only stage.

- [x] Write table-driven precedence tests: manual always beats valid Directory coordinates; valid coordinates beat conditional/manual research; each conditional policy has its precise eligibility; manual beats research; present street disqualifies research even after a failed geocode; otherwise current resolved institution precedes city/postcode fallback. Verify absent/malformed coordinate components fall back rather than crashing.
- [x] Add `test_new_street_same_contact_defeats_all_old_institution_cache` and `test_changed_address_does_not_reuse_biobank_fallback`. Spy on cache keys and queried text, not merely final coordinates. A failed current-address lookup must not return an institution coordinate.
- [x] Add authoritative-snapshot cases: removed entry, omitted file, empty catalogue, changed coordinates/evidence/context, and resolved-to-ambiguous/unresolved changes. None may resurrect an old institution cache entry. An invalid requested file is rejected by Task 1 before calling this resolver.
- [x] Exercise complete/partial cached query variants, negative cache entries, live success, live failure and service disable. Test a success found from cache after another lookup attempted the API: its channel remains `cache`. Count shared-address cache reuse per biobank without counting retries as separate successes.
- [x] Run `pytest -q tests/test_geocoding_resolution.py` red, then implement the ordered source selection from the design. Return one structured result on every normal resolution path; an unresolved result retains a reason. Validate manual/research pairs through the same finite/range checks.
- [x] Use namespaced v2 cache records holding source, current context/entry signature, coordinates, query fields and explanation. Check eligible cached address variants before live lookups, choosing the most specific cached success. Preserve address order `address, zip, city, country`; classify the actual winning suffix, including cases where fields are absent.
- [x] Reuse legacy query records only where the stored query proves compatibility. Do not let a legacy biobank cache lacking current-address signature bypass a street lookup. Retain unusable old entries on disk; no purge or API request just to enrich statistics. Never mix institution/manual records into address caches. A currently supplied file, not a cache record, authorizes research use.
- [x] Run both Task 1 and Task 2 suites green. Commit resolver/cache behavior and tests, recording exact scenarios and commands.

## Task 3: Generate A Self-Contained Institution Research Packet

**Files:** `geocoding_utils.py`, `tests/test_geocoding_review.py`; consume the committed schema.

**Interfaces:** Produce `collect_institution_requests(observations: Sequence[tuple[LocationContext, CoordinateResult]], institutions: LocationCatalogue) -> list[dict]`; `render_institution_review(requests: Sequence[Mapping], institutions: LocationCatalogue, schema: Mapping) -> str`.

- [x] Write tests selecting only non-excluded observations with missing usable supplied coordinates and missing street, no applicable manual winner and no current eligible resolved research entry. City/postcode-only fallback success remains eligible for better institution research. Valid supplied coordinates prevent research.
- [x] Test per-biobank binding and deterministic country/institution/ID order. Similar names and separate locations must not be silently merged. Use one request per biobank ID; avoid institution-identity inference. Include original names, country, city/postcode, request ID and matching context fingerprint; never contact names/emails/phones/IDs.
- [x] Add `test_second_packet_carries_complete_prior_catalogue_without_researching_accepted_entries`: retain all supplied entries, including out-of-scope IDs, unchanged in the carry-forward block; list only the new/stale/unresolved eligible targets for research. With no input catalogue, carry-forward is empty. The expected external return is one complete replacement JSON, never a partial delta.
- [x] Add adversarial invented organization text containing Unicode, quotes, Markdown backticks and instruction-like text. The packet must encode these as data, preserve identifiers through JSON round-trip, and identify source values as untrusted data rather than instructions.
- [x] Run `pytest -q tests/test_geocoding_review.py` red, then implement rendering with an embedded exact schema, invented example and explicit return-JSON-only instructions. Require evidence-backed address/coordinate research and ambiguity explanations; prohibit invented coordinates, Directory writes or changes to manual overrides. Specify preservation of carry-forward entries without re-research.
- [x] Keep unresolved/ambiguous fields status-dependent and match Task 1 schema. Read the schema using a module-relative path, never the invocation cwd. Generated Markdown/results are sensitive/local outputs; add no real institution fixture.
- [x] Run Tasks 1–3 suites green, then commit packet generation and tests. No separate AI runner or second executable is added.

## Task 4: Add Reconciled Verbose Statistics

**Files:** `geocoding_utils.py`, `tests/test_geocoding_statistics.py`.

**Interfaces:** Produce `summarize_results(observations: Sequence[tuple[LocationContext, CoordinateResult]]) -> dict`; `format_statistics(summary: Mapping) -> str`. The caller supplies only selected, non-excluded biobanks, once each.

The summary keys are `considered`, `directory`, `manual`, `manual_by_policy`,
`institution_biobanks`, `institutions_represented`, `address_total`,
`address_by_specificity`, `unresolved`, `unresolved_by_reason`.
`address_by_specificity` maps `street`, `postcode`, `city`, `country`, `unknown`
to integer `cache`/`api` counts. Enforce both winning-source reconciliation and
the address subcounts; institution counts are supplementary, never additive.

- [x] Write a mixed fixture with Directory, all manual policies, institution, cached/live address and unresolved winners. Assert mutually exclusive winning-source counts sum to considered biobanks and address cache/API rows reconcile independently. A supplied-coordinate/manual winner must not count as AI merely because a research entry exists.
- [x] Test actual query specificity classes: address included; postcode without address; city without postcode/address; country only; unknown legacy specificity. Missing fields must not shift classification by positional index. Zero API successes must print zero even if some unsuccessful calls occurred.
- [x] Add `test_one_institution_two_biobank_locations_counts_once`: two distinct positions with the same institution name/country count two AI-resolved biobanks, one represented institution. Case/whitespace normalize; no fuzzy matching. Different countries or institution names remain separate. A warm-cache research position stays in the AI category.
- [x] Run the statistics suite red, then implement the exact design labels, including `AI-assisted institution resolution: N biobanks` and `Institutions represented: N`. Do not add campus/location totals or public AI file/cache splits. Use the accepted research entry's institution/country for its supplementary name-based count.
- [x] Run Tasks 1–4 suites green, verify output contains query-specificity wording rather than claims of building-level precision, and commit the summary checkpoint.

## Task 5: Rename And Integrate The Standalone CLI

**Files:** Rename `geocoding_2022.py` to `geocoding.py`; rename coordinate test; create `tests/test_geocoding_cli.py`; modify helper/config documentation comments if necessary.

**Interfaces:** `geocoding.py` exposes `build_cli_parser() -> argparse.ArgumentParser`, `main(argv: Sequence[str] | None = None) -> int` and a guarded executable entry point. The existing rate-limited Nominatim behavior becomes an injected callable; helper imports perform no CLI parsing, Directory access, cache opening or geocoding.

- [x] Add CLI red tests for new help/standard option order, positional config, `-o/--output-prefix`, hidden old long aliases, shared auth/schema/withdrawn/cache flags and all three optional JSON/review flags. Keep `--print-filtered-dataframe`; no short-option collisions. Importing either module must make no network or output calls.
- [x] Add offline orchestration tests with a fake Directory and geocoder. INI country/name/ID exclusions and dataset filters must remove records before any manual override, research lookup, request generation or statistics, including an excluded record with policy `always`. Preserve existing feature/property and withdrawn-scope behavior.
- [x] Add failure-path tests: missing config/sections report actionable input errors; nonempty legacy `[Override biobank position]` fails with ID-based JSON migration instructions; an empty legacy section is accepted. Other INI settings continue to function. No old coordinate authority remains active behind the two JSON snapshots.
- [x] Test requested malformed/missing JSON and input/output aliases before API calls or output replacement, including symlink aliases and aliases between the GeoJSON and Markdown targets. Test numeric/missing-coordinate columns and invalid manual overrides without generating user reports.
- [x] Rename and refactor the executable. Use existing shared parser/auth/cache helpers, existing Directory access and existing INI selection semantics. Read current contacts to build contexts; do not mutate shared Directory records. Process each selected biobank once, call Task 2 resolver, preserve map properties and write via `geojsonutils` feature helpers.
- [x] Preserve `safe_geocode()` retry/rate-limit/service-disable and existing TLS behavior in a testable adapter; do not introduce startup probes or change transport policy. Instantiate the live adapter lazily only when an address lookup actually needs it. Close diskcache in `finally`; report Ctrl+C concisely.
- [x] Validate all inputs/output targets before publication. Generate the optional Markdown using Task 3, including the full current research catalogue. Use sibling staging files for GeoJSON and Markdown, then publish only after both requested products serialize; remove task-created stages on failure and preserve pre-existing output bytes when staging fails. Retain ordinary successful rerun overwrite behavior; do not add an unrelated mandatory overwrite option.
- [x] Emit Task 4 summary at INFO only after successful requested output writes. Capture logs to prove it appears in `-v` and `-d`, not default mode; dataframe printing remains independently controlled. Keep filtered/excluded counts separate from the considered denominator.
- [x] Update the renamed coordinate tests to import the helper rather than AST-extracting script definitions; preserve both original combined-error assertions. Run all five geocoding suites plus coordinate tests, `python3 geocoding.py --help`, and changed-file compile checks. Commit integration only when these pass; no legacy executable wrapper remains.

## Task 6: Update Map Callers, Operator Guides And Specifications

**Files:** `R-maps/export.sh`, `R-maps/render_pilot_maps.R`, `R-maps/{README.md,AGENTS.md,SKILLS.md,TRANSFER.md}`, root `README.md`, `AGENTS.md`, `DEVELOPMENT.md`, `docs/{maps.md,setup.md,libraries.md}`, `tests/test_cli_help.py`, `tests/test_python_docstring_contract.py`, `tests/test_rmaps_new_maps.py` and any additional tracked references found by search.

**Interfaces:** Existing map entry points invoke `geocoding.py` with the same prefix/config behavior. The R function `bbmri_run_geocoding_export(...)` keeps its public parameters; its default filename and canonical output option change, not map semantics.

- [x] Add or update caller tests expecting the new executable and `--output-prefix`, including Directory cache-purge forwarding. Verify the shell launcher resolves a clone-relative executable rather than machine-specific paths. Run red before changing callers.
- [x] Update all active references found by `git grep -n geocoding_2022`. Historical migration notes may name the old script explicitly, but no live launcher, helper-path contract or operator command may invoke it. Update CLI-help and documentation-contract inventories to include both the renamed CLI and new helper.
- [x] Document the canonical three-run workflow: normal geocoding with `--output-institution-review`; external research returning complete JSON; rerun with `--institution-resolutions`. Include continuing research with the current JSON, authoritative removal semantics, separate manual overrides, evidence/ambiguity interpretation and INI coordinate migration. Use invented/example paths only.
- [x] Add exact override-policy/precedence/cache/statistics specifications to `DEVELOPMENT.md`, and update the relevant root/R-map guardrails without repeating the full specification in AGENTS. Explain that country exclusions remain in the INI and beat JSON coordinate overrides.
- [x] Document the strict executable rename, hidden argument aliases, unchanged `.geojson` suffix, no runtime AI dependency, no automatic Directory changes, and privacy of review/results. Add narrowly named ignore patterns for generated default review/result filenames; do not ignore the committed schema/examples or broad unrelated JSON files.
- [x] Run `sh -n R-maps/export.sh`, `sh R-maps/export.sh --help`, `pytest -q tests/test_rmaps_new_maps.py tests/test_cli_help.py tests/test_python_docstring_contract.py tests/test_markdown_portability.py`. If native R is unavailable, record R-test skips and use the existing configured proot only if already available; no installation or full map rendering. Reconcile pre-existing failures with baseline, not weakened assertions.
- [x] Validate all changed Markdown links and operator examples against real parser help; commit caller/docs integration with exact test evidence.

## Task 7: Independent Audit And Final Verification

**Files:** Whole task delta, this plan's execution ledger; repair only in-scope findings.

**Interfaces:** Final runtime behavior satisfies the approved design, with source provenance, authoritative snapshot revocation, INI scope and statistics verified together.

- [x] Pause writers and review committed, staged, unstaged and relevant new files against the original requirements and design. Check all runtime/schema/example files are tracked and no private packet/result/cache or generated output is staged. Confirm no survey or unrelated map changes slipped in.
- [x] Run `python3 -m py_compile geocoding.py geocoding_utils.py` plus changed tests, all targeted geocoding suites, then `pytest -q` in the isolated execution checkout. Log exact commit, commands, failures, skips and fixture scope. Compare each failed test ID with the recorded baseline; synthetic acceptance tests cannot be skipped to declare success.
- [x] Obtain one independent read-only Sol 6.1 medium audit of the full requirements/delta and evidence. The earlier Astra design review is not an implementation audit. Fix substantive in-scope findings with red/green tests; rerun affected gates and broaden when interfaces changed. Do not add repeated whole-context reviewers by default.
- [x] Reconcile every design section with code and tests, especially missing-file cache authority, newly added addresses, complete carry-forward JSON, unresolved status validation, correct institution counts and INI exclusions. Record any true blocker rather than marking partial work complete.
- [x] Commit the final scoped repair/evidence checkpoint only after applicable gates pass. Hand over actual tool commands, commit(s), existing baseline limitations and any still-pending specialist/environment check. Do not push, merge into another branch, purge live caches, run AI research or regenerate maps without separate authorization.

## Planned Operator Examples

Run from the clone root; filenames below are illustrative local artifacts:

```sh
python3 geocoding.py -v geocoding.config \
  -o biobank-points \
  --manual-overrides geocoding-manual.local.json \
  --output-institution-review geocoding-institutions-review.md

# Supply the Markdown to an external research interface and retain its complete
# institution-resolution JSON as geocoding-institutions.local.json.
python3 geocoding.py -v geocoding.config \
  -o biobank-points \
  --manual-overrides geocoding-manual.local.json \
  --institution-resolutions geocoding-institutions.local.json

# Research only remaining eligible targets while carrying accepted entries forward.
python3 geocoding.py -v geocoding.config \
  -o biobank-points \
  --manual-overrides geocoding-manual.local.json \
  --institution-resolutions geocoding-institutions.local.json \
  --output-institution-review geocoding-institutions-review.md
```

All explicitly supplied files must exist; omit an optional flag rather than
supplying a nonexistent placeholder. Removing either JSON entry/file disables
that source on the next run. The cache is never its replacement authority.

## Execution Ledger

- Execution started on isolated branch `geocoding-cleanup` from `ea44a2b`; the main master checkout is untouched. Baseline full suite: 582 passed, 40 skipped, eight pre-existing CLI/Yapsy, exporter-document format and R-map failures in 76.28 seconds. Logs are under the main checkout's ignored `data-check-cache/geocoding-cleanup/`. Weekly allowance telemetry is not surfaced. No installations or live geocoding performed.
- Task 1 red: missing helper import; first green 15 tests. Additional malformed-field red cases exposed empty IDs and unhashable confidence; validators now reject them as ValueError. The parser already rejects non-text policy/status before enum membership. Schema and examples contain invented organizations only.
- Task 1 complete: commit `b75f767`; 19 input tests and 19 documentation-contract tests passed. Task 2 red reproduced missing resolver; green validates precedence, address changes, file revocation and provenance. Internal contact ID was added to context solely for safe legacy query-cache lookup; it is excluded from research exports and fingerprints. No legacy cache scanning or deletion is performed.
- Task 2 complete: 27 input/resolver cases passed. Tasks 3/4 red: missing packet/statistics imports. Green: 31 tests across all four targeted modules. Packets preserve complete out-of-scope catalogue entries without repeat research, encode instruction-like names as JSON data, and exclude personal contact fields. Summary tests distinguish two biobank positions from one institution-name/country group and reconcile actual successful address channels.
- Tasks 3/4 complete: combined checkpoint `bf50986`. Task 5 CLI red: new import absent; green: 42 geocoding cases including round-trip research, authoritative file omission, excluded always-override, publication rollback, recovery-copy retention, numeric coordinates and hidden aliases. API transport adapter remains lazy. Ruling: do not activate the old unreachable insecure SSL fallback during extraction; installed GeocoderUnavailable inherits GeocoderServiceError and followed the ordinary retry branch before this refactor. A targeted red/green test locks that effective behavior. Cost if wrong: different provider exception hierarchies could require a separately approved transport-policy change; no TLS verification is disabled here.
- Tasks 5/6: renamed executable and coordinate tests, updated all live callers and documentation, preserved the shared CLI and INI filter semantics. Feature/doc-contract gate: 62 passed before the final review additions. Caller gate: 140 passed, 14 native-R skips and four pre-existing baseline failures. Shell syntax/help passed; existing Debian proot R parsed the actual renderer and verified canonical output-prefix plus directory-purge arguments without rendering maps or installing packages. Official schema and both invented examples also validate with the already-installed optional schema checker; no new runtime dependency.
- Task 7 audit: independent `gpt-6.1-sol` medium runtime verified. Three substantive findings reproduced RED: bank-cache shortcut hiding a more-specific query cache; contact-address country incorrectly taken from the biobank; cleanup exceptions masking retained-backup diagnostics. All three fixed in one pass, with 48 geocoding tests GREEN. Contact country is now separate in context/query/research fingerprints. Cleanup failures log separately and cannot replace the primary recovery error. No reviewer edits, live queries or private-data fixtures.
- Verification environment: Android Python omits hardlink creation; the alias regression tests real symlinks and a simulated same-inode contract instead of skipping protection. The first full run exposed this fixture limitation, which was corrected; subsequent full run had 626 passed, 40 skipped and exactly the same eight baseline failures before review fixes. A fresh full suite is running after the three review fixes. No weekly allowance telemetry surfaced.
- Final verification complete: post-review full suite `pytest -q -ra` reported 629 passed, 40 skipped, eight failures in 73.24 seconds; exact failed IDs match baseline, with no new failures. All 48 targeted geocoding cases pass; source/changed-test compilation, shell syntax/help, schema/examples, Python docstring and Markdown contracts passed. Existing proot R parsing/launcher checks passed; no map images or real research were generated. The independent review's three findings are all fixed and regression-covered; no deferred findings remain. Main checkout still has no tracked changes; implementation is retained on `geocoding-cleanup`, not merged or pushed under this authorization.

- Planning only: approved design incorporates Astra review and explicit preservation of INI selection/exclusions. No production code, dependencies, caches or Git refs changed while preparing this plan.
- Preferred execution: native/inline with one independent completion audit, because resolver/cache/CLI contracts are tightly coupled. Preserve remaining allowance for integration and repairs; runtime weekly telemetry is unknown unless surfaced during execution.
- At each task boundary record base/commit, red and green test commands, decisions, failures, model/effort when delegated, and next safe action. Logs and private input details stay local; do not duplicate this ledger elsewhere.
