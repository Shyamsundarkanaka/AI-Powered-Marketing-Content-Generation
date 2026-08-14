"""Word-document primitives for the Capstone II report builder.

Everything the report needs and python-docx does not give directly: chapter-scoped
headings, figure/table captions that also emit hidden TC fields, TOC / list-of-
figures / list-of-tables fields, and roman-then-arabic section page numbering.

House format, applied here rather than in the content modules:

    body text          Times New Roman 12 pt, 1.5 line spacing, justified, black
    chapter heading    Times New Roman 14 pt bold black
    section heading    Times New Roman 12 pt bold black
    table cells        10 pt single spaced
    caption            11 pt
    code listing       9 pt Consolas

Every run in the document is black. Only the figures carry colour, and they are
images rather than text.

Fields are written with a cached result so the document reads sensibly before the
user refreshes them; opening the file in Word and pressing Ctrl+A then F9 fills in
the real page numbers.
"""
from __future__ import annotations

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

BODY_FONT = "Times New Roman"
MONO_FONT = "Consolas"
BLACK = RGBColor(0x00, 0x00, 0x00)

BODY_SIZE = 12.0        # every paragraph of running text
BODY_SPACING = 1.5      # every paragraph of running text
CHAPTER_SIZE = 14.0     # "Chapter N: ..." and the front-matter headings
SECTION_SIZE = 12.0     # 1.1 and 1.1.1 headings
TABLE_SIZE = 10.0
CAPTION_SIZE = 10.5
CODE_SIZE = 9.0

HEADER_FILL = "D9D9D9"

# The pages before the table of contents keep the tighter spacing they were laid
# out with, so that the cover and the signature blocks stay on one page each.
FRONT_SPACING = 1.06
FRONT_SIZE = 11.5


# --------------------------------------------------------------------------- xml
def _el(tag, **attrs):
    e = OxmlElement(tag)
    for k, v in attrs.items():
        e.set(qn(k), v)
    return e


def add_field(paragraph, instr: str, cached: str = "", hidden: bool = False,
              italic: bool = False, size: float | None = None):
    """Insert a Word field: { instr } with an optional cached result."""
    def _run(children):
        r = OxmlElement("w:r")
        rpr = OxmlElement("w:rPr")
        if hidden:
            rpr.append(OxmlElement("w:vanish"))
        if italic:
            rpr.append(OxmlElement("w:i"))
        if size:
            sz = _el("w:sz", **{"w:val": str(int(size * 2))})
            rpr.append(sz)
        r.append(rpr)
        for c in children:
            r.append(c)
        paragraph._p.append(r)
        return r

    _run([_el("w:fldChar", **{"w:fldCharType": "begin"})])
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = instr
    _run([it])
    _run([_el("w:fldChar", **{"w:fldCharType": "separate"})])
    if cached:
        t = OxmlElement("w:t")
        t.set(qn("xml:space"), "preserve")
        t.text = cached
        _run([t])
    _run([_el("w:fldChar", **{"w:fldCharType": "end"})])


def _shade(cell, hexcolor):
    tcpr = cell._tc.get_or_add_tcPr()
    tcpr.append(_el("w:shd", **{"w:val": "clear", "w:color": "auto", "w:fill": hexcolor}))


def _cell_margins(table, top=18, bottom=18, left=60, right=60):
    tblpr = table._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for name, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        mar.append(_el(f"w:{name}", **{"w:w": str(val), "w:type": "dxa"}))
    tblpr.append(mar)


def _repeat_header(row):
    trpr = row._tr.get_or_add_trPr()
    trpr.append(_el("w:tblHeader", **{"w:val": "true"}))


# --------------------------------------------------------------------------- doc
class Report:
    def __init__(self, figdir: str):
        self.doc = Document()
        self.figdir = figdir
        self._entries: dict[str, list[tuple[str, str]]] = {}
        self._placeholders: dict[str, object] = {}
        self._bm_id = 1000
        # The front matter is laid out first, so start in front-matter mode.
        self.body_size = FRONT_SIZE
        self.body_spacing = FRONT_SPACING
        self._setup_styles()
        self._setup_page()

    # -- setup ------------------------------------------------------------
    def _setup_page(self):
        s = self.doc.sections[0]
        s.page_width, s.page_height = Inches(8.27), Inches(11.69)   # A4
        s.left_margin = s.right_margin = Inches(1.0)
        s.top_margin = s.bottom_margin = Inches(1.0)

    def _setup_styles(self):
        st = self.doc.styles
        n = st["Normal"]
        n.font.name = BODY_FONT
        n.font.size = Pt(BODY_SIZE)
        n.font.color.rgb = BLACK
        n._element.rPr.rFonts.set(qn("w:eastAsia"), BODY_FONT)
        pf = n.paragraph_format
        pf.line_spacing = BODY_SPACING
        pf.space_after = Pt(3)
        pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        for name, size, before, after in (("Heading 1", CHAPTER_SIZE, 0, 8),
                                          ("Heading 2", SECTION_SIZE, 7, 2),
                                          ("Heading 3", SECTION_SIZE, 6, 2)):
            h = st[name]
            h.font.name = BODY_FONT
            h.font.size = Pt(size)
            h.font.bold = True
            h.font.color.rgb = BLACK
            h.paragraph_format.space_before = Pt(before)
            h.paragraph_format.space_after = Pt(after)
            h.paragraph_format.line_spacing = 1.15
            h.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
            h.paragraph_format.keep_with_next = True
        self._setup_toc_styles()

    def _setup_toc_styles(self):
        """Word builds the contents list from the TOC n styles, which inherit from
        Normal. Left alone they would come out at 1.5 line spacing and run to three
        pages; the list is a navigation aid, so it is single spaced."""
        from docx.enum.style import WD_STYLE_TYPE
        st = self.doc.styles
        for level, indent in ((1, 0.0), (2, 0.22), (3, 0.44)):
            name = f"TOC {level}"
            try:
                s = st[name]
            except KeyError:
                s = st.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
            s.font.name = BODY_FONT
            s.font.size = Pt(11)
            s.font.color.rgb = BLACK
            pf = s.paragraph_format
            pf.line_spacing = 1.0
            pf.space_before = Pt(0)
            pf.space_after = Pt(2)
            pf.left_indent = Inches(indent)

    def start_running_text(self):
        """Switch from front-matter metrics to the 12 pt / 1.5 house format."""
        self.body_size = BODY_SIZE
        self.body_spacing = BODY_SPACING

    # -- primitives -------------------------------------------------------
    def para(self, text="", *, size=None, bold=False, italic=False, align="justify",
             space_after=3, space_before=0, color=None, font=None, indent=0,
             line_spacing=None, keep_with_next=False):
        p = self.doc.add_paragraph()
        pf = p.paragraph_format
        pf.alignment = {"justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
                        "left": WD_ALIGN_PARAGRAPH.LEFT,
                        "center": WD_ALIGN_PARAGRAPH.CENTER,
                        "right": WD_ALIGN_PARAGRAPH.RIGHT}[align]
        pf.space_after = Pt(space_after)
        pf.space_before = Pt(space_before)
        pf.line_spacing = self.body_spacing if line_spacing is None else line_spacing
        pf.keep_with_next = keep_with_next
        if indent:
            pf.left_indent = Inches(indent)
        if text:
            self._runs(p, text, self.body_size if size is None else size,
                       bold, italic, color, font)
        return p

    def _runs(self, p, text, size, bold, italic, color, font):
        """Bold with **…**, italic with *…*, monospace with `…`."""
        import re
        parts = re.split(r"(\*\*.+?\*\*|`[^`]+?`|\*[^*\n]+?\*)", text)
        for part in parts:
            if not part:
                continue
            b, i, f = bold, italic, font
            if part.startswith("**") and part.endswith("**"):
                part, b = part[2:-2], True
            elif part.startswith("`") and part.endswith("`"):
                part, f = part[1:-1], MONO_FONT
            elif len(part) > 2 and part.startswith("*") and part.endswith("*"):
                part, i = part[1:-1], True
            r = p.add_run(part)
            r.font.size = Pt(size if f != MONO_FONT else size - 1.5)
            r.font.bold = b
            r.font.italic = i
            r.font.name = f or BODY_FONT
            r.font.color.rgb = color or BLACK

    def h1(self, text, *, page_break=True, toc=True):
        if getattr(self, "_skip_next_break", False):
            page_break = False
            self._skip_next_break = False
        if page_break:
            self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        p = self.doc.add_paragraph(style="Heading 1" if toc else "Normal")
        r = p.add_run(text)
        if not toc:
            # Front-matter headings are not TOC entries, but they carry the same
            # 14 pt bold black look as a chapter heading.
            r.font.size, r.font.bold = Pt(CHAPTER_SIZE), True
            r.font.name, r.font.color.rgb = BODY_FONT, BLACK
            p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.space_after = Pt(10)
        return p

    def h2(self, text):
        return self.doc.add_paragraph(text, style="Heading 2")

    def h3(self, text):
        return self.doc.add_paragraph(text, style="Heading 3")

    def bullets(self, items, *, size=None, indent=0.15, line_spacing=None,
                space_after=2):
        for it in items:
            p = self.doc.add_paragraph(style="List Bullet")
            pf = p.paragraph_format
            pf.left_indent = Inches(indent + 0.25)
            pf.space_after = Pt(space_after)
            pf.line_spacing = self.body_spacing if line_spacing is None else line_spacing
            pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            self._runs(p, it, self.body_size if size is None else size,
                       False, False, None, None)

    def numbered(self, items, *, size=None, indent=0.15, line_spacing=None,
                 space_after=2):
        for it in items:
            p = self.doc.add_paragraph(style="List Number")
            pf = p.paragraph_format
            pf.left_indent = Inches(indent + 0.25)
            pf.space_after = Pt(space_after)
            pf.line_spacing = self.body_spacing if line_spacing is None else line_spacing
            pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            self._runs(p, it, self.body_size if size is None else size,
                       False, False, None, None)

    def pagebreak(self):
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    def spacer(self, pts=10):
        self.para(space_after=pts)

    # -- captions ---------------------------------------------------------
    def _caption(self, text, kind):
        p = self.doc.add_paragraph()
        pf = p.paragraph_format
        pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf.space_before = Pt(2)
        pf.space_after = Pt(4)
        pf.line_spacing = 1.0
        pf.keep_with_next = (kind == "T")
        num, _, rest = text.partition(":")
        r = p.add_run(num + ":")
        r.font.size, r.font.bold, r.font.name = Pt(CAPTION_SIZE), True, BODY_FONT
        r.font.color.rgb = BLACK
        r2 = p.add_run(rest)
        r2.font.size, r2.font.name = Pt(CAPTION_SIZE), BODY_FONT
        r2.font.color.rgb = BLACK
        self._bookmark(p, kind, text)
        return p

    def _bookmark(self, paragraph, kind, text):
        """Bookmark the caption so the front-matter lists can PAGEREF it."""
        entries = self._entries.setdefault(kind, [])
        name = f"_{'Fig' if kind == 'F' else 'Tbl'}{len(entries) + 1:03d}"
        start = _el("w:bookmarkStart", **{"w:id": str(self._bm_id), "w:name": name})
        end = _el("w:bookmarkEnd", **{"w:id": str(self._bm_id)})
        self._bm_id += 1
        paragraph._p.insert(0, start)
        paragraph._p.append(end)
        entries.append((name, text))

    # -- front-matter lists ----------------------------------------------
    def list_placeholder(self, kind):
        """Reserve the spot where the list of figures/tables will be built."""
        p = self.doc.add_paragraph()
        self._placeholders[kind] = p
        return p

    def build_lists(self):
        from docx.enum.text import WD_TAB_ALIGNMENT, WD_TAB_LEADER
        for kind, anchor in self._placeholders.items():
            prev = anchor._p
            for name, text in self._entries.get(kind, []):
                p = self.doc.add_paragraph()
                pf = p.paragraph_format
                pf.space_after = Pt(2)
                pf.line_spacing = 1.0
                pf.left_indent = Inches(0.0)
                pf.first_line_indent = Inches(0)
                pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
                pf.tab_stops.add_tab_stop(Inches(6.27), WD_TAB_ALIGNMENT.RIGHT,
                                          WD_TAB_LEADER.DOTS)
                # Lists read better with the caption's first sentence only.
                short = text
                head, sep, rest = text.partition(": ")
                if sep:
                    first = rest.split(". ")[0].rstrip(".")
                    if len(first) > 82:
                        first = first[:79].rsplit(" ", 1)[0] + "…"
                    short = f"{head}: {first}"
                run = p.add_run(short + "\t")
                run.font.size, run.font.name = Pt(11), BODY_FONT
                add_field(p, f" PAGEREF {name} \\h ", cached="1")
                for rr in p.runs:
                    rr.font.size, rr.font.name = Pt(11), BODY_FONT
                    rr.font.color.rgb = BLACK
                prev.addnext(p._p)
                prev = p._p
            anchor._p.getparent().remove(anchor._p)

    def fig(self, filename, caption, width_in=4.4):
        """Place a figure at a literal display width, in inches."""
        p = self.doc.add_paragraph()
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.keep_with_next = True
        p.add_run().add_picture(f"{self.figdir}/{filename}",
                                width=Inches(min(width_in, 6.27)))
        self._caption(caption, "F")

    def tbl(self, caption, headers, rows, *, widths=None, size=TABLE_SIZE,
            header_size=TABLE_SIZE, space_after=6):
        if caption:
            self._caption(caption, "T")
        t = self.doc.add_table(rows=1, cols=len(headers))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        _cell_margins(t)
        hdr = t.rows[0]
        _repeat_header(hdr)
        for i, h in enumerate(headers):
            c = hdr.cells[i]
            c.text = ""
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
            self._runs(p, h, header_size, True, False, None, None)
            _shade(c, HEADER_FILL)
        for row in rows:
            cells = t.add_row().cells
            for i, val in enumerate(row):
                c = cells[i]
                c.text = ""
                p = c.paragraphs[0]
                p.paragraph_format.space_after = Pt(1)
                p.paragraph_format.space_before = Pt(1)
                p.paragraph_format.line_spacing = 1.0
                p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
                self._runs(p, str(val), size, False, False, None, None)
        if widths:
            total = sum(widths)
            usable = 6.27
            for r in t.rows:
                for i, w in enumerate(widths):
                    r.cells[i].width = Inches(usable * w / total)
        self.para(space_after=space_after, line_spacing=1.0)
        return t

    def code(self, lines, *, size=CODE_SIZE):
        for ln in lines:
            p = self.doc.add_paragraph()
            pf = p.paragraph_format
            pf.left_indent = Inches(0.35)
            pf.space_after = Pt(0)
            pf.space_before = Pt(0)
            pf.line_spacing = 1.0
            pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(ln if ln else " ")
            r.font.name = MONO_FONT
            r.font.size = Pt(size)
            r.font.color.rgb = BLACK
        self.para(space_after=8, line_spacing=1.0)

    def quote(self, text, *, size=None):
        p = self.doc.add_paragraph()
        pf = p.paragraph_format
        pf.left_indent = Inches(0.4)
        pf.right_indent = Inches(0.3)
        pf.space_before = Pt(3)
        pf.space_after = Pt(6)
        pf.line_spacing = self.body_spacing
        pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        self._runs(p, text, self.body_size if size is None else size,
                   False, True, None, None)

    def reference_list(self, refs):
        """IEEE-numbered references: hanging indent, single spaced, 12 pt."""
        for i, ref in enumerate(refs, start=1):
            p = self.doc.add_paragraph()
            pf = p.paragraph_format
            pf.left_indent = Inches(0.45)
            pf.first_line_indent = Inches(-0.45)
            pf.space_after = Pt(3)
            pf.line_spacing = 1.0
            pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            for text in (f"[{i}]\t", ref):
                run = p.add_run(text)
                run.font.size = Pt(11)
                run.font.name = BODY_FONT
                run.font.color.rgb = BLACK

    # -- sections / page numbers -----------------------------------------
    def start_body_section(self):
        """Front matter = lower-roman; body = arabic restarting at 1."""
        front = self.doc.sections[0]
        self._page_numbers(front, "lowerRoman", restart=1)
        new = self.doc.add_section(WD_SECTION.NEW_PAGE)
        new.page_width, new.page_height = Inches(8.27), Inches(11.69)
        new.left_margin = new.right_margin = Inches(1.0)
        new.top_margin = new.bottom_margin = Inches(1.0)
        new.footer.is_linked_to_previous = False
        self._page_numbers(new, "decimal", restart=1)
        self._skip_next_break = True
        return new

    def _page_numbers(self, section, fmt, restart=None):
        sectpr = section._sectPr
        # add_section() clones the previous sectPr, so an inherited pgNumType would
        # win over the one appended here and the body would keep roman numerals.
        for existing in sectpr.findall(qn("w:pgNumType")):
            sectpr.remove(existing)
        attrs = {"w:fmt": fmt}
        if restart is not None:
            attrs["w:start"] = str(restart)
        node = _el("w:pgNumType", **attrs)
        anchor = sectpr.find(qn("w:pgMar"))
        if anchor is not None:
            anchor.addnext(node)
        else:
            sectpr.append(node)
        footer = section.footer
        footer.is_linked_to_previous = False
        p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        p.text = ""
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_field(p, " PAGE ", cached="1")
        for r in p.runs:
            r.font.size = Pt(11)
            r.font.name = BODY_FONT
            r.font.color.rgb = BLACK

    def save(self, path):
        self.doc.save(path)
        return path
