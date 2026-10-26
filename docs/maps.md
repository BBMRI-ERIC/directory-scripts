# Maps and geospatial output

## Directory GeoJSON

`geocoding_2022.py` geocodes Directory entities and generates the GeoJSON used
by the map-rendering workflow:

```bash
python3 geocoding_2022.py geocoding.config -o bbmri-directory-geojson
```

Use `python3 geocoding_2022.py --help` for output, cache, schema, and withdrawn
scope options. The geocoding cache is separate from the Directory cache.

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
