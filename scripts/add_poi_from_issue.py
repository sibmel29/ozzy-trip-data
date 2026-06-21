import json
import os
import re
import shutil
import urllib.request
from html import unescape
from pathlib import Path
from urllib.parse import unquote


POI_FILE = Path(os.environ.get("POI_FILE", "poi.json"))
RESULT_FILE = Path(os.environ.get("RESULT_FILE", "poi_result.json"))
POI_MEDIA_FOLDER = Path(os.environ.get("POI_MEDIA_FOLDER", "poi-media"))
MARKERS = {"info", "sun", "star", "camera", "camp", "food", "forest", "mountain", "fish", "surf"}
NO_RESPONSE = {"", "_No response_"}
IMAGE_MAX_WIDTH = int(os.environ.get("IMAGE_MAX_WIDTH", "1600"))
IMAGE_QUALITY = int(os.environ.get("IMAGE_QUALITY", "80"))


def parse_sections(body):
    sections = {}
    current = None
    lines = []

    for line in body.splitlines():
        match = re.match(r"^###\s+(.+?)\s*$", line)

        if match:
            if current is not None:
                sections[current] = "\n".join(lines).strip()

            current = match.group(1).strip()
            lines = []
        elif current is not None:
            lines.append(line)

    if current is not None:
        sections[current] = "\n".join(lines).strip()

    return sections


def value_for(sections, label, default=""):
    value = sections.get(label, default).strip()
    return default if value in NO_RESPONSE else value


def has_value(sections, label):
    return sections.get(label, "").strip() not in NO_RESPONSE


def slugify(value):
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "poi"


def parse_coordinate(value, label):
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a number, got {value!r}") from exc


def coordinates_from_maps_link(value):
    if value in NO_RESPONSE:
        return None

    def coordinates_from_text(text):
        text = unquote(unescape(text))

        patterns = [
            r"@(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)",
            r"[?&](?:q|query|ll)=(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)",
            r"/place/(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)",
            r"(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if not match:
                continue

            first = float(match.group(1))
            second = float(match.group(2))

            if -90 <= first <= 90 and -180 <= second <= 180:
                return [second, first]

            if -180 <= first <= 180 and -90 <= second <= 90:
                return [first, second]

        data_match = re.search(
            r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)",
            text
        )

        if data_match:
            latitude = float(data_match.group(1))
            longitude = float(data_match.group(2))

            if -90 <= latitude <= 90 and -180 <= longitude <= 180:
                return [longitude, latitude]

        return None

    if "maps.app.goo.gl" in value or "goo.gl/maps" in value:
        try:
            request = urllib.request.Request(
                value,
                headers={"User-Agent": "Mozilla/5.0 ozzy-trip-data-poi-action"}
            )

            with urllib.request.urlopen(request, timeout=15) as response:
                final_url = response.geturl()
                page = response.read(200000).decode("utf-8", errors="ignore")
                resolved_coordinates = coordinates_from_text(f"{final_url}\n{page}")

                if resolved_coordinates:
                    return resolved_coordinates

                value = final_url
        except Exception:
            pass

    return coordinates_from_text(value)


def parse_paragraphs(value):
    if value in NO_RESPONSE:
        return []

    return [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", value)
        if paragraph.strip()
    ]


def parse_tags(value):
    if value in NO_RESPONSE:
        return []

    return [
        tag.strip()
        for tag in re.split(r"[,\n]", value)
        if tag.strip()
    ]


def image_entries_for(value):
    if value in NO_RESPONSE:
        return []

    entries = []

    for line in value.splitlines():
        line = line.strip()
        if not line:
            continue

        html_srcs = re.findall(r"""src=["'](https?://[^"']+)["']""", line)
        if html_srcs:
            entries.extend(html_srcs)
            continue

        markdown_urls = re.findall(r"!\[[^\]]*\]\((https?://[^)]+)\)", line)
        if markdown_urls:
            entries.extend(markdown_urls)
            continue

        urls = re.findall(r"""https?://[^\s)"'<>]+""", line)
        if urls:
            entries.extend(urls)
            continue

        src = line.lstrip("-").strip()
        if src:
            entries.append(src)

    return entries


def is_url(value):
    return value.startswith("http://") or value.startswith("https://")


def download_image(url, destination):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ozzy-trip-data-poi-action"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        with destination.open("wb") as file:
            shutil.copyfileobj(response, file)


def optimize_image(source, destination):
    from PIL import Image, ImageOps

    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail((IMAGE_MAX_WIDTH, IMAGE_MAX_WIDTH * 4), Image.Resampling.LANCZOS)

        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        image.save(
            destination,
            "JPEG",
            quality=IMAGE_QUALITY,
            optimize=True,
            progressive=True,
        )


def images_from_entries(entries, poi_id, title):
    media_folder = POI_MEDIA_FOLDER / poi_id
    media_folder.mkdir(parents=True, exist_ok=True)
    (media_folder / ".gitkeep").touch()
    images = []
    remote_index = 1

    for entry in entries:
        if not is_url(entry):
            images.append({
                "src": entry,
                "alt": f"{title} photo {len(images) + 1}"
            })
            continue

        raw_path = media_folder / f"_raw_{remote_index}"
        output_path = media_folder / f"{remote_index}.jpg"

        download_image(entry, raw_path)
        optimize_image(raw_path, output_path)
        raw_path.unlink(missing_ok=True)

        images.append({
            "src": output_path.as_posix(),
            "alt": f"{title} photo {len(images) + 1}"
        })
        remote_index += 1

    return images


def unique_id(base_id, issue_number, pois):
    source_issue = str(issue_number)

    for poi in pois:
        if str(poi.get("source_issue", "")) == source_issue:
            return poi.get("id", base_id), poi

    existing_ids = {poi.get("id") for poi in pois}

    if base_id not in existing_ids:
        return base_id, None

    issue_id = f"{base_id}-{issue_number}"
    if issue_id not in existing_ids:
        return issue_id, None

    index = 2
    while f"{issue_id}-{index}" in existing_ids:
        index += 1

    return f"{issue_id}-{index}", None


def find_poi_by_id(pois, poi_id):
    requested = slugify(poi_id)

    for poi in pois:
        if poi.get("id") == poi_id:
            return poi

    for poi in pois:
        poi_id_slug = slugify(poi.get("id", ""))
        title_slug = slugify(poi.get("title", ""))

        if requested in {poi_id_slug, title_slug}:
            return poi

    matches = [
        poi
        for poi in pois
        if slugify(poi.get("id", "")).startswith(requested)
        or slugify(poi.get("title", "")).startswith(requested)
    ]

    if len(matches) == 1:
        return matches[0]

    return None


def coordinates_from_sections(sections, existing=None):
    longitude_value = value_for(sections, "Longitude")
    latitude_value = value_for(sections, "Latitude")

    # Explicit coordinates are authoritative. Google Maps pages can contain
    # unrelated viewport coordinates in their metadata.
    if longitude_value and latitude_value:
        longitude = parse_coordinate(longitude_value, "Longitude")
        latitude = parse_coordinate(latitude_value, "Latitude")

        if 110 <= longitude <= 155 and 0 < latitude <= 45:
            latitude = -latitude

        if not -180 <= longitude <= 180:
            raise ValueError("Longitude must be between -180 and 180")

        if not -90 <= latitude <= 90:
            raise ValueError("Latitude must be between -90 and 90")

        return [longitude, latitude]

    maps_coordinates = coordinates_from_maps_link(value_for(sections, "Google Maps link"))
    if maps_coordinates:
        return maps_coordinates

    if not longitude_value and not latitude_value and existing is not None:
        return existing.get("coordinates", [])

    raise ValueError("Longitude and Latitude must both be filled when changing location")


def published_from_sections(sections, existing=None):
    value = value_for(sections, "Published")

    if not value or value == "keep":
        return existing.get("published", True) if existing else True

    return value.lower() not in {"draft", "no", "false", "private"}


def marker_from_sections(sections, existing=None):
    marker = value_for(sections, "Marker")

    if not marker or marker == "keep":
        return existing.get("marker", "info") if existing else "info"

    marker = marker.lower()
    return marker if marker in MARKERS else "info"


def images_from_sections(sections, poi_id, title, existing=None):
    if not has_value(sections, "Image paths"):
        return existing.get("images", []) if existing else []

    image_entries = image_entries_for(value_for(sections, "Image paths"))
    return images_from_entries(image_entries, poi_id, title)


def build_poi(sections, issue_number, issue_url, existing_pois):
    requested_id = value_for(sections, "Existing POI id")
    existing = find_poi_by_id(existing_pois, requested_id) if requested_id else None

    if requested_id and existing is None:
        raise ValueError(f"Could not find POI id {requested_id!r}")

    title = value_for(sections, "POI title")
    if not title and existing:
        title = existing.get("title", "")

    if not title:
        raise ValueError("POI title is required")

    if existing:
        poi_id = existing.get("id", requested_id)
    else:
        poi_id, existing = unique_id(slugify(title), issue_number, existing_pois)

    media_folder = POI_MEDIA_FOLDER / poi_id
    media_folder.mkdir(parents=True, exist_ok=True)
    (media_folder / ".gitkeep").touch()

    poi = {
        "id": poi_id,
        "title": title,
        "date": value_for(sections, "Date", existing.get("date", "") if existing else ""),
        "coordinates": coordinates_from_sections(sections, existing),
        "marker": marker_from_sections(sections, existing),
        "summary": value_for(sections, "Short summary", existing.get("summary", "") if existing else ""),
        "body": parse_paragraphs(value_for(sections, "Story text")) if has_value(sections, "Story text") else (existing.get("body", []) if existing else []),
        "images": images_from_sections(sections, poi_id, title, existing),
        "tags": parse_tags(value_for(sections, "Tags")) if has_value(sections, "Tags") else (existing.get("tags", []) if existing else []),
        "published": published_from_sections(sections, existing),
        "source_issue": str(issue_number),
        "source_url": issue_url,
    }

    return poi, existing


def main():
    issue_body = os.environ.get("ISSUE_BODY", "")
    issue_number = os.environ.get("ISSUE_NUMBER", "")
    issue_url = os.environ.get("ISSUE_URL", "")

    if not issue_body or not issue_number:
        raise ValueError("ISSUE_BODY and ISSUE_NUMBER are required")

    sections = parse_sections(issue_body)
    pois = json.loads(POI_FILE.read_text(encoding="utf-8"))
    poi, existing = build_poi(sections, issue_number, issue_url, pois)

    if existing is not None:
        existing.clear()
        existing.update(poi)
    else:
        pois.insert(0, poi)

    POI_FILE.write_text(json.dumps(pois, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    action = "updated" if existing is not None else "added"
    RESULT_FILE.write_text(json.dumps({"id": poi["id"], "title": poi["title"], "action": action}), encoding="utf-8")

    print(f"{action.title()} POI {poi['id']}: {poi['title']}")


if __name__ == "__main__":
    main()
