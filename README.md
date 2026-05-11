# Ozzy Trip Data

Static trip map data and processing scripts for an Australia road trip.

## What is here

- `index.html` renders the map with Leaflet.
- `route_past.geojson` stores the historic route.
- `route_live.geojson` stores the current GPX-derived route.
- `route_meta.json` stores the latest car GPS update metadata.
- `car/gpx/` is the upload folder for new car GPX tracks.
- `car/archive/` stores processed car GPX tracks by month.
- `odo.json` stores the current and starting odometer values.
- `geojson_merge.py` converts GPX tracks into `route_live.geojson`.

## How updates work

When a car GPX file is pushed to `car/gpx/`, GitHub Actions runs `geojson_merge.py`.
The script:

1. Reads GPX files in the repository root, `car/gpx/`, and `car/archive/`.
2. Keeps points that move at least 150 metres from the previous accepted point.
3. Splits the route at GPS jumps over 5 km.
4. Writes the result to `route_live.geojson` and latest GPS metadata to `route_meta.json`.
5. Moves processed files from `car/gpx/` into `car/archive/YYYY-MM/`.

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
- `marker`, optionally: `info`, `sun`, `star`, `camera`, `camp`, `food`, `forest`, `mountain`, `fish`, or `surf`
- `summary`
- `body` paragraphs
- `images`
- `tags`
- `published`, optionally set to `false` for drafts hidden from the map

Example:

```json
{
  "id": "byron-stop",
  "title": "First Byron Stop",
  "date": "2026-04-20",
  "coordinates": [153.49925, -28.55479],
  "marker": "sun",
  "summary": "A short note from the road near Byron Bay.",
  "body": ["Story text goes here."],
  "images": [{ "src": "sticker.png", "alt": "Fuji Road Trip sticker" }],
  "tags": ["coast"],
  "published": true
}
```

Published POIs are always shown on the map. Draft POIs stay in `poi.json` but
are hidden from the map until published.

### Add a POI from your phone

Use the GitHub issue form instead of editing JSON manually:

1. Open the repository on your phone.
2. Go to **Issues**.
3. Tap **New issue**.
4. Choose **Add POI**.
5. Fill in the title, date, marker, text, tags, optional images, and either coordinates or a Google Maps link.
6. Submit the issue.

GitHub Actions will validate the form, add the POI to `poi.json`, commit the
change, comment on the issue, and close it.

In the image field, you can paste GitHub uploaded image links, normal image
URLs, or existing repo paths. Remote images are downloaded, resized to a maximum
width of 1600px, stripped of metadata, compressed to JPG, and saved under:

```text
poi-media/<poi-id>/1.jpg
poi-media/<poi-id>/2.jpg
```

For Australian coordinates, the automation will turn a positive latitude into a
negative one if the longitude is clearly in Australia.

Each POI issue also creates `poi-media/<poi-id>/.gitkeep`, so you can add more
images to that folder later.

### Update a POI from your phone

Use the **Update POI** issue form when an existing POI needs edits.

1. Open the repository on your phone.
2. Go to **Issues**.
3. Tap **New issue**.
4. Choose **Update POI**.
5. Enter the existing POI id, such as `hat-head` or `blue-mountains`.
6. Fill only the fields you want to replace.

Blank fields keep the current value. If you fill the image field, the current
image list is replaced; if you leave it blank, existing images stay unchanged.

## Fishing and surf logs

Fishing catches and surf spots are stored separately from normal POIs:

- `fishing-log.json`
- `surf-log.json`
- `fishing-media/`
- `surf-media/`

Use the **Add fishing log** and **Add surf spot** issue forms from your phone.
Each form accepts a Google Maps link or coordinates, story text, tags, optional
images, and log-specific details such as species, count, fish size, caught time,
conditions, wave size, wind, tide, board, and rating.

GitHub Actions writes the entry to the matching JSON file, downloads and
compresses attached images, commits the update, comments on the issue, and
closes it. Fishing and surf entries live behind their own floating toggle menus,
so normal POIs stay always visible and activity logs do not clutter the map.
The fishing menu shows species totals like `Tailor 10`, `Bream 6`, and `GT 2`;
toggling it shows each catch marker with its species, size, and timestamp in the
marker tooltip and popup details. The surf menu shows the fixed list of surf
spots, and toggling it shows each surf marker with spot, wave size, and rating.
Adding the same surf spot again updates that spot instead of creating a second
session marker.

`fish_species_nsw.json` is a small reference list derived from the NSW DPI fish
species index. It stores species names and freshwater/saltwater category only,
with the official source URL kept in the file for deeper lookup.

Use a local web server when testing in Chrome so `fetch()` can load JSON files:

```sh
python3 -m http.server 8001
```

## Hike overlay

The easiest way to add a hike from your phone is the **Add hike** issue form.
Attach the GPX file in the form, add optional text and photos, then submit. The
workflow saves the GPX to `hikes/gpx/`, stores text/photos in `hike_stories.json`
and `hike-media/`, regenerates `hikes.geojson` and `hikes_stats.json`, commits
the result, and closes the issue.

Raw hike GPX files still live in `hikes/gpx/`. Regenerate the hike overlay with:

```sh
python3 process_hikes.py
```

That creates:

- `hikes.geojson` for the map overlay
- `hikes_stats.json` for the floating hike summary panel

The map can toggle hikes on and off separately from the main road-trip route.
Each hike route is clickable and opens the same story window used by POIs.

Custom hike popup text and photos live in `hike_stories.json`. Use the hike id
from `hikes.geojson`, then add any fields you want to override:

```json
{
  "goonengerry-national-park-loop": {
    "summary": "Short custom intro for the popup.",
    "body": ["Longer recap text goes here."],
    "images": [
      { "src": "hike-media/goonengerry-national-park-loop/photo-1.jpg", "alt": "View from the trail" }
    ],
    "tags": ["hike", "national park"]
  }
}
```

To list the current hike ids:

```sh
node -e "const fs=require('fs'); const data=JSON.parse(fs.readFileSync('hikes.geojson','utf8')); for (const f of data.features) console.log(f.properties.id + ' | ' + f.properties.title)"
```

The route, distance, ascent, descent, and start point still come from the GPX
file. Do not hand-edit `hikes.geojson`; it is regenerated by automation.

When a hike GPX is processed, `process_hikes.py` automatically creates a media
folder for that hike:

```text
hike-media/goonengerry-national-park-loop/
```

Upload compressed web images into that folder with simple numbered names:

```text
hike-media/goonengerry-national-park-loop/1.jpg
hike-media/goonengerry-national-park-loop/2.jpg
hike-media/goonengerry-national-park-loop/3.jpg
```

The automation scans `.jpg`, `.jpeg`, `.png`, and `.webp` files in each hike
media folder and adds them to that hike popup automatically. You only need to
edit `hike_stories.json` when you want custom text, tags, title, or date. If you
add an `images` list in `hike_stories.json`, that manual list overrides the
auto-detected folder images for that hike.

## Privacy note

This repository is public and contains trip location data. Review GPX and GeoJSON
precision before publishing if any locations should stay private.
