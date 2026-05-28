"""Seed or update /meta/login.json in the bucket with a bcrypt-hashed password.

Usage:
    cd serve-bucket
    source ./env_NOCOMMIT.sh          # exports UPCLOUD_* + BUCKET_NAME
    uv run python -m scripts.seed_login <username>
"""

import argparse
import getpass
import json
import sys

import bcrypt
from botocore.exceptions import ClientError

from app import bucket

LOGIN_KEY = "meta/login.json"


def load_existing() -> dict[str, str]:
    try:
        raw = bucket.get_bytes(LOGIN_KEY)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404", "NotFound"):
            print(f"No existing {LOGIN_KEY} — creating new file.")
            return {}
        raise
    data = json.loads(raw)
    return data.get("users", {})


def prompt_password() -> str:
    pw = getpass.getpass("Password: ")
    if not pw:
        sys.exit("Aborted: empty password.")
    pw2 = getpass.getpass("Confirm:  ")
    if pw != pw2:
        sys.exit("Aborted: passwords did not match.")
    return pw


def main():
    parser = argparse.ArgumentParser(description="Seed/update a user in /meta/login.json")
    parser.add_argument("username", help="Username to add or update")
    args = parser.parse_args()

    users = load_existing()

    if args.username in users:
        print(f"Updating existing user `{args.username}`.")
    else:
        print(f"Adding new user `{args.username}`.")

    pw = prompt_password()
    users[args.username] = bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    body = json.dumps({"users": users}, indent=2).encode("utf-8")
    bucket.put_object(LOGIN_KEY, body, content_type="application/json")

    print(f"Wrote {LOGIN_KEY}. Users: {sorted(users)}")


if __name__ == "__main__":
    main()
