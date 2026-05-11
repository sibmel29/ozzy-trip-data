import json
import os
from pathlib import Path

import add_poi_from_issue
from add_poi_from_issue import (
    coordinates_from_sections,
    images_from_entries,
    image_entries_for,
    parse_paragraphs,
    parse_sections,
    parse_tags,
    published_from_sections,
    slugify,
    value_for,
)


JOURNAL_TYPE = os.environ.get("JOURNAL_TYPE", "fishing")
JOURNAL_FILE = Path(os.environ.get("JOURNAL_FILE", f"{JOURNAL_TYPE}-log.json"))
RESULT_FILE = Path(os.environ.get("RESULT_FILE", "journal_result.json"))
MEDIA_FOLDER = Path(os.environ.get("MEDIA_FOLDER", f"{JOURNAL_TYPE}-media"))

TYPE_CONFIG = {
    "fishing": {
        "title_labels": ["Fishing log title"],
        "marker": "fish",
        "default_tag": "fishing",
        "unique_by": "issue",
        "detail_labels": [
            "Spot name",
            "Species",
            "Count",
            "Size",
            "Caught time",
            "Kept or released",
            "Bait or lure",
            "Conditions",
        ],
    },
    "surf": {
        "title_labels": ["Surf spot", "Surf log title"],
        "marker": "surf",
        "default_tag": "surf",
        "unique_by": "id",
        "detail_labels": [
            "Surf spot",
            "First surfed",
            "Wave size",
            "Wind",
            "Tide",
            "Board",
            "Rating",
            "Crowd",
        ],
    },
}


def unique_id(base_id, issue_number, entries, unique_by="issue"):
    source_issue = str(issue_number)

    if unique_by == "issue":
        for entry in entries:
            if str(entry.get("source_issue", "")) == source_issue:
                return entry.get("id", base_id), entry
    else:
        for entry in entries:
            if entry.get("id") == base_id:
                return base_id, entry

    existing_ids = {entry.get("id") for entry in entries}

    if base_id not in existing_ids:
        return base_id, None

    issue_id = f"{base_id}-{issue_number}"
    if issue_id not in existing_ids:
        return issue_id, None

    index = 2
    while f"{issue_id}-{index}" in existing_ids:
        index += 1

    return f"{issue_id}-{index}", None


def first_value(sections, labels, default=""):
    for label in labels:
        value = value_for(sections, label)
        if value:
            return value

    return default


def details_from_sections(sections, labels):
    details = {}

    for label in labels:
        value = value_for(sections, label)
        if value:
            details[label] = value

    return details


def images_from_sections(sections, entry_id, title, existing=None):
    entries = image_entries_for(value_for(sections, "Image paths"))

    if not entries:
        if existing:
            return existing.get("images", [])

        media_folder = MEDIA_FOLDER / entry_id
        media_folder.mkdir(parents=True, exist_ok=True)
        (media_folder / ".gitkeep").touch()
        return []

    return images_from_entries(entries, entry_id, title)


def build_entry(sections, issue_number, issue_url, entries):
    config = TYPE_CONFIG[JOURNAL_TYPE]
    title = first_value(sections, config["title_labels"])

    if not title:
        raise ValueError(f"{config['title_labels'][0]} is required")

    entry_id, existing = unique_id(slugify(title), issue_number, entries, config["unique_by"])
    original_media_folder = add_poi_from_issue.POI_MEDIA_FOLDER
    add_poi_from_issue.POI_MEDIA_FOLDER = MEDIA_FOLDER

    try:
        images = images_from_sections(sections, entry_id, title, existing)
    finally:
        add_poi_from_issue.POI_MEDIA_FOLDER = original_media_folder

    previous_details = existing.get("details", {}) if existing else {}
    details = {**previous_details, **details_from_sections(sections, config["detail_labels"])}

    entry = {
        "id": entry_id,
        "type": JOURNAL_TYPE,
        "title": title,
        "date": value_for(sections, "Date", existing.get("date", "") if existing else ""),
        "coordinates": coordinates_from_sections(sections, existing),
        "marker": config["marker"],
        "summary": value_for(sections, "Short summary", existing.get("summary", "") if existing else ""),
        "body": parse_paragraphs(value_for(sections, "Story text")) if value_for(sections, "Story text") else (existing.get("body", []) if existing else []),
        "images": images,
        "tags": parse_tags(value_for(sections, "Tags")) or (existing.get("tags", []) if existing else [config["default_tag"]]),
        "details": details,
        "published": published_from_sections(sections, existing),
        "source_issue": str(issue_number),
        "source_url": issue_url,
    }

    return entry, existing


def main():
    if JOURNAL_TYPE not in TYPE_CONFIG:
        raise ValueError(f"Unknown journal type {JOURNAL_TYPE!r}")

    issue_body = os.environ.get("ISSUE_BODY", "")
    issue_number = os.environ.get("ISSUE_NUMBER", "")
    issue_url = os.environ.get("ISSUE_URL", "")

    if not issue_body or not issue_number:
        raise ValueError("ISSUE_BODY and ISSUE_NUMBER are required")

    sections = parse_sections(issue_body)
    entries = json.loads(JOURNAL_FILE.read_text(encoding="utf-8")) if JOURNAL_FILE.exists() else []
    entry, existing = build_entry(sections, issue_number, issue_url, entries)

    if existing is not None:
        existing.clear()
        existing.update(entry)
        action = "updated"
    else:
        entries.insert(0, entry)
        action = "added"

    JOURNAL_FILE.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    RESULT_FILE.write_text(json.dumps({
        "id": entry["id"],
        "title": entry["title"],
        "action": action,
        "journal_type": JOURNAL_TYPE,
    }), encoding="utf-8")

    print(f"{action.title()} {JOURNAL_TYPE} entry {entry['id']}: {entry['title']}")


if __name__ == "__main__":
    main()
