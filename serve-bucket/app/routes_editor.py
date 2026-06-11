import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from markdown import markdown as md_to_html
from markdownify import markdownify as html_to_md
from pydantic import BaseModel

import palimpsest

from app import bucket
from app.auth import (
    COOKIE_NAME,
    create_access_token,
    get_current_user,
    invalidate_users_cache,
    load_users,
    verify_password,
)

router = APIRouter(prefix="/api/editor")

SITEMAP_KEY = "meta/sitemap.json"
SIDEBAR_PATH = Path(__file__).parent.parent / "sidebar.html"

IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "webp"}
IMAGE_CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}


# --- Auth ---------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(req: LoginRequest, response: Response):
    users = load_users()
    hashed = users.get(req.username)
    if not hashed or not verify_password(req.password, hashed):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(req.username)
    secure = os.environ.get("COOKIE_SECURE", "0") == "1"
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=secure,
        max_age=60 * 60 * 24 * 30,
        path="/",
    )
    return {"username": req.username}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(username: str = Depends(get_current_user)):
    return {"username": username}


@router.post("/users/reload")
def reload_users(username: str = Depends(get_current_user)):
    invalidate_users_cache()
    return {"ok": True, "users": list(load_users().keys())}


# --- Sitemap ------------------------------------------------------------

def _load_sitemap() -> dict[str, Any]:
    try:
        raw = bucket.get_bytes(SITEMAP_KEY)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return {}
        raise
    return json.loads(raw)


@router.get("/sitemap")
def get_sitemap(username: str = Depends(get_current_user)):
    sitemap = _load_sitemap()
    pages = {}
    for path, page in sitemap.items():
        md = page.get("md", "") or ""
        html = palimpsest.generator.markdown2html(md) if md else ""
        # Rewrite legacy relative image paths (e.g. ../sites/pa-f.net/files/x.jpg)
        # to absolute (/sites/pa-f.net/files/x.jpg). This is the same form
        # palimpsest.generator.images_from_root produces on output, and the only
        # form that works for both the prod /editor/ mount and the Vite dev server.
        html = palimpsest.generator.images_from_root(html)
        def _s(v):
            return v if isinstance(v, str) else ""
        pages[path] = {
            "title": _s(page.get("title", "")),
            "date": _s(page.get("date", "")),
            "image": _s(page.get("image", "")),
            "html": html,
        }
    return {"pages": pages}


class PageIn(BaseModel):
    title: str = ""
    date: str = ""
    image: str = ""
    html: str = ""


class SitemapIn(BaseModel):
    pages: dict[str, PageIn]
    rename_map: dict[str, str] = {}  # new_path -> old_path


def _archive_key() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"meta/archive/sitemap-{ts}.json"


def _convert_pages_to_md(payload: SitemapIn, prior: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for path, page in payload.pages.items():
        md = html_to_md(page.html or "", heading_style="ATX").strip() + "\n"
        # For renames, look up the page's original key so pass-through fields
        # (e.g. `links`) follow it.
        lookup = payload.rename_map.get(path, path)
        existing = prior.get(lookup, {})
        merged = dict(existing)
        merged.update(
            title=page.title,
            date=page.date,
            image=page.image,
            md=md,
        )
        out[path] = merged
    return out


def _regenerate_and_upload(sitemap: dict[str, Any]):
    with tempfile.TemporaryDirectory() as tdir:
        ssg = palimpsest.StaticSiteGenerator(sitemap, output_dir=tdir)
        if SIDEBAR_PATH.exists():
            ssg.load_sidebar(str(SIDEBAR_PATH))
        ssg.generate_site()

        for root, _dirs, files in os.walk(tdir):
            for fname in files:
                if not fname.endswith(".html"):
                    continue
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, tdir)
                bucket.upload_file(full, rel, content_type="text/html")


@router.put("/sitemap")
def put_sitemap(payload: SitemapIn, username: str = Depends(get_current_user)):
    prior = _load_sitemap()
    new_sitemap = _convert_pages_to_md(payload, prior)

    # Paths that existed before but are gone now (deletes + the source side of renames).
    delete_paths = set(prior) - set(new_sitemap)

    # Archive the prior sitemap (if it exists) before overwriting
    if prior:
        try:
            bucket.copy_object(SITEMAP_KEY, _archive_key())
        except ClientError as e:
            raise HTTPException(status_code=500, detail=f"Failed to archive prior sitemap: {e}")

    # Write the new sitemap
    bucket.put_object(
        SITEMAP_KEY,
        json.dumps(new_sitemap, indent=2).encode("utf-8"),
        content_type="application/json",
    )

    # Regenerate the static HTML and overwrite the live site
    _regenerate_and_upload(new_sitemap)

    # Clean up generated HTML for pages that no longer exist (renamed-from or deleted).
    deleted = []
    for path in delete_paths:
        try:
            bucket.delete_object(path)
            deleted.append(path)
        except ClientError:
            pass  # Already gone or never existed; not worth failing the save.

    return {
        "ok": True,
        "page_count": len(new_sitemap),
        "deleted_paths": deleted,
    }


# --- Image upload -------------------------------------------------------

_safe_slug_re = re.compile(r"[^a-z0-9]+")


def _slug(s: str) -> str:
    return _safe_slug_re.sub("-", s.lower()).strip("-")[:40]


@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    caption: str = Form(""),
    username: str = Depends(get_current_user),
):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in IMAGE_EXTS:
        raise HTTPException(status_code=400, detail=f"Unsupported extension: {ext}")
    body = await file.read()
    if not body:
        raise HTTPException(status_code=400, detail="Empty file")

    stem_hint = _slug(Path(file.filename or "").stem) or "image"
    name = f"{stem_hint}-{uuid.uuid4().hex[:8]}.{ext}"
    key = f"sites/pa-f.net/files/{name}"
    bucket.put_object(key, body, content_type=IMAGE_CONTENT_TYPES[ext])
    return {"url": f"/{key}", "caption": caption}
