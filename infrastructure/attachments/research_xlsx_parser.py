import io
import math
import os
import posixpath
import stat
import struct
import unicodedata
import zlib
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

from defusedxml import ElementTree as DefusedElementTree
from defusedxml.common import DefusedXmlException
from openpyxl import load_workbook
from openpyxl.cell.cell import TYPE_FORMULA
from openpyxl.utils.cell import coordinate_to_tuple, range_boundaries
from openpyxl.utils.datetime import CALENDAR_MAC_1904
from openpyxl.worksheet.formula import ArrayFormula, DataTableFormula

from infrastructure.attachments.research_xlsx_contract import (
    MAX_RESEARCH_XLSX_BYTES,
    MAX_RESEARCH_XLSX_CELL_CODEPOINTS,
    MAX_RESEARCH_XLSX_COLUMNS,
    MAX_RESEARCH_XLSX_COMPRESSION_RATIO,
    MAX_RESEARCH_XLSX_NON_EMPTY_CELLS,
    MAX_RESEARCH_XLSX_ROWS,
    MAX_RESEARCH_XLSX_SHEETS,
    MAX_RESEARCH_XLSX_ZIP_ENTRIES,
    MAX_RESEARCH_XLSX_ZIP_ENTRY_BYTES,
    MAX_RESEARCH_XLSX_ZIP_TOTAL_BYTES,
    NormalizedResearchXlsx,
    ResearchXlsxContractError,
    XlsxDescriptor,
    XlsxRow,
    XlsxSheetDescriptor,
    build_normalized_research_xlsx,
)


_CONTENT_TYPES_PATH = "[Content_Types].xml"
_ROOT_RELATIONSHIPS_PATH = "_rels/.rels"
_WORKBOOK_PATH = "xl/workbook.xml"
_WORKBOOK_RELATIONSHIPS_PATH = "xl/_rels/workbook.xml.rels"
_XML_SUFFIXES = (".xml", ".rels", ".vml")
_XML_CONTENT_TYPES = frozenset({"application/xml", "text/xml"})
_OPENPYXL_XML_RELATIONSHIP_TYPES = frozenset(
    {"officedocument", "sharedstrings", "styles", "theme", "worksheet"}
)
_ALLOWED_COMPRESSIONS = frozenset(
    {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
)
_ACTIVE_PART_FRAGMENTS = (
    "vbaproject",
    "/activex/",
    "/controls/",
    "/ctrlprops/",
    "/oleobjects/",
    "/embeddings/",
    "/externallinks/",
    "/macrosheets/",
    "/intlmacrosheets/",
    "/connections",
)
_ACTIVE_CONTENT_TYPE_FRAGMENTS = (
    "macroenabled",
    "vba",
    "activex",
    "oleobject",
    "externalLink".lower(),
)
_ACTIVE_RELATIONSHIP_TYPES = frozenset(
    {
        "activexcontrolbinary",
        "connections",
        "control",
        "controlproperties",
        "ctrlprop",
        "externallink",
        "externallinkpath",
        "intlmacrosheet",
        "macrosheet",
        "oleobject",
        "package",
        "vbaproject",
    }
)
_WORKBOOK_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument."
    "spreadsheetml.sheet.main+xml"
)
_RELATIONSHIP_NAMESPACE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)


@dataclass(frozen=True)
class _Relationship:
    relationship_id: str
    relationship_type: str
    target_path: str


@dataclass(frozen=True)
class _SheetPreflight:
    ordinal: int
    name: str
    visibility: str
    part_path: str
    first_declared_row: int | None
    last_declared_row: int | None
    last_declared_column: int
    merged_ranges: tuple[tuple[int, int, int, int], ...]
    merged_subordinate_masks: dict[int, int]


@dataclass(frozen=True)
class _WorkbookPreflight:
    sheets: tuple[_SheetPreflight, ...]


def parse_research_xlsx_path(
    path: str | os.PathLike[str],
) -> NormalizedResearchXlsx:
    try:
        raw = _read_bounded_file(path)
        preflight = _preflight_xlsx(raw)
        return _parse_preflighted_workbook(raw, preflight)
    except ResearchXlsxContractError:
        raise
    except Exception:
        raise ResearchXlsxContractError(
            "RESEARCH_XLSX_PARSE_FAILED"
        ) from None


def _read_bounded_file(path: str | os.PathLike[str]) -> bytes:
    try:
        resolved = os.fspath(path)
    except TypeError:
        raise ResearchXlsxContractError("RESEARCH_XLSX_UNAVAILABLE") from None
    try:
        with open(resolved, "rb") as stream:
            raw = stream.read(MAX_RESEARCH_XLSX_BYTES + 1)
    except OSError:
        raise ResearchXlsxContractError("RESEARCH_XLSX_UNAVAILABLE") from None
    if not raw:
        raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
    if len(raw) > MAX_RESEARCH_XLSX_BYTES:
        raise ResearchXlsxContractError("RESEARCH_XLSX_SIZE_LIMIT")
    return raw


def _preflight_xlsx(raw: bytes) -> _WorkbookPreflight:
    if raw.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        raise ResearchXlsxContractError("RESEARCH_XLSX_ENCRYPTED")
    if not raw.startswith(b"PK\x03\x04"):
        raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
    if b"PK\x06\x06" in raw or b"PK\x06\x07" in raw:
        raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw), mode="r", allowZip64=False)
    except (zipfile.BadZipFile, zipfile.LargeZipFile, ValueError):
        raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID") from None

    with archive:
        infos = archive.infolist()
        if not infos or len(infos) > MAX_RESEARCH_XLSX_ZIP_ENTRIES:
            raise ResearchXlsxContractError("RESEARCH_XLSX_STRUCTURE_LIMIT")
        names = _validate_archive_entries(infos)
        required = {
            _CONTENT_TYPES_PATH,
            _ROOT_RELATIONSHIPS_PATH,
            _WORKBOOK_PATH,
            _WORKBOOK_RELATIONSHIPS_PATH,
        }
        if not required.issubset(names):
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")

        roots: dict[str, Any] = {}
        for info in infos:
            if info.is_dir() or not info.filename.lower().endswith(_XML_SUFFIXES):
                continue
            try:
                content = archive.read(info)
            except (OSError, RuntimeError, zipfile.BadZipFile):
                raise ResearchXlsxContractError(
                    "RESEARCH_XLSX_INVALID"
                ) from None
            try:
                roots[info.filename] = DefusedElementTree.fromstring(
                    content,
                    forbid_dtd=True,
                    forbid_entities=True,
                    forbid_external=True,
                )
            except (DefusedXmlException, ValueError, SyntaxError):
                raise ResearchXlsxContractError(
                    "RESEARCH_XLSX_INVALID"
                ) from None

        if not required.issubset(roots):
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
        _validate_content_types(roots[_CONTENT_TYPES_PATH])
        relationship_maps = _validate_relationships(roots, names)
        _validate_root_workbook_relationship(
            relationship_maps[_ROOT_RELATIONSHIPS_PATH]
        )
        sheets = _read_workbook_sheets(
            roots[_WORKBOOK_PATH],
            relationship_maps[_WORKBOOK_RELATIONSHIPS_PATH],
            roots,
        )
        try:
            bad_member = archive.testzip()
        except (OSError, RuntimeError, zipfile.BadZipFile, zlib.error):
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID") from None
        if bad_member is not None:
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
        return _WorkbookPreflight(sheets=sheets)


def _validate_archive_entries(infos: list[zipfile.ZipInfo]) -> set[str]:
    names: set[str] = set()
    normalized_names: set[str] = set()
    total_size = 0
    for info in infos:
        name = info.filename
        normalized_name = unicodedata.normalize("NFC", name)
        normalized_key = normalized_name.casefold()
        if (
            not name
            or name != normalized_name
            or "\\" in name
            or "\x00" in name
            or any(ord(character) < 32 for character in name)
            or name.startswith("/")
            or any(part in {"", ".", ".."} for part in name.rstrip("/").split("/"))
            or (name.rstrip("/").split("/")[0].endswith(":"))
            or PurePosixPath(name).is_absolute()
            or name in names
            or normalized_key in normalized_names
        ):
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
        names.add(name)
        normalized_names.add(normalized_key)

        unix_mode = (info.external_attr >> 16) & 0xFFFF
        if unix_mode and stat.S_ISLNK(unix_mode):
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
        if info.flag_bits & 0x41:
            raise ResearchXlsxContractError("RESEARCH_XLSX_ENCRYPTED")
        if info.compress_type not in _ALLOWED_COMPRESSIONS:
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
        if (
            info.extract_version >= 45
            or info.create_version >= 45
            or _contains_zip64_extra(info.extra)
        ):
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
        if (
            info.file_size < 0
            or info.compress_size < 0
            or info.file_size > MAX_RESEARCH_XLSX_ZIP_ENTRY_BYTES
        ):
            raise ResearchXlsxContractError("RESEARCH_XLSX_STRUCTURE_LIMIT")
        total_size += info.file_size
        if total_size > MAX_RESEARCH_XLSX_ZIP_TOTAL_BYTES:
            raise ResearchXlsxContractError("RESEARCH_XLSX_STRUCTURE_LIMIT")
        if info.file_size and (
            info.compress_size == 0
            or info.file_size
            > info.compress_size * MAX_RESEARCH_XLSX_COMPRESSION_RATIO
        ):
            raise ResearchXlsxContractError("RESEARCH_XLSX_STRUCTURE_LIMIT")

        lowered = f"/{name.lower()}"
        if any(fragment in lowered for fragment in _ACTIVE_PART_FRAGMENTS):
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
    return names


def _contains_zip64_extra(extra: bytes) -> bool:
    offset = 0
    while offset < len(extra):
        if offset + 4 > len(extra):
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
        header_id, size = struct.unpack_from("<HH", extra, offset)
        offset += 4
        if offset + size > len(extra):
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
        if header_id == 0x0001:
            return True
        offset += size
    return False


def _validate_content_types(root: Any) -> None:
    workbook_overrides = 0
    seen_part_names: set[str] = set()
    for element in root.iter():
        local_name = _local_name(element.tag)
        content_type = element.attrib.get("ContentType", "").lower()
        part_name = element.attrib.get("PartName", "").lower()
        if any(
            fragment in content_type or fragment in part_name
            for fragment in _ACTIVE_CONTENT_TYPE_FRAGMENTS
        ):
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
        if local_name == "Default":
            extension = element.attrib.get("Extension", "").lower()
            if (
                _is_xml_content_type(content_type)
                and extension not in {"xml", "rels", "vml"}
            ):
                raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
            continue
        if local_name != "Override":
            continue
        if (
            not part_name.startswith("/")
            or part_name in seen_part_names
        ):
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
        if (
            _is_xml_content_type(content_type)
            and not part_name.endswith(_XML_SUFFIXES)
        ):
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
        seen_part_names.add(part_name)
        if part_name == "/xl/workbook.xml":
            workbook_overrides += 1
            if content_type != _WORKBOOK_CONTENT_TYPE:
                raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
    if workbook_overrides != 1:
        raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")


def _is_xml_content_type(content_type: str) -> bool:
    return content_type in _XML_CONTENT_TYPES or content_type.endswith("+xml")


def _validate_relationships(
    roots: dict[str, Any],
    names: set[str],
) -> dict[str, dict[str, _Relationship]]:
    result: dict[str, dict[str, _Relationship]] = {}
    for relationship_path, root in roots.items():
        if not relationship_path.lower().endswith(".rels"):
            continue
        source_path = _relationship_source_path(relationship_path)
        relationships: dict[str, _Relationship] = {}
        for element in root.iter():
            if _local_name(element.tag) != "Relationship":
                continue
            relationship_id = element.attrib.get("Id")
            relationship_type = element.attrib.get("Type")
            target = element.attrib.get("Target")
            target_mode = element.attrib.get("TargetMode", "Internal")
            if (
                not relationship_id
                or not relationship_type
                or target is None
                or relationship_id in relationships
                or target_mode.lower() == "external"
                or target_mode.lower() != "internal"
            ):
                raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
            relationship_kind = relationship_type.rsplit("/", 1)[-1].lower()
            if relationship_kind in _ACTIVE_RELATIONSHIP_TYPES:
                raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
            target_path = _resolve_relationship_target(source_path, target)
            if target_path and target_path not in names:
                raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
            if (
                target_path
                and relationship_kind in _OPENPYXL_XML_RELATIONSHIP_TYPES
                and not target_path.lower().endswith(_XML_SUFFIXES)
            ):
                raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
            relationships[relationship_id] = _Relationship(
                relationship_id=relationship_id,
                relationship_type=relationship_type,
                target_path=target_path,
            )
        result[relationship_path] = relationships
    return result


def _validate_root_workbook_relationship(
    relationships: dict[str, _Relationship],
) -> None:
    office_documents = tuple(
        relationship
        for relationship in relationships.values()
        if relationship.relationship_type.rsplit("/", 1)[-1]
        == "officeDocument"
    )
    if (
        len(office_documents) != 1
        or office_documents[0].target_path != _WORKBOOK_PATH
    ):
        raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")


def _relationship_source_path(relationship_path: str) -> str:
    if relationship_path == _ROOT_RELATIONSHIPS_PATH:
        return ""
    marker = "/_rels/"
    if marker not in relationship_path or not relationship_path.endswith(".rels"):
        raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
    prefix, filename = relationship_path.split(marker, 1)
    if not filename or "/" in filename:
        raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
    return f"{prefix}/{filename[:-5]}"


def _resolve_relationship_target(source_path: str, target: str) -> str:
    if (
        not target
        or "\\" in target
        or "\x00" in target
        or any(ord(character) < 32 for character in target)
    ):
        raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or parsed.query:
        raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
    decoded_path = unquote(parsed.path)
    if "\\" in decoded_path or "\x00" in decoded_path:
        raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
    if not decoded_path:
        if parsed.fragment:
            return ""
        raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
    if decoded_path.startswith("/"):
        candidate = decoded_path.lstrip("/")
    else:
        candidate = posixpath.join(posixpath.dirname(source_path), decoded_path)
    normalized = posixpath.normpath(candidate)
    if (
        normalized in {"", ".", ".."}
        or normalized.startswith("../")
        or normalized.startswith("/")
    ):
        raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
    return normalized


def _read_workbook_sheets(
    workbook_root: Any,
    relationships: dict[str, _Relationship],
    roots: dict[str, Any],
) -> tuple[_SheetPreflight, ...]:
    sheet_elements = [
        element
        for element in workbook_root.iter()
        if _local_name(element.tag) == "sheet"
    ]
    if not sheet_elements or len(sheet_elements) > MAX_RESEARCH_XLSX_SHEETS:
        raise ResearchXlsxContractError("RESEARCH_XLSX_STRUCTURE_LIMIT")
    seen_names: set[str] = set()
    sheets: list[_SheetPreflight] = []
    preliminary_dense_rows = 0
    for ordinal, element in enumerate(sheet_elements):
        name = element.attrib.get("name")
        visibility = element.attrib.get("state", "visible")
        relationship_id = element.attrib.get(
            f"{{{_RELATIONSHIP_NAMESPACE}}}id"
        )
        if (
            not isinstance(name, str)
            or not name
            or len(name) > 31
            or unicodedata.normalize("NFC", name) != name
            or any(
                unicodedata.category(character).startswith("C")
                for character in name
            )
            or name.casefold() in seen_names
            or visibility not in {"visible", "hidden", "veryHidden"}
            or not relationship_id
            or relationship_id not in relationships
        ):
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
        seen_names.add(name.casefold())
        relationship = relationships[relationship_id]
        if not relationship.relationship_type.endswith("/worksheet"):
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
        if relationship.target_path not in roots:
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
        sheet = _preflight_sheet(
            ordinal,
            name,
            visibility,
            relationship.target_path,
            roots[relationship.target_path],
        )
        if (
            sheet.first_declared_row is not None
            and sheet.last_declared_row is not None
        ):
            preliminary_dense_rows += (
                sheet.last_declared_row - sheet.first_declared_row
            )
            if preliminary_dense_rows > MAX_RESEARCH_XLSX_ROWS:
                raise ResearchXlsxContractError(
                    "RESEARCH_XLSX_STRUCTURE_LIMIT"
                )
        sheets.append(sheet)
    return tuple(sheets)


def _preflight_sheet(
    ordinal: int,
    name: str,
    visibility: str,
    part_path: str,
    root: Any,
) -> _SheetPreflight:
    declared_rows: list[int] = []
    last_declared_column = 0
    seen_coordinates: set[tuple[int, int]] = set()
    total_cell_count = 0
    for element in root.iter():
        local_name = _local_name(element.tag)
        if local_name == "f":
            formula_type = element.attrib.get("t")
            if formula_type not in {None, "normal", "shared"}:
                raise ResearchXlsxContractError(
                    "RESEARCH_XLSX_FORMULA_UNSUPPORTED"
                )
        if local_name == "c":
            total_cell_count += 1

    processed_cell_count = 0
    previous_row = 0
    for row_element in root.iter():
        if _local_name(row_element.tag) != "row":
            continue
        row_reference = row_element.attrib.get("r")
        try:
            declared_row = int(row_reference) if row_reference is not None else 0
        except (TypeError, ValueError):
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID") from None
        if row_reference != str(declared_row) or declared_row < 1:
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
        if declared_row > MAX_RESEARCH_XLSX_ROWS:
            raise ResearchXlsxContractError("RESEARCH_XLSX_STRUCTURE_LIMIT")
        if declared_row <= previous_row:
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
        previous_row = declared_row

        previous_column = 0
        for cell_element in row_element:
            if _local_name(cell_element.tag) != "c":
                continue
            processed_cell_count += 1
            coordinate = cell_element.attrib.get("r")
            if not coordinate:
                raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
            try:
                cell_row, cell_column = coordinate_to_tuple(coordinate)
            except (TypeError, ValueError):
                raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID") from None
            if (
                cell_row > MAX_RESEARCH_XLSX_ROWS
                or cell_column > MAX_RESEARCH_XLSX_COLUMNS
            ):
                raise ResearchXlsxContractError(
                    "RESEARCH_XLSX_STRUCTURE_LIMIT"
                )
            if (
                cell_row != declared_row
                or cell_column <= previous_column
                or (cell_row, cell_column) in seen_coordinates
            ):
                raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
            previous_column = cell_column
            seen_coordinates.add((cell_row, cell_column))
            if not _cell_has_declared_content(cell_element):
                continue
            declared_rows.append(cell_row)
            last_declared_column = max(last_declared_column, cell_column)

    if processed_cell_count != total_cell_count:
        raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")

    merged_ranges = _read_merged_ranges(root)
    subordinate_masks = _merged_subordinate_masks(merged_ranges)
    return _SheetPreflight(
        ordinal=ordinal,
        name=name,
        visibility=visibility,
        part_path=part_path,
        first_declared_row=min(declared_rows) if declared_rows else None,
        last_declared_row=max(declared_rows) if declared_rows else None,
        last_declared_column=last_declared_column,
        merged_ranges=merged_ranges,
        merged_subordinate_masks=subordinate_masks,
    )


def _cell_has_declared_content(element: Any) -> bool:
    for child in element:
        local_name = _local_name(child.tag)
        if local_name == "f":
            return True
        if local_name == "v" and child.text not in {None, ""}:
            return True
        if local_name == "is" and any(
            _local_name(descendant.tag) == "t"
            and descendant.text not in {None, ""}
            for descendant in child.iter()
        ):
            return True
    return False


def _read_merged_ranges(
    root: Any,
) -> tuple[tuple[int, int, int, int], ...]:
    result: list[tuple[int, int, int, int]] = []
    for element in root.iter():
        if _local_name(element.tag) != "mergeCell":
            continue
        reference = element.attrib.get("ref")
        if not reference:
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
        try:
            min_col, min_row, max_col, max_row = range_boundaries(reference)
        except (TypeError, ValueError):
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID") from None
        if (
            min_col < 1
            or min_row < 1
            or max_col < min_col
            or max_row < min_row
            or max_col > MAX_RESEARCH_XLSX_COLUMNS
            or max_row > MAX_RESEARCH_XLSX_ROWS
        ):
            raise ResearchXlsxContractError("RESEARCH_XLSX_STRUCTURE_LIMIT")
        result.append((min_col, min_row, max_col, max_row))
    return tuple(result)


def _merged_subordinate_masks(
    ranges: tuple[tuple[int, int, int, int], ...],
) -> dict[int, int]:
    occupied: dict[int, int] = {}
    subordinate: dict[int, int] = {}
    for min_col, min_row, max_col, max_row in ranges:
        mask = ((1 << (max_col - min_col + 1)) - 1) << (min_col - 1)
        for row in range(min_row, max_row + 1):
            if occupied.get(row, 0) & mask:
                raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
            occupied[row] = occupied.get(row, 0) | mask
            row_mask = mask
            if row == min_row:
                row_mask &= ~(1 << (min_col - 1))
            if row_mask:
                subordinate[row] = subordinate.get(row, 0) | row_mask
    return subordinate


def _parse_preflighted_workbook(
    raw: bytes,
    preflight: _WorkbookPreflight,
) -> NormalizedResearchXlsx:
    try:
        workbook = load_workbook(
            filename=io.BytesIO(raw),
            read_only=True,
            data_only=False,
            keep_links=False,
            keep_vba=False,
            rich_text=False,
        )
    except ResearchXlsxContractError:
        raise
    except Exception:
        raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID") from None

    try:
        if (
            len(workbook.sheetnames) != len(preflight.sheets)
            or len(workbook.worksheets) != len(preflight.sheets)
            or tuple(workbook.sheetnames)
            != tuple(sheet.name for sheet in preflight.sheets)
        ):
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
        date_system = "1904" if workbook.epoch == CALENDAR_MAC_1904 else "1900"
        sheet_descriptors: list[XlsxSheetDescriptor] = []
        rows_by_sheet: list[tuple[XlsxRow, ...]] = []
        total_dense_rows = 0
        total_non_empty = 0
        for worksheet, sheet_preflight in zip(
            workbook.worksheets,
            preflight.sheets,
        ):
            parsed = _parse_sheet(worksheet, sheet_preflight)
            if parsed is None:
                continue
            sheet_descriptor, rows = parsed
            total_dense_rows += sheet_descriptor.data_row_count
            total_non_empty += sheet_descriptor.non_empty_cell_count
            if total_dense_rows > MAX_RESEARCH_XLSX_ROWS:
                raise ResearchXlsxContractError(
                    "RESEARCH_XLSX_STRUCTURE_LIMIT"
                )
            if total_non_empty > MAX_RESEARCH_XLSX_NON_EMPTY_CELLS:
                raise ResearchXlsxContractError(
                    "RESEARCH_XLSX_CONTENT_LIMIT"
                )
            sheet_descriptors.append(sheet_descriptor)
            rows_by_sheet.append(rows)
        if not sheet_descriptors:
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
        descriptor = XlsxDescriptor(
            schema_version="research_xlsx_v1",
            date_system=date_system,
            workbook_sheet_count=len(preflight.sheets),
            empty_sheet_count=len(preflight.sheets) - len(sheet_descriptors),
            sheets=tuple(sheet_descriptors),
            total_record_count=sum(
                sheet.record_count for sheet in sheet_descriptors
            ),
            total_data_row_count=sum(
                sheet.data_row_count for sheet in sheet_descriptors
            ),
            total_non_empty_cell_count=sum(
                sheet.non_empty_cell_count for sheet in sheet_descriptors
            ),
            total_formula_like_cell_count=sum(
                sheet.formula_like_cell_count for sheet in sheet_descriptors
            ),
            total_formula_cell_count=sum(
                sheet.formula_cell_count for sheet in sheet_descriptors
            ),
            total_merged_range_count=sum(
                sheet.merged_range_count for sheet in sheet_descriptors
            ),
        )
        return build_normalized_research_xlsx(descriptor, rows_by_sheet)
    finally:
        workbook.close()


def _parse_sheet(
    worksheet: Any,
    preflight: _SheetPreflight,
) -> tuple[XlsxSheetDescriptor, tuple[XlsxRow, ...]] | None:
    if worksheet.title != preflight.name or worksheet.sheet_state != preflight.visibility:
        raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
    if preflight.last_declared_row is None:
        return None

    header_row_number: int | None = None
    headers: tuple[str, ...] = ()
    column_count = 0
    pending_rows: list[XlsxRow] = []
    last_non_empty_data_index = -1
    max_row = preflight.last_declared_row
    max_column = max(1, preflight.last_declared_column)
    for physical_row, cells in enumerate(
        worksheet.iter_rows(
            min_row=1,
            max_row=max_row,
            min_col=1,
            max_col=max_column,
            values_only=False,
        ),
        start=1,
    ):
        subordinate_mask = preflight.merged_subordinate_masks.get(
            physical_row,
            0,
        )
        values: list[str] = []
        formula_indexes: list[int] = []
        for column, cell in enumerate(cells, start=1):
            if subordinate_mask & (1 << (column - 1)):
                values.append("")
                continue
            value, is_formula = _normalize_cell(cell)
            values.append(value)
            if is_formula:
                formula_indexes.append(column - 1)

        if header_row_number is None:
            if not any(values):
                continue
            if formula_indexes:
                raise ResearchXlsxContractError(
                    "RESEARCH_XLSX_FORMULA_UNSUPPORTED"
                )
            header_row_number = physical_row
            column_count = max(
                index for index, value in enumerate(values, start=1) if value
            )
            if column_count > MAX_RESEARCH_XLSX_COLUMNS:
                raise ResearchXlsxContractError(
                    "RESEARCH_XLSX_STRUCTURE_LIMIT"
                )
            headers = tuple(value.strip() for value in values[:column_count])
            if (
                any(not header for header in headers)
                or len(set(headers)) != len(headers)
            ):
                raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
            continue

        if any(values[column_count:]):
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
        row_values = tuple(values[:column_count])
        row_formula_indexes = tuple(
            index for index in formula_indexes if index < column_count
        )
        pending_rows.append(
            XlsxRow(
                logical_row_number=len(pending_rows) + 1,
                physical_row_start=physical_row,
                physical_row_end=physical_row,
                values=row_values,
                formula_cell_indexes=row_formula_indexes,
            )
        )
        if any(row_values):
            last_non_empty_data_index = len(pending_rows) - 1

    if header_row_number is None:
        return None
    if last_non_empty_data_index >= 0:
        rows = tuple(pending_rows[: last_non_empty_data_index + 1])
    else:
        rows = ()
    physical_line_count = (
        rows[-1].physical_row_end if rows else header_row_number
    )
    missing_value_counts = tuple(
        sum(row.values[column] == "" for row in rows)
        for column in range(column_count)
    )
    non_empty_cell_count = len(headers) + sum(
        bool(value) for row in rows for value in row.values
    )
    formula_like_cell_count = sum(
        _is_formula_like(value) for value in headers
    ) + sum(
        _is_formula_like(value) for row in rows for value in row.values
    )
    formula_cell_count = sum(
        len(row.formula_cell_indexes) for row in rows
    )
    return (
        XlsxSheetDescriptor(
            ordinal=preflight.ordinal,
            name=preflight.name,
            visibility=preflight.visibility,
            headers=headers,
            header_row_start=header_row_number,
            header_row_end=header_row_number,
            physical_line_count=physical_line_count,
            record_count=1 + len(rows),
            data_row_count=len(rows),
            column_count=column_count,
            non_empty_cell_count=non_empty_cell_count,
            formula_like_cell_count=formula_like_cell_count,
            formula_cell_count=formula_cell_count,
            merged_range_count=len(preflight.merged_ranges),
            missing_value_counts=missing_value_counts,
        ),
        rows,
    )


def _normalize_cell(cell: Any) -> tuple[str, bool]:
    value = getattr(cell, "value", None)
    data_type = getattr(cell, "data_type", "n")
    if data_type == TYPE_FORMULA:
        if isinstance(value, (ArrayFormula, DataTableFormula)):
            raise ResearchXlsxContractError(
                "RESEARCH_XLSX_FORMULA_UNSUPPORTED"
            )
        if not isinstance(value, str) or not value.startswith("=") or value == "=":
            raise ResearchXlsxContractError(
                "RESEARCH_XLSX_FORMULA_UNSUPPORTED"
            )
        return _normalize_string(value), True
    if value is None:
        return "", False
    if isinstance(value, str):
        return _normalize_string(value), False
    if isinstance(value, bool):
        return ("true" if value else "false"), False
    if isinstance(value, datetime):
        return value.isoformat(), False
    if isinstance(value, date):
        return value.isoformat(), False
    if isinstance(value, time):
        return value.isoformat(), False
    if isinstance(value, timedelta):
        return _timedelta_iso(value), False
    if isinstance(value, int):
        return str(value), False
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
        return repr(value), False
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")
        return format(value, "f"), False
    raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")


def _normalize_string(value: str) -> str:
    normalized = unicodedata.normalize(
        "NFC",
        value.replace("\r\n", "\n").replace("\r", "\n"),
    )
    if (
        "\x00" in normalized
        or any(0xD800 <= ord(character) <= 0xDFFF for character in normalized)
        or len(normalized) > MAX_RESEARCH_XLSX_CELL_CODEPOINTS
    ):
        raise ResearchXlsxContractError("RESEARCH_XLSX_CONTENT_LIMIT")
    return normalized


def _timedelta_iso(value: timedelta) -> str:
    total_microseconds = (
        value.days * 86_400_000_000
        + value.seconds * 1_000_000
        + value.microseconds
    )
    sign = "-" if total_microseconds < 0 else ""
    total_microseconds = abs(total_microseconds)
    days, remainder = divmod(total_microseconds, 86_400_000_000)
    hours, remainder = divmod(remainder, 3_600_000_000)
    minutes, remainder = divmod(remainder, 60_000_000)
    seconds, microseconds = divmod(remainder, 1_000_000)
    date_part = f"{days}D" if days else ""
    time_parts = []
    if hours:
        time_parts.append(f"{hours}H")
    if minutes:
        time_parts.append(f"{minutes}M")
    if seconds or microseconds or not (date_part or time_parts):
        second_value = str(seconds)
        if microseconds:
            second_value += f".{microseconds:06d}".rstrip("0")
        time_parts.append(f"{second_value}S")
    time_part = f"T{''.join(time_parts)}" if time_parts else ""
    return f"{sign}P{date_part}{time_part}"


def _is_formula_like(value: str) -> bool:
    stripped = value.lstrip()
    return bool(stripped and stripped[0] in "=+-@")


def _local_name(tag: Any) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


__all__ = ["parse_research_xlsx_path"]
