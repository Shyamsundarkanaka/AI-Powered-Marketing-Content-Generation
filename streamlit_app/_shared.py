"""Small bits shared between the Dashboard and Output pages."""
from __future__ import annotations

import streamlit as st

# Mirrors the node order in graph/pipeline.py::build_graph — used only to turn
# a job's current_stage into a progress fraction, not to drive the graph.
STAGE_ORDER = [
    "scrape",
    "load_context",
    "campaign_brief",
    "script",
    "caption",
    "hashtags",
    "video_plan",
    "voiceover",
    "render_video",
    "finalize",
]

STAGE_LABELS = {
    "scrape": "Scraping product page",
    "load_context": "Loading product context",
    "campaign_brief": "Writing campaign brief",
    "script": "Writing script",
    "caption": "Writing caption",
    "hashtags": "Generating hashtags",
    "video_plan": "Planning video scenes",
    "voiceover": "Generating voiceover",
    "render_video": "Rendering video",
    "finalize": "Finalizing version",
}


def stage_progress(stage: str | None) -> tuple[float, str]:
    """(fraction 0..1, label) for a job's current_stage, for st.progress."""
    if not stage or stage not in STAGE_ORDER:
        return 0.05, "Starting…"
    idx = STAGE_ORDER.index(stage)
    return (idx + 1) / len(STAGE_ORDER), STAGE_LABELS.get(stage, stage)


def hide_sidebar() -> None:
    """Remove Streamlit's sidebar entirely — the app has no sidebar content, so
    even the empty collapsible panel and its toggle arrow are just clutter.
    Navigation instead goes through explicit page_link buttons on each page."""
    st.markdown(
        "<style>"
        "[data-testid='stSidebar'] { display: none; }"
        "[data-testid='stSidebarCollapsedControl'] { display: none; }"
        "</style>",
        unsafe_allow_html=True,
    )


def tighten_top_padding() -> None:
    """Streamlit's default block-container padding leaves a large empty gap
    above the page title (meant to clear a sidebar toggle we don't have)."""
    st.markdown(
        "<style>"
        ".block-container { padding-top: 1.5rem; }"
        "</style>",
        unsafe_allow_html=True,
    )


def inject_spinner_css() -> None:
    """CSS keyframes for the small rotating-icon badge used to flag whichever
    row/page has a job actively running, on top of the numeric progress bar."""
    st.markdown(
        "<style>"
        "@keyframes spin-icon { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }"
        ".running-spinner { display: inline-block; animation: spin-icon 1s linear infinite; }"
        "</style>",
        unsafe_allow_html=True,
    )


def running_badge(text: str) -> str:
    """HTML for a spinning-icon + label, e.g. to prefix a product name or
    status caption that's actively being worked on. Render with
    unsafe_allow_html=True."""
    return f"<span class='running-spinner'>⏳</span> {text}"


def centered_title(text: str) -> None:
    """A page's main heading, center-aligned. Replaces st.title, which is
    always left-aligned with no layout option."""
    st.markdown(f"<h1 style='text-align: center;'>{text}</h1>", unsafe_allow_html=True)


def dashboard_button() -> None:
    """Big, unmissable way back to the Dashboard from any other page."""
    st.page_link("app.py", label="🏠 Back to Dashboard", use_container_width=True)
