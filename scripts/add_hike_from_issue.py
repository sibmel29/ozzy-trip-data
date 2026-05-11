import json
import os
import shutil
import urllib.request
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


def download_file(url, destination):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ozzy-trip-data-hike-action"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        with destination.open("wb") as file:
            shutil.copyfileobj(response, file)


def first_url(value):
    entries = image_entries_for(value)
    urls = [entry for entry in entries if entry.startswith("http://") or entry.startswith("https://")]

    if not urls:
        raise ValueError("GPX file must include a GitHub attachment URL or direct GPX URL")

    return urls[0]


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

    gpx_url = first_url(value_for(sections, "GPX file"))
    gpx_path = GPX_FOLDER / f"{hike_id}.gpx"
    download_file(gpx_url, gpx_path)

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
