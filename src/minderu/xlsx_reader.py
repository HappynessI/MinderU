from __future__ import annotations

from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def _shared_strings(zf: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for si in root.findall("a:si", NS):
        values.append("".join(t.text or "" for t in si.findall(".//a:t", NS)))
    return values


def read_first_sheet(path: str | Path) -> list[dict[str, str]]:
    with ZipFile(path) as zf:
        shared = _shared_strings(zf)
        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        sheet = workbook.find("a:sheets/a:sheet", NS)
        if sheet is None:
            return []
        rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        target = "xl/" + rid_to_target[rid].lstrip("/")
        root = ET.fromstring(zf.read(target))
        rows: list[list[str]] = []
        for row in root.findall("a:sheetData/a:row", NS):
            by_col: dict[int, str] = {}
            for cell in row.findall("a:c", NS):
                ref = cell.attrib.get("r", "")
                col_idx = _col_index(ref)
                value = cell.find("a:v", NS)
                text = "" if value is None else value.text or ""
                if cell.attrib.get("t") == "s" and text:
                    text = shared[int(text)]
                by_col[col_idx] = text
            if not by_col:
                continue
            values = [by_col.get(i, "") for i in range(max(by_col) + 1)]
            if any(values):
                rows.append(values)
    if not rows:
        return []
    headers = rows[0]
    return [{headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))} for row in rows[1:]]


def _col_index(cell_ref: str) -> int:
    m = re.match(r"([A-Z]+)", cell_ref)
    if not m:
        return 0
    value = 0
    for ch in m.group(1):
        value = value * 26 + (ord(ch) - ord("A") + 1)
    return value - 1
