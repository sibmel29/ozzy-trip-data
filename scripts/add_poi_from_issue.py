import json
import os
import re
from pathlib import Path


POI_FILE = Path(os.environ.get("POI_FILE", "poi.json"))
RESULT_FILE = Path(os.environ.get("RESULT_FILE", "poi_result.json"))
MARKERS = {"info", "sun", "star", "camera", "camp", "food"}
NO_RESPONSE = {"", "_No response_"}


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


def slugify(value):
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "poi"


def parse_coordinate(value, label):
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a number, got {value!r}") from exc


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


def parse_images(value, title):
    if value in NO_RESPONSE:
        return []

    images = []

    for line in value.splitlines():
        src = line.strip().lstrip("-").strip()
        if not src:
            continue

        images.append({
            "src": src,
            "alt": f"{title} photo {len(images) + 1}"
        })

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


def build_poi(sections, issue_number, issue_url, existing_pois):
    title = value_for(sections, "POI title")
    if not title:
        raise ValueError("POI title is required")

    longitude = parse_coordinate(value_for(sections, "Longitude"), "Longitude")
    latitude = parse_coordinate(value_for(sections, "Latitude"), "Latitude")

    if 110 <= longitude <= 155 and 0 < latitude <= 45:
        latitude = -latitude

    if not -180 <= longitude <= 180:
        raise ValueError("Longitude must be between -180 and 180")

    if not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90")

    marker = value_for(sections, "Marker", "info").lower()
    if marker not in MARKERS:
        marker = "info"

    poi_id, existing = unique_id(slugify(title), issue_number, existing_pois)

    poi = {
        "id": poi_id,
        "title": title,
        "date": value_for(sections, "Date"),
        "coordinates": [longitude, latitude],
        "marker": marker,
        "summary": value_for(sections, "Short summary"),
        "body": parse_paragraphs(value_for(sections, "Story text")),
        "images": parse_images(value_for(sections, "Image paths"), title),
        "tags": parse_tags(value_for(sections, "Tags")),
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
    RESULT_FILE.write_text(json.dumps({"id": poi["id"], "title": poi["title"]}), encoding="utf-8")

    print(f"Added POI {poi['id']}: {poi['title']}")


if __name__ == "__main__":
    main()
