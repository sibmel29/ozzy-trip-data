import json
import os
import shutil
import tempfile
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

from add_poi_from_issue import image_entries_for, parse_sections, value_for


GALLERY_FILE = Path(os.environ.get("ANALOG_GALLERY_FILE", "analog-gallery/gallery.json"))
WEB_FOLDER = Path(os.environ.get("ANALOG_WEB_FOLDER", "analog-gallery/web"))
THUMB_FOLDER = Path(os.environ.get("ANALOG_THUMB_FOLDER", "analog-gallery/thumbs"))
RESULT_FILE = Path(os.environ.get("RESULT_FILE", "analog_gallery_result.json"))
WEB_MAX_SIZE = int(os.environ.get("ANALOG_WEB_MAX_SIZE", "2000"))
THUMB_MAX_SIZE = int(os.environ.get("ANALOG_THUMB_MAX_SIZE", "600"))


def download_file(url, destination):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ozzy-trip-data-analog-gallery-action"},
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        with destination.open("wb") as output:
            shutil.copyfileobj(response, output)


def save_jpeg(source, destination, max_size, quality):
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(
            destination,
            "JPEG",
            quality=quality,
            optimize=True,
            progressive=True,
        )


def caption_lines(value):
    return [line.strip().lstrip("-").strip() for line in value.splitlines() if line.strip()]


def clear_previous_issue_files(issue_number):
    pattern = f"issue-{issue_number}-*.jpg"

    for folder in (WEB_FOLDER, THUMB_FOLDER):
        for path in folder.glob(pattern):
            path.unlink()


def main():
    issue_body = os.environ.get("ISSUE_BODY", "")
    issue_number = os.environ.get("ISSUE_NUMBER", "")
    issue_url = os.environ.get("ISSUE_URL", "")

    if not issue_body or not issue_number:
        raise ValueError("ISSUE_BODY and ISSUE_NUMBER are required")

    sections = parse_sections(issue_body)
    uploads = image_entries_for(value_for(sections, "Photo uploads"))

    if not uploads:
        raise ValueError("Photo uploads must include at least one uploaded image")

    collection_title = value_for(sections, "Collection title", "Analog photo")
    date = value_for(sections, "Date")
    captions = caption_lines(value_for(sections, "Captions"))
    gallery = json.loads(GALLERY_FILE.read_text(encoding="utf-8")) if GALLERY_FILE.exists() else []
    gallery = [item for item in gallery if str(item.get("source_issue", "")) != str(issue_number)]

    WEB_FOLDER.mkdir(parents=True, exist_ok=True)
    THUMB_FOLDER.mkdir(parents=True, exist_ok=True)
    clear_previous_issue_files(issue_number)
    new_items = []

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_folder = Path(temp_dir)

        for index, url in enumerate(uploads, start=1):
            file_id = f"issue-{issue_number}-{index}"
            raw_path = temp_folder / f"{file_id}.upload"
            web_path = WEB_FOLDER / f"{file_id}.jpg"
            thumb_path = THUMB_FOLDER / f"{file_id}.jpg"
            download_file(url, raw_path)
            save_jpeg(raw_path, web_path, WEB_MAX_SIZE, 84)
            save_jpeg(raw_path, thumb_path, THUMB_MAX_SIZE, 76)

            if index <= len(captions):
                title = captions[index - 1]
            elif len(uploads) == 1:
                title = collection_title
            else:
                title = f"{collection_title} {index}"

            new_items.append({
                "id": file_id,
                "title": title,
                "date": date,
                "src": web_path.as_posix(),
                "thumb": thumb_path.as_posix(),
                "source_issue": str(issue_number),
                "source_url": issue_url,
            })

    GALLERY_FILE.parent.mkdir(parents=True, exist_ok=True)
    GALLERY_FILE.write_text(
        json.dumps(new_items + gallery, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    RESULT_FILE.write_text(
        json.dumps({"count": len(new_items), "collection_title": collection_title}),
        encoding="utf-8",
    )
    print(f"Added {len(new_items)} analog photos from issue #{issue_number}")


if __name__ == "__main__":
    main()
