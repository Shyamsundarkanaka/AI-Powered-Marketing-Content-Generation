# Capstone Project II — report sources

`Capstone_II_Report.docx` is the deliverable. Everything else here regenerates it.

## Regenerating

```bash
venv\Scripts\python.exe docs/capstone2_report/build_report.py     # writes the .docx
powershell -File docs/capstone2_report/finalize_fields.ps1        # refreshes TOC + page numbers
```

`finalize_fields.ps1` needs Microsoft Word installed. Without it, open the document
in Word, press `Ctrl+A` then `F9`, and choose "Update entire table" for the contents
list. It prints the page and word count when it finishes.

`report_stats.ps1` prints the page each chapter starts on — useful when checking the
report against the programme's page budget.

## House format

Applied centrally in `docbuild.py`, not in the content modules:

| Element | Format |
|---|---|
| Body text | Times New Roman 12 pt, 1.5 line spacing, justified, black |
| Chapter headings | Times New Roman 14 pt bold black |
| Section headings (1.1, 1.1.1) | Times New Roman 12 pt bold black |
| Table cells | 9–9.5 pt, single spaced, grey header fill |
| Figure/table captions | 10.5 pt |
| Code listings | 9 pt Consolas |
| References | 11 pt, single spaced, hanging indent |
| Table of contents | levels 1–2, single spaced |

Every run in the document is black. Only the figures carry colour, because they are
images rather than text. The pages before the table of contents keep the tighter
spacing they were laid out with, so the cover and the signature blocks stay on one
page each — `Report.start_running_text()` switches to the 12 pt / 1.5 metrics at the
contents page.

## Layout of the sources

| File | Contains |
|---|---|
| `docbuild.py` | Word primitives: styles, headings, captions with bookmarks, tables, code listings, TOC/PAGEREF fields, roman-then-arabic page numbering |
| `build_report.py` | Assembles the document and stitches in the list of tables and list of figures |
| `content_front.py` | Cover, declaration, ownership, certificate, acknowledgement, similarity index, abbreviations, abstract |
| `content_ch1_4.py` | Introduction, Literature Review, Problem Statement, Objectives |
| `content_ch5_7.py` | Methodology (TDSP), Resource Requirements, Software Design |
| `content_ch8.py` | Implementation |
| `content_ch9_11.py` | Testing and Validation, Analysis and Results, Conclusions, References, Appendices |
| `figstyle.py` | Shared matplotlib drawing primitives (boxes, arrows, labels) used by the diagram generator scripts |
| `generate_fig_7_3_7_5.py` | Regenerates Fig. 7.3 (level-1 DFD) and Fig. 7.5 (request-lifecycle sequence diagram) — run it after editing either diagram |
| `figures/` | All figures. Diagrams and charts were generated with matplotlib; `fig_9_4_contact_sheet.png` and `frame_*.png` are real frames extracted from `output/electric-unicycle-kingsong-14d/v1/video.mp4` |

Figure and table numbers are literal text, so they are stable across rebuilds. Each
caption carries a bookmark that the front-matter lists reference with a `PAGEREF`
field, which is why those lists show real page numbers after the field refresh.

`figures/` holds several images the current draft does not use — the TDSP phase
diagram, the job state machine, the TTS chain, the render pipeline, the feedback
cascade and the `fig_code_*.png` set. They were cut to meet the page budget and are
kept because they are useful for the viva presentation deck.

## Before submitting

Fill in the placeholders: `[NAME OF GUIDE]`, `[DESIGNATION / AFFILIATION]`,
`[NAME OF INDUSTRY MENTOR]`, `[MONTH]`, `[DD-MM-2026]`, the similarity index figures,
and the Turnitin report in Appendix B.
