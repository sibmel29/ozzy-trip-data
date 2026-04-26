import gpxpy
import json
from datetime import datetime

INPUT_FILE = "track.gpx"
OUTPUT_FILE = "route_live.geojson"

# === SETTINGS (tune these later if needed)
MIN_DISTANCE_METERS = 100   # skip points too close
MAX_POINTS = 500            # avoid huge files


def haversine(lat1, lon1, lat2, lon2):
    from math import radians, sin, cos, sqrt, atan2

    R = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c


with open(INPUT_FILE, "r") as f:
    gpx = gpxpy.parse(f)

coords = []
times = []

last_lat = None
last_lon = None

# === EXTRACT + FILTER
for track in gpx.tracks:
    for segment in track.segments:
        for point in segment.points:

            lat = point.latitude
            lon = point.longitude
            time = point.time

            if not time:
                continue

            # distance filter
            if last_lat is not None:
                dist = haversine(lat, lon, last_lat, last_lon)
                if dist < MIN_DISTANCE_METERS:
                    continue

            coords.append([round(lon, 5), round(lat, 5)])
            times.append(time.isoformat())

            last_lat = lat
            last_lon = lon

# === LIMIT POINT COUNT (important)
if len(coords) > MAX_POINTS:
    step = len(coords) // MAX_POINTS
    coords = coords[::step]
    times = times[::step]

# === BUILD GEOJSON
geojson = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coords
            },
            "properties": {
                "times": times,
                "label": times[-1][:10] if times else ""
            }
        }
    ]
}

with open(OUTPUT_FILE, "w") as f:
    json.dump(geojson, f)

print(f"Points kept: {len(coords)} → {OUTPUT_FILE}")