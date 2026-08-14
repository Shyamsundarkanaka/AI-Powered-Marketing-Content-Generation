"""Shared drawing helpers for the Capstone II report figures.

Print-friendly: white ground, dark navy strokes, brand orange/teal accents.
Everything is drawn in a 0..100 x 0..H coordinate space and saved at 200 dpi.
"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe  # noqa: E402
from matplotlib import font_manager  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

OUT = os.environ.get(
    "FIGDIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures"),
)
os.makedirs(OUT, exist_ok=True)

INK = "#16202B"
LINE = "#41506180"
GREY = "#5A6B7C"
SOFT = "#EEF2F6"
SOFT2 = "#E2E8F0"
ORANGE = "#D9480F"
ORANGE_F = "#FFF1E8"
TEAL = "#0F766E"
TEAL_F = "#E4F5F2"
BLUE = "#1D4ED8"
BLUE_F = "#E8EEFF"
PURPLE = "#6D28D9"
PURPLE_F = "#F1EAFE"
RED = "#B42318"
RED_F = "#FDECEA"
GREEN = "#15803D"
GREEN_F = "#E9F7EE"

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Segoe UI", "Calibri", "DejaVu Sans"],
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
        "axes.facecolor": "white",
    }
)

MONO = ["Consolas", "Courier New", "DejaVu Sans Mono"]


def canvas(width_in: float, height_in: float, xmax: float = 100.0, ymax: float = 100.0):
    fig, ax = plt.subplots(figsize=(width_in, height_in))
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.axis("off")
    ax.invert_yaxis()  # top-left origin, easier to reason about
    return fig, ax


def save(fig, name: str):
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=200, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print("wrote", name)
    return path


def box(
    ax,
    x,
    y,
    w,
    h,
    text,
    *,
    fill=SOFT,
    edge=INK,
    fc=INK,
    fs=9,
    bold=False,
    round_r=1.4,
    lw=1.1,
    align="center",
    pad_left=1.6,
    ls="solid",
    zorder=3,
    linespacing=1.35,
):
    """Rounded box with centred (or left-aligned) wrapped text. x,y = top-left."""
    patch = FancyBboxPatch(
        (x, y + h),
        w,
        h,
        boxstyle=f"round,pad=0,rounding_size={round_r}",
        linewidth=lw,
        edgecolor=edge,
        facecolor=fill,
        linestyle=ls,
        zorder=zorder,
        mutation_aspect=1,
    )
    # FancyBboxPatch with inverted y: build it from the un-inverted rect instead
    patch.set_bounds(x, y, w, h)
    ax.add_patch(patch)
    if align == "center":
        ax.text(
            x + w / 2,
            y + h / 2,
            text,
            ha="center",
            va="center",
            fontsize=fs,
            color=fc,
            fontweight="bold" if bold else "normal",
            zorder=zorder + 1,
            linespacing=linespacing,
        )
    else:
        ax.text(
            x + pad_left,
            y + h / 2,
            text,
            ha="left",
            va="center",
            fontsize=fs,
            color=fc,
            fontweight="bold" if bold else "normal",
            zorder=zorder + 1,
            linespacing=linespacing,
        )
    return patch


def group(ax, x, y, w, h, label=None, *, edge=GREY, fill="#FBFCFD", ls=(0, (4, 3)), fs=8.5, lw=1.0):
    r = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0,rounding_size=1.8",
        linewidth=lw,
        edgecolor=edge,
        facecolor=fill,
        linestyle=ls,
        zorder=1,
    )
    ax.add_patch(r)
    if label:
        ax.text(x + 1.8, y + 2.4, label, ha="left", va="center", fontsize=fs, color=edge,
                fontweight="bold", zorder=2)
    return r


def arrow(ax, p0, p1, *, color=INK, lw=1.2, style="-|>", rad=0.0, ls="solid", zorder=2,
          ms=8):
    a = FancyArrowPatch(
        p0,
        p1,
        arrowstyle=style,
        mutation_scale=ms,
        linewidth=lw,
        color=color,
        connectionstyle=f"arc3,rad={rad}",
        linestyle=ls,
        zorder=zorder,
        shrinkA=0,
        shrinkB=0,
    )
    ax.add_patch(a)
    return a


def label(ax, x, y, text, *, fs=8, color=GREY, ha="center", va="center", bg=None,
          bold=False, rot=0):
    kw = {}
    if bg:
        kw["bbox"] = dict(boxstyle="round,pad=0.22", fc=bg, ec="none")
    return ax.text(x, y, text, ha=ha, va=va, fontsize=fs, color=color, zorder=6,
                   fontweight="bold" if bold else "normal", rotation=rot, **kw)


def title(ax, text, xmax=100):
    ax.text(xmax / 2, 1.5, text, ha="center", va="top", fontsize=10.5,
            fontweight="bold", color=INK)


def code_figure(lines, name, *, width_in=6.3, fs=7.4, header=None, highlight=()):
    """Render a code snippet as a bordered listing image."""
    n = len(lines) + (1 if header else 0)
    height_in = 0.20 * n + 0.30
    fig, ax = plt.subplots(figsize=(width_in, height_in))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, n + 0.6)
    ax.axis("off")
    ax.invert_yaxis()
    ax.add_patch(
        Rectangle((0, 0), 100, n + 0.6, facecolor="#F7F9FB", edgecolor="#C7D2DD", linewidth=1.0)
    )
    y = 0.55
    if header:
        ax.text(1.4, y, header, fontsize=fs - 0.3, family=MONO, color="#5A6B7C",
                style="italic", va="center")
        y += 1.0
    for i, ln in enumerate(lines):
        col = INK
        st = "normal"
        stripped = ln.strip()
        if stripped.startswith("#"):
            col = "#6B7C8D"
            st = "italic"
        if i in highlight:
            ax.add_patch(Rectangle((0.8, y - 0.42), 98.4, 0.84, facecolor="#FFF3E8",
                                   edgecolor="none", zorder=1))
        ax.text(1.4, y, ln, fontsize=fs, family=MONO, color=col, va="center",
                style=st, zorder=2)
        y += 1.0
    return save(fig, name)
