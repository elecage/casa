"""표 한 장짜리 PDF를 만드는 아주 작은 생성기.

바깥 의존성이 없다. 글꼴은 PDF 표준 글꼴 하나만 쓴다.

    from vendor.minipdf import write_table
    write_table("out.pdf", "제목", [("이름", "값"), ...])
"""

from __future__ import annotations

from pathlib import Path


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_table(path, title: str, rows) -> None:
    lines = [f"BT /F1 14 Tf 40 780 Td ({_escape(title)}) Tj ET"]
    y = 750
    for left, right in rows:
        lines.append(
            f"BT /F1 10 Tf 40 {y} Td ({_escape(str(left))}) Tj ET")
        lines.append(
            f"BT /F1 10 Tf 300 {y} Td ({_escape(str(right))}) Tj ET")
        y -= 16
        if y < 60:
            break
    stream = "\n".join(lines).encode("latin-1", "replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
        + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    start = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{start}\n%%EOF\n").encode()
    Path(path).write_bytes(bytes(out))
