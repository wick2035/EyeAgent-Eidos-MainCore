import unittest
from contextlib import contextmanager

import httpx
from fastapi import FastAPI, Request

from domain.security.principal import CurrentPrincipal
from presentation.exception_handlers.platform_validation_handler import (
    install_platform_validation_handler,
)
from presentation.routers.research_document_router import (
    get_research_document_db,
    get_research_document_repository,
    router,
)


DOCTOR_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
HEX_DOCTOR_ID = "0123456789abcdef0123456789abcdef"
OTHER_DOCTOR_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
ATTACHMENT_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"


class FakeDB:
    def __init__(self):
        self.depth = 0
        self.events: list[str] = []

    @contextmanager
    def transaction(self):
        self.events.append("begin")
        self.depth += 1
        try:
            yield
        except Exception:
            self.events.append("rollback")
            raise
        else:
            self.events.append("commit")
        finally:
            self.depth -= 1


class FakeRepository:
    def __init__(self, db: FakeDB):
        self.db = db
        self.calls: list[tuple[str, str, int]] = []
        self.results = [1, 0]

    def purge(self, doctor_id: str, attachment_id: str) -> int:
        self.calls.append((doctor_id, attachment_id, self.db.depth))
        return self.results.pop(0) if self.results else 0


def _principal(
    *,
    subject: str = DOCTOR_ID,
    principal_type: str = "doctor",
    scopes: frozenset[str] = frozenset({"ai:research"}),
) -> CurrentPrincipal:
    return CurrentPrincipal(
        issuer="eye-agent-backend",
        subject=subject,
        principal_type=principal_type,
        roles=frozenset({principal_type}),
        scopes=scopes,
        institution_id="institution-1",
        tenant_id="tenant-1",
        authorized_party="eye-agent-platform",
        schema_version=1,
        token_id="token-1",
        issued_at=1,
        not_before=1,
        expires_at=9999999999,
    )


class ResearchDocumentPurgeRouterTest(unittest.IsolatedAsyncioTestCase):
    def _app(self, principal: CurrentPrincipal | None):
        db = FakeDB()
        repository = FakeRepository(db)
        app = FastAPI()
        install_platform_validation_handler(app)

        @app.middleware("http")
        async def inject_principal(request: Request, call_next):
            if principal is not None:
                request.state.internal_principal = principal
            return await call_next(request)

        app.include_router(router)
        app.dependency_overrides[get_research_document_db] = lambda: db
        app.dependency_overrides[get_research_document_repository] = (
            lambda: repository
        )
        return app, db, repository

    async def _delete(
        self,
        principal: CurrentPrincipal | None,
        *,
        doctor_id: object = DOCTOR_ID,
        attachment_id: str = ATTACHMENT_ID,
    ):
        app, db, repository = self._app(principal)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.request(
                "DELETE",
                f"/api/platform/research-documents/{attachment_id}",
                json={"doctor_id": doctor_id},
            )
        return response, db, repository

    async def test_auth_matrix_requires_matching_doctor_and_ai_research(self):
        cases = (
            (None, 401),
            (_principal(principal_type="patient"), 403),
            (_principal(subject=OTHER_DOCTOR_ID), 403),
            (_principal(scopes=frozenset({"ai:chat"})), 403),
        )

        for principal, expected in cases:
            with self.subTest(principal=principal, expected=expected):
                response, db, repository = await self._delete(principal)
                self.assertEqual(response.status_code, expected)
                self.assertEqual(repository.calls, [])
                self.assertEqual(db.events, [])

    async def test_authorized_purge_uses_subject_and_attachment_inside_transaction(self):
        response, db, repository = await self._delete(_principal())

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(
            repository.calls,
            [(DOCTOR_ID, ATTACHMENT_ID, 1)],
        )
        self.assertEqual(db.events, ["begin", "commit"])

    async def test_32_hex_principal_is_preserved_and_authorized_for_purge(self):
        response, db, repository = await self._delete(
            _principal(subject=HEX_DOCTOR_ID),
            doctor_id=HEX_DOCTOR_ID,
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(
            repository.calls,
            [(HEX_DOCTOR_ID, ATTACHMENT_ID, 1)],
        )
        self.assertEqual(db.events, ["begin", "commit"])

    async def test_32_hex_body_must_equal_principal_subject_verbatim(self):
        response, db, repository = await self._delete(
            _principal(subject=DOCTOR_ID),
            doctor_id=HEX_DOCTOR_ID,
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(repository.calls, [])
        self.assertEqual(db.events, [])

    async def test_repeated_delete_is_idempotent_and_never_leaks_existence(self):
        app, db, repository = self._app(_principal())
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            responses = [
                await client.request(
                    "DELETE",
                    f"/api/platform/research-documents/{ATTACHMENT_ID}",
                    json={"doctor_id": DOCTOR_ID},
                )
                for _ in range(2)
            ]

        self.assertEqual([item.status_code for item in responses], [204, 204])
        self.assertEqual([item.content for item in responses], [b"", b""])
        self.assertEqual(
            repository.calls,
            [
                (DOCTOR_ID, ATTACHMENT_ID, 1),
                (DOCTOR_ID, ATTACHMENT_ID, 1),
            ],
        )
        self.assertEqual(
            db.events,
            ["begin", "commit", "begin", "commit"],
        )

    async def test_repeated_cross_doctor_purge_is_rejected_before_repository(self):
        app, db, repository = self._app(_principal())
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            responses = [
                await client.request(
                    "DELETE",
                    f"/api/platform/research-documents/{ATTACHMENT_ID}",
                    json={"doctor_id": OTHER_DOCTOR_ID},
                )
                for _ in range(2)
            ]

        self.assertEqual([item.status_code for item in responses], [403, 403])
        self.assertEqual(responses[0].content, responses[1].content)
        self.assertEqual(repository.calls, [])
        self.assertEqual(db.events, [])

    async def test_body_and_path_identifiers_are_strict_uuid_values(self):
        cases = (
            ({"doctor_id": 123}, ATTACHMENT_ID),
            ({"doctor_id": "doctor-1"}, ATTACHMENT_ID),
            ({"doctor_id": DOCTOR_ID, "extra": True}, ATTACHMENT_ID),
            ({"doctor_id": DOCTOR_ID}, "attachment-1"),
            (
                {"doctor_id": DOCTOR_ID.upper()},
                ATTACHMENT_ID,
            ),
            (
                {"doctor_id": "aaaaaaaa-aaaa-0aaa-8aaa-aaaaaaaaaaaa"},
                ATTACHMENT_ID,
            ),
            (
                {"doctor_id": "aaaaaaaa-aaaa-9aaa-8aaa-aaaaaaaaaaaa"},
                ATTACHMENT_ID,
            ),
            (
                {"doctor_id": "aaaaaaaa-aaaa-4aaa-7aaa-aaaaaaaaaaaa"},
                ATTACHMENT_ID,
            ),
            (
                {"doctor_id": "aaaaaaaa-aaaa-4aaa-caaa-aaaaaaaaaaaa"},
                ATTACHMENT_ID,
            ),
            (
                {"doctor_id": HEX_DOCTOR_ID.upper()},
                ATTACHMENT_ID,
            ),
            (
                {"doctor_id": f" {HEX_DOCTOR_ID}"},
                ATTACHMENT_ID,
            ),
            (
                {"doctor_id": HEX_DOCTOR_ID[:-1]},
                ATTACHMENT_ID,
            ),
            (
                {"doctor_id": f"{HEX_DOCTOR_ID}0"},
                ATTACHMENT_ID,
            ),
            (
                {"doctor_id": f"g{HEX_DOCTOR_ID[1:]}"},
                ATTACHMENT_ID,
            ),
            (
                {"doctor_id": DOCTOR_ID},
                ATTACHMENT_ID.upper(),
            ),
            (
                {"doctor_id": DOCTOR_ID},
                ATTACHMENT_ID.replace("-", ""),
            ),
        )
        for body, attachment_id in cases:
            with self.subTest(body=body, attachment_id=attachment_id):
                app, db, repository = self._app(_principal())
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    response = await client.request(
                        "DELETE",
                        f"/api/platform/research-documents/{attachment_id}",
                        json=body,
                    )
                self.assertEqual(response.status_code, 422)
                self.assertEqual(
                    response.json(),
                    {"error_code": "INVALID_PLATFORM_REQUEST"},
                )
                self.assertEqual(repository.calls, [])
                self.assertEqual(db.events, [])


if __name__ == "__main__":
    unittest.main()
