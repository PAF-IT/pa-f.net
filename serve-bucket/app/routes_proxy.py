import os

from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse

from app import bucket

router = APIRouter()


def _is_no_such_key(e: ClientError) -> bool:
    return e.response["Error"]["Code"] in ("NoSuchKey", "404")


def _stream(response):
    def gen():
        for chunk in response["Body"].iter_chunks(chunk_size=8192):
            yield chunk
    content_type = response["ResponseMetadata"]["HTTPHeaders"].get(
        "content-type", "application/octet-stream"
    )
    return StreamingResponse(gen(), media_type=content_type)


@router.get("/{path:path}")
def proxy(path: str):
    raw = path
    last = raw.split("/")[-1] if raw else ""

    # 1. Redirect .html URLs (other than index.html) to the bare canonical form.
    if last.endswith(".html") and last != "index.html":
        bare = raw[: -len(".html")]
        return RedirectResponse(url=f"/{bare}", status_code=301)

    # 2. Empty or extensionless: try <path>.html first, then <path>/index.html.
    if not raw or "." not in last:
        candidates = []
        if raw:
            candidates.append(f"{raw}.html")
        candidates.append(os.path.join(raw, "index.html") if raw else "index.html")
        last_err = None
        for key in candidates:
            try:
                return _stream(bucket.get_object(key.strip("/")))
            except ClientError as e:
                if _is_no_such_key(e):
                    last_err = e
                    continue
                raise
        raise HTTPException(status_code=404, detail="Not found")

    # 3. Has an extension (asset): serve as-is.
    try:
        return _stream(bucket.get_object(raw.strip("/")))
    except ClientError as e:
        if _is_no_such_key(e):
            raise HTTPException(status_code=404, detail="Not found")
        raise
