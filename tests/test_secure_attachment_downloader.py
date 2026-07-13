import hashlib
import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from aiohttp import web

from infrastructure.attachments.config import (
    AttachmentConfigurationError,
    AttachmentDownloadSettings,
)
from infrastructure.attachments.secure_downloader import (
    AttachmentDownloadError,
    SecureAttachmentDownloader,
    _safe_suffix,
)
from presentation.schemas.platform_chat_turn_schemas import (
    InternalAttachmentDescriptor,
)


_PNG = b"\x89PNG\r\n\x1a\n" + b"safe-image"
_MIB = 1024 * 1024
_TXT_LIMIT_BYTES = 512 * 1024
_CSV_LIMIT_BYTES = 10 * 1024 * 1024
_XLSX_LIMIT_BYTES = 10 * 1024 * 1024
_XLSX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def _descriptor(url: str, payload: bytes = _PNG, **overrides):
    values = {
        "attachment_id": "attachment-1",
        "file_type": "image",
        "filename": "fundus.png",
        "mime_type": "image/png",
        "size_bytes": len(payload),
        "page_count": None,
        "content_sha256": hashlib.sha256(payload).hexdigest(),
        "document_version": 1,
        "analysis_attempt_id": "attempt-1",
        "download_url": url,
    }
    values.update(overrides)
    return InternalAttachmentDescriptor(**values)


def _text_descriptor(url: str, payload: bytes, **overrides):
    return _descriptor(
        url,
        payload,
        file_type="text",
        filename="research.txt",
        mime_type="text/plain",
        page_count=None,
        **overrides,
    )


def _csv_descriptor(url: str, payload: bytes, **overrides):
    return _descriptor(
        url,
        payload,
        file_type="csv",
        filename="dataset.csv",
        mime_type="text/csv",
        page_count=None,
        **overrides,
    )


def _xlsx_descriptor(url: str, payload: bytes, **overrides):
    return _descriptor(
        url,
        payload,
        file_type="xlsx",
        filename="dataset.xlsx",
        mime_type=_XLSX_MIME_TYPE,
        page_count=None,
        **overrides,
    )


class SecureAttachmentDownloaderTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._runners = []
        self._temp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self._temp_dir.name)

    async def asyncTearDown(self):
        for runner in reversed(self._runners):
            await runner.cleanup()
        self._temp_dir.cleanup()

    async def _serve(self, handler):
        server = web.Server(handler)
        runner = web.ServerRunner(server)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        self._runners.append(runner)
        port = site._server.sockets[0].getsockname()[1]
        return port

    def _settings(self, port: int, *, allow_http: bool = True):
        return AttachmentDownloadSettings.from_env(
            {
                "PLATFORM_ATTACHMENT_DOWNLOAD_ALLOWLIST_JSON": json.dumps(
                    [["http", "storage.test", port, "127.0.0.1"]]
                ),
                "PLATFORM_ATTACHMENT_ALLOW_HTTP": str(allow_http).lower(),
            }
        )

    def _assert_no_request_directories(self):
        self.assertEqual(list(self.temp_root.iterdir()), [])

    def test_text_plain_uses_txt_suffix(self):
        self.assertEqual(_safe_suffix("text/plain"), ".txt")

    def test_text_csv_uses_csv_suffix(self):
        self.assertEqual(_safe_suffix("text/csv"), ".csv")

    def test_xlsx_mime_uses_xlsx_suffix(self):
        self.assertEqual(_safe_suffix(_XLSX_MIME_TYPE), ".xlsx")

    async def test_valid_csv_requires_exact_mime_and_skips_binary_magic(self):
        payload = b"Name,Value\nA,1"

        async def handler(_request):
            return web.Response(body=payload, content_type="text/csv")

        port = await self._serve(handler)
        downloader = SecureAttachmentDownloader(
            self._settings(port),
            temp_root=self.temp_root,
        )
        descriptor = _csv_descriptor(
            f"http://storage.test:{port}/dataset.csv",
            payload,
        )

        with patch(
            "infrastructure.attachments.secure_downloader._matches_magic"
        ) as matches_magic:
            async with downloader.download_all(
                [descriptor],
                "request-valid-csv",
            ) as items:
                self.assertEqual(items[0].file_type, "csv")
                self.assertEqual(items[0].mime_type, "text/csv")
                self.assertIsNone(items[0].page_count)
                self.assertEqual(items[0].path.suffix, ".csv")
                self.assertEqual(items[0].path.read_bytes(), payload)

        matches_magic.assert_not_called()
        self._assert_no_request_directories()

    async def test_csv_descriptor_rejects_mime_page_and_size_before_network(self):
        settings = AttachmentDownloadSettings.from_env(
            {
                "PLATFORM_ATTACHMENT_DOWNLOAD_ALLOWLIST_JSON": json.dumps(
                    [["https", "storage.test", 443, "192.0.2.10"]]
                )
            }
        )
        downloader = SecureAttachmentDownloader(
            settings,
            temp_root=self.temp_root,
        )
        base = _csv_descriptor(
            "https://storage.test/dataset.csv",
            b"A\n1",
        ).model_dump()
        cases = (
            ({**base, "mime_type": "text/plain"}, "ATTACHMENT_DESCRIPTOR_INVALID"),
            ({**base, "page_count": 1}, "ATTACHMENT_DESCRIPTOR_INVALID"),
            (
                {**base, "size_bytes": _CSV_LIMIT_BYTES + 1},
                "RESEARCH_CSV_SIZE_LIMIT",
            ),
        )

        for descriptor, error_code in cases:
            with self.subTest(error_code=error_code):
                with self.assertRaisesRegex(AttachmentDownloadError, error_code):
                    async with downloader.download_all(
                        [descriptor],
                        f"request-{error_code}",
                    ):
                        self.fail("invalid CSV must fail before networking")
                self._assert_no_request_directories()

    async def test_csv_stream_returns_size_limit_after_ten_mib(self):
        payload = b"a" * (_CSV_LIMIT_BYTES + 1)

        async def handler(_request):
            return web.Response(body=payload, content_type="text/csv")

        port = await self._serve(handler)
        downloader = SecureAttachmentDownloader(
            self._settings(port),
            temp_root=self.temp_root,
        )
        descriptor = _csv_descriptor(
            f"http://storage.test:{port}/oversized.csv",
            b"a" * _CSV_LIMIT_BYTES,
        )

        with self.assertRaises(AttachmentDownloadError) as captured:
            async with downloader.download_all(
                [descriptor],
                "request-csv-stream-limit",
            ):
                self.fail("CSV stream overflow must fail before yielding")

        self.assertEqual(captured.exception.error_code, "RESEARCH_CSV_SIZE_LIMIT")
        self.assertEqual(captured.exception.bytes_received, len(payload))
        self._assert_no_request_directories()

    async def test_valid_xlsx_requires_exact_descriptor_and_zip_magic(self):
        payload = b"PK\x03\x04safe-xlsx"

        async def handler(_request):
            return web.Response(body=payload, content_type=_XLSX_MIME_TYPE)

        port = await self._serve(handler)
        downloader = SecureAttachmentDownloader(
            self._settings(port),
            temp_root=self.temp_root,
        )
        descriptor = _xlsx_descriptor(
            f"http://storage.test:{port}/dataset.xlsx",
            payload,
        ).model_dump()
        descriptor["filename"] = "DATASET.XLSX"

        async with downloader.download_all(
            [descriptor],
            "request-valid-xlsx",
        ) as items:
            self.assertEqual(items[0].file_type, "xlsx")
            self.assertEqual(items[0].mime_type, _XLSX_MIME_TYPE)
            self.assertIsNone(items[0].page_count)
            self.assertEqual(items[0].path.suffix, ".xlsx")
            self.assertEqual(items[0].path.read_bytes(), payload)

        self._assert_no_request_directories()

    async def test_xlsx_descriptor_rejects_mime_page_and_size_before_network(self):
        settings = AttachmentDownloadSettings.from_env(
            {
                "PLATFORM_ATTACHMENT_DOWNLOAD_ALLOWLIST_JSON": json.dumps(
                    [["https", "storage.test", 443, "192.0.2.10"]]
                )
            }
        )
        downloader = SecureAttachmentDownloader(settings, temp_root=self.temp_root)
        base = _xlsx_descriptor(
            "https://storage.test/dataset.xlsx",
            b"PK\x03\x04xlsx",
        ).model_dump()
        cases = (
            ({**base, "mime_type": "application/zip"}, "ATTACHMENT_DESCRIPTOR_INVALID"),
            ({**base, "page_count": 1}, "ATTACHMENT_DESCRIPTOR_INVALID"),
            ({**base, "filename": "dataset.csv"}, "ATTACHMENT_DESCRIPTOR_INVALID"),
            (
                {**base, "filename": "nested/dataset.xlsx"},
                "ATTACHMENT_DESCRIPTOR_INVALID",
            ),
            (
                {**base, "filename": r"nested\dataset.xlsx"},
                "ATTACHMENT_DESCRIPTOR_INVALID",
            ),
            (
                {**base, "size_bytes": _XLSX_LIMIT_BYTES + 1},
                "RESEARCH_XLSX_SIZE_LIMIT",
            ),
        )

        for descriptor, error_code in cases:
            with self.subTest(error_code=error_code):
                with self.assertRaisesRegex(AttachmentDownloadError, error_code):
                    async with downloader.download_all(
                        [descriptor],
                        f"request-{error_code}",
                    ):
                        self.fail("invalid XLSX must fail before networking")
                self._assert_no_request_directories()

    async def test_xlsx_stream_returns_size_limit_after_ten_mib(self):
        payload = b"PK\x03\x04" + b"a" * (_XLSX_LIMIT_BYTES - 3)

        async def handler(_request):
            return web.Response(body=payload, content_type=_XLSX_MIME_TYPE)

        port = await self._serve(handler)
        downloader = SecureAttachmentDownloader(
            self._settings(port),
            temp_root=self.temp_root,
        )
        descriptor = _xlsx_descriptor(
            f"http://storage.test:{port}/oversized.xlsx",
            payload[:_XLSX_LIMIT_BYTES],
        )

        with self.assertRaises(AttachmentDownloadError) as captured:
            async with downloader.download_all(
                [descriptor],
                "request-xlsx-stream-limit",
            ):
                self.fail("XLSX stream overflow must fail before yielding")

        self.assertEqual(captured.exception.error_code, "RESEARCH_XLSX_SIZE_LIMIT")
        self.assertEqual(captured.exception.bytes_received, len(payload))
        self._assert_no_request_directories()

    async def test_xlsx_invalid_and_cfb_magic_map_to_stable_codes(self):
        cfb = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1encrypted"
        payloads = {
            "/invalid": b"not-an-xlsx",
            "/encrypted": cfb,
        }

        async def handler(request):
            return web.Response(body=payloads[request.path])

        port = await self._serve(handler)
        downloader = SecureAttachmentDownloader(
            self._settings(port),
            temp_root=self.temp_root,
        )
        cases = (
            ("/invalid", "RESEARCH_XLSX_INVALID"),
            ("/encrypted", "RESEARCH_XLSX_ENCRYPTED"),
        )
        for path, error_code in cases:
            with self.subTest(error_code=error_code):
                descriptor = _xlsx_descriptor(
                    f"http://storage.test:{port}{path}",
                    payloads[path],
                )
                with self.assertRaisesRegex(AttachmentDownloadError, error_code):
                    async with downloader.download_all(
                        [descriptor],
                        f"request-{error_code}",
                    ):
                        self.fail("invalid XLSX must fail before yielding")
                self._assert_no_request_directories()

    async def test_valid_text_preserves_raw_bytes_and_skips_binary_magic(self):
        payload = b"\xef\xbb\xbfCafe\xcc\x81\r\nline\r"

        async def handler(_request):
            return web.Response(body=payload, content_type="text/plain")

        port = await self._serve(handler)
        downloader = SecureAttachmentDownloader(
            self._settings(port), temp_root=self.temp_root
        )
        descriptor = _text_descriptor(
            f"http://storage.test:{port}/research.txt",
            payload,
        )

        with patch(
            "infrastructure.attachments.secure_downloader._matches_magic"
        ) as matches_magic:
            async with downloader.download_all(
                [descriptor],
                "request-valid-text",
            ) as items:
                self.assertEqual(items[0].path.suffix, ".txt")
                self.assertEqual(items[0].path.read_bytes(), payload)
                self.assertEqual(items[0].size_bytes, len(payload))
                self.assertEqual(
                    items[0].content_sha256,
                    hashlib.sha256(payload).hexdigest(),
                )

        matches_magic.assert_not_called()
        self._assert_no_request_directories()

    async def test_text_contract_failures_map_to_stable_download_error_codes(self):
        invalid_payloads = {
            "/encoding": (
                b"unsafe-encoding-sentinel\xff",
                "RESEARCH_TXT_ENCODING_UNSUPPORTED",
            ),
            "/binary": (b"safe\x00text", "RESEARCH_TXT_BINARY"),
            "/blank": (b" \t\r\n", "RESEARCH_TXT_INVALID"),
            "/characters": (
                b"a" * 500_001,
                "RESEARCH_TXT_CONTENT_LIMIT",
            ),
        }

        async def handler(request):
            payload, _error_code = invalid_payloads[request.path]
            return web.Response(body=payload, content_type="text/plain")

        port = await self._serve(handler)
        downloader = SecureAttachmentDownloader(
            self._settings(port), temp_root=self.temp_root
        )

        for path, (payload, expected_code) in invalid_payloads.items():
            with self.subTest(expected_code=expected_code):
                descriptor = _text_descriptor(
                    f"http://storage.test:{port}{path}",
                    payload,
                )
                with self.assertRaises(AttachmentDownloadError) as captured:
                    async with downloader.download_all(
                        [descriptor],
                        f"request-{expected_code}",
                    ):
                        self.fail("invalid TXT must fail before yielding")

                self.assertEqual(captured.exception.error_code, expected_code)
                self.assertEqual(str(captured.exception), expected_code)
                self._assert_no_request_directories()

    async def test_text_stream_returns_size_limit_at_524289th_byte(self):
        payload = b"a" * (_TXT_LIMIT_BYTES + 1)

        async def handler(_request):
            return web.Response(body=payload, content_type="text/plain")

        port = await self._serve(handler)
        downloader = SecureAttachmentDownloader(
            self._settings(port), temp_root=self.temp_root
        )
        descriptor = _text_descriptor(
            f"http://storage.test:{port}/oversized.txt",
            b"a" * _TXT_LIMIT_BYTES,
        )

        with self.assertRaises(AttachmentDownloadError) as captured:
            async with downloader.download_all(
                [descriptor],
                "request-text-stream-limit",
            ):
                self.fail("TXT stream overflow must fail before yielding")

        self.assertEqual(
            captured.exception.error_code,
            "RESEARCH_TXT_SIZE_LIMIT",
        )
        self.assertEqual(captured.exception.bytes_received, len(payload))
        self._assert_no_request_directories()

    async def test_text_failure_does_not_leak_body_decoder_path_or_hash(self):
        body_sentinel = "PRIVATE_RESEARCH_BODY_SENTINEL"
        path_sentinel = "PRIVATE_RESEARCH_PATH_SENTINEL"
        payload = body_sentinel.encode("ascii") + b"\xff"
        content_sha256 = hashlib.sha256(payload).hexdigest()

        async def handler(_request):
            return web.Response(body=payload, content_type="text/plain")

        port = await self._serve(handler)
        downloader = SecureAttachmentDownloader(
            self._settings(port), temp_root=self.temp_root
        )
        descriptor = _text_descriptor(
            f"http://storage.test:{port}/{path_sentinel}",
            payload,
        )

        with self.assertLogs(
            "infrastructure.attachments.secure_downloader",
            level="WARNING",
        ) as captured_logs:
            with self.assertRaises(AttachmentDownloadError) as captured_error:
                async with downloader.download_all(
                    [descriptor],
                    "request-text-private",
                ):
                    self.fail("invalid TXT must fail before yielding")

        rendered_error = repr(captured_error.exception)
        rendered_logs = "\n".join(captured_logs.output)
        self.assertEqual(
            captured_error.exception.error_code,
            "RESEARCH_TXT_ENCODING_UNSUPPORTED",
        )
        for private_value in (
            body_sentinel,
            path_sentinel,
            content_sha256,
            str(self.temp_root),
        ):
            self.assertNotIn(private_value, rendered_error)
            self.assertNotIn(private_value, rendered_logs)
        self.assertNotIn("position", rendered_error.lower())
        self.assertNotIn("position", rendered_logs.lower())
        self.assertIsNone(captured_error.exception.__cause__)
        self.assertIsNone(captured_error.exception.__context__)
        self._assert_no_request_directories()

    async def test_success_uses_pinned_ip_and_private_permissions(self):
        async def handler(_request):
            return web.Response(body=_PNG, content_type="image/png")

        port = await self._serve(handler)
        downloader = SecureAttachmentDownloader(
            self._settings(port), temp_root=self.temp_root
        )
        descriptor = _descriptor(
            f"http://storage.test:{port}/download?token=private",
            document_version=7,
        )

        async with downloader.download_all([descriptor], "request-1") as items:
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].path.read_bytes(), _PNG)
            self.assertEqual(items[0].document_version, 7)
            self.assertEqual(
                stat.S_IMODE(items[0].path.parent.stat().st_mode), 0o700
            )
            self.assertEqual(stat.S_IMODE(items[0].path.stat().st_mode), 0o600)

        self._assert_no_request_directories()

    async def test_downloader_rejects_non_integer_document_version_before_request(self):
        requested = []

        async def handler(_request):
            requested.append(True)
            return web.Response(body=_PNG, content_type="image/png")

        port = await self._serve(handler)
        downloader = SecureAttachmentDownloader(
            self._settings(port), temp_root=self.temp_root
        )
        descriptor = _descriptor(
            f"http://storage.test:{port}/download"
        ).model_dump()
        descriptor["document_version"] = True

        with self.assertRaisesRegex(
            AttachmentDownloadError,
            "ATTACHMENT_DESCRIPTOR_INVALID",
        ):
            async with downloader.download_all(
                [descriptor],
                "request-invalid-document-version",
            ):
                self.fail("invalid document version must fail before yielding")

        self.assertEqual(requested, [])
        self._assert_no_request_directories()

    async def test_multiple_exact_ips_for_one_endpoint_are_all_allowlisted(self):
        async def handler(_request):
            return web.Response(body=_PNG, content_type="image/png")

        port = await self._serve(handler)
        settings = AttachmentDownloadSettings.from_env(
            {
                "PLATFORM_ATTACHMENT_DOWNLOAD_ALLOWLIST_JSON": json.dumps(
                    [
                        ["http", "storage.test", port, "127.0.0.1"],
                        ["http", "storage.test", port, "127.0.0.2"],
                    ]
                ),
                "PLATFORM_ATTACHMENT_ALLOW_HTTP": "true",
            }
        )
        downloader = SecureAttachmentDownloader(settings, temp_root=self.temp_root)
        descriptor = _descriptor(f"http://storage.test:{port}/download")

        async with downloader.download_all([descriptor], "request-multi-ip") as items:
            self.assertEqual(items[0].path.read_bytes(), _PNG)

        self._assert_no_request_directories()

    async def test_resolver_pins_each_descriptor_without_cross_scheme_ip_mixing(self):
        port = 18443
        settings = AttachmentDownloadSettings.from_env(
            {
                "PLATFORM_ATTACHMENT_DOWNLOAD_ALLOWLIST_JSON": json.dumps(
                    [
                        ["http", "storage.test", port, "192.0.2.10"],
                        ["https", "storage.test", port, "192.0.2.20"],
                    ]
                ),
                "PLATFORM_ATTACHMENT_ALLOW_HTTP": "true",
            }
        )
        downloader = SecureAttachmentDownloader(settings, temp_root=self.temp_root)
        descriptors = [
            _descriptor(
                f"http://storage.test:{port}/one",
                attachment_id="attachment-http",
            ),
            _descriptor(
                f"https://storage.test:{port}/two",
                attachment_id="attachment-https",
            ),
        ]
        constructed_endpoint_sets = []

        from infrastructure.attachments import secure_downloader as module

        resolver_type = module._PinnedResolver

        def capture_resolver(endpoints):
            endpoint_tuple = tuple(endpoints)
            constructed_endpoint_sets.append(endpoint_tuple)
            return resolver_type(endpoint_tuple)

        fake_download = AsyncMock(
            side_effect=[
                type("Downloaded", (), {"path": self.temp_root / "one"})(),
                type("Downloaded", (), {"path": self.temp_root / "two"})(),
            ]
        )
        with patch.object(module, "_PinnedResolver", side_effect=capture_resolver), patch.object(
            downloader,
            "_download_one",
            fake_download,
        ):
            async with downloader.download_all(descriptors, "request-schemes"):
                pass

        self.assertEqual(
            [[endpoint.ip for endpoint in endpoints] for endpoints in constructed_endpoint_sets],
            [["192.0.2.10"], ["192.0.2.20"]],
        )

    async def test_redirect_is_rejected_without_following(self):
        followed = []

        async def handler(request):
            if request.path == "/target":
                followed.append(True)
                return web.Response(body=_PNG)
            status = 302 if request.path.endswith("302") else 307
            raise web.HTTPFound(location="/target") if status == 302 else web.HTTPTemporaryRedirect(location="/target")

        port = await self._serve(handler)
        downloader = SecureAttachmentDownloader(
            self._settings(port), temp_root=self.temp_root
        )

        for status in (302, 307):
            with self.subTest(status=status):
                descriptor = _descriptor(
                    f"http://storage.test:{port}/redirect-{status}"
                )
                with self.assertRaisesRegex(
                    AttachmentDownloadError, "ATTACHMENT_REDIRECT_REJECTED"
                ):
                    async with downloader.download_all(
                        [descriptor], f"request-{status}"
                    ):
                        self.fail("redirect must fail before yielding")

        self.assertEqual(followed, [])
        self._assert_no_request_directories()

    async def test_hash_mismatch_removes_request_directory(self):
        async def handler(_request):
            return web.Response(body=_PNG)

        port = await self._serve(handler)
        downloader = SecureAttachmentDownloader(
            self._settings(port), temp_root=self.temp_root
        )
        descriptor = _descriptor(
            f"http://storage.test:{port}/download",
            content_sha256="0" * 64,
        )

        with self.assertRaisesRegex(
            AttachmentDownloadError, "ATTACHMENT_HASH_MISMATCH"
        ):
            async with downloader.download_all([descriptor], "request-hash"):
                self.fail("hash mismatch must fail before yielding")

        self._assert_no_request_directories()

    async def test_stream_limit_does_not_trust_content_length(self):
        payload = _PNG + b"overflow"

        async def handler(request):
            response = web.StreamResponse(status=200)
            response.enable_chunked_encoding()
            await response.prepare(request)
            await response.write(payload)
            await response.write_eof()
            return response

        port = await self._serve(handler)
        downloader = SecureAttachmentDownloader(
            self._settings(port), temp_root=self.temp_root, chunk_size=4
        )
        descriptor = _descriptor(
            f"http://storage.test:{port}/download",
            payload=_PNG,
        )

        with self.assertRaisesRegex(
            AttachmentDownloadError, "ATTACHMENT_STREAM_LIMIT_EXCEEDED"
        ):
            async with downloader.download_all([descriptor], "request-stream"):
                self.fail("stream overflow must fail before yielding")

        self._assert_no_request_directories()

    async def test_declared_content_length_deception_is_rejected(self):
        async def handler(request):
            response = web.StreamResponse(
                status=200,
                headers={"Content-Length": str(len(_PNG))},
            )
            await response.prepare(request)
            await response.write(_PNG[:-2])
            request.transport.close()
            return response

        port = await self._serve(handler)
        downloader = SecureAttachmentDownloader(
            self._settings(port), temp_root=self.temp_root
        )
        descriptor = _descriptor(f"http://storage.test:{port}/download")

        with self.assertRaisesRegex(
            AttachmentDownloadError, "ATTACHMENT_DOWNLOAD_INCOMPLETE"
        ):
            async with downloader.download_all([descriptor], "request-length"):
                self.fail("truncated response must fail before yielding")

        self._assert_no_request_directories()

    async def test_actual_size_and_magic_mismatches_are_rejected(self):
        payloads = {
            "/short": _PNG[:-1],
            "/magic": b"not-a-png-file",
        }

        async def handler(request):
            return web.Response(body=payloads[request.path])

        port = await self._serve(handler)
        downloader = SecureAttachmentDownloader(
            self._settings(port), temp_root=self.temp_root
        )
        cases = (
            (
                _descriptor(
                    f"http://storage.test:{port}/short",
                    size_bytes=len(_PNG),
                ),
                "ATTACHMENT_SIZE_MISMATCH",
            ),
            (
                _descriptor(
                    f"http://storage.test:{port}/magic",
                    payload=payloads["/magic"],
                ),
                "ATTACHMENT_MAGIC_MISMATCH",
            ),
        )

        for descriptor, error_code in cases:
            with self.subTest(error_code=error_code):
                with self.assertRaisesRegex(AttachmentDownloadError, error_code):
                    async with downloader.download_all(
                        [descriptor], f"request-{error_code}"
                    ):
                        self.fail("invalid file must fail before yielding")
                self._assert_no_request_directories()

    async def test_url_components_and_non_allowlisted_endpoints_fail_closed(self):
        async def handler(_request):
            return web.Response(body=_PNG)

        port = await self._serve(handler)
        downloader = SecureAttachmentDownloader(
            self._settings(port), temp_root=self.temp_root
        )
        urls = (
            f"http://user:secret@storage.test:{port}/download",
            f"http://storage.test:{port}/download#fragment",
            f"https://storage.test:{port}/download",
            f"http://other.test:{port}/download",
            f"http://storage.test:{port + 1}/download",
            f"http://127.0.0.2:{port}/download",
        )

        for index, url in enumerate(urls):
            with self.subTest(url_index=index):
                descriptor = _descriptor(url)
                with self.assertRaisesRegex(
                    AttachmentDownloadError, "ATTACHMENT_URL_REJECTED"
                ):
                    async with downloader.download_all(
                        [descriptor], f"request-url-{index}"
                    ):
                        self.fail("unsafe URL must fail before yielding")

        self._assert_no_request_directories()

    async def test_production_http_is_rejected(self):
        port = 18080
        downloader = SecureAttachmentDownloader(
            self._settings(port, allow_http=False), temp_root=self.temp_root
        )
        descriptor = _descriptor(f"http://storage.test:{port}/download")

        with self.assertRaisesRegex(
            AttachmentDownloadError, "ATTACHMENT_URL_REJECTED"
        ):
            async with downloader.download_all([descriptor], "request-prod-http"):
                self.fail("HTTP must be disabled by default")

        self._assert_no_request_directories()

    async def test_total_declared_size_over_forty_mib_is_rejected(self):
        settings = AttachmentDownloadSettings.from_env(
            {
                "PLATFORM_ATTACHMENT_DOWNLOAD_ALLOWLIST_JSON": json.dumps(
                    [["https", "storage.test", 443, "192.0.2.10"]]
                )
            }
        )
        downloader = SecureAttachmentDownloader(settings, temp_root=self.temp_root)
        descriptors = [
            _descriptor(
                "https://storage.test/download",
                attachment_id=f"attachment-{index}",
                file_type="pdf",
                filename=f"report-{index}.pdf",
                mime_type="application/pdf",
                size_bytes=21 * _MIB,
                page_count=1,
            )
            for index in range(2)
        ]

        with self.assertRaisesRegex(
            AttachmentDownloadError, "ATTACHMENT_TOTAL_LIMIT_EXCEEDED"
        ):
            async with downloader.download_all(descriptors, "request-total"):
                self.fail("total limit must fail before networking")

        self._assert_no_request_directories()

    async def test_logs_do_not_include_signed_download_url(self):
        async def handler(_request):
            return web.Response(status=500)

        port = await self._serve(handler)
        downloader = SecureAttachmentDownloader(
            self._settings(port), temp_root=self.temp_root
        )
        secret = "signed-secret-value"
        descriptor = _descriptor(
            f"http://storage.test:{port}/download?token={secret}"
        )

        with self.assertLogs(
            "infrastructure.attachments.secure_downloader", level="WARNING"
        ) as captured:
            with self.assertRaises(AttachmentDownloadError):
                async with downloader.download_all([descriptor], "request-log"):
                    self.fail("server error must fail before yielding")

        self.assertNotIn(secret, "\n".join(captured.output))


class AttachmentDownloadSettingsTest(unittest.TestCase):
    def test_allowlist_is_required_and_rejects_wildcards_or_cidr(self):
        invalid_values = (
            {},
            {"PLATFORM_ATTACHMENT_DOWNLOAD_ALLOWLIST_JSON": "[]"},
            {
                "PLATFORM_ATTACHMENT_DOWNLOAD_ALLOWLIST_JSON": json.dumps(
                    [["https", "*.example", 443, "192.0.2.10"]]
                )
            },
            {
                "PLATFORM_ATTACHMENT_DOWNLOAD_ALLOWLIST_JSON": json.dumps(
                    [["https", "storage.test", 443, "192.0.2.0/24"]]
                )
            },
            {
                "PLATFORM_ATTACHMENT_DOWNLOAD_ALLOWLIST_JSON": json.dumps(
                    [["https", "storage.test", "443", "192.0.2.10"]]
                )
            },
            {
                "PLATFORM_ATTACHMENT_DOWNLOAD_ALLOWLIST_JSON": json.dumps(
                    [["https", "192.0.2.11", 443, "192.0.2.10"]]
                )
            },
        )

        for environ in invalid_values:
            with self.subTest(environ=environ):
                with self.assertRaises(AttachmentConfigurationError):
                    AttachmentDownloadSettings.from_env(environ)

    def test_http_switch_defaults_to_false(self):
        settings = AttachmentDownloadSettings.from_env(
            {
                "PLATFORM_ATTACHMENT_DOWNLOAD_ALLOWLIST_JSON": json.dumps(
                    [["https", "storage.test", 443, "192.0.2.10"]]
                )
            }
        )

        self.assertFalse(settings.allow_http)


if __name__ == "__main__":
    unittest.main()
