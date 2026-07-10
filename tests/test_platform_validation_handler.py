import copy
import json
import logging
import unittest

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from presentation.exception_handlers.platform_validation_handler import (
    install_platform_validation_handler,
)
from presentation.schemas.platform_chat_turn_schemas import (
    AbortPlatformChatTurnRequest,
    ExecutePlatformChatTurnRequest,
    PreparePlatformChatTurnRequest,
)

from tests.test_platform_chat_turn_schemas import load_fixture


_LOGGER_NAME = "presentation.exception_handlers.platform_validation_handler"
_SENTINEL = "platform-validation-secret-sentinel"


class RecordingLogHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class LegacyPayload(BaseModel):
    count: int


def build_app() -> FastAPI:
    app = FastAPI()
    install_platform_validation_handler(app)

    @app.post("/api/platform/chat/turns/prepare")
    async def prepare(payload: PreparePlatformChatTurnRequest):
        return payload

    @app.post("/api/platform/chat/turns/execute")
    async def execute(payload: ExecutePlatformChatTurnRequest):
        return payload

    @app.get("/api/platform/chat/turns/{request_id}")
    async def status(request_id: int):
        return {"request_id": request_id}

    @app.post("/api/platform/chat/turns/{request_id}/abort")
    async def abort(
        request_id: str,
        payload: AbortPlatformChatTurnRequest,
    ):
        return {"request_id": request_id, "payload": payload}

    @app.post("/api/platform/chat/turns/{request_id}/extra")
    async def platform_lookalike(request_id: str, payload: LegacyPayload):
        return {"request_id": request_id, "payload": payload}

    @app.post("/api/legacy")
    async def legacy(payload: LegacyPayload):
        return payload

    return app


class PlatformValidationHandlerTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = build_app()
        self.transport = httpx.ASGITransport(app=self.app)
        self.client = httpx.AsyncClient(
            transport=self.transport,
            base_url="http://testserver",
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def _request_with_logs(self, method: str, path: str, *, json_body=None):
        logger = logging.getLogger(_LOGGER_NAME)
        handler = RecordingLogHandler()
        previous_level = logger.level
        previous_propagate = logger.propagate
        logger.setLevel(logging.INFO)
        logger.propagate = False
        logger.addHandler(handler)
        try:
            response = await self.client.request(
                method,
                path,
                json=json_body,
            )
        finally:
            logger.removeHandler(handler)
            logger.setLevel(previous_level)
            logger.propagate = previous_propagate
        return response, handler.records

    async def test_platform_validation_is_fixed_and_does_not_leak_input(self):
        fixture = load_fixture("platform_chat_turn_internal_wire_v1.json")
        raw_url = f"https://storage.example/{_SENTINEL}"
        raw_base64 = f"data:image/png;base64,{_SENTINEL}"

        prepare_with_url = copy.deepcopy(fixture["prepare_request"])
        prepare_with_url["download_url"] = raw_url
        prepare_with_base64 = copy.deepcopy(fixture["prepare_request"])
        prepare_with_base64["base64"] = raw_base64
        malformed_execute = copy.deepcopy(fixture["execute_request"])
        malformed_execute["attachments"][0]["base64"] = raw_base64

        cases = (
            (
                "POST",
                "/api/platform/chat/turns/prepare",
                prepare_with_url,
                "/api/platform/chat/turns/prepare",
            ),
            (
                "POST",
                "/api/platform/chat/turns/prepare",
                prepare_with_base64,
                "/api/platform/chat/turns/prepare",
            ),
            (
                "POST",
                "/api/platform/chat/turns/execute",
                malformed_execute,
                "/api/platform/chat/turns/execute",
            ),
            (
                "GET",
                "/api/platform/chat/turns/not-an-integer",
                None,
                "/api/platform/chat/turns/{request_id}",
            ),
            (
                "POST",
                "/api/platform/chat/turns/turn-request-1/abort",
                {"conversation_id": _SENTINEL},
                "/api/platform/chat/turns/{request_id}/abort",
            ),
        )

        for method, path, body, expected_path in cases:
            with self.subTest(method=method, path=path):
                response, records = await self._request_with_logs(
                    method,
                    path,
                    json_body=body,
                )

                self.assertEqual(response.status_code, 422)
                self.assertEqual(
                    response.json(),
                    {"error_code": "INVALID_PLATFORM_REQUEST"},
                )
                self.assertEqual(len(records), 1)
                self.assertEqual(
                    records[0].getMessage(),
                    "platform_validation_failed "
                    f"method={method} path={expected_path} "
                    "error_code=INVALID_PLATFORM_REQUEST",
                )
                exposed = response.text + repr(records[0].__dict__)
                for secret in (_SENTINEL, raw_url, raw_base64):
                    self.assertNotIn(secret, exposed)
                self.assertNotIn('"input"', response.text)
                self.assertIsNone(records[0].exc_info)

    async def test_non_platform_validation_keeps_fastapi_default_behavior(self):
        for path in (
            "/api/legacy",
            "/api/platform/chat/turns/turn-request-1/extra",
        ):
            with self.subTest(path=path):
                response, records = await self._request_with_logs(
                    "POST",
                    path,
                    json_body={"count": _SENTINEL},
                )

                self.assertEqual(response.status_code, 422)
                body = response.json()
                self.assertIn("detail", body)
                self.assertNotEqual(
                    body,
                    {"error_code": "INVALID_PLATFORM_REQUEST"},
                )
                self.assertIn('"input"', json.dumps(body))
                self.assertEqual(records, [])


if __name__ == "__main__":
    unittest.main()
