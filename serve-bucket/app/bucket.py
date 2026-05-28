import os

# Non-AWS S3 (Upcloud) compatibility — see https://github.com/fsspec/s3fs/issues/931
os.environ.setdefault("AWS_REQUEST_CHECKSUM_CALCULATION", "when_required")
os.environ.setdefault("AWS_RESPONSE_CHECKSUM_VALIDATION", "when_required")

import boto3
from botocore.exceptions import ClientError


_client = boto3.client(
    service_name="s3",
    aws_access_key_id=os.environ["UPCLOUD_OBJ_ID"],
    aws_secret_access_key=os.environ["UPCLOUD_OBJ_SECRET"],
    endpoint_url=os.environ["UPCLOUD_OBJ_ENDPOINT"],
)
BUCKET = os.environ["BUCKET_NAME"]


def client():
    return _client


def get_object(key: str):
    """Return the raw boto3 GetObject response (caller iterates Body)."""
    return _client.get_object(Bucket=BUCKET, Key=key.lstrip("/"))


def get_bytes(key: str) -> bytes:
    return get_object(key)["Body"].read()


def put_object(key: str, body, content_type: str | None = None):
    extra = {"ContentType": content_type} if content_type else {}
    _client.put_object(Bucket=BUCKET, Key=key.lstrip("/"), Body=body, **extra)


def upload_file(local_path: str, key: str, content_type: str | None = None):
    extra = {"ContentType": content_type} if content_type else {}
    _client.upload_file(local_path, BUCKET, key.lstrip("/"), ExtraArgs=extra)


def copy_object(src_key: str, dst_key: str):
    _client.copy_object(
        Bucket=BUCKET,
        CopySource={"Bucket": BUCKET, "Key": src_key.lstrip("/")},
        Key=dst_key.lstrip("/"),
    )


def object_exists(key: str) -> bool:
    try:
        _client.head_object(Bucket=BUCKET, Key=key.lstrip("/"))
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return False
        raise
