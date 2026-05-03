import json
import math
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path


INPUT_FOLDER = Path("hikes/gpx")
MEDIA_FOLDER = Path("hike-media")
OUTPUT_GEOJSON = Path("hikes.geojson")
OUTPUT_STATS = Path("hikes_stats.json")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def slugify(value):
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "hike"


def haversine(lat1, lon1, lat2, lon2):
    radius = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def parse_time(value):
    if not value:
        return None

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def text_for(point, name):
    value = point.findtext(f"gpx:{name}", namespaces=NS)
    return value.strip() if value else None


def read_gpx(path):
    tree = ET.parse(path)
    root = tree.getroot()

    title = (
        root.findtext("gpx:metadata/gpx:name", namespaces=NS)
        or root.findtext("gpx:trk/gpx:name", namespaces=NS)
        or path.stem
    ).strip()

    points = []

    for trkpt in root.findall(".//gpx:trkpt", namespaces=NS):
        lat = float(trkpt.attrib["lat"])
        lon = float(trkpt.attrib["lon"])
        ele = text_for(trkpt, "ele")
        time = text_for(trkpt, "time")

        points.append({
            "lat": lat,
            "lon": lon,
            "ele": float(ele) if ele is not None else None,
            "time": time
        })

    return title, points


def summarize(points):
    distance_m = 0
    ascent_m = 0
    descent_m = 0
    previous = None

    for point in points:
        if previous:
            distance_m += haversine(point["lat"], point["lon"], previous["lat"], previous["lon"])

            if point["ele"] is not None and previous["ele"] is not None:
                delta = point["ele"] - previous["ele"]
                if delta > 0:
                    ascent_m += delta
                else:
                    descent_m += abs(delta)

        previous = point

    times = [parse_time(point["time"]) for point in points if point.get("time")]
    times = [value for value in times if value is not None]

    return {
        "distance_km": round(distance_m / 1000, 2),
        "ascent_m": round(ascent_m),
        "descent_m": round(descent_m),
        "started_at": min(times).isoformat() if times else None,
        "ended_at": max(times).isoformat() if times else None
    }


def ensure_media_folder(hike_id):
    folder = MEDIA_FOLDER / hike_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ".gitkeep").touch()
    return folder


def image_sort_key(path):
    try:
        return (0, int(path.stem))
    except ValueError:
        return (1, path.name.lower())


def images_for(folder, title):
    images = []

    for path in sorted(folder.iterdir(), key=image_sort_key):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        images.append({
            "src": path.as_posix(),
            "alt": f"{title} photo {len(images) + 1}"
        })

    return images


def feature_for(path):
    title, points = read_gpx(path)

    if len(points) < 2:
        return None

    stats = summarize(points)
    hike_id = slugify(path.stem)
    media_folder = ensure_media_folder(hike_id)
    start = points[0]
    coordinates = []

    for point in points:
        coordinate = [round(point["lon"], 6), round(point["lat"], 6)]

        if point["ele"] is not None:
            coordinate.append(round(point["ele"], 1))

        coordinates.append(coordinate)

    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates
        },
        "properties": {
            "id": hike_id,
            "title": title,
            "date": stats["started_at"][:10] if stats["started_at"] else None,
            "summary": f"{stats['distance_km']} km hike with {stats['ascent_m']} m ascent.",
            "body": [
                "Imported from a Komoot GPX file.",
                f"Add photos by uploading 1.jpg, 2.jpg, 3.jpg, and so on to hike-media/{hike_id}/.",
                "Add a longer recap by creating a matching entry in hike_stories.json."
            ],
            "images": images_for(media_folder, title),
            "tags": ["hike"],
            "start": [round(start["lon"], 6), round(start["lat"], 6)],
            **stats
        }
    }


def build_outputs():
    features = []

    paths = [path for path in INPUT_FOLDER.iterdir() if path.suffix.lower() == ".gpx"]

    for path in sorted(paths):
        feature = feature_for(path)
        if feature:
            features.append(feature)

    totals = {
        "hike_count": len(features),
        "distance_km": round(sum(feature["properties"]["distance_km"] for feature in features), 2),
        "ascent_m": round(sum(feature["properties"]["ascent_m"] for feature in features)),
        "descent_m": round(sum(feature["properties"]["descent_m"] for feature in features))
    }

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    with OUTPUT_GEOJSON.open("w", encoding="utf-8") as file:
        json.dump(geojson, file, indent=2)
        file.write("\n")

    with OUTPUT_STATS.open("w", encoding="utf-8") as file:
        json.dump(totals, file, indent=2)
        file.write("\n")

    print(f"Processed {totals['hike_count']} hikes")
    print(f"Total distance: {totals['distance_km']} km")
    print(f"Total ascent: {totals['ascent_m']} m")


NS = {"gpx": "http://www.topografix.com/GPX/1/1"}


if __name__ == "__main__":
    build_outputs()
