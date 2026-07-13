import hashlib
import unittest

from infrastructure.attachments.research_text_contract import (
    MAX_RESEARCH_TEXT_CANONICAL_BYTES,
    ResearchTextContractError,
    normalize_research_text_bytes,
    validate_canonical_research_text_bytes,
)


_RAW_SIZE_LIMIT = 512 * 1024
_CHARACTER_LIMIT = 500_000


class ResearchTextContractTest(unittest.TestCase):
    def test_normalizes_utf8_bom_newlines_and_nfc(self):
        result = normalize_research_text_bytes(
            b"\xef\xbb\xbfCafe\xcc\x81\r\nline\r"
        )

        self.assertEqual(result.text, "Caf\u00e9\nline\n")
        self.assertEqual(result.utf8_bytes, result.text.encode("utf-8"))
        self.assertEqual(result.character_count, len(result.text))
        self.assertEqual(
            result.sha256,
            hashlib.sha256(result.utf8_bytes).hexdigest(),
        )

    def test_counts_unicode_code_points_including_emoji(self):
        result = normalize_research_text_bytes("A\U0001f600".encode("utf-8"))

        self.assertEqual(result.character_count, 2)
        self.assertEqual(result.text, "A\U0001f600")

    def test_accepts_raw_size_and_character_count_at_limits(self):
        raw_limit_result = normalize_research_text_bytes(
            b"\xc3\xa9" * (_RAW_SIZE_LIMIT // 2)
        )
        character_limit_result = normalize_research_text_bytes(
            b"a" * _CHARACTER_LIMIT
        )

        self.assertEqual(len(raw_limit_result.utf8_bytes), _RAW_SIZE_LIMIT)
        self.assertEqual(
            character_limit_result.character_count,
            _CHARACTER_LIMIT,
        )

    def test_rejects_raw_size_above_limit_before_decoding(self):
        self._assert_contract_error(
            b"a" * _RAW_SIZE_LIMIT + b"\xff",
            "RESEARCH_TXT_SIZE_LIMIT",
        )

    def test_rejects_character_count_above_limit(self):
        self._assert_contract_error(
            b"a" * (_CHARACTER_LIMIT + 1),
            "RESEARCH_TXT_CONTENT_LIMIT",
        )

    def test_rejects_invalid_utf8_without_decoder_details_or_body(self):
        body_sentinel = "DO_NOT_LEAK_RESEARCH_BODY"

        error = self._assert_contract_error(
            body_sentinel.encode("ascii") + b"\xff",
            "RESEARCH_TXT_ENCODING_UNSUPPORTED",
        )

        rendered = repr(error)
        self.assertNotIn(body_sentinel, rendered)
        self.assertNotIn("position", rendered.lower())

    def test_rejects_nul_c0_and_del_controls(self):
        disallowed_code_points = [
            code_point
            for code_point in range(32)
            if code_point not in (9, 10, 13)
        ] + [127]

        for code_point in disallowed_code_points:
            with self.subTest(code_point=code_point):
                self._assert_contract_error(
                    b"safe" + bytes([code_point]) + b"text",
                    "RESEARCH_TXT_BINARY",
                )

    def test_allows_tab_and_newline_controls(self):
        result = normalize_research_text_bytes(b"safe\ttext\n")

        self.assertEqual(result.text, "safe\ttext\n")

    def test_rejects_empty_and_whitespace_only_content(self):
        for content in (b"", b" \t\r\n"):
            with self.subTest(content=content):
                self._assert_contract_error(content, "RESEARCH_TXT_INVALID")

    def test_rejects_non_bytes_content(self):
        for content in ("text", bytearray(b"text"), None):
            with self.subTest(content=content):
                self._assert_contract_error(content, "RESEARCH_TXT_INVALID")

    def test_canonical_artifact_accepts_four_bytes_per_character_at_limit(self):
        canonical_text = "\U0001f600" * _CHARACTER_LIMIT
        canonical = canonical_text.encode("utf-8")
        self.assertEqual(
            MAX_RESEARCH_TEXT_CANONICAL_BYTES,
            4 * _CHARACTER_LIMIT,
        )
        self.assertEqual(len(canonical), MAX_RESEARCH_TEXT_CANONICAL_BYTES)

        result = validate_canonical_research_text_bytes(canonical)

        self.assertEqual(result.text, canonical_text)
        self.assertEqual(result.utf8_bytes, canonical)
        self.assertEqual(result.character_count, _CHARACTER_LIMIT)

    def test_canonical_artifact_rejects_bytes_above_theoretical_limit(self):
        oversized = ("\U0001f600" * _CHARACTER_LIMIT).encode("utf-8") + b"x"

        with self.assertRaises(ResearchTextContractError) as captured:
            validate_canonical_research_text_bytes(oversized)

        self.assertEqual(
            captured.exception.error_code,
            "RESEARCH_TXT_CONTENT_LIMIT",
        )

    def _assert_contract_error(self, content, expected_code):
        with self.assertRaises(ResearchTextContractError) as captured:
            normalize_research_text_bytes(content)

        error = captured.exception
        self.assertEqual(error.error_code, expected_code)
        self.assertEqual(str(error), expected_code)
        self.assertEqual(error.args, (expected_code,))
        return error


if __name__ == "__main__":
    unittest.main()
