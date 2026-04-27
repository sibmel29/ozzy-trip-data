# Ozzy Trip Data

Static trip map data and processing scripts for an Australia road trip.

## What is here

- `index.html` renders the map with Leaflet.
- `route_past.geojson` stores the historic route.
- `route_live.geojson` stores the current GPX-derived route.
- `track.gpx` is the latest GPX input.
- `odo.json` stores the current and starting odometer values.
- `geojson_merge.py` converts GPX tracks into `route_live.geojson`.

## How updates work

When a `*.gpx` file is pushed, GitHub Actions runs `geojson_merge.py`.
The script:

1. Reads all GPX files in the repository root.
2. Keeps points that move at least 150 metres from the previous accepted point.
3. Splits the route at GPS jumps over 5 km.
4. Writes the result to `route_live.geojson`.

If the GPX data does not include enough movement to draw a line, the script writes
an empty GeoJSON feature collection and exits successfully.

## Local processing

Install the dependency:

```sh
pip install gpxpy
```

Regenerate the live route:

```sh
python geojson_merge.py
```

Then open `index.html` in a browser or serve the directory locally.

## Privacy note

This repository is public and contains trip location data. Review GPX and GeoJSON
precision before publishing if any locations should stay private.
