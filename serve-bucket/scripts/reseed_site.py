"""Reseed `meta/sitemap.json` + regenerate static HTML from a fresh wget mirror.

Usage:
    cd serve-bucket
    source ./env_NOCOMMIT.sh
    uv run python -m scripts.reseed_site [--source ../pa-f.net] [--images] [--dry-run]
"""

import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path

from botocore.exceptions import ClientError

from app import bucket
from app.routes_editor import (
    IMAGE_CONTENT_TYPES,
    SITEMAP_KEY,
    _archive_key,
    _bare_key,
    _regenerate_and_upload,
)
from palimpsest import SiteParser


def _normalize_page(raw: dict) -> dict:
    """Coerce a parsed page to the fields the editor flow stores."""
    image = raw.get("image")
    return {
        "title": raw.get("title") or "",
        "md": raw.get("md") or "",
        "date": raw.get("date") or "",
        "image": image if isinstance(image, str) else "",
    }


def _list_existing_html_keys() -> list[str]:
    """Page-tree HTML object keys currently in the bucket (excludes meta/, sites/)."""
    client = bucket.client()
    paginator = client.get_paginator("list_objects_v2")
    keys: list[str] = []
    for page in paginator.paginate(Bucket=bucket.BUCKET):
        for obj in page.get("Contents", []) or []:
            key = obj["Key"]
            if not key.endswith(".html"):
                continue
            if key.startswith("meta/") or key.startswith("sites/"):
                continue
            keys.append(key)
    return keys


def _image_content_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in IMAGE_CONTENT_TYPES:
        return IMAGE_CONTENT_TYPES[ext]
    guess, _ = mimetypes.guess_type(filename)
    return guess or "application/octet-stream"


def _upload_images(images_dir: Path, dry_run: bool) -> int:
    """Walk `<source>/sites/pa-f.net/files/` and upload each non-`?`-tainted file."""
    if not images_dir.exists():
        print(f"No images dir at {images_dir}, skipping images.")
        return 0
    count = 0
    for root, _dirs, files in os.walk(images_dir):
        for fname in files:
            if "?" in fname:  # wget query-string variants (e.g. ?size=…)
                continue
            full = Path(root) / fname
            rel = full.relative_to(images_dir.parent.parent.parent)  # → sites/pa-f.net/files/...
            key = str(rel)
            if dry_run:
                count += 1
                continue
            bucket.upload_file(str(full), key, content_type=_image_content_type(fname))
            count += 1
            if count % 100 == 0:
                print(f"  uploaded {count} images…")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Reseed sitemap + static site from a wget mirror.")
    parser.add_argument(
        "--source",
        default="../pa-f.net",
        help="Path to the wgetted pa-f.net directory (default: ../pa-f.net).",
    )
    parser.add_argument(
        "--images",
        action="store_true",
        help="Also (re-)upload files under <source>/sites/pa-f.net/files/ to the bucket.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without touching the bucket.",
    )
    args = parser.parse_args()

    source = Path(args.source).resolve()
    if not source.is_dir():
        sys.exit(f"Source dir does not exist: {source}")

    print(f"Parsing {source} …")
    sp = SiteParser(root_dir=str(source) + "/")
    parsed = sp.parse()
    new_sitemap = {_bare_key(k): _normalize_page(v) for k, v in parsed.items()}
    print(f"Parsed {len(new_sitemap)} pages.")

    # Stale page deletes.
    new_html_keys = {f"{k}.html" if not k.endswith(".html") else k for k in new_sitemap}
    existing_html_keys = set(_list_existing_html_keys())
    stale = sorted(existing_html_keys - new_html_keys)

    archive_key = _archive_key()
    prior_exists = bucket.object_exists(SITEMAP_KEY)

    print("--- Plan ---")
    print(f"  archive prior sitemap → {archive_key}" if prior_exists else "  (no prior sitemap to archive)")
    print(f"  write meta/sitemap.json ({len(new_sitemap)} pages)")
    print(f"  regenerate + upload {len(new_sitemap)} static HTML pages")
    print(f"  delete {len(stale)} stale HTML objects")
    if args.images:
        print(f"  upload images from {source / 'sites' / 'pa-f.net' / 'files'}")
    print("------------")

    if args.dry_run:
        if stale:
            sample = stale[:20]
            print("Would delete (first 20):")
            for k in sample:
                print(f"  - {k}")
            if len(stale) > len(sample):
                print(f"  ... and {len(stale) - len(sample)} more")
        print("Dry-run; not touching the bucket.")
        return

    if prior_exists:
        try:
            bucket.copy_object(SITEMAP_KEY, archive_key)
            print(f"Archived prior sitemap to {archive_key}")
        except ClientError as e:
            sys.exit(f"Failed to archive prior sitemap: {e}")

    body = json.dumps(new_sitemap, indent=2).encode("utf-8")
    bucket.put_object(SITEMAP_KEY, body, content_type="application/json")
    print(f"Wrote {SITEMAP_KEY} ({len(body)} bytes).")

    print("Regenerating static HTML…")
    _regenerate_and_upload(new_sitemap)
    print(f"Uploaded {len(new_sitemap)} HTML pages.")

    deleted = 0
    for key in stale:
        try:
            bucket.delete_object(key)
            deleted += 1
        except ClientError:
            pass
    print(f"Deleted {deleted}/{len(stale)} stale HTML objects.")

    if args.images:
        images_dir = source / "sites" / "pa-f.net" / "files"
        print(f"Uploading images from {images_dir} …")
        n = _upload_images(images_dir, dry_run=False)
        print(f"Uploaded {n} image files.")

    print("Done.")


if __name__ == "__main__":
    main()
