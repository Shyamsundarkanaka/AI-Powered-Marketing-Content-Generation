"""Preliminary pages: cover, declaration, ownership, certificate, acknowledgement,
similarity index, abbreviations / tables / figures, abstract."""
from docbuild import add_field
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

TITLE = ("Brand-Governed Multi-Agent Generation of\n"
         "Short-Form Video Marketing Content\n"
         "from E-Commerce Product Data")
STUDENT = "Shyam Sundar K"
SRN = "R22MSA55"
GUIDE = "[NAME OF GUIDE]"
GUIDE_DESIG = "[DESIGNATION / AFFILIATION]"
MENTOR = "[NAME OF INDUSTRY MENTOR]"
YEAR = "2026"
SUBMONTH = "[MONTH], 2026"
PLACE = "Bengaluru"
DATE = "[DD-MM-2026]"
REPO = "https://github.com/Shyamsundarkanaka/AI-Powered-Marketing-Content-Generation"


def front(r):
    # ------------------------------------------------------------ cover page
    r.para(space_after=26)
    r.para("A Project Report on", align="center", size=13, space_after=18)
    for line in TITLE.split("\n"):
        r.para(line, align="center", size=19, bold=True, space_after=4, line_spacing=1.15)
    r.para(space_after=16)
    r.para("Submitted in partial fulfilment for the award of the degree of",
           align="center", size=12, space_after=8)
    r.para("Master of Science", align="center", size=15, bold=True, space_after=2)
    r.para("in", align="center", size=12, space_after=2)
    r.para("Artificial Intelligence", align="center", size=15, bold=True, space_after=22)
    r.para("Submitted by", align="center", size=12, space_after=6)
    r.para(STUDENT, align="center", size=14, bold=True, space_after=2)
    r.para(SRN, align="center", size=13, space_after=22)
    r.para("Under the Guidance of", align="center", size=12, space_after=6)
    r.para(GUIDE, align="center", size=14, bold=True, space_after=2)
    r.para(GUIDE_DESIG, align="center", size=11.5, italic=True, space_after=6)
    r.para(f"Industry Mentor: {MENTOR}", align="center", size=11.5, italic=True, space_after=26)
    r.para("REVA Academy for Corporate Excellence", align="center", size=14, bold=True,
           space_after=2)
    r.para("REVA University", align="center", size=14, bold=True, space_after=6)
    r.para("Rukmini Knowledge Park, Kattigenahalli,", align="center", size=12, space_after=2)
    r.para("Yelahanka, Bengaluru – 560064", align="center", size=12, space_after=18)
    r.para(SUBMONTH, align="center", size=13, bold=True)

    # --------------------------------------------------- candidate's declaration
    r.h1("Candidate's Declaration", toc=False)
    r.para(
        f"I, {STUDENT}, hereby declare that I have completed the project work towards the "
        f"Master of Science in Artificial Intelligence at REVA University on the topic entitled "
        f"“Brand-Governed Multi-Agent Generation of Short-Form Video Marketing Content from "
        f"E-Commerce Product Data” under the supervision of {GUIDE}. This report embodies the "
        f"original work done by me in partial fulfilment of the requirements for the award of "
        f"the degree for the academic year {YEAR}.")
    r.para(space_after=30)
    r.para(f"Place: {PLACE}\t\t\t\tName of the Student: {STUDENT}", align="left")
    r.para(f"Date: {DATE}\t\t\t\tSignature of Student:", align="left")

    # --------------------------------------------- acknowledgment of ownership
    r.h1("Acknowledgment of Project Ownership and Usage Rights", toc=False)
    r.para(
        f"I, {STUDENT}, a student enrolled in the Master of Science Program and {YEAR} Year at "
        "RACE, hereby acknowledge that any project, including but not limited to software, "
        "hardware, research, or other intellectual property created by me during my academic "
        "tenure at RACE, is the property of RACE, REVA University.")
    r.para(
        "I understand and agree that RACE has the exclusive rights to use, reproduce, modify, or "
        "distribute the aforementioned projects for academic, research, and further development "
        "purposes. This includes the right to monetize, commercialize, or otherwise exploit the "
        "projects as deemed fit by RACE.")
    r.para(
        "I acknowledge that I have no objection to RACE, REVA University, using, reproducing, or "
        "further developing the projects for the benefit of the institution and its academic "
        "community. I further affirm that any commercial or research activities related to the "
        "projects conducted by RACE shall not require additional consent or approval from me.")
    r.para(
        "This acknowledgment is made willingly and without any reservations. I am grateful for "
        "the education and opportunities provided by RACE, and I recognize the importance of "
        "contributing to the academic and research goals of the institution.")
    r.para(space_after=30)
    r.para(f"Place: {PLACE}\t\t\t\tName of the Student: {STUDENT}", align="left")
    r.para(f"Date: {DATE}\t\t\t\tSignature of Student", align="left")

    # --------------------------------------------------------------- certificate
    r.h1("Certificate", toc=False)
    r.para(
        "This is to certify that the project work entitled “Brand-Governed Multi-Agent Generation "
        f"of Short-Form Video Marketing Content from E-Commerce Product Data” has been carried out "
        f"by {STUDENT} with SRN {SRN}, who is a bonafide student of REVA University, is submitting "
        f"the second year project report in fulfilment for the award of Master of Science in "
        f"Artificial Intelligence during the academic year {YEAR}. The project report has been "
        "tested for plagiarism, and has passed the plagiarism test with the similarity score less "
        "than 15%. The project report has been approved as it satisfies the academic requirements "
        "in respect of the project work prescribed for the said degree.")
    r.para(space_after=26)
    r.para("Signature of the Guide\t\t\t\t\tSignature of the Director", align="left",
           space_after=18)
    r.para(f"{GUIDE}\t\t\t\t\tDr. Shinu Abhi", align="left", space_after=2)
    r.para("Guide\t\t\t\t\t\t\tDirector", align="left", space_after=24)
    r.para("External Viva", align="left", bold=True, space_after=6)
    r.para("Names of the Examiners", align="left", space_after=14)
    r.para("<Name>\t\t\t<Designation>\t\t\t<Signature>", align="left", space_after=14)
    r.para("<Name>\t\t\t<Designation>\t\t\t<Signature>", align="left", space_after=24)
    r.para(f"Place: {PLACE}", align="left", space_after=2)
    r.para(f"Date: {DATE}", align="left")

    # ---------------------------------------------------------- acknowledgement
    r.h1("Acknowledgement", toc=False)
    r.para(
        "I express my sincere gratitude to my mentors and trainers for their guidance and "
        "encouragement throughout this project. In particular I thank Dr. Shinu Abhi, Director – "
        f"Corporate Training, {GUIDE}, and {MENTOR} for their advice, their willingness to "
        "challenge design decisions rather than accept them, and their support through the review "
        "sessions that shaped this work.")
    r.para(
        "I extend my appreciation to my classmates and to the program office for the discussions "
        "and the practical help that kept this project moving, and I am grateful to my family and "
        "friends for their patience while it was being built.")
    r.para(
        "I would also like to acknowledge the Hon'ble Chancellor, Dr. P Shyama Raju, the Hon'ble "
        "Vice Chancellor, Dr. Sanjay Chitnis, and the Registrar, Dr. M. Dhanamjaya, whose "
        "leadership and commitment to academic excellence have created an environment that "
        "fosters innovation and research.")
    r.para(
        "Finally, I thank everyone who contributed to this project directly or indirectly. Their "
        "support has been invaluable in completing this work.")
    r.para(space_after=26)
    r.para(f"Place: {PLACE}", align="left", space_after=2)
    r.para(f"Date: {DATE}", align="left", space_after=2)
    r.para(STUDENT, align="left", bold=True)

    # -------------------------------------------------------- similarity index
    r.h1("Similarity Index Report", toc=False)
    r.para(
        "This is to certify that this project report titled “Brand-Governed Multi-Agent Generation "
        "of Short-Form Video Marketing Content from E-Commerce Product Data” was scanned for "
        "similarity detection. The process and outcome are given below. The plagiarism report is "
        "attached in Appendix B.")
    r.bullets([
        "Software Used: Turnitin",
        "Date of Report Generation: [DD-MM-2026]",
        "Similarity Index in %: [TO BE FILLED]",
        "Total word count: [TO BE FILLED]",
        f"Name of the Guide: {GUIDE}",
    ], size=12)
    r.para(space_after=26)
    r.para(f"Place: {PLACE}\t\t\t\tName of the Student: {STUDENT}", align="left")
    r.para(f"Date: {DATE}\t\t\t\tSignature of Student", align="left", space_after=24)
    r.para("Verified by:", align="left", space_after=18)
    r.para("Signature", align="left", space_after=2)
    r.para("Dr. Shinu Abhi,", align="left", space_after=2)
    r.para("Director, Corporate Training", align="left")

    # ----------------------------------------------------- table of contents
    # Everything from here on uses the 12 pt / 1.5 house format.
    r.h1("Table of Contents", toc=False)
    r.start_running_text()
    p = r.doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    add_field(p, ' TOC \\o "1-2" \\h \\z \\u ',
              cached="Select this list and press F9 in Microsoft Word to build the "
                     "table of contents with page numbers.", italic=True, size=11)

    # -------------------------------------- abbreviations / tables / figures
    r.h1("List of Abbreviations, Tables and Figures", toc=False)
    r.h2("1.  List of Abbreviations")
    r.tbl("", ["Abbreviation", "Expansion", "Abbreviation", "Expansion"], [
        ["AAC", "Advanced Audio Coding", "LLM", "Large Language Model"],
        ["AI", "Artificial Intelligence", "MP4", "MPEG-4 Part 14 container"],
        ["API", "Application Programming Interface", "ONNX", "Open Neural Network Exchange"],
        ["ASCI", "Advertising Standards Council of India", "PK", "Primary Key"],
        ["CLI", "Command-Line Interface", "RAG", "Retrieval-Augmented Generation"],
        ["CPU", "Central Processing Unit", "RAM", "Random Access Memory"],
        ["CRUD", "Create, Read, Update, Delete", "SHA-1", "Secure Hash Algorithm 1"],
        ["CTA", "Call To Action", "SQL", "Structured Query Language"],
        ["DAG", "Directed Acyclic Graph", "SWOT", "Strengths, Weaknesses, Opportunities, Threats"],
        ["DFD", "Data Flow Diagram", "TDSP", "Team Data Science Process"],
        ["DOI", "Digital Object Identifier", "TTS", "Text-To-Speech"],
        ["ER", "Entity–Relationship", "UI", "User Interface"],
        ["FIFO", "First In, First Out", "URL", "Uniform Resource Locator"],
        ["FK", "Foreign Key", "WAL", "Write-Ahead Logging"],
        ["fps", "Frames Per Second", "WAV", "Waveform Audio File Format"],
        ["HTML", "HyperText Markup Language", "YAML", "YAML Ain't Markup Language"],
        ["HTTP", "HyperText Transfer Protocol", "FR / NFR",
         "Functional / Non-Functional Requirement"],
        ["JSON", "JavaScript Object Notation", "TC", "Test Case"],
    ], widths=[1.3, 3.4, 1.3, 4.0], size=9.5)

    r.h2("2.  List of Tables")
    r.list_placeholder("T")

    r.h2("3.  List of Figures")
    r.list_placeholder("F")

    # ------------------------------------------------------------------ abstract
    r.h1("Abstract", toc=False)
    r.para(
        "A small direct-to-consumer retailer selling any catalogue of physical products — gifts, "
        "apparel, handmade goods or otherwise — through a Shopify storefront is typical of the "
        "target user. Like most catalogue-driven retailers, it needs a short vertical video, a "
        "caption and a hashtag set for every product it lists, and "
        "for every revision a reviewer asks for. Generative models can write that copy, but the "
        "failure that matters in marketing is not a clumsy sentence. It is a confident, "
        "brand-shaped claim about a specification or price that nobody can trace to a source and "
        "that a reviewer may approve because it reads well.")
    r.para(
        "This project builds and validates a system that turns a single public Shopify product URL "
        "into a complete, reviewable content package: a campaign brief, a five-beat voiceover "
        "script, an Instagram caption, a hashtag set, a shot-by-shot video plan, a synthesised "
        "narration track and a rendered 1080×1920 H.264 video, together with a provenance sidecar "
        "recording what produced each artefact. The work follows the Team Data Science Process. The "
        "generation layer is a LangGraph state graph of nine nodes over seven supersteps, with five "
        "prompt-driven LLM agents, three of which run as one parallel superstep joined by explicit "
        "state reducers.")
    r.para(
        "The distinguishing design decision is that the system has no fallback content. Every brand "
        "rule — tone, banned vocabulary, personas, script length, caption limits, hashtag policy, "
        "compliance clauses, colour palette and video geometry — lives in a single machine-readable "
        "brand file that is injected verbatim into every prompt and read directly by the renderer. "
        "Model output is parsed by a four-stage hardened JSON extractor, validated against "
        "brand-derived schemas, and re-asked with the specific violation fed back. If the model "
        "still cannot produce valid output, the run fails; no placeholder copy is ever substituted. "
        "A human approve/reject gate closes the loop, and a rejection carries written feedback and "
        "a scope, so content the reviewer was happy with is carried forward byte-identically "
        "instead of being regenerated.")
    r.para(
        "The implementation is 6,488 lines of application Python across eight packages, exercised "
        "by a 174-test suite that runs offline with no API key, of which 171 pass. End-to-end "
        "validation on a live product page produced a complete version in 214 seconds, with "
        "the narration measured at 22.37 s from the WAV header and the rendered MP4 landing on "
        "exactly the same duration. Every factual claim in that package traces to the scraped "
        "record.")
    r.para(
        "**Keywords:** Generative AI, Multi-Agent Systems, LangGraph, Marketing Content Generation, "
        "Hallucination Mitigation, Schema Validation, Human-in-the-Loop, Short-Form Video, "
        "Text-to-Speech, Team Data Science Process.")
