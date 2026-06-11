"""Mirror the bucket to a local directory.

Usage:
    cd serve-bucket
    source ./env_NOCOMMIT.sh
    uv run python -m scripts.backup_bucket [--out ./bucket-backup] [--prefix ""] [--dry-run]

Re-runs are resume-friendly: files already on disk with the matching size are
skipped.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from botocore.exceptions import ClientError

from app import bucket


def _human_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    f = float(n)
    for u in units:
        if f < 1024 or u == units[-1]:
            return f"{f:.1f} {u}"
        f /= 1024
    return f"{n} B"


def _list_all(prefix: str) -> list[dict]:
    client = bucket.client()
    paginator = client.get_paginator("list_objects_v2")
    objs: list[dict] = []
    for page in paginator.paginate(Bucket=bucket.BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []) or []:
            objs.append({"key": obj["Key"], "size": obj["Size"], "etag": obj["ETag"].strip('"')})
    return objs


def main() -> None:
    ap = argparse.ArgumentParser(description="Download a full mirror of the bucket to disk.")
    ap.add_argument("--out", default="./bucket-backup", help="Output directory (default: ./bucket-backup).")
    ap.add_argument("--prefix", default="", help="Optional key prefix filter (default: all).")
    ap.add_argument("--dry-run", action="store_true", help="List + size only; don't download.")
    args = ap.parse_args()

    out_dir = Path(args.out).resolve()
    print(f"Listing s3://{bucket.BUCKET}/{args.prefix or ''} …")
    objects = _list_all(args.prefix)
    total_bytes = sum(o["size"] for o in objects)
    print(f"Found {len(objects)} objects, {_human_bytes(total_bytes)} total.")

    if args.dry_run:
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    client = bucket.client()

    downloaded = 0
    skipped = 0
    bytes_done = 0
    next_progress_files = 100
    next_progress_bytes = 100 * 1024 * 1024

    for obj in objects:
        key = obj["key"]
        if key.endswith("/"):
            continue
        # Strip a leading slash so the key resolves under out_dir rather than /.
        local_path = out_dir / key.lstrip("/")
        local_path.parent.mkdir(parents=True, exist_ok=True)

        if local_path.exists() and local_path.stat().st_size == obj["size"]:
            skipped += 1
            bytes_done += obj["size"]
            continue

        try:
            client.download_file(bucket.BUCKET, key, str(local_path))
            downloaded += 1
            bytes_done += obj["size"]
        except ClientError as e:
            print(f"  failed: {key}: {e}", file=sys.stderr)

        done = downloaded + skipped
        if done >= next_progress_files or bytes_done >= next_progress_bytes:
            print(
                f"  {done}/{len(objects)} files "
                f"({_human_bytes(bytes_done)} / {_human_bytes(total_bytes)}), "
                f"downloaded={downloaded} skipped={skipped}"
            )
            while next_progress_files <= done:
                next_progress_files += 100
            while next_progress_bytes <= bytes_done:
                next_progress_bytes += 100 * 1024 * 1024

    manifest = {
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "bucket": bucket.BUCKET,
        "prefix": args.prefix,
        "object_count": len(objects),
        "total_bytes": total_bytes,
        "objects": objects,
    }
    manifest_path = out_dir / "_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    print(
        f"Done. downloaded={downloaded} skipped={skipped} "
        f"({_human_bytes(bytes_done)}) → {out_dir}"
    )
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
