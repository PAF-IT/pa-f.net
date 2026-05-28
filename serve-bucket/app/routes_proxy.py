import os

from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app import bucket

router = APIRouter()


@router.get("/{path:path}")
def proxy(path: str):
    if not path or "." not in path.split("/")[-1]:
        path = os.path.join(path, "index.html")
    path = path.strip("/")

    try:
        response = bucket.get_object(path)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            raise HTTPException(status_code=404, detail="Not found")
        raise

    content_type = response["ResponseMetadata"]["HTTPHeaders"].get(
        "content-type", "application/octet-stream"
    )

    def stream():
        for chunk in response["Body"].iter_chunks(chunk_size=8192):
            yield chunk

    return StreamingResponse(stream(), media_type=content_type)
