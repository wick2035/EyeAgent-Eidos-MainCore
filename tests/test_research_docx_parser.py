import hashlib
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from infrastructure.attachments.attachment_parser_worker import (
    parse_attachment_file,
)
from infrastructure.attachments.parser_protocol import (
    AttachmentParserError,
    ResearchDocxManifest,
    WorkerRequest,
)
from infrastructure.attachments.parser_sandbox import (
    _read_validated_research_docx_bundle,
)


DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
CONTENT_TYPES = b"""<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Override PartName="/word/document.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""


def document_xml(body: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:body>'
        f"{body}</w:body></w:document>"
    ).encode("utf-8")


class ResearchDocxParserTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.input_dir = self.root / "input"
        self.output_dir = self.root / "output"
        self.input_dir.mkdir(mode=0o700)
        self.output_dir.mkdir(mode=0o700)

    def tearDown(self):
        self.temporary.cleanup()

    def _request(self) -> WorkerRequest:
        return WorkerRequest(
            input_filename="paper.docx",
            file_type="docx",
            mime_type=DOCX_MIME,
            declared_page_count=None,
            profile="research_docx_v1",
        )

    def _write_docx(
        self,
        body: str,
        *,
        content_types: bytes = CONTENT_TYPES,
        extras: tuple[tuple[str, bytes], ...] = (),
    ) -> Path:
        path = self.input_dir / "paper.docx"
        with zipfile.ZipFile(
            path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            allowZip64=False,
        ) as archive:
            archive.writestr("[Content_Types].xml", content_types)
            archive.writestr("word/document.xml", document_xml(body))
            for name, content in extras:
                archive.writestr(name, content)
        return path

    def test_extracts_paragraphs_breaks_and_tables_in_source_order(self):
        self._write_docx(
            "<w:p><w:r><w:t>标题</w:t></w:r></w:p>"
            "<w:sdt><w:sdtContent><w:p><w:r><w:t>内容控件正文</w:t>"
            "</w:r></w:p></w:sdtContent></w:sdt>"
            "<w:p><w:pPr><w:numPr><w:ilvl w:val=\"1\"/>"
            "<w:numId w:val=\"1\"/></w:numPr></w:pPr>"
            "<w:r><w:t>列表项</w:t></w:r></w:p>"
            "<w:tbl><w:tr>"
            "<w:tc><w:p><w:r><w:t>A</w:t></w:r></w:p></w:tc>"
            "<w:tc><w:p><w:r><w:t>B</w:t></w:r></w:p></w:tc>"
            "</w:tr></w:tbl>"
            "<w:p><w:r><w:t>结论</w:t><w:tab/><w:t>有效</w:t>"
            "<w:br/><w:t>下一行</w:t></w:r>"
            "<w:r><w:drawing><w:txbxContent><w:p><w:r><w:t>对象秘密</w:t>"
            "</w:r></w:p></w:txbxContent></w:drawing></w:r>"
            "<w:del><w:r><w:t>删除历史</w:t></w:r></w:del>"
            "<w:r><w:rPr><w:vanish/></w:rPr><w:t>隐藏指令</w:t></w:r>"
            "<mc:AlternateContent xmlns:mc=\"http://schemas.openxmlformats.org/"
            "markup-compatibility/2006\"><mc:Choice Requires=\"w\">"
            "<w:r><w:t>兼容正文</w:t></w:r></mc:Choice><mc:Fallback>"
            "<w:r><w:t>回退副本</w:t></w:r></mc:Fallback></mc:AlternateContent>"
            "</w:p>"
        )

        manifest = parse_attachment_file(
            self._request(),
            self.input_dir,
            self.output_dir,
        )

        expected = (
            "标题\n\n内容控件正文\n\n  - 列表项\n\nA\tB\n\n"
            "结论\t有效\n下一行兼容正文"
        )
        content = (self.output_dir / "document.txt").read_text(encoding="utf-8")
        self.assertEqual(content, expected)
        self.assertIsInstance(manifest, ResearchDocxManifest)
        self.assertEqual(manifest.character_count, len(expected))
        self.assertEqual(
            manifest.text_sha256,
            hashlib.sha256(expected.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(
            stat.S_IMODE((self.output_dir / "document.txt").stat().st_mode),
            0o600,
        )

    def test_rejects_dtd_macro_external_relationship_traversal_and_zip_bomb(self):
        macro_content_types = CONTENT_TYPES.replace(
            b"</Types>",
            b'<Override PartName="/custom/payload.bin" '
            b'ContentType="application/vnd.ms-office.vbaProject"/></Types>',
        )
        embedded_package_relationship = b"""<Relationships
          xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
          <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/package"
            Target="../../custom/payload.bin"/>
        </Relationships>"""
        cases = (
            (
                "dtd",
                b'<!DOCTYPE x [<!ENTITY boom "boom">]><Types/>',
                (),
            ),
            (
                "macro",
                macro_content_types,
                (("custom/payload.bin", b"macro"),),
            ),
            (
                "embedded-package-relationship",
                CONTENT_TYPES,
                (
                    (
                        "word/_rels/document.xml.rels",
                        embedded_package_relationship,
                    ),
                    ("custom/payload.bin", b"embedded"),
                ),
            ),
            (
                "traversal",
                CONTENT_TYPES,
                (("../escape.bin", b"escape"),),
            ),
            (
                "zip-bomb",
                CONTENT_TYPES,
                (("word/media/bomb.bin", b"0" * (1024 * 1024)),),
            ),
        )
        for name, content_types, extras in cases:
            with self.subTest(name=name):
                self.output_dir = self.root / f"output-{name}"
                self.output_dir.mkdir(mode=0o700)
                self._write_docx(
                    "<w:p><w:r><w:t>正文</w:t></w:r></w:p>",
                    content_types=content_types,
                    extras=extras,
                )
                with self.assertRaises(AttachmentParserError):
                    parse_attachment_file(
                        self._request(),
                        self.input_dir,
                        self.output_dir,
                    )

    def test_allows_visible_hyperlink_text_but_never_reads_external_target(self):
        relationship = b"""<Relationships
          xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
          <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
            Target="https://example.invalid/reference" TargetMode="External"/>
        </Relationships>"""
        self._write_docx(
            '<w:p><w:hyperlink r:id="rId1" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<w:r><w:t>参考链接</w:t></w:r></w:hyperlink></w:p>',
            extras=(("word/_rels/document.xml.rels", relationship),),
        )

        manifest = parse_attachment_file(
            self._request(),
            self.input_dir,
            self.output_dir,
        )

        self.assertEqual(
            (self.output_dir / manifest.text_relative_path).read_text("utf-8"),
            "参考链接",
        )

    def test_host_revalidates_exact_bundle_hash_and_character_count(self):
        content = "规范化DOCX正文".encode("utf-8")
        bundle = self.root / "output.bundle"
        with zipfile.ZipFile(bundle, mode="w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("document.txt", content)
        bundle.chmod(0o600)
        manifest = ResearchDocxManifest(
            profile="research_docx_v1",
            text_relative_path="document.txt",
            text_sha256=hashlib.sha256(content).hexdigest(),
            character_count=len("规范化DOCX正文"),
        )

        normalized = _read_validated_research_docx_bundle(
            bundle,
            manifest.to_json_bytes(),
        )

        self.assertEqual(normalized.text, "规范化DOCX正文")
        bad_manifest = ResearchDocxManifest(
            profile="research_docx_v1",
            text_relative_path="document.txt",
            text_sha256="0" * 64,
            character_count=len("规范化DOCX正文"),
        )
        with self.assertRaisesRegex(
            AttachmentParserError,
            "ATTACHMENT_OUTPUT_HASH_MISMATCH",
        ):
            _read_validated_research_docx_bundle(
                bundle,
                bad_manifest.to_json_bytes(),
            )

    def test_rejects_zip64_extra_even_when_extract_version_is_forged_low(self):
        path = self.input_dir / "paper.docx"
        with zipfile.ZipFile(path, mode="w", allowZip64=False) as archive:
            content_types_info = zipfile.ZipInfo("[Content_Types].xml")
            content_types_info.extract_version = 20
            content_types_info.extra = b"\x01\x00\x00\x00"
            archive.writestr(content_types_info, CONTENT_TYPES)
            archive.writestr(
                "word/document.xml",
                document_xml("<w:p><w:r><w:t>正文</w:t></w:r></w:p>"),
            )

        with self.assertRaisesRegex(
            AttachmentParserError,
            "RESEARCH_DOCX_STRUCTURE_LIMIT",
        ):
            parse_attachment_file(
                self._request(),
                self.input_dir,
                self.output_dir,
            )


if __name__ == "__main__":
    unittest.main()
