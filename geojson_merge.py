import gpxpy
import json
import glob
import os
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2

# === SETTINGS (tune these if needed)
MIN_DISTANCE_METERS = 150     # skip jitter
MAX_POINTS = 800              # keep file light
INPUT_FOLDER = "."            # where GPX files are
OUTPUT_FILE = "route_live.geojson"


# === DISTANCE FUNCTION
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c


# === LOAD ALL GPX FILES
gpx_files = sorted(glob.glob(os.path.join(INPUT_FOLDER, "*.gpx")))

if not gpx_files:
    print("❌ No GPX files found")
    exit(1)

print(f"📂 Found {len(gpx_files)} GPX files")

coords = []
times = []

last_lat = None
last_lon = None


# === MERGE ALL FILES
for file in gpx_files:
    print(f"→ Processing {file}")

    with open(file, "r") as f:
        gpx = gpxpy.parse(f)

    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:

                if point.latitude is None or point.longitude is None:
                    continue

                if point.time is None:
                    continue

                lat = point.latitude
                lon = point.longitude
                time = point.time

                # distance filter (removes jitter + duplicates)
                if last_lat is not None:
                    dist = haversine(lat, lon, last_lat, last_lon)

                    if dist < MIN_DISTANCE_METERS:
                        continue

                    # skip crazy GPS jumps
                    if dist > 5000:
                        continue

                coords.append([round(lon, 5), round(lat, 5)])
                times.append(time.isoformat())

                last_lat = lat
                last_lon = lon


# === SAFETY CHECK
if len(coords) < 2:
    print("⚠️ Not enough valid points")
    exit(1)


# === LIMIT SIZE
if len(coords) > MAX_POINTS:
    step = len(coords) // MAX_POINTS
    coords = coords[::step]
    times = times[::step]


# === BUILD GEOJSON
geojson = {
    "type": "FeatureCollection",
    "features": [{
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": coords
        },
        "properties": {
            "times": times,
            "label": times[-1][:10]
        }
    }]
}


# === SAVE FILE
with open(OUTPUT_FILE, "w") as f:
    json.dump(geojson, f)

print(f"✅ Done: {len(coords)} points → {OUTPUT_FILE}")