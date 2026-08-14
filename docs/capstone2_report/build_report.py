"""Build the Capstone Project II report as a Word document.

    python docs/capstone2_report/build_report.py

Writes Capstone_II_Report.docx next to this file. Open it in Word and press
Ctrl+A then F9 to populate the table of contents, list of tables, list of
figures and page numbers.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from content_ch1_4 import ch1, ch2, ch3, ch4          # noqa: E402
from content_ch5_7 import ch5, ch6, ch7               # noqa: E402
from content_ch8 import ch8                           # noqa: E402
from content_ch9_11 import appendices, ch9, ch10, ch11, references  # noqa: E402
from content_front import front                       # noqa: E402
from docbuild import Report                           # noqa: E402


def main():
    r = Report(figdir=os.path.join(HERE, "figures"))

    front(r)
    r.start_body_section()

    for chapter in (ch1, ch2, ch3, ch4, ch5, ch6, ch7, ch8, ch9, ch10, ch11):
        chapter(r)

    references(r)
    appendices(r)

    # The list of tables and list of figures live in the front matter but can only be
    # built once every caption has been emitted, so they are stitched in at the end.
    r.build_lists()

    out = os.path.join(HERE, "Capstone_II_Report.docx")
    r.save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
