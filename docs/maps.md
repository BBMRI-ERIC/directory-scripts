# Maps and geospatial output

## Directory GeoJSON

`geocoding.py` geocodes Directory entities and generates the GeoJSON used
by the map-rendering workflow:

```bash
python3 geocoding.py geocoding.config -o bbmri-directory-geojson
```

Use `python3 geocoding.py --help` for output, cache, schema, and withdrawn
scope options. The geocoding cache is separate from the Directory cache.

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

```sh
python3 geocoding.py -v geocoding.config -o biobank-points \
  --institution-resolutions geocoding-institutions.local.json
```

Resolved entries require an evidence-supported address and valid coordinates.
If an institution/site cannot be identified unambiguously, use `ambiguous` or
`unresolved` and explain why; those statuses need no invented coordinates.
Confidence is not proof of accuracy. Review results before using/sharing maps:
institution positions are approximate, not confirmed biobank premises.

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

### Statistics And Cache Behavior

`-v` and `-d` show a final summary after successful publication: considered
biobanks, Directory coordinates, manual overrides by policy, AI-assisted
institution positions, address-geocoding successes and unresolved biobanks.
Winning categories sum to the considered total. Supplementary
`Institutions represented` counts normalized institution-name/country groups,
not separate addresses or positions, and is never added to biobank totals.

Address successes show cache/API counts and query specificity: street included,
postcode without street, city without street/postcode, country only, or unknown.
These describe **query contents**, not guaranteed positional accuracy. Failed
requests/retries are not successful biobank resolutions. Warm-cache institution
results remain AI-derived, without a redundant public file/cache distinction.
Address queries use the contact address's country; institution grouping uses
the biobank's reported country. A contact-country edit also invalidates the
relevant cache/research context rather than silently reusing the previous position.

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
