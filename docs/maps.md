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
rendering commands, and output publishing. This page only describes how the
top-level Python tools supply geospatial data.
