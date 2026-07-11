import asyncio
import dataclasses
import unittest
from types import SimpleNamespace

from application.services.platform_attachment_analyzer import (
    AttachmentAnalysisBatchError,
    AttachmentStatusUpdate,
    PlatformAttachmentAnalyzer,
)
from infrastructure.attachments.parser_protocol import (
    AttachmentParserError,
    ParsedAttachment,
    ParsedAttachmentPage,
)


def _downloaded(index: int):
    return SimpleNamespace(
        attachment_id=f"attachment-{index}",
        analysis_attempt_id=f"attempt-{index}",
        file_type="image",
        mime_type="image/png",
    )


def _parsed(index: int):
    return ParsedAttachment(
        attachment_id=f"attachment-{index}",
        file_type="image",
        mime_type="image/png",
        pages=(
            ParsedAttachmentPage(
                page_number=1,
                mime_type="image/png",
                sha256="a" * 64,
                content=b"image",
            ),
        ),
    )


class _ConcurrencySandbox:
    def __init__(self):
        self.active = 0
        self.peak = 0

    async def parse(self, downloaded):
        self.active += 1
        self.peak = max(self.peak, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        return _parsed(int(downloaded.attachment_id.rsplit("-", 1)[1]))


class PlatformAttachmentAnalyzerTest(unittest.IsolatedAsyncioTestCase):
    async def test_concurrency_peak_is_two_and_results_keep_input_order(self):
        sandbox = _ConcurrencySandbox()

        async def analyze(parsed):
            await asyncio.sleep(0)
            return f"analysis:{parsed.attachment_id}"

        statuses = []

        async def on_status(update):
            statuses.append(update)

        analyzer = PlatformAttachmentAnalyzer(
            sandbox,
            analyze_parsed=analyze,
            timeout_seconds=1,
            heartbeat_interval=30,
        )
        results = await analyzer.analyze_all(
            [_downloaded(index) for index in range(4)], on_status
        )

        self.assertEqual(sandbox.peak, 2)
        self.assertEqual(
            [result.attachment_id for result in results],
            [f"attachment-{index}" for index in range(4)],
        )
        self.assertTrue(all(result.untrusted_text.startswith("analysis:") for result in results))
        self.assertEqual(
            {field.name for field in dataclasses.fields(AttachmentStatusUpdate)},
            {"attachment_id", "status", "error_code"},
        )
        self.assertFalse(hasattr(statuses[0], "sequence"))

    async def test_processing_heartbeat_uses_injected_sleep_and_clock(self):
        now = [0.0]
        heartbeat_seen = asyncio.Event()

        async def sleep(delay):
            self.assertEqual(delay, 30)
            now[0] += delay
            await asyncio.sleep(0)

        class WaitingSandbox:
            async def parse(self, _downloaded_item):
                await asyncio.wait_for(heartbeat_seen.wait(), timeout=1)
                return _parsed(1)

        statuses = []

        async def on_status(update):
            statuses.append(update)
            processing_count = sum(
                item.status == "processing" for item in statuses
            )
            if processing_count >= 2:
                heartbeat_seen.set()

        async def analyze(_parsed_item):
            return "ready"

        analyzer = PlatformAttachmentAnalyzer(
            WaitingSandbox(),
            analyze_parsed=analyze,
            timeout_seconds=1,
            heartbeat_interval=30,
            sleep=sleep,
            clock=lambda: now[0],
        )
        await analyzer.analyze_all([_downloaded(1)], on_status)

        self.assertGreaterEqual(
            sum(update.status == "processing" for update in statuses), 2
        )
        self.assertEqual(statuses[-1].status, "ready")

    async def test_timeout_reports_safe_code_and_raises_aggregate_error(self):
        class SlowSandbox:
            async def parse(self, _downloaded_item):
                await asyncio.sleep(60)

        statuses = []

        async def on_status(update):
            statuses.append(update)

        analyzer = PlatformAttachmentAnalyzer(
            SlowSandbox(),
            analyze_parsed=lambda _parsed_item: None,
            timeout_seconds=0.01,
        )

        with self.assertRaisesRegex(
            AttachmentAnalysisBatchError, "ATTACHMENT_ANALYSIS_FAILED"
        ) as raised:
            await analyzer.analyze_all([_downloaded(1)], on_status)

        self.assertEqual(raised.exception.error_code, "ATTACHMENT_ANALYSIS_FAILED")
        self.assertEqual(statuses[-1].status, "failed")
        self.assertEqual(statuses[-1].error_code, "ATTACHMENT_ANALYSIS_TIMEOUT")

    async def test_worker_failure_is_aggregated_without_leaking_details(self):
        secret = "patient-secret-path"

        class FailingSandbox:
            async def parse(self, _downloaded_item):
                raise AttachmentParserError("PDF_ENCRYPTED", detail=secret)

        statuses = []

        async def on_status(update):
            statuses.append(update)

        analyzer = PlatformAttachmentAnalyzer(
            FailingSandbox(),
            analyze_parsed=lambda _parsed_item: None,
            timeout_seconds=1,
        )

        with self.assertRaises(AttachmentAnalysisBatchError) as raised:
            await analyzer.analyze_all([_downloaded(1)], on_status)

        self.assertNotIn(secret, str(raised.exception))
        self.assertEqual(statuses[-1].error_code, "PDF_ENCRYPTED")
        self.assertNotIn(secret, repr(statuses[-1]))


if __name__ == "__main__":
    unittest.main()
