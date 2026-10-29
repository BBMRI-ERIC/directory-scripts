# Maps and geospatial output

## Directory GeoJSON

`geocoding.py` geocodes Directory entities and generates the GeoJSON used
by the map-rendering workflow:

```bash
python3 geocoding.py geocoding.config -o bbmri-directory-geojson
```

Use the [CLI reference](#geocoding-cli-reference) for every option and the
[institution research workflow](#institution-research-workflow) for the
Markdown-to-AI-to-JSON round trip. The geocoding cache is separate from the
Directory cache. For the feature branch, run these commands from its checkout
(currently `.worktrees/geocoding-cleanup`), where `geocoding.py` is present.

Withdrawn biobanks are excluded by default. Use `-w`/`--include-withdrawn` to
include them, or `--only-withdrawn` for withdrawn biobanks only. Shared Directory
scope is applied first; INI exclusions still apply in every mode.

```sh
python3 geocoding.py -v -w geocoding.config -o biobank-points-including-withdrawn
python3 geocoding.py -v --only-withdrawn geocoding.config -o biobank-points-withdrawn-only
```

Caches default to the **working directory**, not the script directory. Running
after `cd .worktrees/geocoding-cleanup` uses a separate cache unless
`DIRECTORY_CACHE_ROOT` is set. To share Directory and geocoding caches with the
main checkout, set their common root before running:

```sh
export DIRECTORY_CACHE_ROOT="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
python3 geocoding.py -v geocoding.config -o biobank-points
```

Do not point unit-test caches at a real shared production cache.
Alternatively set `DIRECTORY_CACHE_ROOT` directly to the absolute main-checkout
path; this avoids relying on Git discovery where ownership checks prevent it.

### Geocoding CLI Reference

```text
python3 geocoding.py [OPTIONS] config_file
```

All relative paths are interpreted from the invocation's working directory.
The positional `config_file` is required and contains the INI selection,
exclusion and feature-property rules, normally `geocoding.config`.

| Option | Meaning / default |
|---|---|
| `-h`, `--help` | Print usage and exit without loading Directory data. |
| `-v`, `--verbose` | INFO progress and final coordinate-source, query-specificity and unresolved statistics. |
| `-d`, `--debug` | DEBUG diagnostics, including winning source, channel, query fields and reason; also includes the final summary. Takes precedence over verbose. |
| `-u USERNAME`, `--username USERNAME` | Directory account; defaults to the shared environment/`.env` value when configured. |
| `-p PASSWORD`, `--password PASSWORD` | Directory account password; prefer protected environment/`.env` settings over shell-history exposure. |
| `-t TOKEN`, `--token TOKEN` | Access token as an alternative to username/password. |
| `-P SCHEMA`, `--schema SCHEMA` | Directory schema/staging area; default `ERIC`. Non-public schemas require appropriate credentials. |
| `--emergency-skip-dag-checks` | Skip hierarchy acyclicity checks explicitly at the operator's risk; other graph diagnostics remain active. Not a normal-run requirement. |
| `-w`, `--include-withdrawn` | Include active and withdrawn biobanks; default is active only. |
| `--only-withdrawn` | Restrict the Directory scope to withdrawn biobanks; implies inclusion of withdrawn data. |
| `--purge-all-caches` | Clear both configured Directory and geocoding caches for this invocation. Avoid during ordinary reruns. |
| `--purge-cache NAME [NAME ...]` | Clear only specified caches: `directory`, `geocoding`, or both. Put `config_file` before this multi-value option so it is not consumed as a cache name. |
| `-o PREFIX`, `--output-prefix PREFIX` | Output filename prefix; default `bbmri-directory-5-0`. Appends `.geojson`; supply a prefix, not the final extension. |
| `--print-filtered-dataframe` | Print selected flattened source data to stdout, before coordinate resolution. Appearing here does not mean a biobank was successfully positioned. |
| `--manual-overrides FILE` | Read the complete authoritative manual-override JSON. Omit the flag to disable that source. |
| `--institution-resolutions FILE` | Read the complete authoritative AI-researched institution JSON. Omit the flag to disable it, including its cached positions. |
| `--output-institution-review FILE` | Write Markdown research instructions, remaining eligible targets, complete carry-forward catalogue and JSON schema. Without this option, no Markdown file is generated. |

Accepted compatibility aliases are `--package SCHEMA` for `--schema`,
`--out-name PREFIX` / `--outName PREFIX` for `--output-prefix`, and
`--print-filtered-df` for `--print-filtered-dataframe`. They are hidden from help;
use canonical spellings in new jobs. See [shared authentication](setup.md#authentication)
for credentials; never commit secrets or real research data.

Explicitly supplied config/JSON inputs must exist and validate. Omit an optional
input flag rather than supplying a nonexistent placeholder. Output parent
directories must exist, and all output paths must be distinct from inputs and
each other, including symlink/hardlink aliases. Successful reruns replace the
requested output files; failures use the staged-publication/recovery behavior
described below. Normal progress, warnings and summaries go to stderr; the
optional dataframe goes to stdout, and GeoJSON/Markdown go to their files.

Example of an **intentional geocoder-only refresh**, not required for normal
AI-result ingestion or the city-level precision upgrade:

```sh
python3 geocoding.py -v geocoding.config -o biobank-points-refreshed \
  --purge-cache geocoding
```

### Location Sources And Overrides

The old `geocoding_2022.py` executable is now `geocoding.py`, without a wrapper;
update external jobs. Canonical `-o/--output-prefix` appends `.geojson` to the
prefix. `--out-name`, `--outName` and `--print-filtered-df` remain accepted but
hidden from help. The INI still controls dataset OR filters, skipped
names/IDs/countries and selected feature properties. Its `[Skip country]` values
are **node/staging prefixes**, as before (`EXT` differs from reported country).
Exclusions run first: no override can reintroduce an excluded biobank.

Two independent optional JSON inputs provide coordinates:

- `--manual-overrides FILE`: exact biobank IDs with coordinates, explanation and
  policy `always`, `missing-coordinates` or `missing-location`.
- `--institution-resolutions FILE`: externally researched institution addresses,
  coordinates, evidence and request fingerprints; only `missing-location` is allowed.

`always` beats Directory coordinates. Otherwise valid Directory coordinates win.
`missing-coordinates` applies only without a valid supplied pair, even if a
street exists. `missing-location` additionally requires the street/address to be
absent; city/postcode alone do not disqualify it. Eligible manual overrides beat
institution results. When a street exists, normal address geocoding applies;
an institution position must not be used even if that geocoding fails.

Both JSON files are **complete authoritative snapshots**. Removing an entry
disables it on the next run; omitting the file disables its entire source.
Caches cannot resurrect removed entries or replace malformed/missing explicitly
requested files. New streets or coordinates supersede institution results
without purging caches. Real review packets/results are local inputs, not Git data.

Move any nonempty `[Override biobank position]` entries to manual JSON using
exact biobank IDs, status `resolved`, an explanation, named longitude/latitude
and policy `always`. Do not guess IDs from similar names. Keep the old INI
section empty; nonempty legacy positions produce an actionable migration error.
All other INI settings remain active.

See the [JSON schema](../schemas/geocoding-locations-v1.schema.json),
[invented manual example](examples/geocoding-manual-overrides.json) and
[invented unresolved research example](examples/geocoding-institution-resolutions.json).
These examples are not real locations.

### Institution Research Workflow

Run from the clone root, omitting optional flags whose files do not exist:

#### Prepare Research

```sh
python3 geocoding.py -v geocoding.config -o biobank-points \
  --output-institution-review geocoding-institutions-review.md
```

The Markdown includes instructions, schema, invented example and organizational
context for selected biobanks missing both valid supplied coordinates and a
street, even when city/postcode is known. Existing manual locations and accepted
research are not re-researched. Give the packet to Codex, ChatGPT or another
interface and save its **complete JSON catalogue** as
`geocoding-institutions.local.json`. The geocoder never calls an AI model itself.

The research instructions require using **biobank name and country together**,
including when no usable institution name is available. The researcher must
verify that the evidenced institution/address and coordinate location agree with
the requested country, document the check, and leave conflicting or ambiguous
identities unresolved rather than select a namesake abroad. A missing country
requires independent identity evidence, not a guess.

These are institutional map locations, not specimen storage locations.
Street-level points are sufficient; an exact building, laboratory or storage
room is not required. The researcher must explain approximate precision and
support the institutional association; a city name alone does not justify
selecting its centre. This is an AI research requirement, not an automated
coordinate-versus-country boundary check by the JSON importer. Regenerate the
Markdown packet to obtain updated instructions; existing packets are unchanged.

#### Import Results

After reviewing the AI-generated JSON, rerun the geocoder with that file. No
Markdown generation option is needed unless another research packet is wanted:

```sh
python3 geocoding.py -v geocoding.config -o biobank-points \
  --institution-resolutions geocoding-institutions.local.json
```

Resolved entries require an evidence-supported address and valid coordinates.
If an institution/site cannot be identified unambiguously, use `ambiguous` or
`unresolved` and explain why; those statuses need no invented coordinates.
Confidence is not proof of accuracy. Review results before using/sharing maps:
institution positions are approximate, not confirmed biobank premises.

#### Continue Research

For another batch, include the current file when generating the next packet:

```sh
python3 geocoding.py -v geocoding.config -o biobank-points \
  --institution-resolutions geocoding-institutions.local.json \
  --output-institution-review geocoding-institutions-review.md
```

The packet carries all existing entries forward, including out-of-scope entries,
and requests only remaining eligible targets. The returned JSON must preserve
unchanged entries without re-research and replace the full current catalogue.
Add `--manual-overrides geocoding-manual.local.json` on each run if used; never
combine that file with the researched catalogue.

#### Combined Run

This complete example shares caches, includes withdrawn biobanks, applies the
separate manual and AI files, and emits another packet for remaining targets:

```sh
export DIRECTORY_CACHE_ROOT="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
python3 geocoding.py -v -w geocoding.config -o biobank-points \
  --manual-overrides geocoding-manual.local.json \
  --institution-resolutions geocoding-institutions.local.json \
  --output-institution-review geocoding-institutions-review.md
```

Use `--only-withdrawn` instead of `-w` for withdrawn-only output, or omit both for
active-only output. Keep the same intended INI, schema and scope across research
batches; carried entries outside a selection stay in the catalogue but are not
positioned by that run. Never replace the manual JSON with AI output.

### Statistics And Cache Behavior

`-v` and `-d` show a final summary after successful publication: considered
biobanks, Directory coordinates, manual overrides by policy, AI-assisted
institution positions, address-geocoding successes and unresolved biobanks.
Winning categories sum to the considered total. Supplementary
`Institutions represented` counts normalized institution-name/country groups,
not separate addresses or positions, and is never added to biobank totals.

Address successes show cache/API counts and query specificity: street included,
postcode without street, city without street/postcode, or unknown.
These describe **query contents**, not guaranteed positional accuracy. Failed
requests/retries are not successful biobank resolutions. Warm-cache institution
results remain AI-derived, without a redundant public file/cache distinction.
Address queries use the contact address's country; institution grouping uses
the biobank's reported country. A contact-country edit also invalidates the
relevant cache/research context rather than silently reusing the previous position.

**A geocoder match must be city/locality-level or better.** Country/state/county
points and unverified result granularity remain unresolved and are excluded
from GeoJSON, even if the query included a street. Country-only queries are not
sent, without an automatic micro-country exception. An old country-cache hit
cannot suppress more-specific lookups. Supplied Directory, manual and accepted
institution coordinates retain their existing authority; this check does not
independently certify those positions.

The summary states the acceptance floor and explains unresolved outcomes.
Query text alone is not precision evidence: new address records retain provider
feature metadata. Old entries without it may require actual live revalidation,
not cache purging. Geographic level is not a guaranteed distance-error bound.
The classification uses Nominatim's [returned feature fields](https://nominatim.org/release-docs/latest/api/Output/)
and [place ranking](https://nominatim.org/release-docs/latest/customize/Ranking/),
conservatively rejecting coarse and unsupported features.

The existing shared `data-check-cache/geocoding` cache and `DIRECTORY_CACHE_ROOT`
remain supported. Current address values and research fingerprints govern
freshness. Proven compatible legacy queries can be reused; unsafe old biobank
fallbacks remain on disk but cannot mask changed addresses. No purge is needed
for the rename. Use `--purge-cache geocoding` only for an intentional refresh.

GeoJSON and optional Markdown are staged before replacement. Publication failure
attempts rollback. If rollback itself fails, the error names retained backup
files with original bytes: preserve those files until manual recovery is complete.

`exporter-cMDR.py` can also produce a focused GeoJSON of study-linked
collections and studies:

```bash
python3 exporter-cMDR.py -G cMDR-map.geojson
```

## R map rendering

The maintained rendering workflow lives in `R-maps/`:

- [R map overview and setup](../R-maps/README.md)
- [Operational recipes](../R-maps/SKILLS.md)
- [R map implementation contracts](../R-maps/AGENTS.md)
- [Migration and handover notes](../R-maps/TRANSFER.md)

Use the R-maps documentation as the canonical source for dependencies, layers,
rendering commands, and output publishing. This page covers geospatial inputs
and the membership configuration used by the maps.

## Member And Observer Countries

Edit `R-maps/map_config.R`: `standard_country_groups` controls standard maps
and OEC point selection; `oec_country_groups` controls OEC country colours.
Keep their member/observer lists aligned and remove newly admitted countries
from the OEC `gray` list. Country labels are configured separately in
`standard_country_labels` and `fedplat_country_labels`.

The requested map classification as of 2026-10-21 includes Portugal (`PT`) and
Cyprus (`CY`) as members; Ukraine (`UA`), Montenegro (`ME`), Denmark (`DK`) and
Turkey (`TR`) as observers. Montenegro's three-letter code `MNE` is represented
by the basemap's two-letter code `ME`. Other country classifications are retained.

`fedplat_country_groups` uses a separate `fedplat` participation overlay: Cyprus
remains in that overlay even though its underlying membership is now member.
Changing status does not add Directory biobanks or create node-marker coordinates;
the OEC node overlays remain explicit GeoJSON inputs. These R settings do not
automatically update Python's `nncontacts.py`; keep its member/observer country
set aligned with the R lists. Rare-disease GeoJSON preparation reuses that
Python registry: member/observer-country biobanks are magenta unless managed in
the `EXT` staging area. EXT biobanks and biobanks outside member/observer
countries are green. Both colors share the same circle-size rules.

The `bbmri-members-nolabelcountry` and `global-nolabelcountry` variants omit
country names as well as biobank names. Generate them with:

```bash
sh R-maps/export.sh bbmri-members-nolabelcountry global-nolabelcountry
```
