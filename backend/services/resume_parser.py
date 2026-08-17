"""PDF 解析（无 AI，无 LangChain）。

将 PDF 转为可处理文本，保留基本段落结构。V1 不要求完美排版、图片识别、复杂表格。
"""
import io

import pdfplumber


def parse_pdf(file_bytes: bytes) -> str:
    """从 PDF 二进制内容提取纯文本。"""
    parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text:
                parts.append(text)
    return "\n\n".join(parts).strip()
