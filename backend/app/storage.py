"""Cloudflare R2 storage client (S3-compatible)."""

import boto3
import uuid
from datetime import datetime
from app.config import (
    R2_ACCOUNT_ID,
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    R2_BUCKET_NAME,
    R2_ENDPOINT,
)


def get_r2_client():
    """Create S3-compatible client for Cloudflare R2."""
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def create_session() -> str:
    """Create a new processing session, return session_id."""
    return f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def upload_file(session_id: str, folder: str, filename: str, data: bytes) -> str:
    """Upload file to R2, return object key."""
    key = f"sessions/{session_id}/{folder}/{filename}"
    client = get_r2_client()
    client.put_object(
        Bucket=R2_BUCKET_NAME,
        Key=key,
        Body=data,
    )
    return key


def download_file(key: str) -> bytes:
    """Download file from R2."""
    client = get_r2_client()
    response = client.get_object(Bucket=R2_BUCKET_NAME, Key=key)
    return response["Body"].read()


def list_session_files(session_id: str, folder: str = "") -> list[dict]:
    """List all files in a session folder."""
    client = get_r2_client()
    prefix = f"sessions/{session_id}/{folder}" if folder else f"sessions/{session_id}/"
    response = client.list_objects_v2(Bucket=R2_BUCKET_NAME, Prefix=prefix)

    files = []
    for obj in response.get("Contents", []):
        files.append({
            "key": obj["Key"],
            "size": obj["Size"],
            "last_modified": obj["LastModified"].isoformat(),
        })
    return files


def delete_session(session_id: str):
    """Delete all files in a session."""
    client = get_r2_client()
    prefix = f"sessions/{session_id}/"
    response = client.list_objects_v2(Bucket=R2_BUCKET_NAME, Prefix=prefix)

    objects = [{"Key": obj["Key"]} for obj in response.get("Contents", [])]
    if objects:
        client.delete_objects(
            Bucket=R2_BUCKET_NAME,
            Delete={"Objects": objects},
        )
    return len(objects)
