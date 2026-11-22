"""Yandex Message Queue trigger entry point."""

import hashlib
import json
import os
import re
import tempfile
import uuid
import zipfile
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from source import source_response


class NoCloudRedirects(HTTPRedirectHandler):
    """Keep IAM credentials on the configured cloud endpoint."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


cloud = build_opener(NoCloudRedirects())
CHUNK_SIZE = 64 * 1024


def archive_key(message):
    # RFC 9562: 48-bit Unix timestamp in ms, version 7, RFC variant, 74 random bits.
    # Derive the random bits from YMQ's unique ID so redelivery uses the same object.
    millis = int(message["attributes"]["SentTimestamp"])
    if not 0 <= millis < 1 << 48:
        raise ValueError("Invalid queue timestamp")
    digest = hashlib.sha256(message["message_id"].encode()).digest()
    fields = bytearray(millis.to_bytes(6, "big") + digest[:10])
    fields[6] = (fields[6] & 0x0F) | 0x70
    fields[8] = (fields[8] & 0x3F) | 0x80
    return f"{uuid.UUID(bytes=bytes(fields))}.zip"


def write_archive(file, name, url):
    with source_response(url) as response, zipfile.ZipFile(file, "w", zipfile.ZIP_DEFLATED) as archive:
        size = 0
        with archive.open(name, "w") as member:
            while chunk := response.read(CHUNK_SIZE):
                member.write(chunk)
                size += len(chunk)
        expected = response.getheader("Content-Length")
        if expected is not None and size != int(expected):
            raise OSError("Source download was incomplete")


def object_exists(url, headers):
    try:
        with cloud.open(Request(url, headers=headers, method="HEAD"), timeout=30):
            return True
    except HTTPError as error:
        if error.code != 404:
            raise
        error.close()
        return False


def handler(event, context):
    (record,) = event["messages"]
    message = record["details"]["message"]
    task = json.loads(message["body"])
    name, url = task["name"], task["url"]
    if not re.fullmatch(r"[^/\\:\x00-\x1f\x7f]+", name) or name in {".", ".."}:
        raise ValueError("Expected a single file name")

    key = archive_key(message)
    object_url = f"https://storage.yandexcloud.net/{os.environ['BUCKET_NAME']}/{key}"
    auth = {"Authorization": f"Bearer {context.token['access_token']}"}
    if not object_exists(object_url, auth):
        with tempfile.TemporaryFile() as file:
            write_archive(file, name, url)
            headers = {**auth, "Content-Type": "application/zip", "Content-Length": str(file.tell())}
            file.seek(0)
            with cloud.open(Request(object_url, file, headers, method="PUT"), timeout=60):
                pass

    item = {"name": {"S": name}, "url": {"S": url}, "key": {"S": key}}
    payload = json.dumps({"TableName": os.environ["TABLE_NAME"], "Item": item}).encode()
    headers = {
        **auth,
        "X-Amz-Target": "DynamoDB_20120810.PutItem",
        "Content-Type": "application/x-amz-json-1.0",
    }
    with cloud.open(Request(os.environ["DOCUMENT_ENDPOINT"], payload, headers), timeout=30):
        pass
    return {"key": key}
