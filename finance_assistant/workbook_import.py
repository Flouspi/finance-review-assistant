"""Read the supplied knowledge workbook without modifying it or executing cells."""
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .documents import InputError

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
DATA_SHEETS = {"01_法规条款", "02_监管规则", "03_监管案例", "04_市场披露", "05_司法案例", "06_风险规则"}


def read_sheets(path):
    """Read text, shared strings and cached scalar values; reject formulas.

    The source workbook stores its dates as text and has no formulas. This is
    a read-only importer for this schema, not a general Excel calculation engine.
    """
    with ZipFile(path) as archive:
        if sum(x.file_size for x in archive.infolist()) > 60 * 1024 * 1024:
            raise InputError("知识库工作簿解压后过大。")
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ["".join(t.text or "" for t in n.findall(".//s:t", NS))
                       for n in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("s:si", NS)]
        relationships = {r.get("Id"): r.get("Target") for r in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
                         if r.get("TargetMode") != "External"}
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        for sheet in workbook.findall("s:sheets/s:sheet", NS):
            name = sheet.get("name")
            target = relationships.get(sheet.get(RID), "")
            target = target.lstrip("/") if target.startswith("/") else "xl/" + target
            if ".." in PurePosixPath(target).parts or not target.startswith("xl/"):
                raise InputError("工作簿引用了异常的工作表路径。")
            xml = ET.fromstring(archive.read(target))
            rows = []
            for row in xml.findall("s:sheetData/s:row", NS):
                cells = {}
                for cell in row.findall("s:c", NS):
                    ref = cell.get("r", "")
                    if cell.find("s:f", NS) is not None:
                        raise InputError(f"{name}!{ref} 含公式；此知识库导入器不计算公式，请先提供静态值副本。")
                    kind = cell.get("t")
                    value = cell.findtext("s:v", "", NS)
                    if kind == "s":
                        value = strings[int(value)] if value else ""
                    elif kind == "inlineStr":
                        value = "".join(t.text or "" for t in cell.findall(".//s:t", NS))
                    elif kind == "e":
                        raise InputError(f"{name}!{ref} 包含表格错误值。")
                    value = value.strip()
                    if value:
                        cells[re.sub(r"\d", "", ref)] = value
                if cells:
                    rows.append((int(row.get("r")), cells))
            yield name, rows


def convert_workbook(path):
    path = Path(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    records, skipped, counts, seen = [], [], Counter(), set()
    for name, rows in read_sheets(path):
        if name not in DATA_SHEETS:
            skipped.append(name)
            continue
        if not rows:
            raise InputError(f"{name} 为空。")
        headers = rows[0][1]
        if not {"KB_ID", "RULE_ID"}.intersection(headers.values()) or "检索文本" not in headers.values():
            raise InputError(f"{name} 缺少记录 ID 或检索文本列。")
        for row_no, cells in rows[1:]:
            fields = {header: cells.get(col, "") for col, header in headers.items()}
            record_id = fields.get("KB_ID") or fields.get("RULE_ID")
            if not record_id:
                raise InputError(f"{name} 第 {row_no} 行缺少记录 ID，导入停止以免遗漏。")
            if record_id in seen:
                raise InputError(f"重复知识记录 ID：{record_id}")
            seen.add(record_id)
            title = next((fields.get(key) for key in ("文件名称", "案例名称", "公告标题", "风险名称") if fields.get(key)), record_id)
            evidence_type = fields.get("数据层级") or "风险规则（人工整理的审查线索）"
            verification = fields.get("核验状态") or "人工整理规则，未独立核验"
            # Keep source values, but do not turn workbook guidance into system instructions.
            text = "\n".join(f"{key}：{value}" for key, value in fields.items() if value and key != "检索文本")
            records.append({"id": record_id, "title": title, "source": path.name,
                            "sheet": name, "row": row_no, "location": f"{name} 第 {row_no} 行",
                            "source_sha256": digest, "source_url": fields.get("来源URL", ""),
                            "evidence_type": evidence_type, "verification_status": verification,
                            "text": text, "retrieval_text": fields["检索文本"], "fields": fields})
            counts[name] += 1
    if not records:
        raise InputError("工作簿没有可导入的知识记录。")
    return records, {"source": path.name, "source_sha256": digest, "record_count": len(records),
                     "sheets": dict(counts), "excluded_sheets": skipped,
                     "note": "保留原表核验状态；本次未逐条核验法规时效性、链接或案例真实性。"}


def write_records(records, output):
    output = Path(output)
    content = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    if output.exists():
        if output.read_text(encoding="utf-8") == content:
            return
        raise InputError("目标知识库文件已存在且内容不同，请使用新的版本文件名。")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        handle.write(content)
