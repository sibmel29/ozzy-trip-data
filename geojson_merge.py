import gpxpy
import json
import glob
import os
import shutil
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime, timezone
from pathlib import Path

# === SETTINGS (tune these if needed)
MIN_DISTANCE_METERS = 150     # skip jitter
MAX_JUMP_METERS = 5000        # split tracks at impossible GPS jumps
MAX_BRIDGE_GAP_SECONDS = 30 * 60
MAX_BRIDGE_SPEED_KMH = 160
MAX_POINTS = 800              # keep file light
INPUT_FOLDERS = [".", "car/gpx", "car/archive"]
OUTPUT_FILE = "route_live.geojson"
META_FILE = "route_meta.json"
ARCHIVE_CAR_GPX = os.environ.get("ARCHIVE_CAR_GPX") == "1"


# === DISTANCE FUNCTION
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c


def can_bridge_signal_gap(distance_meters, previous_time, current_time):
    if previous_time is None or current_time is None:
        return False

    elapsed_seconds = (current_time - previous_time).total_seconds()

    if elapsed_seconds <= 0 or elapsed_seconds > MAX_BRIDGE_GAP_SECONDS:
        return False

    implied_speed_kmh = distance_meters / elapsed_seconds * 3.6
    return implied_speed_kmh <= MAX_BRIDGE_SPEED_KMH


def car_gpx_files():
    files = []

    for folder in INPUT_FOLDERS:
        pattern = "**/*.gpx" if folder == "car/archive" else "*.gpx"
        files.extend(glob.glob(os.path.join(folder, pattern), recursive=True))
        files.extend(glob.glob(os.path.join(folder, pattern.upper()), recursive=True))

    return sorted(set(files))


def archive_car_files(files):
    for file in files:
        path = Path(file)

        if path.parent != Path("car/gpx"):
            continue

        month = "unknown"

        try:
            with path.open("r") as handle:
                gpx = gpxpy.parse(handle)

            times = [
                point.time
                for track in gpx.tracks
                for segment in track.segments
                for point in segment.points
                if point.time is not None
            ]

            if times:
                month = min(times).strftime("%Y-%m")
        except Exception:
            pass

        target_folder = Path("car/archive") / month
        target_folder.mkdir(parents=True, exist_ok=True)
        target = target_folder / path.name

        if target.exists():
            target = target_folder / f"{path.stem}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{path.suffix}"

        shutil.move(str(path), str(target))
        print(f"↳ Archived {path} → {target}")


# === LOAD ALL GPX FILES
gpx_files = car_gpx_files()

if not gpx_files:
    print("❌ No GPX files found")
    geojson = {"type": "FeatureCollection", "features": []}
    metadata = {
        "gpx_count": 0,
        "latest_time": None,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(geojson, f, indent=2)
        f.write("\n")

    with open(META_FILE, "w") as f:
        json.dump(metadata, f, indent=2)
        f.write("\n")

    exit(0)

print(f"📂 Found {len(gpx_files)} GPX files")

coords = []
times = []
segments = []
all_times = []

last_lat = None
last_lon = None
last_time = None
bridged_gaps = 0


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
                all_times.append(time)

                # distance filter (removes jitter + duplicates)
                if last_lat is not None:
                    dist = haversine(lat, lon, last_lat, last_lon)

                    # skip crazy GPS jumps
                    if dist > MAX_JUMP_METERS:
                        if can_bridge_signal_gap(dist, last_time, time):
                            bridged_gaps += 1
                        else:
                            if len(coords) >= 2:
                                segments.append((coords, times))
                            coords = []
                            times = []
                            last_lat = None
                            last_lon = None
                            last_time = None

                    elif dist < MIN_DISTANCE_METERS:
                        continue

                coords.append([round(lon, 5), round(lat, 5)])
                times.append(time.isoformat())

                last_lat = lat
                last_lon = lon
                last_time = time

if len(coords) >= 2:
    segments.append((coords, times))

# === SAFETY CHECK
if not segments:
    print("⚠️ Not enough movement, writing empty route")
    geojson = {
        "type": "FeatureCollection",
        "features": []
    }
    metadata = {
        "gpx_count": len(gpx_files),
        "latest_time": max(all_times).isoformat() if all_times else None,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(geojson, f, indent=2)
        f.write("\n")

    with open(META_FILE, "w") as f:
        json.dump(metadata, f, indent=2)
        f.write("\n")

    if ARCHIVE_CAR_GPX:
        archive_car_files(gpx_files)

    exit(0)


# === LIMIT SIZE
total_points = sum(len(segment_coords) for segment_coords, _ in segments)

if total_points > MAX_POINTS:
    step = max(1, total_points // MAX_POINTS)
    segments = [
        (segment_coords[::step], segment_times[::step])
        for segment_coords, segment_times in segments
    ]
    segments = [
        (segment_coords, segment_times)
        for segment_coords, segment_times in segments
        if len(segment_coords) >= 2
    ]


# === BUILD GEOJSON
geojson = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": segment_coords
            },
            "properties": {
                "times": segment_times,
                "label": segment_times[-1][:10]
            }
        }
        for segment_coords, segment_times in segments
    ]
}


# === SAVE FILE
with open(OUTPUT_FILE, "w") as f:
    json.dump(geojson, f, indent=2)
    f.write("\n")

metadata = {
    "gpx_count": len(gpx_files),
    "latest_time": max(all_times).isoformat() if all_times else None,
    "generated_at": datetime.now(timezone.utc).isoformat()
}

with open(META_FILE, "w") as f:
    json.dump(metadata, f, indent=2)
    f.write("\n")

if ARCHIVE_CAR_GPX:
    archive_car_files(gpx_files)

print(
    f"✅ Done: {sum(len(segment_coords) for segment_coords, _ in segments)} points "
    f"→ {OUTPUT_FILE} ({bridged_gaps} GPS gaps bridged)"
)
