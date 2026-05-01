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

## Points of interest

`poi.json` stores clickable map stories. Each entry includes:

- `title`
- `date`
- `coordinates` as `[longitude, latitude]`
- `summary`
- `body` paragraphs
- `images`
- `tags`

Example:

```json
{
  "id": "byron-stop",
  "title": "First Byron Stop",
  "date": "2026-04-20",
  "coordinates": [153.49925, -28.55479],
  "summary": "A short note from the road near Byron Bay.",
  "body": ["Story text goes here."],
  "images": [{ "src": "sticker.png", "alt": "Fuji Road Trip sticker" }],
  "tags": ["coast"]
}
```

Use a local web server when testing in Chrome so `fetch()` can load JSON files:

```sh
python3 -m http.server 8001
```

## Hike overlay

Raw hike GPX files live in `hikes/gpx/`. Regenerate the hike overlay with:

```sh
python3 process_hikes.py
```

That creates:

- `hikes.geojson` for the map overlay
- `hikes_stats.json` for the floating hike summary panel

The map can toggle hikes on and off separately from the main road-trip route.
Each hike route is clickable and opens the same story window used by POIs.

You can also create a matching POI in `poi.json` for a hike if you want photos,
longer recap text, or tags. Store hike photos in a folder such as:

```text
poi-media/goonengerry-hike/
```

Then reference those images from the POI or hike story data.

## Privacy note

This repository is public and contains trip location data. Review GPX and GeoJSON
precision before publishing if any locations should stay private.
