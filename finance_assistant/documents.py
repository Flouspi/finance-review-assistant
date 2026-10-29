from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

SUPPORTED = {".txt", ".md", ".csv", ".pdf", ".docx"}
MAX_BYTES = 15 * 1024 * 1024


class InputError(ValueError):
    pass


def extract(name: str, data: bytes) -> str:
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED:
        raise InputError(f"不支持 {suffix}；请使用 TXT、MD、CSV、PDF 或 DOCX。图片、音视频和旧版 DOC 需先转换为文本。")
    if len(data) > MAX_BYTES:
        raise InputError(f"{name} 超过 15 MB，请拆分后上传。")
    try:
        if suffix == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted:
                raise InputError(f"{name} 已加密，请上传解密后的副本。")
            parts = []
            for i, page in enumerate(reader.pages, 1):
                content = (page.extract_text() or "").strip()
                if not content:
                    raise InputError(f"{name} 第 {i} 页无可提取文字（可能是扫描页或空白页），请先 OCR 或移除空白页后再上传，以免遗漏内容。")
                parts.append(f"[第 {i} 页]\n{content}")
            text = "\n\n".join(parts)
        elif suffix == ".docx":
            from docx import Document
            # Bound expanded size before XML parsing.
            with ZipFile(BytesIO(data)) as archive:
                if sum(x.file_size for x in archive.infolist()) > 60 * 1024 * 1024:
                    raise InputError(f"{name} 解压后过大，请拆分文件。")
            doc = Document(BytesIO(data))
            parts = []
            from docx.table import Table
            from docx.text.paragraph import Paragraph
            for block in doc.iter_inner_content():
                if isinstance(block, Paragraph):
                    parts.append(block.text)
                elif isinstance(block, Table):
                    parts.extend(" | ".join(cell.text for cell in row.cells) for row in block.rows)
            text = "\n".join(parts)
        else:
            for encoding in ("utf-8-sig", "gb18030"):
                try:
                    text = data.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise InputError(f"{name} 无法解码，请转为 UTF-8。")
    except InputError:
        raise
    except Exception:
        raise InputError(f"无法解析 {name}，请检查格式或重新导出为文本。") from None
    if not text.strip():
        raise InputError(f"{name} 没有可提取文字，请检查文件或先进行 OCR。")
    return text.strip()


def extract_uploads(files: list[dict]) -> str:
    if len(files) > 3:
        raise InputError("最多同时上传 3 个文件，与原应用设置一致。")
    return "\n\n".join(f"【材料：{f['name']}】\n{extract(f['name'], f['data'])}" for f in files)
