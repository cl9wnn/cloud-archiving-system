"""Run against a deployed gateway: python3 tests/smoke.py https://..."""

import io
import json
import sys
import time
import uuid
import zipfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request(url, expected, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    try:
        response = urlopen(Request(url, data=data, headers=headers), timeout=30)
    except HTTPError as error:
        response = error
    with response:
        if response.status != expected:
            raise RuntimeError(f"{url}: expected {expected}, got {response.status}: {response.read(512)!r}")
        return response.read()


def main(base):
    source = "https://www.rfc-editor.org/rfc/rfc9562.txt"
    name = f"demo-{uuid.uuid4().hex}.txt"
    original = request(source, 200)
    request(base + "/tasks", 400, {"name": name})
    missing = "00000000-0000-7000-8000-000000000000.zip"
    for route in ("/archives/", "/download/"):
        request(base + route + missing, 404)
    request(base + "/tasks", 202, {"name": name, "url": source})

    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        rows = json.loads(request(base + "/archives", 200))
        record = next((r for r in rows if r["name"] == name), None)
        if record:
            break
        time.sleep(3)
    else:
        raise TimeoutError("Archive did not appear within four minutes")

    key = record["key"]
    identifier = uuid.UUID(key[:-4])
    if identifier.version != 7 or key != f"{identifier}.zip":
        raise ValueError(f"Invalid archive key: {key}")
    expected = {"key": key, "url": source, "name": name}
    if record != expected or json.loads(request(base + "/archives/" + key, 200)) != expected:
        raise ValueError("Archive metadata differs from task")
    with zipfile.ZipFile(io.BytesIO(request(base + "/download/" + key, 200))) as archive:
        if archive.namelist() != [name] or archive.read(name) != original:
            raise ValueError("Downloaded ZIP differs from the source")
    print(f"OK: 202, 400, both 404s, list, metadata and ZIP contents verified for {key}")


if __name__ == "__main__":
    main(sys.argv[1].rstrip("/"))
