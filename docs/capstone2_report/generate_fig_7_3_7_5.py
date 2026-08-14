"""Fig 7.3 (level-1 DFD) and Fig 7.5 (request-lifecycle sequence diagram).

Regenerate with: venv\\Scripts\\python.exe docs/capstone2_report/generate_fig_7_3_7_5.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figstyle import *  # noqa: F401,F403
from figstyle import arrow, box, canvas, group, label, save

# ================================================================== Fig 7.3 DFD level 1
fig, ax = canvas(8.3, 5.3, 130, 100)

# -- external entities
box(ax, 8, 4, 16, 12, "Shopify\nstorefront", fill="white", edge=INK, fs=8.0, bold=True, round_r=0.4)
box(ax, 8, 41, 16, 12, "Reviewer\n(marketer)", fill="white", edge=INK, fs=8.0, bold=True, round_r=0.4)
box(ax, 104, 41, 18, 12, "LLM provider\nAPI", fill="white", edge=INK, fs=8.0, bold=True, round_r=0.4)
box(ax, 104, 55, 18, 22, "brand/brand.yaml\n(D3, read-only)", fill=SOFT, edge=GREY, fs=7.4, round_r=0.4)
box(ax, 104, 81, 18, 12, "output/<slug>/\nv<N>/ files (D2)", fill=SOFT, edge=GREY, fs=7.4, round_r=0.4)

# -- D1 spine (the only store any process may read or write product/version state through)
box(ax, 8, 24, 114, 9, "D1   SQLite — products · jobs · versions · outputs · scraped_data · logs",
    fill=SOFT, edge=GREY, fs=7.6, round_r=0.3)

# -- processes
box(ax, 32, 4, 22, 12, "P2\nScrape & store\nproduct facts", fill=TEAL_F, edge=TEAL, fs=7.8)
box(ax, 32, 41, 22, 12, "P1\nQueue & review\ncontent versions", fill=BLUE_F, edge=BLUE, fs=7.8)
box(ax, 64, 41, 24, 12, "P3\nGenerate copy\n(5 LLM agents)", fill=ORANGE_F, edge=ORANGE, fs=7.8)
box(ax, 64, 61, 24, 12, "P4\nSynthesise voice\n& render video", fill=PURPLE_F, edge=PURPLE, fs=7.8)
box(ax, 64, 81, 24, 12, "P5\nFinalise version\n& provenance", fill=GREEN_F, edge=GREEN, fs=7.8)

# -- Shopify -> P2 -> D1 (facts enter exactly once, here)
arrow(ax, (24, 10), (31.6, 10), color=TEAL)
label(ax, 27.8, 7.4, "product json", fs=6.6, color=TEAL, ha="center")
arrow(ax, (43, 16), (43, 23.6), color=TEAL)
label(ax, 46, 20, "product facts", fs=6.6, color=TEAL, ha="left")

# -- Reviewer <-> P1
arrow(ax, (24, 45), (31.6, 45), color=BLUE)
label(ax, 27.8, 41.6, "run / reject", fs=6.4, color=BLUE, ha="center")
arrow(ax, (31.6, 50), (24, 50), color=BLUE)
label(ax, 27.8, 53.6, "video, copy", fs=6.6, color=BLUE, ha="center")

# -- P1 <-> D1
arrow(ax, (43, 40.6), (43, 33.2), color=BLUE, style="<->")
label(ax, 46, 37, "job rows,\nscraped_data", fs=6.5, color=BLUE, ha="left")

# -- D1 -> P3: the ONLY path a product fact takes to reach copy generation
arrow(ax, (76, 33.2), (76, 40.6), color=ORANGE, lw=1.4)
label(ax, 79, 37, "facts", fs=7.0, color=ORANGE, ha="left", bold=True)

# -- P3 <-> LLM provider
arrow(ax, (88, 46), (103.6, 46), color=ORANGE, style="<->")
label(ax, 95.8, 49.8, "prompt / JSON", fs=6.5, color=ORANGE, ha="center")

# -- P3 -> P4: script and shot plan flow DOWN into rendering, not the reverse
arrow(ax, (76, 53), (76, 60.6), color=PURPLE, lw=1.4)
label(ax, 79, 57, "script, plan", fs=6.8, color=PURPLE, ha="left", bold=True)

# -- D3 -> P3 and D3 -> P4 (brand rules feed both; two short local hops, no long diagonal)
arrow(ax, (103.6, 58), (91, 58), color=GREY)
arrow(ax, (91, 57.6), (91, 53.4), color=GREY)
label(ax, 97, 55.5, "brand rules", fs=6.0, color=GREY, ha="center")
arrow(ax, (103.6, 68), (88, 68), color=GREY)
label(ax, 95.8, 71.6, "brand rules", fs=6.4, color=GREY, ha="center")

# -- P3 -> P5: copy artefacts, routed right of P4 so it never touches it
arrow(ax, (88, 51), (95, 51), color=GREEN, style="-")
arrow(ax, (95, 51), (95, 83), color=GREEN, style="-")
arrow(ax, (95, 83), (88.4, 83), color=GREEN)
label(ax, 99, 76.5, "copy artefacts", fs=6.0, color=GREEN, ha="center", bg="white")

# -- P4 -> P5: render artefacts, straight down
arrow(ax, (76, 73), (76, 80.6), color=PURPLE, lw=1.4)
label(ax, 79, 77, "audio,\nvideo", fs=6.4, color=PURPLE, ha="left")

# -- P5 -> D2
arrow(ax, (88, 90), (103.6, 90), color=GREEN)
label(ax, 95.8, 87.3, "artefact files", fs=6.4, color=GREEN, ha="center")

# -- P5 -> D1: version + output rows, returned via the left margin so it crosses nothing
arrow(ax, (64, 90), (3, 90), color=GREEN, style="-", lw=1.1)
arrow(ax, (3, 90), (3, 28.5), color=GREEN, style="-", lw=1.1)
arrow(ax, (3, 28.5), (7.6, 28.5), color=GREEN, lw=1.1)
label(ax, 5, 84, "version + output rows", fs=6.4, color=GREEN, ha="left", rot=90)

save(fig, "fig_7_3_dfd.png")

# ================================================================== Fig 7.5 sequence
fig, ax = canvas(7.0, 6.4, 100, 112)
actors = [("Reviewer", 8, INK), ("Streamlit UI", 27, BLUE), ("SQLite", 46, GREY),
          ("Worker", 65, PURPLE), ("LLM provider", 88, ORANGE)]
for name, x, c in actors:
    box(ax, x - 8.5, 1.5, 17, 7, name, fill="white", edge=c, fc=c, fs=8.0, bold=True)
    arrow(ax, (x, 8.5), (x, 109), color="#B9C4CF", style="-", lw=0.9, zorder=0)

msgs = [
    (8, 27, 15.0, "click Run"),
    (27, 46, 21.5, "create_job(product_id) · status → Running"),
    (46, 65, 28.0, "get_next_pending_job()   (FIFO poll, 5 s)"),
    (65, 65, 34.5, "check_configuration()  ·  scrape_and_store()"),
    (65, 88, 44.5, "generate_json(campaign_brief …)"),
    (88, 65, 51.0, "raw text → extract_json → validate"),
    (65, 88, 57.5, "repair-retry with the schema error fed back"),
    (65, 65, 71.0, "voiceover (Piper)  ·  render_video (Pillow / MoviePy)"),
    (65, 46, 77.5, "create_version · add_output ×N · _meta.json"),
    (65, 46, 84.0, "product → Review  ·  job → Completed"),
    (27, 46, 90.5, "poll every 2 s while a job is active"),
    (27, 8, 97.0, "video + copy + provenance"),
    (8, 27, 103.5, "Approve   /   Reject + scoped feedback"),
]
for x0, x1, y, text in msgs:
    if x0 == x1:
        ax.add_patch(__import__("matplotlib").patches.FancyArrowPatch(
            (x0, y - 2.0), (x0, y + 2.0), arrowstyle="-|>", mutation_scale=8,
            connectionstyle="arc3,rad=-1.3", color=INK, lw=1.0))
        label(ax, x0 + 4.5, y, text, fs=7.0, color=INK, ha="left")
    else:
        arrow(ax, (x0, y), (x1, y), color=INK, lw=1.0)
        label(ax, (x0 + x1) / 2, y - 2.4, text, fs=7.0, color=INK, bg="white")

group(ax, 58, 39, 41, 25, None, edge=ORANGE, ls=(0, (4, 3)), fill="none")
label(ax, 58, 37.0, "×5 agents; up to LLM_JSON_ATTEMPTS = 3 shape retries each",
      fs=6.8, color=ORANGE, ha="left", bg="white")
save(fig, "fig_7_5_sequence.png")
