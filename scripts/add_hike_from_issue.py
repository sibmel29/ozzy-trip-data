import json
import os
import shutil
import urllib.request
import zipfile
from pathlib import Path

import add_poi_from_issue
from add_poi_from_issue import (
    image_entries_for,
    images_from_entries,
    parse_paragraphs,
    parse_sections,
    parse_tags,
    slugify,
    value_for,
)


GPX_FOLDER = Path(os.environ.get("HIKE_GPX_FOLDER", "hikes/gpx"))
MEDIA_FOLDER = Path(os.environ.get("HIKE_MEDIA_FOLDER", "hike-media"))
STORIES_FILE = Path(os.environ.get("HIKE_STORIES_FILE", "hike_stories.json"))
RESULT_FILE = Path(os.environ.get("RESULT_FILE", "hike_result.json"))
GPX_FIELD_LABELS = ["GPX file or ZIP", "GPX file"]


def download_file(url, destination):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ozzy-trip-data-hike-action"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        with destination.open("wb") as file:
            shutil.copyfileobj(response, file)


def extract_gpx_from_zip(zip_path, destination):
    with zipfile.ZipFile(zip_path) as archive:
        gpx_names = sorted(
            name
            for name in archive.namelist()
            if not name.endswith("/") and name.lower().endswith(".gpx")
        )

        if not gpx_names:
            raise ValueError("ZIP attachment must contain at least one .gpx file")

        with archive.open(gpx_names[0]) as source, destination.open("wb") as output:
            shutil.copyfileobj(source, output)


def save_gpx_from_url(url, destination):
    download_path = destination.with_suffix(".download")
    download_file(url, download_path)

    try:
        if zipfile.is_zipfile(download_path):
            extract_gpx_from_zip(download_path, destination)
        else:
            download_path.replace(destination)
    finally:
        if download_path.exists():
            download_path.unlink()


def first_url(value):
    entries = image_entries_for(value)
    urls = [entry for entry in entries if entry.startswith("http://") or entry.startswith("https://")]

    if not urls:
        raise ValueError("GPX field must include a GitHub ZIP attachment URL or direct GPX URL")

    return urls[0]


def first_value(sections, labels):
    for label in labels:
        value = value_for(sections, label)

        if value:
            return value

    return ""


def main():
    issue_body = os.environ.get("ISSUE_BODY", "")
    issue_number = os.environ.get("ISSUE_NUMBER", "")
    issue_url = os.environ.get("ISSUE_URL", "")

    if not issue_body or not issue_number:
        raise ValueError("ISSUE_BODY and ISSUE_NUMBER are required")

    sections = parse_sections(issue_body)
    title = value_for(sections, "Hike title")

    if not title:
        raise ValueError("Hike title is required")

    hike_id = slugify(title)
    GPX_FOLDER.mkdir(parents=True, exist_ok=True)
    MEDIA_FOLDER.mkdir(parents=True, exist_ok=True)

    gpx_url = first_url(first_value(sections, GPX_FIELD_LABELS))
    gpx_path = GPX_FOLDER / f"{hike_id}.gpx"
    save_gpx_from_url(gpx_url, gpx_path)

    original_media_folder = add_poi_from_issue.POI_MEDIA_FOLDER
    add_poi_from_issue.POI_MEDIA_FOLDER = MEDIA_FOLDER

    try:
        images = images_from_entries(image_entries_for(value_for(sections, "Image paths")), hike_id, title)
    finally:
        add_poi_from_issue.POI_MEDIA_FOLDER = original_media_folder

    stories = json.loads(STORIES_FILE.read_text(encoding="utf-8")) if STORIES_FILE.exists() else {}
    existing = stories.get(hike_id, {})

    story = {
        "title": title,
        "date": value_for(sections, "Date", existing.get("date", "")),
        "summary": value_for(sections, "Short summary", existing.get("summary", "")),
        "body": parse_paragraphs(value_for(sections, "Story text")) or existing.get("body", []),
        "images": images or existing.get("images", []),
        "tags": parse_tags(value_for(sections, "Tags")) or existing.get("tags", ["hike"]),
        "source_issue": str(issue_number),
        "source_url": issue_url,
    }

    stories[hike_id] = story
    STORIES_FILE.write_text(json.dumps(stories, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    RESULT_FILE.write_text(json.dumps({"id": hike_id, "title": title}, indent=2), encoding="utf-8")

    print(f"Added hike {hike_id}: {title}")


if __name__ == "__main__":
    main()
