# Geocoding Cleanup And Institution Resolution

Status: Approved and implemented; verification and follow-ups are recorded in the plan ledger.

## Intent And Scope

Rename the Directory map producer to `geocoding.py`, align its CLI with shared
conventions, and explain coordinate provenance in end-of-run verbose statistics.
Support ID-based manual overrides and a separate file of researched institution
locations, without allowing cached approximate locations to mask newly added
Directory addresses or coordinates.

The research workflow is `geocoder -> Markdown review packet -> human-operated
Codex/ChatGPT/other interface -> resolution JSON -> geocoder`. No model API,
additional AI runner, automatic Directory updates or new installation is required.
The research JSON is local input, not an authoritative Directory correction.

## Approaches

1. Patch the existing monolithic script. Smaller initial delta, but duplicates
   precedence and fallback bookkeeping across its invalid/missing-coordinate paths.
2. Focused refactor, recommended: a thin executable `geocoding.py` and an
   importable `geocoding_utils.py` resolver with explicit results, cache metadata,
   validation and statistics. Retain existing configuration filtering and GeoJSON
   properties rather than redesigning map generation.
3. Autonomous institution research in the geocoder. Not selected: the user chose
   a portable Markdown-to-JSON workflow usable through different AI interfaces.

The separate-file research workflow and precedence are agreed. The focused
refactor is the implementation recommendation submitted for design approval.

## Existing Implementation And Integration

`geocoding_2022.py` already uses `cli_common.py` logging, Directory auth/schema,
withdrawn scope and purge flags. Its `lookForCoordinates()` builds query suffixes
from nonempty contact fields in order `address`, `zip`, `city`, `country`.
`safe_geocode()` supplies rate limiting, retrying and service-disable behavior.
Successful results are cached by address query and again by biobank source.

Its biobank cache key currently omits address contents, its fallback lookup
returns only coordinates, and its success paths discard the fields used. These
prevent trustworthy freshness checks and cache/API/specificity statistics.

Known references to update include `R-maps/export.sh`,
`R-maps/render_pilot_maps.R`, R-map guidance, root README/AGENTS, `docs/maps.md`,
`docs/setup.md`, CLI/documentation tests and coordinate tests. Audit all tracked
references rather than relying on that list. Do not merge the survey branch into
master; its future integration consumes this shared rename through normal merges.

## CLI Contract

Preserve positional `config_file` and shared `-v/--verbose`, `-d/--debug`, auth,
`-P/--schema`, withdrawn scope and cache-purge options, in their standard order.
Canonical tool options:

- `-o/--output-prefix PREFIX`: retain existing prefix plus `.geojson` behavior.
- `--print-filtered-dataframe`: retain the explicit diagnostic option.
- `--manual-overrides PATH`: optional ID-based override JSON, never auto-discovered.
- `--institution-resolutions PATH`: optional researched result JSON; never writes
  or merges into the manual file.
- `--output-institution-review PATH`: optional Markdown research packet.

Hide existing long aliases `--out-name`, `--outName` and `--print-filtered-df`
for argument compatibility. Rename the executable without leaving a legacy
wrapper, to avoid duplicate entry points; update all in-repository callers.
Document the old executable's removal clearly. This is a proposed builder choice,
not an additional user requirement.

Resolve relative config/input/output paths from the invocation working directory
as today. Read input files before any output write; reject output/input aliases
and validate the resolution files before geocoding. No silent new API requests
merely to upgrade legacy cache metadata. Do not purge caches automatically.

## Eligibility And Source Precedence

An address is present when the current contact's `address` field is a nonblank
string after trimming. City and postcode alone do not make a street address.
Usable supplied coordinates are a finite, valid longitude/latitude pair; malformed,
incomplete and out-of-range pairs do not block fallback, but retain diagnostics.

Evaluate current Directory data and manual policies on every run before caches:

1. Applicable manual `always` override.
2. Usable Directory-supplied coordinates.
3. Applicable conditional manual override.
4. If street/address exists: normal address-query resolution, retaining existing
   postcode/city/country suffix fallbacks. Never use institution resolutions on
   this path, including when address geocoding fails.
5. If street/address is missing: a current, accepted institution-resolution entry
   authorized by the explicitly supplied institution-resolution file. A matching
   separately typed cache record may accelerate that entry, but cannot authorize it.
6. Existing postcode/city geocoding fallbacks, with country as context only.
7. Unresolved, with a reason distinguishing missing context, no match and disabled
   service where possible.

Manual policies, one entry per biobank ID:

| Policy | Eligibility |
|---|---|
| `missing-location` | No usable supplied coordinates and no street/address |
| `missing-coordinates` | No usable supplied coordinates, regardless of address |
| `always` | Applies even with usable supplied coordinates |

Institution entries use only `missing-location`; they cannot claim either more
powerful policy. Manual conditional overrides beat institution entries when both
are eligible. An institution result may never override supplied coordinates.

The INI remains authoritative for existing dataset filters and country, ID and
name exclusions. Apply those restrictions before coordinate resolution, overrides,
research-packet selection and statistics: neither JSON file may reintroduce an
excluded biobank. Preserve the existing selection semantics and remaining INI
settings, including output-property selection; this is not removal of the INI.

Only legacy coordinate entries in `[Override biobank position]` migrate to
ID-based manual JSON entries with policy `always`. An empty legacy section
remains valid. A nonempty legacy coordinate section must produce an actionable
migration error before lookups or output, rather than silently dropping positions
or introducing a third coordinate-override authority. Migration instructions must
require exact, unambiguous biobank-ID selection; never guess an ID from a similar
name. Preserve IDs exactly in the JSON, without INI-style key lowercasing.

## Two Separate JSON Files

Use a versioned common envelope and entry structure. `kind` distinguishes
`manual_overrides` from `institution_resolutions`; a file of the wrong kind fails
clearly. Each entry has `biobank_id`, `policy`, `status` and a human-readable
explanation. Coordinate and address requirements depend on source and status.
Use named components to avoid silent latitude/longitude swaps.

Both files are authoritative snapshots, not incremental updates. Read at most one
manual-overrides file and one institution-resolution file per run. Removing an
entry from the current file disables that entry regardless of previously cached
results. Omitting either file disables that source completely. A valid catalogue
with an empty entries list disables all entries from that source; a missing or unreadable explicitly
requested file is an input error, not permission to use cached positions. The
external research workflow maintains the single institution-resolution JSON
as a complete current catalogue, retaining accepted entries when adding newly
researched institutions. Do not infer incremental merge semantics on ingestion.

Manual entries require status `resolved`, named `longitude` and `latitude`, a
reason and one of the three policies. All institution entries require the research
request ID/context fingerprint, institution/country context, status, explanation
and policy `missing-location`. Resolved institution entries additionally require
a supported street/address, valid coordinates, evidence references and confidence.
Ambiguous/unresolved entries may omit coordinates and address entirely; do not
require invented values merely to validate the catalogue. Preserve whatever
partial evidence and qualifications are available, without using them as resolved
positions. Structured address fields are `address`, `zip`, `city`, `country`;
postcode can be unknown. Preserve original institution spelling and biobank identity.

Research statuses are `resolved`, `ambiguous` and `unresolved`. Only a `resolved`
entry with a complete valid coordinate pair, supported address, matching request
context and nonempty evidence can supply a position. Ambiguous/unresolved entries
remain inspectable and never become cached successful positions. Confidence is
recorded, not a substitute for disambiguating an institution or campus. Supplying
the result file explicitly opts into its well-formed resolved proposals; no AI
execution or automatic acceptance of ambiguous proposals occurs in the geocoder.

Reject unsupported schema versions, non-finite coordinates, out-of-range values,
unknown policy/status/kind and duplicate IDs within a file before requests/writes.
The same ID may occur once in each file; source precedence resolves that case.
Institution entries with stale identity/location context are skipped with a
diagnostic and cannot replace newer Directory data. Entries outside the current
selected scope are not applied. JSON objects must not conceal duplicate keys.

## Markdown Research Packet

Only emit on request, with deterministic country/institution/biobank ordering.
Include selected biobanks missing both usable Directory coordinates and a
street/address that lack a current eligible resolved institution entry. Exclude
biobanks already positioned by an applicable manual override. Include city and
postcode as available context. Do not request unnecessary research for biobanks
with usable supplied coordinates; research eligibility follows the institution
fallback's `missing-location` policy.
Never group distinct campuses solely because institution names resemble each
other. Group clearly identical research context only while retaining every
biobank ID and a separate result binding for each.

The Markdown must be self-contained: purpose, evidence requirements, exact JSON
schema/example with invented data, coordinate order/range/unit, statuses and
instructions to return JSON only. Include a deterministic request ID, original
biobank ID, biobank name, `juridical_person`, country, available city/postcode and
context fingerprint for every item. Do not include personal names, email/phone
or contact IDs; use only organization/location context. The fingerprint excludes
personal contact fields and volatile runtime metadata.

When a current institution-resolution file is supplied, include its complete
catalogue in a separate carry-forward block, not in the list to research. Instruct
the AI to return a complete replacement catalogue: preserve entries not being
researched unchanged, including entries outside the current selection, and add or
replace only the requested IDs. Never re-research unchanged accepted entries or
drop them from the returned snapshot. Do not include the manual-overrides file.
Without an institution-resolution file, the carry-forward catalogue is empty.
This supports repeated research batches without incremental ingestion semantics.

Require research of the specific institution/campus, a supported address, cited
sources and coordinate evidence; no plausible-sounding invented addresses or
unexplained centroids. If ambiguous or unsupported, return that status and explain
what is missing. Never edit Directory records or the manual override file.

Requests/results use the same fingerprint definition: canonical biobank ID,
institution identity, biobank country, contact-address country and nonblank
city/postcode context. Preserve raw
values while canonicalizing whitespace deterministically for comparison. Missing
`juridical_person` may use the biobank name with an explicit lower-specificity
note; do not invent a juridical person. A newly added street always disables the
institution path independently of the fingerprint.

## Cache Freshness And Provenance

Keep the current shared Directory/cache conventions and `DIRECTORY_CACHE_ROOT`.
Use versioned, source-typed resolution records with coordinates, current source
signature, source category, origin details and query fields actually used.
Address-cache identity includes current address/zip/city/country values, not just
contact ID. Institution-cache identity includes the exact request context and
the institution-result provenance. Never place an institution result into the
address-query cache or treat it as confirmed street-address geocoding.

The explicit current files authorize their respective sources on every run.
Changed, ambiguous, unresolved or removed institution entries must not be bypassed
by older successful cache records. With no institution-resolution file supplied,
institution-derived cache entries are ineligible. With no manual-overrides file,
manual coordinate overrides are ineligible; INI filters and exclusions still
apply independently. Match cached research results to
the current entry contents and current Directory context, not just its biobank ID.
Reject invalid input files before coordinate resolution; never silently replace
them with an older cache. No persistent tombstone or incremental-update protocol
is needed. Cache entries can remain on disk, but removing an entry/file removes
its authority immediately on the next run.

Legacy address-query entries can be reused when their stored query proves
compatibility with current fields. A legacy biobank record lacking an address
signature must not bypass a current street-address lookup. If its provenance
cannot be established, retain it on disk but do not use it unsafely; an actually
needed current lookup may call the API. No request is made solely to improve
statistics. Legacy specificity is reported unknown if a safe usable entry lacks
the metadata needed to classify it.

Cache-first address behavior means checking all eligible cached query variants
before launching a fresh API lookup; a more specific cached result wins over a
less specific one. Institution research, when eligible, takes priority over old
city-only results. Diagnostics must record which source won and why rejected
fallbacks were ineligible. Existing negative-cache behavior and rate limits are
retained; cache and API success attribution describes this run, not the original
historical creation of a cache entry.

## Statistics

Emit at INFO at the end after successful output writing, visible in both verbose
and debug modes. Count each selected, non-excluded biobank once, not API calls,
queries or retries. Include considered total and, separately, filtered/excluded
counts when useful for reconciling the run.

The mutually exclusive biobank outcome categories are supplied Directory
coordinates, manual override, AI-assisted institution
resolution, address geocoding success and unresolved. These add to the considered
total. The AI-assisted institution category must be an explicit row in the same
verbose stratification, not just a debug message or an implicit part of address
geocoding. Its name identifies the external Markdown-to-JSON research workflow;
the geocoder itself does not run AI or certify the research.

Report manual counts by policy. For AI-assisted institution resolution, report
the number of biobanks actually positioned using accepted research results.
Do not add a public file-versus-cache split: the current file must authorize
every use and already contains the accepted position. A warm-cache result remains AI-assisted institution
resolution; it must not migrate into the ordinary address-geocoding cache row.
Count a biobank whose supplied coordinates, manual override or current address
wins only in that winning category, even if research exists for its institution.

Also report `Institutions represented`, since several biobanks can belong to the
same institution. Count distinct institution-name/country pairs among the used
research results, normalizing whitespace and case only. Do not include street,
postcode, coordinates or campus in this counting key: different locations of the
same named institution in the same country count once, while their biobank
positions remain independent. This is a reported-name/country count, not new
institution entity resolution or fuzzy matching. Count separately per country;
do not infer international corporate identity. Label this supplementary count
separately so it is never added to the biobank denominator. The minimum layout is:

```text
Biobanks considered: N
Minimum accepted geocoder match: city/locality
Directory-provided coordinates: N
Manual overrides: N
AI-assisted institution resolution: N biobanks
  Institutions represented: N
Address geocoding succeeded: N (cache: N; API: N)
  Street/address included: N (cache: N; API: N)
  Postcode, without street: N (cache: N; API: N)
  City, without street/postcode: N (cache: N; API: N)
  Query specificity unknown: N (cache: N)
Unresolved: N
```

Approved follow-up: a usable address-geocoder result must have returned
city/locality-or-better geographic evidence. Country/state/county or unverified
matches remain unresolved and are excluded from GeoJSON. Never request a
country-only point, and never let its cache entry suppress more-specific queries.
The example's historical country-only success row is removed; print the minimum
accepted level and unresolved reasons instead. Store and revalidate provider
match metadata in v3 address caches, not just query fields. Older entries lacking
such evidence require actual validation before reuse; retain them on disk.
This threshold is geographic granularity, not guaranteed metric accuracy.

For address-geocoded successes, report total and cache/API columns, stratified by
successful query fields: street/address included; postcode without street; city
without street/postcode; unknown specificity. Both cache layers
contribute to cache successes. Do not count unsuccessful API calls as successful
resolutions, or a cached success found later in a lookup as an API success.

Call this query specificity, not guaranteed positional precision. A street in
the request does not prove a building-level result. Retain the successful query
fields in debug evidence and cache. Unresolved records include API outages,
negative results and missing contact/context, without silently counting skipped
biobanks as unresolved.

## Refactor And Identified Defects

Use `Directory` exclusively for Directory data and scope, and reuse
`geojsonutils.py` parsing/feature-writing helpers where semantics match. Preserve
existing map feature properties and existing config filter semantics.

The resolver returns a structured result rather than just a coordinate list:
coordinates or None, winning source, resolution channel, query fields/specificity,
reason and evidence. The caller accounts for one result per biobank. Keep lookup
functions usable in tests without CLI parsing, cache opening or network I/O at
import time. Document every argument, result and relevant exception.

Fix the identified stale-address cache key, lost provenance and cache/API
misclassification. Also cover existing numeric coordinate handling (numeric
values must not be mistaken for malformed strings), missing longitude/latitude
columns, exact case-preserving override-ID matching, and validation of override pairs.
Do not redesign service retry/TLS policy or unrelated map analytics in this
cleanup; record any additional defect separately before expanding scope.

## Validation, Documentation And Non-Goals

Use invented fixtures and fake geocoders/caches. Test each precedence edge,
missing-address with city/postcode, address added/changed with unchanged contact,
coordinates added later, changed institution context, cold/warm caches, old cache
records, stale imports, ambiguous results, duplicate IDs/keys, invalid coordinates,
source statistics and no unexpected API calls. Verify that a supplied address
whose geocoding fails never falls back to an institution result.

Exercise the AI-assisted statistics row on cold and warm caches, two biobanks
belonging to the same named institution at different locations, distinct
institutions, and researched
entries superseded by supplied coordinates, manual overrides or current street
addresses. Assert biobank-category reconciliation independently from the
supplementary institution-name/country count. Verify that missing coordinates
and addresses are valid for unresolved/ambiguous research entries, but never
position a biobank. Verify that supplied coordinates prevent new research.

Test Markdown/JSON round-trip with invented biobanks, determinism, escaping,
personal-contact exclusion and file separation. Cover both an explicitly provided
result file and rejection of cached institution positions when it is absent.
Test entry removal, an empty catalogue, missing/unreadable requested files and
resolved-to-ambiguous/unresolved changes. Changing manual overrides must also take
effect immediately, without cache purging. Keep default map
output feature/schema behavior intact. Exercise CLI help, R launcher command
construction and renamed tests without live requests or writing into local user
reports. Run relevant/full suites, recording pre-existing failures separately.

Test repeated Markdown research batches: carry all unchanged catalogue entries
forward without adding them to the research list, including out-of-scope IDs,
and produce a complete replacement snapshot. Test INI country/name/ID exclusions
and dataset filters against both JSON sources and the research packet; excluded
biobanks must not reappear. Verify empty legacy coordinate sections are valid
and nonempty ones produce the documented migration error, without disabling
the INI's other settings.

Update operator instructions in `docs/maps.md` and R-map documentation, shared
behavior specifications in `DEVELOPMENT.md`, root guardrail references, CLI help,
and tests. Keep respondent/research packets and result files local by default;
commit only data-free schemas/examples unless explicitly requested otherwise.

Non-goals: automatic institution matching accepted without evidence, AI runtime
dependency, updating Directory metadata, purging live caches, regenerating every
map, importing survey tooling, or making approximate institution positions look
like confirmed biobank premises.

## Approval And Builder Decisions

User-agreed: street absence is eligible even with city/postcode; Markdown research
instructions produce separately ingested JSON; manual and researched files stay
separate; supplied coordinates and subsequently added addresses beat institution
fallbacks; manual overrides have three policies; source-specific statistics;
both files are authoritative snapshots and absent files cannot authorize caches.
INI selection/exclusion rules remain authoritative; only legacy coordinate
override entries move into manual JSON. Astra's other consistency corrections
are accepted: status-dependent research fields, carry-forward of existing
catalogue entries, no research of already-positioned biobanks, institutions rather
than locations counted, and no public AI file/cache split.

Submitted choices: focused helper extraction, canonical option names, hard rename
with updated callers, and no automatic high-confidence AI acceptance beyond
explicit file ingestion. Review these as part of approval.
The implementation plan will define exact helper signatures, schema locations,
tests and checkpoint order after approval; this document authorizes no code edits.
