import hashlib
import json
import os
import resource
import stat
import sys
import zipfile
import xml.etree.ElementTree as ElementTree
from pathlib import Path, PurePosixPath

from PIL import Image

from infrastructure.attachments.parser_protocol import (
    AttachmentParserError,
    ResearchCsvChunkManifest,
    ResearchCsvManifest,
    ResearchDocxManifest,
    ResearchPdfManifest,
    ResearchPdfPageManifest,
    ResearchTextManifest,
    WorkerManifest,
    WorkerPageManifest,
    WorkerRequest,
)
from infrastructure.attachments.research_csv_contract import (
    MAX_RESEARCH_CSV_BYTES,
    RESEARCH_CSV_ERROR_CODES,
    ResearchCsvContractError,
    parse_research_csv_bytes,
)
from infrastructure.attachments.research_text_contract import (
    ResearchTextContractError,
    normalize_research_text_bytes,
)
from infrastructure.attachments.research_docx_contract import (
    MAX_RESEARCH_DOCX_BYTES,
    ResearchDocxContractError,
    normalize_research_docx_text,
)
from utils.pdf_utils import (
    StrictPdfError,
    extract_research_pdf_path_strict,
    render_pdf_path_strict,
)


MAX_IMAGE_PIXELS = 50_000_000
_MAX_REQUEST_BYTES = 16 * 1024
_MAX_OUTPUT_FILE_BYTES = 64 * 1024 * 1024
_MAX_OUTPUT_TOTAL_BYTES = 64 * 1024 * 1024
_MAX_DOCX_ENTRIES = 512
_MAX_DOCX_ENTRY_BYTES = 16 * 1024 * 1024
_MAX_DOCX_TOTAL_BYTES = 64 * 1024 * 1024
_MAX_DOCX_COMPRESSION_RATIO = 100
_MAX_DOCX_XML_BYTES = 16 * 1024 * 1024
_DOCX_DOCUMENT_PATH = "word/document.xml"
_DOCX_CONTENT_TYPES_PATH = "[Content_Types].xml"
_DOCX_MAIN_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument."
    "wordprocessingml.document.main+xml"
)
_CONTENT_TYPES_NS = (
    "http://schemas.openxmlformats.org/package/2006/content-types"
)
_RELATIONSHIPS_NS = (
    "http://schemas.openxmlformats.org/package/2006/relationships"
)
_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_W = f"{{{_WORD_NS}}}"
_MARKUP_COMPATIBILITY_NS = (
    "http://schemas.openxmlformats.org/markup-compatibility/2006"
)
_MC = f"{{{_MARKUP_COMPATIBILITY_NS}}}"
_IGNORED_TEXT_SUBTREES = frozenset(
    {
        f"{_W}drawing",
        f"{_W}pict",
        f"{_W}object",
        f"{_W}del",
        f"{_W}moveFrom",
    }
)
_ALLOWED_BLOCK_WRAPPERS = frozenset(
    {
        f"{_W}sdt",
        f"{_W}sdtContent",
        f"{_W}customXml",
    }
)


def parse_attachment_file(
    request: WorkerRequest,
    input_dir: Path | str,
    output_dir: Path | str,
) -> (
    WorkerManifest
    | ResearchPdfManifest
    | ResearchTextManifest
    | ResearchDocxManifest
    | ResearchCsvManifest
):
    input_root = _resolve_directory(input_dir)
    output_root = _resolve_directory(output_dir)
    input_path = input_root / request.input_filename
    try:
        input_lstat = input_path.lstat()
        input_real = input_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise AttachmentParserError("ATTACHMENT_INPUT_PATH_INVALID") from exc
    if (
        not stat.S_ISREG(input_lstat.st_mode)
        or input_path.is_symlink()
        or input_real.parent != input_root
    ):
        raise AttachmentParserError("ATTACHMENT_INPUT_PATH_INVALID")

    if request.profile == "research_csv_v1":
        return _parse_research_csv(input_real, output_root)
    if request.file_type == "image":
        return _parse_image(request, input_real, output_root)
    if request.profile == "research_text_v1":
        return _parse_research_text(input_real, output_root)
    if request.profile == "research_docx_v1":
        return _parse_research_docx(input_real, output_root)
    if request.profile == "research_pdf_v1":
        return _parse_research_pdf(request, input_real, output_root)
    return _parse_pdf(request, input_real, output_root)


def _parse_image(
    request: WorkerRequest,
    input_path: Path,
    output_root: Path,
) -> WorkerManifest:
    expected_format = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
    }[request.mime_type]
    try:
        with Image.open(input_path) as image:
            width, height = image.size
            image_format = image.format
            if width <= 0 or height <= 0:
                raise AttachmentParserError("ATTACHMENT_IMAGE_INVALID")
            if width * height > MAX_IMAGE_PIXELS:
                raise AttachmentParserError("ATTACHMENT_IMAGE_PIXEL_LIMIT")
            if image_format != expected_format:
                raise AttachmentParserError("ATTACHMENT_IMAGE_FORMAT_MISMATCH")
            image.verify()
    except AttachmentParserError:
        raise
    except Exception as exc:
        raise AttachmentParserError("ATTACHMENT_IMAGE_INVALID") from exc

    suffix = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[expected_format]
    relative_path = f"page-0001{suffix}"
    output_path = output_root / relative_path
    digest = hashlib.sha256()
    total = 0
    try:
        file_descriptor = os.open(
            output_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with input_path.open("rb") as source, os.fdopen(file_descriptor, "wb") as output:
            while True:
                chunk = source.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_OUTPUT_FILE_BYTES:
                    raise AttachmentParserError("ATTACHMENT_OUTPUT_LIMIT")
                output.write(chunk)
                digest.update(chunk)
    except AttachmentParserError:
        try:
            output_path.unlink()
        except OSError:
            pass
        raise
    except OSError as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_FAILED") from exc

    return WorkerManifest(
        pages=(
            WorkerPageManifest(
                page_number=1,
                relative_path=relative_path,
                sha256=digest.hexdigest(),
            ),
        )
    )


def _parse_pdf(
    request: WorkerRequest,
    input_path: Path,
    output_root: Path,
) -> WorkerManifest:
    try:
        rendered_pages = render_pdf_path_strict(
            input_path,
            output_root,
            dpi=150,
        )
    except StrictPdfError as exc:
        raise AttachmentParserError(exc.error_code) from exc
    if len(rendered_pages) != request.declared_page_count:
        raise AttachmentParserError("ATTACHMENT_PAGE_COUNT_MISMATCH")
    return WorkerManifest(
        pages=tuple(
            WorkerPageManifest(
                page_number=page.page_number,
                relative_path=page.relative_path,
                sha256=page.sha256,
            )
            for page in rendered_pages
        )
    )


def _parse_research_pdf(
    request: WorkerRequest,
    input_path: Path,
    output_root: Path,
) -> ResearchPdfManifest:
    declared_page_count = request.declared_page_count
    if type(declared_page_count) is not int:
        raise AttachmentParserError("ATTACHMENT_PAGE_COUNT_INVALID")
    try:
        extracted_pages = extract_research_pdf_path_strict(
            input_path,
            output_root,
            declared_page_count=declared_page_count,
        )
    except StrictPdfError as exc:
        raise AttachmentParserError(exc.error_code) from exc
    return ResearchPdfManifest(
        pages=tuple(
            ResearchPdfPageManifest(
                page_number=page.page_number,
                text_relative_path=page.text_relative_path,
                text_sha256=page.text_sha256,
                ocr_image_relative_path=page.ocr_image_relative_path,
                ocr_image_sha256=page.ocr_image_sha256,
            )
            for page in extracted_pages
        )
    )


def _parse_research_text(
    input_path: Path,
    output_root: Path,
) -> ResearchTextManifest:
    try:
        content = input_path.read_bytes()
    except OSError as exc:
        raise AttachmentParserError("ATTACHMENT_INPUT_PATH_INVALID") from exc
    try:
        normalized = normalize_research_text_bytes(content)
    except ResearchTextContractError as exc:
        raise AttachmentParserError(exc.error_code) from exc

    output_path = output_root / "document.txt"
    try:
        file_descriptor = os.open(
            output_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except OSError as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_FAILED") from exc
    try:
        with os.fdopen(file_descriptor, "wb") as output:
            output.write(normalized.utf8_bytes)
    except OSError as exc:
        try:
            output_path.unlink()
        except OSError:
            pass
        raise AttachmentParserError("ATTACHMENT_OUTPUT_FAILED") from exc

    return ResearchTextManifest(
        profile="research_text_v1",
        text_relative_path=output_path.name,
        text_sha256=normalized.sha256,
        character_count=normalized.character_count,
    )


def _parse_research_docx(
    input_path: Path,
    output_root: Path,
) -> ResearchDocxManifest:
    try:
        if not 1 <= input_path.stat().st_size <= MAX_RESEARCH_DOCX_BYTES:
            raise AttachmentParserError("RESEARCH_DOCX_SIZE_LIMIT")
    except OSError as exc:
        raise AttachmentParserError("RESEARCH_DOCX_INVALID") from exc
    try:
        with zipfile.ZipFile(input_path, mode="r", allowZip64=False) as archive:
            entries = _validate_docx_archive(archive)
            content_types = _read_docx_entry(
                archive,
                entries[_DOCX_CONTENT_TYPES_PATH],
            )
            _validate_content_types(content_types)
            _validate_docx_relationships(archive, entries)
            document_xml = _read_docx_entry(
                archive,
                entries[_DOCX_DOCUMENT_PATH],
            )
    except AttachmentParserError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile):
        raise AttachmentParserError("RESEARCH_DOCX_INVALID") from None

    text = _extract_docx_text(document_xml)
    try:
        normalized = normalize_research_docx_text(text)
    except ResearchDocxContractError as exc:
        raise AttachmentParserError(exc.error_code) from exc

    output_path = output_root / "document.txt"
    try:
        file_descriptor = os.open(
            output_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(file_descriptor, "wb") as output:
            output.write(normalized.utf8_bytes)
    except OSError as exc:
        try:
            output_path.unlink()
        except OSError:
            pass
        raise AttachmentParserError("ATTACHMENT_OUTPUT_FAILED") from exc

    return ResearchDocxManifest(
        profile="research_docx_v1",
        text_relative_path=output_path.name,
        text_sha256=normalized.sha256,
        character_count=normalized.character_count,
    )


def _parse_research_csv(
    input_path: Path,
    output_root: Path,
) -> ResearchCsvManifest:
    created_paths: list[Path] = []
    try:
        with input_path.open("rb") as source:
            content = source.read(MAX_RESEARCH_CSV_BYTES + 1)
        if len(content) > MAX_RESEARCH_CSV_BYTES:
            raise AttachmentParserError("RESEARCH_CSV_SIZE_LIMIT")
        normalized = parse_research_csv_bytes(content)

        descriptor_bytes = normalized.descriptor_canonical_json_bytes
        descriptor_path = output_root / "descriptor.json"
        _write_research_csv_artifact(descriptor_path, descriptor_bytes)
        created_paths.append(descriptor_path)

        chunks: list[ResearchCsvChunkManifest] = []
        for chunk, chunk_bytes in zip(
            normalized.chunks,
            normalized.chunk_canonical_json_bytes,
        ):
            relative_path = f"chunk-{chunk.ordinal:05d}.json"
            output_path = output_root / relative_path
            _write_research_csv_artifact(output_path, chunk_bytes)
            created_paths.append(output_path)
            chunks.append(
                ResearchCsvChunkManifest(
                    ordinal=chunk.ordinal,
                    relative_path=relative_path,
                    sha256=hashlib.sha256(chunk_bytes).hexdigest(),
                    byte_count=len(chunk_bytes),
                    row_count=chunk.row_count,
                    logical_row_start=chunk.logical_row_start,
                    logical_row_end=chunk.logical_row_end,
                    physical_row_start=chunk.physical_row_start,
                    physical_row_end=chunk.physical_row_end,
                )
            )

        descriptor = normalized.descriptor
        return ResearchCsvManifest(
            profile="research_csv_v1",
            descriptor_relative_path=descriptor_path.name,
            descriptor_sha256=hashlib.sha256(descriptor_bytes).hexdigest(),
            descriptor_byte_count=len(descriptor_bytes),
            chunks=tuple(chunks),
            physical_line_count=descriptor.physical_line_count,
            record_count=descriptor.record_count,
            data_row_count=descriptor.data_row_count,
            column_count=descriptor.column_count,
            non_empty_cell_count=descriptor.non_empty_cell_count,
            formula_like_cell_count=descriptor.formula_like_cell_count,
        )
    except ResearchCsvContractError as exc:
        _remove_research_csv_artifacts(created_paths)
        error_code = (
            exc.error_code
            if exc.error_code in RESEARCH_CSV_ERROR_CODES
            else "RESEARCH_CSV_PARSE_FAILED"
        )
        raise AttachmentParserError(error_code) from None
    except AttachmentParserError as exc:
        _remove_research_csv_artifacts(created_paths)
        error_code = (
            exc.error_code
            if exc.error_code in RESEARCH_CSV_ERROR_CODES
            else "RESEARCH_CSV_PARSE_FAILED"
        )
        raise AttachmentParserError(error_code) from None
    except Exception:
        _remove_research_csv_artifacts(created_paths)
        raise AttachmentParserError("RESEARCH_CSV_PARSE_FAILED") from None


def _write_research_csv_artifact(path: Path, content: bytes) -> None:
    try:
        file_descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(file_descriptor, "wb") as output:
            output.write(content)
    except OSError:
        try:
            path.unlink()
        except OSError:
            pass
        raise AttachmentParserError("RESEARCH_CSV_PARSE_FAILED") from None


def _remove_research_csv_artifacts(paths: list[Path]) -> None:
    for path in reversed(paths):
        try:
            path.unlink()
        except OSError:
            pass


def _validate_docx_archive(
    archive: zipfile.ZipFile,
) -> dict[str, zipfile.ZipInfo]:
    entries = archive.infolist()
    if not 1 <= len(entries) <= _MAX_DOCX_ENTRIES:
        raise AttachmentParserError("RESEARCH_DOCX_STRUCTURE_LIMIT")
    by_name: dict[str, zipfile.ZipInfo] = {}
    total_size = 0
    for entry in entries:
        name = entry.filename
        path = PurePosixPath(name)
        unix_mode = entry.external_attr >> 16
        if (
            not name
            or "\\" in name
            or path.is_absolute()
            or ".." in path.parts
            or name in by_name
            or stat.S_IFMT(unix_mode) == stat.S_IFLNK
        ):
            raise AttachmentParserError("RESEARCH_DOCX_INVALID")
        if entry.flag_bits & 0x1:
            raise AttachmentParserError("RESEARCH_DOCX_ENCRYPTED")
        if entry.extract_version >= 45 or _contains_zip64_extra(entry.extra):
            raise AttachmentParserError("RESEARCH_DOCX_STRUCTURE_LIMIT")
        if entry.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
            raise AttachmentParserError("RESEARCH_DOCX_INVALID")
        if entry.file_size > _MAX_DOCX_ENTRY_BYTES:
            raise AttachmentParserError("RESEARCH_DOCX_STRUCTURE_LIMIT")
        total_size += entry.file_size
        if total_size > _MAX_DOCX_TOTAL_BYTES:
            raise AttachmentParserError("RESEARCH_DOCX_STRUCTURE_LIMIT")
        if entry.file_size and (
            entry.compress_size <= 0
            or entry.file_size
            > entry.compress_size * _MAX_DOCX_COMPRESSION_RATIO
        ):
            raise AttachmentParserError("RESEARCH_DOCX_STRUCTURE_LIMIT")
        lowered = name.lower()
        if (
            lowered.endswith("vbaproject.bin")
            or lowered.startswith("word/activex/")
            or lowered.startswith("word/embeddings/")
            or "oleobject" in lowered
        ):
            raise AttachmentParserError("RESEARCH_DOCX_INVALID")
        by_name[name] = entry
    if not {_DOCX_CONTENT_TYPES_PATH, _DOCX_DOCUMENT_PATH}.issubset(by_name):
        raise AttachmentParserError("RESEARCH_DOCX_INVALID")
    return by_name


def _read_docx_entry(
    archive: zipfile.ZipFile,
    entry: zipfile.ZipInfo,
) -> bytes:
    if entry.is_dir() or entry.file_size > _MAX_DOCX_XML_BYTES:
        raise AttachmentParserError("RESEARCH_DOCX_STRUCTURE_LIMIT")
    try:
        with archive.open(entry, mode="r") as source:
            content = source.read(entry.file_size + 1)
    except (OSError, RuntimeError, zipfile.BadZipFile):
        raise AttachmentParserError("RESEARCH_DOCX_INVALID") from None
    if len(content) != entry.file_size:
        raise AttachmentParserError("RESEARCH_DOCX_INVALID")
    return content


def _contains_zip64_extra(extra: bytes) -> bool:
    cursor = 0
    while cursor < len(extra):
        if cursor + 4 > len(extra):
            raise AttachmentParserError("RESEARCH_DOCX_INVALID")
        header_id = int.from_bytes(extra[cursor : cursor + 2], "little")
        field_size = int.from_bytes(extra[cursor + 2 : cursor + 4], "little")
        cursor += 4
        if cursor + field_size > len(extra):
            raise AttachmentParserError("RESEARCH_DOCX_INVALID")
        if header_id == 0x0001:
            return True
        cursor += field_size
    return False


def _parse_safe_xml(content: bytes) -> ElementTree.Element:
    upper = content.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise AttachmentParserError("RESEARCH_DOCX_INVALID")
    try:
        return ElementTree.fromstring(content)
    except ElementTree.ParseError:
        raise AttachmentParserError("RESEARCH_DOCX_INVALID") from None


def _validate_content_types(content: bytes) -> None:
    root = _parse_safe_xml(content)
    if root.tag != f"{{{_CONTENT_TYPES_NS}}}Types":
        raise AttachmentParserError("RESEARCH_DOCX_INVALID")
    document_overrides: list[str] = []
    for node in root:
        if node.tag not in {
            f"{{{_CONTENT_TYPES_NS}}}Default",
            f"{{{_CONTENT_TYPES_NS}}}Override",
        }:
            raise AttachmentParserError("RESEARCH_DOCX_INVALID")
        content_type = node.attrib.get("ContentType")
        if not isinstance(content_type, str) or not content_type:
            raise AttachmentParserError("RESEARCH_DOCX_INVALID")
        lowered = content_type.lower()
        if any(
            token in lowered
            for token in ("macroenabled", "vbaproject", "oleobject", "activex")
        ):
            raise AttachmentParserError("RESEARCH_DOCX_INVALID")
        if (
            node.tag == f"{{{_CONTENT_TYPES_NS}}}Override"
            and node.attrib.get("PartName") == "/word/document.xml"
        ):
            document_overrides.append(content_type)
    if document_overrides != [_DOCX_MAIN_CONTENT_TYPE]:
        raise AttachmentParserError("RESEARCH_DOCX_INVALID")


def _validate_docx_relationships(
    archive: zipfile.ZipFile,
    entries: dict[str, zipfile.ZipInfo],
) -> None:
    for name, entry in entries.items():
        if not name.lower().endswith(".rels"):
            continue
        root = _parse_safe_xml(_read_docx_entry(archive, entry))
        if root.tag != f"{{{_RELATIONSHIPS_NS}}}Relationships":
            raise AttachmentParserError("RESEARCH_DOCX_INVALID")
        for relationship in root:
            if relationship.tag != f"{{{_RELATIONSHIPS_NS}}}Relationship":
                raise AttachmentParserError("RESEARCH_DOCX_INVALID")
            relationship_type = relationship.attrib.get("Type")
            target = relationship.attrib.get("Target")
            relationship_kind = (
                relationship_type.rsplit("/", 1)[-1].lower()
                if isinstance(relationship_type, str)
                else ""
            )
            if (
                not isinstance(relationship_type, str)
                or not relationship_type
                or not isinstance(target, str)
                or not target
                or (
                    relationship.attrib.get("TargetMode", "").lower()
                    == "external"
                    and relationship_kind != "hyperlink"
                )
                or any(
                    token in relationship_type.lower()
                    for token in ("vbaproject", "oleobject", "activex")
                )
                or relationship_kind == "package"
            ):
                raise AttachmentParserError("RESEARCH_DOCX_INVALID")


def _extract_docx_text(content: bytes) -> str:
    root = _parse_safe_xml(content)
    body = root.find(f".//{_W}body")
    if body is None:
        raise AttachmentParserError("RESEARCH_DOCX_INVALID")
    blocks: list[str] = []
    _append_docx_blocks(body, blocks)
    return "\n\n".join(blocks)


def _append_docx_blocks(
    container: ElementTree.Element,
    blocks: list[str],
) -> None:
    for child in container:
        if child.tag == f"{_W}p":
            raw = _paragraph_text(child)
            if raw.strip():
                blocks.append(raw.rstrip())
        elif child.tag == f"{_W}tbl":
            rows: list[str] = []
            for row in child.findall(f"./{_W}tr"):
                cells: list[str] = []
                for cell in row.findall(f"./{_W}tc"):
                    parts: list[str] = []
                    for paragraph in cell.findall(f".//{_W}p"):
                        raw = _paragraph_text(paragraph)
                        if raw.strip():
                            parts.append(raw.rstrip())
                    value = "\n".join(parts)
                    cells.append(value)
                if any(cells):
                    rows.append("\t".join(cells))
            if rows:
                blocks.append("\n".join(rows))
        elif child.tag in _ALLOWED_BLOCK_WRAPPERS:
            _append_docx_blocks(child, blocks)


def _paragraph_text(paragraph: ElementTree.Element) -> str:
    values: list[str] = []
    _collect_visible_word_text(paragraph, values)
    text = "".join(values)
    numbering = paragraph.find(f"./{_W}pPr/{_W}numPr")
    if numbering is None or not text.strip():
        return text
    level_node = numbering.find(f"./{_W}ilvl")
    try:
        level = (
            int(level_node.attrib.get(f"{_W}val", "0"))
            if level_node is not None
            else 0
        )
    except (TypeError, ValueError):
        level = 0
    return f"{'  ' * min(max(level, 0), 8)}- {text}"


def _collect_visible_word_text(
    node: ElementTree.Element,
    values: list[str],
) -> None:
    if node.tag in _IGNORED_TEXT_SUBTREES:
        return
    if node.tag == f"{_MC}AlternateContent":
        selected = node.find(f"./{_MC}Choice")
        if selected is None:
            selected = node.find(f"./{_MC}Fallback")
        if selected is not None:
            _collect_visible_word_text(selected, values)
        return
    if node.tag == f"{_W}r":
        run_properties = node.find(f"./{_W}rPr")
        if run_properties is not None and any(
            run_properties.find(f"./{_W}{name}") is not None
            for name in ("vanish", "webHidden", "specVanish")
        ):
            return
    if node.tag == f"{_W}t" and node.text:
        values.append(node.text)
        return
    if node.tag == f"{_W}tab":
        values.append("\t")
        return
    if node.tag in {f"{_W}br", f"{_W}cr"}:
        values.append("\n")
        return
    for child in node:
        _collect_visible_word_text(child, values)


def _resolve_directory(path: Path | str) -> Path:
    candidate = Path(path)
    try:
        resolved = candidate.resolve(strict=True)
        mode = candidate.lstat().st_mode
    except (OSError, RuntimeError) as exc:
        raise AttachmentParserError("ATTACHMENT_SANDBOX_PATH_INVALID") from exc
    if not stat.S_ISDIR(mode) or candidate.is_symlink():
        raise AttachmentParserError("ATTACHMENT_SANDBOX_PATH_INVALID")
    return resolved


def _write_output_bundle(
    manifest: (
        WorkerManifest
        | ResearchPdfManifest
        | ResearchTextManifest
        | ResearchDocxManifest
        | ResearchCsvManifest
    ),
    output_dir: Path | str,
    bundle_path: Path | str,
) -> None:
    output_root = _resolve_directory(output_dir)
    bundle = Path(bundle_path)
    try:
        bundle_metadata = bundle.lstat()
    except OSError as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID") from exc
    if (
        bundle.is_symlink()
        or not stat.S_ISREG(bundle_metadata.st_mode)
        or stat.S_IMODE(bundle_metadata.st_mode) != 0o600
    ):
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")

    validated: list[tuple[Path, str]] = []
    total_bytes = 0
    for relative_path, expected_sha256, expected_byte_count in _manifest_artifacts(
        manifest
    ):
        source = output_root / relative_path
        try:
            metadata = source.lstat()
            resolved = source.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID") from exc
        if (
            source.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or resolved.parent != output_root
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
        total_bytes += metadata.st_size
        if total_bytes > _MAX_OUTPUT_TOTAL_BYTES:
            raise AttachmentParserError("ATTACHMENT_OUTPUT_LIMIT")
        if (
            expected_byte_count is not None
            and metadata.st_size != expected_byte_count
        ):
            raise AttachmentParserError("ATTACHMENT_OUTPUT_SIZE_MISMATCH")
        if _sha256_file(resolved) != expected_sha256:
            raise AttachmentParserError("ATTACHMENT_OUTPUT_HASH_MISMATCH")
        validated.append((resolved, relative_path))

    try:
        with zipfile.ZipFile(
            bundle,
            mode="w",
            compression=zipfile.ZIP_STORED,
            allowZip64=False,
        ) as archive:
            for source, relative_path in validated:
                archive.write(source, arcname=relative_path)
    except (OSError, RuntimeError, zipfile.LargeZipFile) as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_FAILED") from exc


def _manifest_artifacts(
    manifest: (
        WorkerManifest
        | ResearchPdfManifest
        | ResearchTextManifest
        | ResearchDocxManifest
        | ResearchCsvManifest
    ),
) -> tuple[tuple[str, str, int | None], ...]:
    if isinstance(manifest, WorkerManifest):
        return tuple(
            (page.relative_path, page.sha256, None) for page in manifest.pages
        )
    if isinstance(manifest, ResearchTextManifest):
        manifest = ResearchTextManifest(
            profile=manifest.profile,
            text_relative_path=manifest.text_relative_path,
            text_sha256=manifest.text_sha256,
            character_count=manifest.character_count,
        )
        return ((manifest.text_relative_path, manifest.text_sha256, None),)
    if isinstance(manifest, ResearchDocxManifest):
        manifest = ResearchDocxManifest(
            profile=manifest.profile,
            text_relative_path=manifest.text_relative_path,
            text_sha256=manifest.text_sha256,
            character_count=manifest.character_count,
        )
        return ((manifest.text_relative_path, manifest.text_sha256, None),)
    if isinstance(manifest, ResearchCsvManifest):
        manifest = ResearchCsvManifest(
            profile=manifest.profile,
            descriptor_relative_path=manifest.descriptor_relative_path,
            descriptor_sha256=manifest.descriptor_sha256,
            descriptor_byte_count=manifest.descriptor_byte_count,
            chunks=tuple(manifest.chunks),
            physical_line_count=manifest.physical_line_count,
            record_count=manifest.record_count,
            data_row_count=manifest.data_row_count,
            column_count=manifest.column_count,
            non_empty_cell_count=manifest.non_empty_cell_count,
            formula_like_cell_count=manifest.formula_like_cell_count,
        )
        artifacts = [
            (
                manifest.descriptor_relative_path,
                manifest.descriptor_sha256,
                manifest.descriptor_byte_count,
            )
        ]
        artifacts.extend(
            (chunk.relative_path, chunk.sha256, chunk.byte_count)
            for chunk in manifest.chunks
        )
        return tuple(artifacts)
    if not isinstance(manifest, ResearchPdfManifest):
        raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
    manifest = ResearchPdfManifest(tuple(manifest.pages))
    artifacts: list[tuple[str, str, int | None]] = []
    for page in manifest.pages:
        artifacts.append((page.text_relative_path, page.text_sha256, None))
        if page.ocr_image_relative_path is not None:
            if page.ocr_image_sha256 is None:
                raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
            artifacts.append(
                (page.ocr_image_relative_path, page.ocr_image_sha256, None)
            )
    return tuple(artifacts)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            while chunk := source.read(64 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_READ_FAILED") from exc
    return digest.hexdigest()


def _apply_resource_limits() -> None:
    limits = (
        (resource.RLIMIT_CPU, 120, 121),
        (resource.RLIMIT_AS, 768 * 1024 * 1024, 768 * 1024 * 1024),
        (resource.RLIMIT_FSIZE, _MAX_OUTPUT_FILE_BYTES, _MAX_OUTPUT_FILE_BYTES),
        (resource.RLIMIT_NOFILE, 128, 128),
    )
    try:
        for resource_name, soft, hard in limits:
            resource.setrlimit(resource_name, (soft, hard))
    except (OSError, ValueError) as exc:
        raise AttachmentParserError("ATTACHMENT_RESOURCE_LIMIT_FAILED") from exc


def _assert_network_namespace_isolated() -> None:
    try:
        ipv4_lines = Path("/proc/net/route").read_text(encoding="ascii").splitlines()
        ipv6_lines = Path("/proc/net/ipv6_route").read_text(
            encoding="ascii"
        ).splitlines()
    except (OSError, UnicodeError) as exc:
        raise AttachmentParserError("ATTACHMENT_NETWORK_CHECK_FAILED") from exc
    ipv4_interfaces = {
        fields[0]
        for line in ipv4_lines[1:]
        if len(fields := line.split()) >= 1
    }
    ipv6_interfaces = {
        fields[-1]
        for line in ipv6_lines
        if len(fields := line.split()) >= 10
    }
    if (ipv4_interfaces | ipv6_interfaces) - {"lo"}:
        raise AttachmentParserError("ATTACHMENT_NETWORK_ISOLATION_FAILED")


def _assert_input_is_read_only(input_path: Path) -> None:
    try:
        file_descriptor = os.open(input_path, os.O_WRONLY)
    except OSError:
        return
    else:
        os.close(file_descriptor)
    raise AttachmentParserError("ATTACHMENT_INPUT_MOUNT_WRITABLE")


def main() -> int:
    request: WorkerRequest | None = None
    try:
        payload = sys.stdin.buffer.read(_MAX_REQUEST_BYTES + 1)
        if len(payload) > _MAX_REQUEST_BYTES:
            raise AttachmentParserError("ATTACHMENT_WORKER_REQUEST_INVALID")
        request = WorkerRequest.from_json_bytes(payload)
        _apply_resource_limits()
        _assert_network_namespace_isolated()
        _assert_input_is_read_only(Path("/input") / request.input_filename)
        manifest = parse_attachment_file(request, Path("/input"), Path("/output"))
        _write_output_bundle(manifest, Path("/output"), Path("/output.bundle"))
        sys.stdout.buffer.write(manifest.to_json_bytes())
        sys.stdout.buffer.flush()
        return 0
    except AttachmentParserError as exc:
        error_code = exc.error_code
        if (
            request is not None
            and request.profile == "research_csv_v1"
            and error_code not in RESEARCH_CSV_ERROR_CODES
        ):
            error_code = "RESEARCH_CSV_PARSE_FAILED"
        sys.stderr.write(
            json.dumps({"error_code": error_code}, separators=(",", ":"))
            + "\n"
        )
        return 2
    except BaseException:
        error_code = (
            "RESEARCH_CSV_PARSE_FAILED"
            if request is not None and request.profile == "research_csv_v1"
            else "ATTACHMENT_WORKER_FAILED"
        )
        sys.stderr.write(
            json.dumps({"error_code": error_code}, separators=(",", ":"))
            + "\n"
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
