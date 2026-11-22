import io
import json
import pathlib
import socket
import sys
import unittest
import uuid
import zipfile
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "function"))
import main
import source


class SourceFile(io.BytesIO):
    def getheader(self, name):
        return str(len(self.getvalue()))


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.objects = {}
        self.items = []
        self.fail_write = False
        self.message = {
            "message_id": "cf09ed0e-9dd1-49af-8b5b-68856ae7f945",
            "attributes": {"SentTimestamp": "1730000000123"},
            "body": json.dumps({"name": "пример.txt", "url": "https://example.com/file"}),
        }
        self.event = {"messages": [{"details": {"message": self.message}}]}
        self.context = SimpleNamespace(token={"access_token": "local-test"})
        self.content = bytes(range(256)) * 700
        self.start_patch(patch.dict(main.os.environ, {
            "BUCKET_NAME": "vvot27-test", "TABLE_NAME": "archives",
            "DOCUMENT_ENDPOINT": "https://database.invalid",
        }))
        self.start_patch(patch.object(main.cloud, "open", side_effect=self.cloud_request))
        self.download = self.start_patch(patch.object(main, "source_response",
                                                     side_effect=lambda url: SourceFile(self.content)))

    def start_patch(self, mock_patch):
        result = mock_patch.start()
        self.addCleanup(mock_patch.stop)
        return result

    @contextmanager
    def cloud_request(self, request, timeout):
        self.assertEqual(request.get_header("Authorization"), "Bearer local-test")
        method = request.get_method()
        if method == "HEAD" and request.full_url not in self.objects:
            raise HTTPError(request.full_url, 404, "Not Found", {}, None)
        if method == "PUT":
            data = request.data.read()
            self.assertEqual(len(data), int(request.get_header("Content-length")))
            self.objects[request.full_url] = data
        if method == "POST":
            if self.fail_write:
                raise OSError("YDB unavailable")
            self.items.append(json.loads(request.data))
        yield

    def test_archive_and_record(self):
        key = main.handler(self.event, self.context)["key"]
        identifier = uuid.UUID(key.removesuffix(".zip"))
        self.assertEqual(identifier.version, 7)
        self.assertEqual(identifier.int >> 80, int(self.message["attributes"]["SentTimestamp"]))
        record = self.items[0]
        self.assertEqual(record["TableName"], "archives")
        self.assertEqual(record["Item"], {
            "key": {"S": key}, "name": {"S": "пример.txt"}, "url": {"S": "https://example.com/file"}
        })
        archive_url = f"https://storage.yandexcloud.net/vvot27-test/{key}"
        with zipfile.ZipFile(io.BytesIO(self.objects[archive_url])) as archive:
            self.assertEqual(archive.namelist(), ["пример.txt"])
            self.assertEqual(archive.read("пример.txt"), self.content)

    def test_redelivery_after_database_error_reuses_upload(self):
        self.fail_write = True
        with self.assertRaises(OSError):
            main.handler(self.event, self.context)
        self.fail_write = False
        main.handler(self.event, self.context)
        self.download.assert_called_once()
        self.assertEqual(len(self.objects), 1)
        self.assertEqual(len(self.items), 1)

    def test_failed_download_propagates(self):
        self.download.side_effect = OSError("Source unavailable")
        with self.assertRaises(OSError):
            main.handler(self.event, self.context)
        self.assertFalse(self.items)
        self.assertFalse(self.objects)

    def test_truncated_download_is_rejected(self):
        file = SourceFile(b"short")
        file.getheader = lambda name: "100"
        self.download.side_effect = lambda url: file
        with self.assertRaises(OSError):
            main.handler(self.event, self.context)
        self.assertFalse(self.objects)

    def test_path_in_zip_rejected(self):
        self.message["body"] = json.dumps({"name": "../bad", "url": "https://example.com"})
        with self.assertRaises(ValueError):
            main.handler(self.event, self.context)
        self.download.assert_not_called()

    def test_local_targets_rejected(self):
        for url in ("http://127.0.0.1/test", "http://[::1]/", "file:///tmp/example"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                with source.source_response(url):
                    self.fail("Unexpected source connection")

    def test_redirect_and_http_download(self):
        def connect(host, port):
            self.assertEqual(port, 80)
            client, server = socket.socketpair()
            self.addCleanup(server.close)
            if host == "first.example":
                server.sendall(b"HTTP/1.1 302 Found\r\nLocation: http://second.example/file\r\n\r\n")
            else:
                self.assertEqual(host, "second.example")
                server.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhello")
            return client

        with patch.object(source, "connect_public", side_effect=connect) as mocked:
            with source.source_response("http://first.example/start") as response:
                self.assertEqual(response.read(), b"hello")
            self.assertEqual(mocked.call_count, 2)

    def test_distinct_messages_have_distinct_keys(self):
        other = dict(self.message, message_id="another-message")
        self.assertNotEqual(main.archive_key(self.message), main.archive_key(other))
