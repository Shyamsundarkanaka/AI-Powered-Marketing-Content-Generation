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


def inject_action_button_css() -> None:
    """Give approve/reject/delete buttons their semantic color.

    This Streamlit version (1.38) predates the `st-key-<key>` CSS class that
    later versions attach automatically, and `st.container(key=...)` doesn't
    exist yet either — so there's no first-party hook to color one specific
    button. Instead, `colored_button()` renders an invisible marker element
    (a `<span class="btn-marker-*">`) immediately before the button; each
    marker's `element-container` is hidden here, and `:has()` + the adjacent-
    sibling combinator reach past it to style the button in the very next
    `element-container`. `:has()` needs a fairly recent browser (Chrome/Edge
    105+, Safari 15.4+, Firefox 121+), which is a safe bet for local Streamlit
    use."""
    st.markdown(
        "<style>"
        "div[data-testid='element-container']:has(> div .btn-marker) { display: none; }"
        "div[data-testid='element-container']:has(> div .btn-marker-approve)"
        " + div[data-testid='element-container'] button {"
        "  background-color: #1a7f37; border-color: #1a7f37; color: #fff;"
        "}"
        "div[data-testid='element-container']:has(> div .btn-marker-approve)"
        " + div[data-testid='element-container'] button:hover {"
        "  background-color: #15672d; border-color: #15672d; color: #fff;"
        "}"
        "div[data-testid='element-container']:has(> div .btn-marker-approve)"
        " + div[data-testid='element-container'] button p { color: #fff; }"
        "div[data-testid='element-container']:has(> div .btn-marker-reject)"
        " + div[data-testid='element-container'] button,"
        "div[data-testid='element-container']:has(> div .btn-marker-delete)"
        " + div[data-testid='element-container'] button {"
        "  background-color: #d1242f; border-color: #d1242f; color: #fff;"
        "}"
        "div[data-testid='element-container']:has(> div .btn-marker-reject)"
        " + div[data-testid='element-container'] button:hover,"
        "div[data-testid='element-container']:has(> div .btn-marker-delete)"
        " + div[data-testid='element-container'] button:hover {"
        "  background-color: #a3202a; border-color: #a3202a; color: #fff;"
        "}"
        "div[data-testid='element-container']:has(> div .btn-marker-reject)"
        " + div[data-testid='element-container'] button p,"
        "div[data-testid='element-container']:has(> div .btn-marker-delete)"
        " + div[data-testid='element-container'] button p { color: #fff; }"
        "</style>",
        unsafe_allow_html=True,
    )


def colored_button(container, label: str, key: str, marker: str, **kwargs) -> bool:
    """`st.button`, but preceded by an invisible marker element so
    `inject_action_button_css()` can color it. `container` is anything with
    `.markdown`/`.button` — `st`, a column, or a `st.container()`. `marker` is
    "approve", "reject", or "delete"."""
    container.markdown(f"<span class='btn-marker btn-marker-{marker}'></span>", unsafe_allow_html=True)
    return container.button(label, key=key, **kwargs)


def dashboard_button() -> None:
    """Big, unmissable way back to the Dashboard from any other page."""
    st.page_link("app.py", label="🏠 Back to Dashboard", use_container_width=True)


def llm_configuration_banner() -> bool:
    """Warn, at the top of the page, if the pipeline cannot generate anything.

    Returns True when the configuration is usable. The check is import-light
    and never contacts the provider — it only asks whether a real key is
    present for whichever provider is selected.
    """
    from graph.llm import LLMConfigurationError, active_config, check_configuration

    try:
        check_configuration()
    except LLMConfigurationError as exc:
        st.error(
            f"**Content generation is not configured.** {exc}\n\n"
            f"Runs will fail until this is fixed. Nothing is generated locally as a "
            f"substitute — the pipeline produces real model output or it produces nothing."
        )
        return False

    config = active_config()
    st.caption(f"Model: `{config.model}` via `{config.name}`")
    return True


def render_warnings(warnings: list[str]) -> None:
    """Show a version's non-fatal warnings to the person approving it.

    These used to live only in `_meta.json`, which meant a reviewer could
    approve a video whose voiceover was silent without ever being told.
    """
    if not warnings:
        return
    silent = [w for w in warnings if "silent" in w.lower()]
    other = [w for w in warnings if w not in silent]
    if silent:
        st.warning("🔇 **This version has no spoken narration.** " + " ".join(silent))
    if other:
        with st.container(border=True):
            st.markdown("**Warnings from this run**")
            for warning in other:
                st.caption(f"• {warning}")
