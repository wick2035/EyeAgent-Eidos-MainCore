import asyncio
import hashlib
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from application.services.research_document_ingestion_service import (
    IMAGE_EXTRACTOR_VERSION,
    PDF_EXTRACTOR_VERSION,
    ResearchDocumentIngestionError,
    ResearchDocumentIngestionService,
)
from application.services.research_document_segmenter import SEGMENT_SCHEMA_VERSION
from domain.models.research_document import (
    ExtractedResearchPage,
    IngestionIdentity,
    ResearchDocumentClaimResult,
    ResearchDocumentIngestionEntity,
    build_research_document_ingestion_id,
)
from infrastructure.attachments.secure_downloader import DownloadedAttachment
from infrastructure.repositories.research_document_repository_impl import (
    ResearchDocumentFencingError,
)


def _downloaded(
    root,
    attachment_id="attachment-1",
    *,
    file_type="image",
    mime_type="image/png",
    content=b"safe-content",
    size_bytes=None,
    page_count=None,
    document_version=1,
):
    path = Path(root) / f"{attachment_id}.bin"
    path.write_bytes(content)
    path.chmod(0o600)
    return DownloadedAttachment(
        attachment_id=attachment_id,
        analysis_attempt_id=f"attempt-{attachment_id}",
        file_type=file_type,
        filename=path.name,
        mime_type=mime_type,
        size_bytes=len(content) if size_bytes is None else size_bytes,
        content_sha256=hashlib.sha256(content).hexdigest(),
        page_count=page_count,
        path=path,
        document_version=document_version,
    )


def _entity(identity, *, status="processing", attempt=1, lease=None):
    now = datetime.now()
    return ResearchDocumentIngestionEntity(
        id=build_research_document_ingestion_id(identity),
        **identity.model_dump(),
        status=status,
        attempt_count=attempt,
        lease_expires_at=lease,
        page_count=(1 if status == "ready" else None),
        started_at=now,
        completed_at=(now if status == "ready" else None),
        create_time=now,
        update_time=now,
    )


class FakeRepository:
    def __init__(self):
        self.records = {}
        self.segments = {}
        self.claim_calls = []
        self.renew_calls = []
        self.complete_calls = []
        self.fail_calls = []
        self.renew_results = []
        self.complete_result = True
        self.complete_error = None
        self.fail_result = True

    def claim(self, identity, now, lease_until):
        self.claim_calls.append((identity, now, lease_until))
        entity = self.records.get(identity)
        if entity is None:
            entity = _entity(identity, lease=lease_until)
            self.records[identity] = entity
            return ResearchDocumentClaimResult(entity, True)
        if entity.status == "ready":
            return ResearchDocumentClaimResult(entity, False)
        if (
            entity.status == "processing"
            and entity.lease_expires_at is not None
            and entity.lease_expires_at > now
        ):
            return ResearchDocumentClaimResult(entity, False)
        entity = entity.model_copy(
            update={
                "status": "processing",
                "attempt_count": entity.attempt_count + 1,
                "lease_expires_at": lease_until,
                "error_code": None,
            }
        )
        self.records[identity] = entity
        return ResearchDocumentClaimResult(entity, True)

    def renew_lease(self, ingestion_id, attempt_count, lease_until):
        self.renew_calls.append((ingestion_id, attempt_count, lease_until))
        return self.renew_results.pop(0) if self.renew_results else True

    def complete(self, ingestion_id, attempt_count, segments):
        self.complete_calls.append((ingestion_id, attempt_count, segments))
        if self.complete_error is not None:
            raise self.complete_error
        if not self.complete_result:
            return False
        identity = next(
            key for key, value in self.records.items() if value.id == ingestion_id
        )
        current = self.records[identity]
        self.segments[ingestion_id] = list(segments)
        self.records[identity] = current.model_copy(
            update={
                "status": "ready",
                "lease_expires_at": None,
                "page_count": max((item.page_end or 0 for item in segments), default=0),
                "completed_at": datetime.now(),
            }
        )
        return True

    def fail(self, ingestion_id, attempt_count, error_code):
        self.fail_calls.append((ingestion_id, attempt_count, error_code))
        return self.fail_result

    def get_ready(self, identity):
        entity = self.records.get(identity)
        return entity if entity is not None and entity.status == "ready" else None


class FakeProcessor:
    def __init__(self, *, block=False, fail_ids=()):
        self.calls = []
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = set()
        self.block = block
        self.fail_ids = set(fail_ids)

    async def process(self, item):
        self.calls.append(item.attachment_id)
        self.started.set()
        try:
            if self.block:
                await self.release.wait()
            if item.attachment_id in self.fail_ids:
                raise RuntimeError("raw processor detail")
            return [
                ExtractedResearchPage(
                    page_number=1,
                    text=f"科研正文-{item.attachment_id}",
                    extraction_method=(
                        "digital_text" if item.file_type == "pdf" else "vision"
                    ),
                )
            ]
        except asyncio.CancelledError:
            self.cancelled.add(item.attachment_id)
            raise


class ResearchDocumentIngestionServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = FakeRepository()
        self.processor = FakeProcessor()

    def tearDown(self):
        self.temp.cleanup()

    def _service(self, **kwargs):
        return ResearchDocumentIngestionService(
            repository=self.repo,
            processor=self.processor,
            poll_interval_seconds=0.001,
            renew_interval_seconds=0.01,
            **kwargs,
        )

    def test_legacy_deadline_code_maps_to_stable_ingestion_timeout(self):
        error = ResearchDocumentIngestionError(
            "RESEARCH_DOCUMENT_DEADLINE_EXCEEDED"
        )

        self.assertEqual(
            error.error_code,
            "RESEARCH_DOCUMENT_INGESTION_TIMEOUT",
        )
        self.assertEqual(str(error), "RESEARCH_DOCUMENT_INGESTION_TIMEOUT")

    async def test_authoritative_metadata_limits_cover_4_40_100_120(self):
        files = [
            _downloaded(
                self.temp.name,
                f"image-{index}",
                size_bytes=10 * 1024 * 1024,
            )
            for index in range(4)
        ]
        service = self._service(file_validator=lambda _: None)
        result = await service.ingest("doctor-1", files)
        self.assertEqual(len(result.entities), 4)

        page_101 = _downloaded(
            self.temp.name,
            "page-101",
            file_type="pdf",
            mime_type="application/pdf",
            page_count=100,
        )
        object.__setattr__(page_101, "page_count", 101)
        invalid_batches = [
            files + [_downloaded(self.temp.name, "image-5")],
            [
                _downloaded(
                    self.temp.name,
                    "too-large-image",
                    size_bytes=10 * 1024 * 1024 + 1,
                )
            ],
            [
                _downloaded(
                    self.temp.name,
                    "too-large-pdf",
                    file_type="pdf",
                    mime_type="application/pdf",
                    size_bytes=30 * 1024 * 1024 + 1,
                    page_count=1,
                )
            ],
            [page_101],
            [
                _downloaded(
                    self.temp.name,
                    "pages-100",
                    file_type="pdf",
                    mime_type="application/pdf",
                    page_count=100,
                ),
                _downloaded(
                    self.temp.name,
                    "pages-21",
                    file_type="pdf",
                    mime_type="application/pdf",
                    page_count=21,
                ),
            ],
        ]
        for batch in invalid_batches:
            with self.subTest(batch=[item.attachment_id for item in batch]):
                with self.assertRaises(ResearchDocumentIngestionError):
                    await service.ingest("doctor-1", batch)

        over_total = [
            _downloaded(
                self.temp.name,
                "total-pdf",
                file_type="pdf",
                mime_type="application/pdf",
                size_bytes=20 * 1024 * 1024,
                page_count=1,
            ),
            _downloaded(self.temp.name, "total-image-1", size_bytes=10 * 1024 * 1024),
            _downloaded(self.temp.name, "total-image-2", size_bytes=10 * 1024 * 1024),
            _downloaded(self.temp.name, "total-image-3", size_bytes=1),
        ]
        with self.assertRaises(ResearchDocumentIngestionError):
            await service.ingest("doctor-1", over_total)

    async def test_exact_pdf_size_page_and_total_page_boundaries_are_accepted(self):
        class PageCountProcessor(FakeProcessor):
            async def process(inner_self, item):
                inner_self.calls.append(item.attachment_id)
                return [
                    ExtractedResearchPage(
                        page_number=page,
                        text=f"第{page}页",
                        extraction_method="digital_text",
                    )
                    for page in range(1, item.page_count + 1)
                ]

        self.processor = PageCountProcessor()
        files = [
            _downloaded(
                self.temp.name,
                "pdf-100",
                file_type="pdf",
                mime_type="application/pdf",
                size_bytes=30 * 1024 * 1024,
                page_count=100,
            ),
            _downloaded(
                self.temp.name,
                "pdf-20",
                file_type="pdf",
                mime_type="application/pdf",
                page_count=20,
            ),
        ]

        result = await self._service(file_validator=lambda _: None).ingest(
            "doctor-1", files
        )

        self.assertEqual([item.page_count for item in result.entities], [100, 20])
        self.assertEqual(self.processor.calls, ["pdf-100", "pdf-20"])

    async def test_rejects_duplicate_id_and_real_path_size_hash_or_privacy_mismatch(self):
        item = _downloaded(self.temp.name)
        with self.assertRaises(ResearchDocumentIngestionError):
            await self._service().ingest("doctor-1", [item, item])

        mutations = ["size", "hash", "privacy", "symlink"]
        for mutation in mutations:
            item = _downloaded(self.temp.name, f"bad-{mutation}")
            if mutation == "size":
                object.__setattr__(item, "size_bytes", item.size_bytes + 1)
            elif mutation == "hash":
                object.__setattr__(item, "content_sha256", "0" * 64)
            elif mutation == "privacy":
                item.path.chmod(0o644)
            else:
                target = item.path
                link = target.with_suffix(".link")
                link.symlink_to(target)
                object.__setattr__(item, "path", link)
            with self.subTest(mutation=mutation):
                with self.assertRaises(ResearchDocumentIngestionError):
                    await self._service().ingest("doctor-1", [item])

        valid = _downloaded(self.temp.name, "batch-valid")
        invalid = _downloaded(self.temp.name, "batch-invalid")
        invalid.path.chmod(0o644)
        self.repo.claim_calls.clear()
        with self.assertRaises(ResearchDocumentIngestionError):
            await self._service().ingest("doctor-1", [valid, invalid])
        self.assertEqual(self.repo.claim_calls, [])

    async def test_owner_completes_and_ready_observer_reuses_in_input_order(self):
        first = _downloaded(self.temp.name, "first")
        second = _downloaded(self.temp.name, "second")

        initial = await self._service().ingest("doctor-1", [first, second])
        reused = await self._service().ingest("doctor-1", [second, first])

        self.assertEqual(self.processor.calls, ["first", "second"])
        self.assertEqual(
            reused.ingestion_ids,
            (initial.ingestion_ids[1], initial.ingestion_ids[0]),
        )
        self.assertTrue(all(entity.status == "ready" for entity in reused.entities))
        identities = [call[0] for call in self.repo.claim_calls]
        self.assertEqual(identities[0].extractor_version, IMAGE_EXTRACTOR_VERSION)
        self.assertEqual(identities[0].segment_schema_version, SEGMENT_SCHEMA_VERSION)

    async def test_ready_observer_and_claim_failures_are_revalidated_to_stable_error(self):
        item = _downloaded(self.temp.name, "bad-ready")
        identity = IngestionIdentity(
            doctor_id="doctor-1",
            attachment_id=item.attachment_id,
            document_version=1,
            content_sha256=item.content_sha256,
            processor_type="image_vision_v1",
            extractor_version=IMAGE_EXTRACTOR_VERSION,
            segment_schema_version=SEGMENT_SCHEMA_VERSION,
        )
        ready = _entity(identity, status="ready")
        ready.page_count = 9
        self.repo.records[identity] = ready
        with self.assertRaises(ResearchDocumentIngestionError):
            await self._service().ingest("doctor-1", [item])
        self.assertEqual(self.processor.calls, [])
        self.assertEqual(self.repo.fail_calls, [])

        class BrokenClaimRepository(FakeRepository):
            def claim(inner_self, identity, now, lease_until):
                raise RuntimeError("database secret")

        self.repo = BrokenClaimRepository()
        with self.assertRaises(ResearchDocumentIngestionError) as raised:
            await self._service().ingest("doctor-1", [item])
        self.assertEqual(
            raised.exception.error_code,
            "RESEARCH_DOCUMENT_INGESTION_FAILED",
        )
        self.assertNotIn("secret", repr(raised.exception))

    async def test_malformed_acquired_claim_never_processes_completes_or_fails(self):
        item = _downloaded(self.temp.name, "malformed-owner")
        mutations = {
            "zero_attempt": {"attempt_count": 0},
            "missing_lease": {"lease_expires_at": None},
            "expired_lease": {"lease_expires_at": datetime(2000, 1, 1)},
            "missing_started": {"started_at": None},
            "unexpected_page_count": {"page_count": 1},
            "unexpected_error": {"error_code": "RESEARCH_DOCUMENT_FAILED"},
            "unexpected_completed": {"completed_at": datetime.now()},
        }

        for name, updates in mutations.items():
            with self.subTest(name=name):
                processor = FakeProcessor()

                class MalformedClaimRepository(FakeRepository):
                    def claim(inner_self, identity, now, lease_until):
                        inner_self.claim_calls.append((identity, now, lease_until))
                        entity = _entity(identity, lease=lease_until)
                        for field, value in updates.items():
                            setattr(entity, field, value)
                        return ResearchDocumentClaimResult(entity, True)

                repository = MalformedClaimRepository()
                service = ResearchDocumentIngestionService(
                    repository=repository,
                    processor=processor,
                    poll_interval_seconds=0.001,
                    renew_interval_seconds=0.01,
                )

                with self.assertRaises(ResearchDocumentIngestionError) as raised:
                    await service.ingest("doctor-1", [item])

                self.assertEqual(
                    raised.exception.error_code,
                    "RESEARCH_DOCUMENT_INGESTION_FAILED",
                )
                self.assertEqual(processor.calls, [])
                self.assertEqual(repository.complete_calls, [])
                self.assertEqual(repository.fail_calls, [])

    async def test_malformed_processing_observer_and_ready_started_at_fail_closed(self):
        item = _downloaded(self.temp.name, "malformed-observer")
        identity = IngestionIdentity(
            doctor_id="doctor-1",
            attachment_id=item.attachment_id,
            document_version=1,
            content_sha256=item.content_sha256,
            processor_type="image_vision_v1",
            extractor_version=IMAGE_EXTRACTOR_VERSION,
            segment_schema_version=SEGMENT_SCHEMA_VERSION,
        )
        malformed_processing = _entity(
            identity,
            lease=datetime.now() + timedelta(minutes=1),
        )
        malformed_processing.started_at = None
        self.repo.records[identity] = malformed_processing

        with self.assertRaises(ResearchDocumentIngestionError) as observer_error:
            await self._service().ingest(
                "doctor-1",
                [item],
                deadline=time.monotonic() + 0.02,
            )

        self.assertEqual(
            observer_error.exception.error_code,
            "RESEARCH_DOCUMENT_INGESTION_FAILED",
        )
        self.assertEqual(self.processor.calls, [])
        self.assertEqual(self.repo.fail_calls, [])

        ready = _entity(identity, status="ready")
        ready.page_count = 0
        ready.started_at = None
        self.repo.records[identity] = ready
        with self.assertRaises(ResearchDocumentIngestionError) as ready_error:
            await self._service().ingest("doctor-1", [item])
        self.assertEqual(
            ready_error.exception.error_code,
            "RESEARCH_DOCUMENT_FENCING_FAILED",
        )
        self.assertEqual(self.processor.calls, [])
        self.assertEqual(self.repo.fail_calls, [])

    async def test_attachment_id_boundary_and_identity_errors_are_stable(self):
        valid = _downloaded(self.temp.name, "a" * 64)
        result = await self._service().ingest("doctor-1", [valid])
        self.assertEqual(len(result.entities), 1)

        self.repo = FakeRepository()
        self.processor = FakeProcessor()
        invalid = _downloaded(self.temp.name, "b" * 65)
        with self.assertRaises(ResearchDocumentIngestionError) as raised:
            await self._service().ingest("doctor-1", [invalid])

        self.assertEqual(
            raised.exception.error_code,
            "RESEARCH_DOCUMENT_INPUT_INVALID",
        )
        self.assertEqual(self.repo.claim_calls, [])
        self.assertEqual(self.processor.calls, [])

    async def test_pre_await_deadline_closes_coroutine_and_cancels_future(self):
        service = self._service()

        async def pending_work():
            await asyncio.sleep(0)

        coroutine = pending_work()
        try:
            with self.assertRaises(ResearchDocumentIngestionError) as raised:
                await service._await_deadline(
                    coroutine,
                    time.monotonic() - 1,
                )
            self.assertEqual(
                raised.exception.error_code,
                "RESEARCH_DOCUMENT_INGESTION_TIMEOUT",
            )
            self.assertIsNone(coroutine.cr_frame)
        finally:
            coroutine.close()

        future = asyncio.get_running_loop().create_future()
        try:
            with self.assertRaises(ResearchDocumentIngestionError) as raised:
                await service._await_deadline(
                    future,
                    time.monotonic() - 1,
                )
            self.assertEqual(
                raised.exception.error_code,
                "RESEARCH_DOCUMENT_INGESTION_TIMEOUT",
            )
            self.assertTrue(future.cancelled())
        finally:
            if not future.done():
                future.cancel()

    async def test_pdf_identity_uses_fixed_versions_and_failed_record_is_taken_over(self):
        item = _downloaded(
            self.temp.name,
            "paper",
            file_type="pdf",
            mime_type="application/pdf",
            page_count=1,
        )
        identity = IngestionIdentity(
            doctor_id="doctor-1",
            attachment_id=item.attachment_id,
            document_version=1,
            content_sha256=item.content_sha256,
            processor_type="pdf_hybrid_v1",
            extractor_version=PDF_EXTRACTOR_VERSION,
            segment_schema_version=SEGMENT_SCHEMA_VERSION,
        )
        self.repo.records[identity] = _entity(identity, status="failed", attempt=2)

        result = await self._service().ingest("doctor-1", [item])

        self.assertEqual(result.entities[0].attempt_count, 3)
        self.assertEqual(self.processor.calls, ["paper"])

    async def test_expired_processing_is_taken_over_with_default_90_second_lease(self):
        item = _downloaded(self.temp.name, "expired")
        identity = IngestionIdentity(
            doctor_id="doctor-1",
            attachment_id=item.attachment_id,
            document_version=1,
            content_sha256=item.content_sha256,
            processor_type="image_vision_v1",
            extractor_version=IMAGE_EXTRACTOR_VERSION,
            segment_schema_version=SEGMENT_SCHEMA_VERSION,
        )
        self.repo.records[identity] = _entity(
            identity,
            attempt=2,
            lease=datetime.now() - timedelta(seconds=1),
        )

        result = await self._service().ingest("doctor-1", [item])

        self.assertEqual(result.entities[0].attempt_count, 3)
        claim_now, lease_until = self.repo.claim_calls[0][1:]
        self.assertEqual((lease_until - claim_now).total_seconds(), 90)

    async def test_observer_cancel_or_deadline_never_fails_external_attempt(self):
        for mode in ("cancel", "deadline"):
            with self.subTest(mode=mode):
                self.repo = FakeRepository()
                self.processor = FakeProcessor()
                item = _downloaded(self.temp.name, f"observer-{mode}")
                identity = IngestionIdentity(
                    doctor_id="doctor-1",
                    attachment_id=item.attachment_id,
                    document_version=1,
                    content_sha256=item.content_sha256,
                    processor_type="image_vision_v1",
                    extractor_version=IMAGE_EXTRACTOR_VERSION,
                    segment_schema_version=SEGMENT_SCHEMA_VERSION,
                )
                self.repo.records[identity] = _entity(
                    identity,
                    lease=datetime.now() + timedelta(minutes=1),
                )
                task = asyncio.create_task(
                    self._service().ingest(
                        "doctor-1",
                        [item],
                        deadline=(time.monotonic() + 0.02 if mode == "deadline" else None),
                    )
                )
                await asyncio.sleep(0.005)
                if mode == "cancel":
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                else:
                    with self.assertRaises(ResearchDocumentIngestionError):
                        await task
                self.assertEqual(self.repo.fail_calls, [])
                self.assertEqual(self.processor.calls, [])

    async def test_two_concurrent_ingests_have_one_processor_owner(self):
        item = _downloaded(self.temp.name, "shared")
        self.processor.block = True
        service = self._service()

        first = asyncio.create_task(service.ingest("doctor-1", [item]))
        await asyncio.wait_for(self.processor.started.wait(), timeout=1)
        second = asyncio.create_task(service.ingest("doctor-1", [item]))
        await asyncio.sleep(0.01)
        self.processor.release.set()
        first_result, second_result = await asyncio.gather(first, second)

        self.assertEqual(self.processor.calls, ["shared"])
        self.assertEqual(first_result.ingestion_ids, second_result.ingestion_ids)

    async def test_lease_loss_cancels_work_and_never_completes(self):
        item = _downloaded(self.temp.name, "lease-loss")
        self.processor.block = True
        self.repo.renew_results = [False]

        with self.assertRaises(ResearchDocumentIngestionError) as raised:
            await self._service().ingest("doctor-1", [item])

        self.assertEqual(raised.exception.error_code, "RESEARCH_DOCUMENT_LEASE_LOST")
        self.assertIn("lease-loss", self.processor.cancelled)
        self.assertEqual(self.repo.complete_calls, [])
        self.assertTrue(self.repo.fail_calls)

    async def test_simultaneous_work_completion_and_lease_loss_prefers_loss(self):
        barrier = asyncio.Event()

        class BarrierProcessor(FakeProcessor):
            async def process(inner_self, item):
                inner_self.calls.append(item.attachment_id)
                inner_self.started.set()
                await barrier.wait()
                return [
                    ExtractedResearchPage(
                        page_number=1,
                        text="正文",
                        extraction_method="vision",
                    )
                ]

        async def barrier_sleep(_seconds):
            await barrier.wait()

        item = _downloaded(self.temp.name, "lease-race")
        self.processor = BarrierProcessor()
        self.repo.renew_results = [False]
        service = self._service(sleep=barrier_sleep)
        task = asyncio.create_task(service.ingest("doctor-1", [item]))
        await asyncio.wait_for(self.processor.started.wait(), timeout=1)
        barrier.set()

        with self.assertRaises(ResearchDocumentIngestionError) as raised:
            await task
        self.assertEqual(raised.exception.error_code, "RESEARCH_DOCUMENT_LEASE_LOST")
        self.assertEqual(self.repo.complete_calls, [])

    async def test_caller_cancel_and_deadline_cancel_processor_and_renewer(self):
        for mode in ("cancel", "deadline"):
            with self.subTest(mode=mode):
                self.repo = FakeRepository()
                self.processor = FakeProcessor(block=True)
                item = _downloaded(self.temp.name, f"blocked-{mode}")
                service = self._service()
                task = asyncio.create_task(
                    service.ingest(
                        "doctor-1",
                        [item],
                        deadline=(time.monotonic() + 0.02 if mode == "deadline" else None),
                    )
                )
                await asyncio.wait_for(self.processor.started.wait(), timeout=1)
                if mode == "cancel":
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                else:
                    with self.assertRaises(ResearchDocumentIngestionError) as raised:
                        await task
                    self.assertEqual(
                        raised.exception.error_code,
                        "RESEARCH_DOCUMENT_INGESTION_TIMEOUT",
                    )
                self.assertIn(item.attachment_id, self.processor.cancelled)
                self.assertEqual(self.repo.complete_calls, [])

    async def test_complete_false_and_fail_cas_loss_are_stable_fail_closed(self):
        item = _downloaded(self.temp.name, "fenced")
        self.repo.complete_result = False
        self.repo.fail_result = False

        with self.assertRaises(ResearchDocumentIngestionError) as raised:
            await self._service().ingest("doctor-1", [item])

        self.assertEqual(
            raised.exception.error_code,
            "RESEARCH_DOCUMENT_FENCING_FAILED",
        )
        self.assertTrue(self.repo.fail_calls)

    async def test_parser_stable_code_and_complete_exception_are_mapped_safely(self):
        class StableFailureProcessor(FakeProcessor):
            async def process(inner_self, item):
                error = RuntimeError("raw parser detail")
                error.error_code = "RESEARCH_PDF_ENCRYPTED"
                raise error

        item = _downloaded(self.temp.name, "stable-code")
        self.processor = StableFailureProcessor()
        with self.assertRaises(ResearchDocumentIngestionError) as raised:
            await self._service().ingest("doctor-1", [item])
        self.assertEqual(raised.exception.error_code, "RESEARCH_PDF_ENCRYPTED")
        self.assertEqual(self.repo.fail_calls[-1][2], "RESEARCH_PDF_ENCRYPTED")

        self.repo = FakeRepository()
        self.processor = FakeProcessor()
        self.repo.complete_error = ResearchDocumentFencingError("fenced")
        item = _downloaded(self.temp.name, "complete-error")
        with self.assertRaises(ResearchDocumentIngestionError) as raised:
            await self._service().ingest("doctor-1", [item])
        self.assertEqual(
            raised.exception.error_code,
            "RESEARCH_DOCUMENT_FENCING_FAILED",
        )

    async def test_sibling_failure_cancels_remaining_and_returns_no_partial(self):
        good = _downloaded(self.temp.name, "slow-good")
        bad = _downloaded(self.temp.name, "bad")
        self.processor = FakeProcessor(block=True, fail_ids={"bad"})
        service = self._service()
        task = asyncio.create_task(service.ingest("doctor-1", [good, bad]))
        await asyncio.wait_for(self.processor.started.wait(), timeout=1)
        self.processor.release.set()

        with self.assertRaises(ResearchDocumentIngestionError):
            await task
        self.assertFalse(
            all(record.status == "ready" for record in self.repo.records.values())
        )


if __name__ == "__main__":
    unittest.main()
