"""把 PRD 的 Markdown 渲染成中文排版的 DOCX。"""

import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

# 脚本放在 scripts/，源文件与输出都在 docs/，从仓库任意位置运行都可
DOCS = Path(__file__).resolve().parent.parent / "docs"
SRC = DOCS / "PRD.md"
DST = DOCS / "PRD.docx"

BODY_EA = "宋体"
HEAD_EA = "黑体"
CODE_FONT = "Consolas"


def set_run_font(run, ea_font, ascii_font, size_pt, bold=False, color=None):
    run.font.name = ascii_font
    run.font.size = Pt(size_pt)
    run.bold = bold
    if color is not None:
        run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), ea_font)
    rfonts.set(qn("w:ascii"), ascii_font)
    rfonts.set(qn("w:hAnsi"), ascii_font)


INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")


def add_inline(paragraph, text, ea_font=BODY_EA, ascii_font="Times New Roman",
               size_pt=12, base_bold=False):
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            run = paragraph.add_run(part[2:-2])
            set_run_font(run, ea_font, ascii_font, size_pt, True)
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            run = paragraph.add_run(part[1:-1])
            set_run_font(run, "Consolas", CODE_FONT, size_pt - 1, base_bold)
        else:
            run = paragraph.add_run(part)
            set_run_font(run, ea_font, ascii_font, size_pt, base_bold)


def setup_page(doc):
    section = doc.sections[0]
    section.page_height = Cm(29.7)
    section.page_width = Cm(21.0)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(3.17)
    section.right_margin = Cm(2.54)

    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), BODY_EA)
    pf = normal.paragraph_format
    pf.line_spacing = 1.5
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)


def add_heading(doc, text, level):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    if level == 1:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf.space_before = Pt(6)
        pf.space_after = Pt(18)
        pf.line_spacing = 1.5
        add_inline(p, text, HEAD_EA, "Times New Roman", 22, True)
    elif level == 2:
        pf.space_before = Pt(18)
        pf.space_after = Pt(8)
        pf.line_spacing = 1.5
        pf.keep_with_next = True
        add_inline(p, text, HEAD_EA, "Times New Roman", 15, True)
    else:
        pf.space_before = Pt(12)
        pf.space_after = Pt(6)
        pf.line_spacing = 1.5
        pf.keep_with_next = True
        add_inline(p, text, HEAD_EA, "Times New Roman", 13, True)
    return p


def add_body(doc, text, indent=True, style=None):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = 1.5
    pf.space_before = Pt(0)
    pf.space_after = Pt(6)
    if indent:
        pf.first_line_indent = Pt(24)
    if style == "bullet":
        pf.left_indent = Pt(24)
        pf.first_line_indent = Pt(-12)
        add_inline(p, "• " + text)
    elif style == "number":
        pf.left_indent = Pt(24)
        pf.first_line_indent = Pt(-12)
        add_inline(p, text)
    elif style == "quote":
        pf.left_indent = Pt(24)
        pf.first_line_indent = Pt(0)
        pf.space_before = Pt(6)
        add_inline(p, text)
    else:
        add_inline(p, text)
    return p


def is_sep_row(cells):
    return all(re.fullmatch(r":?-{2,}:?", c.strip()) for c in cells if c.strip())


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def add_table(doc, rows):
    header, body = rows[0], rows[1:]
    ncols = max(len(r) for r in rows)
    table = doc.add_table(rows=1, cols=ncols)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True

    for idx in range(ncols):
        cell = table.rows[0].cells[idx]
        cell.text = ""
        p = cell.paragraphs[0]
        p.paragraph_format.line_spacing = 1.15
        p.paragraph_format.space_after = Pt(2)
        text = header[idx] if idx < len(header) else ""
        add_inline(p, text, HEAD_EA, "Times New Roman", 9, True)

    for row in body:
        cells = table.add_row().cells
        for idx in range(ncols):
            cell = cells[idx]
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.space_after = Pt(2)
            text = row[idx] if idx < len(row) else ""
            add_inline(p, text, BODY_EA, "Times New Roman", 9)

    doc.add_paragraph()
    return table


def add_code(doc, lines):
    for line in lines:
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.line_spacing = 1.15
        pf.space_before = Pt(0)
        pf.space_after = Pt(0)
        pf.left_indent = Pt(12)
        run = p.add_run(line if line else " ")
        set_run_font(run, "Consolas", CODE_FONT, 9)
    doc.add_paragraph()


def main():
    text = SRC.read_text(encoding="utf-8")
    lines = text.splitlines()

    doc = Document()
    setup_page(doc)

    i = 0
    table_buf = []
    code_buf = []
    in_code = False
    quote_buf = []

    def flush_table():
        if table_buf:
            add_table(doc, table_buf[:])
            table_buf.clear()

    def flush_quote():
        if quote_buf:
            add_body(doc, " ".join(quote_buf), indent=False, style="quote")
            quote_buf.clear()

    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()

        if line.strip().startswith("```"):
            if in_code:
                add_code(doc, code_buf)
                code_buf.clear()
                in_code = False
            else:
                flush_table()
                flush_quote()
                in_code = True
            i += 1
            continue

        if in_code:
            code_buf.append(line)
            i += 1
            continue

        if line.startswith("|"):
            flush_quote()
            cells = split_row(line)
            if not is_sep_row(cells):
                table_buf.append(cells)
            i += 1
            continue

        flush_table()

        if line.startswith(">"):
            quote_buf.append(line.lstrip(">").strip())
            i += 1
            continue
        flush_quote()

        if not line.strip() or line.strip() == "---":
            i += 1
            continue

        if line.startswith("# "):
            add_heading(doc, line[2:].strip(), 1)
        elif line.startswith("## "):
            add_heading(doc, line[3:].strip(), 2)
        elif line.startswith("### "):
            add_heading(doc, line[4:].strip(), 3)
        elif re.match(r"^\s*[-*]\s+", line):
            add_body(doc, re.sub(r"^\s*[-*]\s+", "", line), indent=False, style="bullet")
        elif re.match(r"^\s*\d+\.\s+", line):
            add_body(doc, line.strip(), indent=False, style="number")
        else:
            add_body(doc, line.strip())

        i += 1

    flush_table()
    flush_quote()
    if code_buf:
        add_code(doc, code_buf)

    doc.save(DST)

    check = Document(DST)
    print(f"段落数: {len(check.paragraphs)}")
    print(f"表格数: {len(check.tables)}")
    print(f"字符数: {sum(len(p.text) for p in check.paragraphs)}")
    print(f"输出: {DST.resolve()}")


if __name__ == "__main__":
    main()
