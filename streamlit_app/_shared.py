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


# ---------------------------------------------------------------------------
# Visual theme — warm "clay & ink" palette (deliberately not the default blue).
# Everything below is presentational only; no page logic depends on it.
# ---------------------------------------------------------------------------

STATUS_COLORS: dict[str, str] = {
    "Pending": "#B7791F",
    "Running": "#2F8577",
    "Review": "#7C5CBF",
    "Approved": "#2F8F5F",
    "Failed": "#C1443B",
    "Cancelled": "#7A756C",
}


def inject_theme_css() -> None:
    """App-wide look and feel: typography, spacing, cards, badges, form
    controls. Kept purely presentational — no widget keys, no logic."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap');

        :root {
            --clay-50:  #FBF8F3;
            --clay-100: #F2EAE0;
            --clay-200: #E7DCCB;
            --clay-ink: #2B2620;
            --clay-muted: #756C5F;
            --clay-accent: #B5562F;
            --clay-accent-dark: #8F421F;
            --clay-teal: #2F8577;
            --clay-border: #E4D9C8;
        }

        html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
        h1, h2, h3, h4, .app-eyebrow { font-family: 'Sora', 'Inter', sans-serif; }

        [data-testid="stAppViewContainer"] {
            background: radial-gradient(circle at 10% -10%, #FDF3E7 0%, var(--clay-50) 42%);
        }
        [data-testid="stHeader"] { background: transparent; }
        .block-container { padding-top: 1.1rem; padding-bottom: 3rem; max-width: 1180px; }

        /* Hero header --------------------------------------------------- */
        .app-header { text-align: center; margin-bottom: .25rem; }
        .app-eyebrow {
            display: inline-block; font-size: .72rem; font-weight: 700;
            letter-spacing: .16em; text-transform: uppercase; color: var(--clay-accent);
            background: rgba(181, 86, 47, 0.10); border-radius: 999px;
            padding: .25rem .85rem; margin-bottom: .6rem;
        }
        .app-title {
            font-family: 'Sora', sans-serif; font-weight: 800; font-size: 2.15rem;
            color: var(--clay-ink); margin: 0 0 .2rem 0; letter-spacing: -0.01em;
        }
        .app-title-bar {
            width: 64px; height: 4px; margin: .35rem auto 0 auto; border-radius: 999px;
            background: linear-gradient(90deg, var(--clay-accent), var(--clay-teal));
        }

        /* Generic surfaces ----------------------------------------------- */
        div[data-testid="stExpander"] {
            border: 1px solid var(--clay-border); border-radius: 14px;
            background: #FFFFFF; box-shadow: 0 1px 3px rgba(43, 38, 32, 0.05);
        }
        div[data-testid="stExpander"] summary { font-weight: 600; color: var(--clay-ink); }

        /* Metrics as cards ------------------------------------------------ */
        div[data-testid="stMetric"] {
            background: #FFFFFF; border: 1px solid var(--clay-border);
            border-top: 4px solid var(--clay-accent); border-radius: 12px;
            padding: .85rem .9rem .7rem .9rem; box-shadow: 0 1px 3px rgba(43,38,32,0.05);
        }
        div[data-testid="stHorizontalBlock"] > div:nth-of-type(1) div[data-testid="stMetric"] { border-top-color: #B7791F; }
        div[data-testid="stHorizontalBlock"] > div:nth-of-type(2) div[data-testid="stMetric"] { border-top-color: #2F8577; }
        div[data-testid="stHorizontalBlock"] > div:nth-of-type(3) div[data-testid="stMetric"] { border-top-color: #7C5CBF; }
        div[data-testid="stHorizontalBlock"] > div:nth-of-type(4) div[data-testid="stMetric"] { border-top-color: #2F8F5F; }
        div[data-testid="stHorizontalBlock"] > div:nth-of-type(5) div[data-testid="stMetric"] { border-top-color: #C1443B; }
        div[data-testid="stHorizontalBlock"] > div:nth-of-type(6) div[data-testid="stMetric"] { border-top-color: #7A756C; }
        div[data-testid="stMetric"] label { color: var(--clay-muted) !important; font-weight: 600; }
        div[data-testid="stMetricValue"] { color: var(--clay-ink); font-weight: 700; }

        /* Section labels ---------------------------------------------------*/
        h2, h3 { color: var(--clay-ink); }

        /* Row cards (product table) --------------------------------------- */
        div[data-testid='element-container']:has(> div .row-marker) { display: none; }
        div[data-testid='element-container']:has(> div .row-marker-header) + div[data-testid='stHorizontalBlock'] {
            background: var(--clay-100); border-radius: 10px; padding: .3rem .6rem;
            margin-bottom: .35rem; font-size: .72rem; font-weight: 700;
            letter-spacing: .06em; text-transform: uppercase; color: var(--clay-muted);
        }
        div[data-testid='element-container']:has(> div .row-marker-header) + div[data-testid='stHorizontalBlock'] p {
            font-size: .72rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
            color: var(--clay-muted); margin: 0;
        }
        /* Sortable column headers, rendered as st.button so they can be clicked -
           strip all button chrome and make them read like plain column labels. */
        div[data-testid='element-container']:has(> div .row-marker-header) + div[data-testid='stHorizontalBlock'] button {
            background: transparent !important; border: none !important; box-shadow: none !important;
            padding: .25rem 0 !important; margin: 0 !important; text-align: left !important;
            font-size: .72rem !important; font-weight: 700 !important; letter-spacing: .06em !important;
            text-transform: uppercase !important; color: var(--clay-muted) !important; justify-content: flex-start !important;
        }
        div[data-testid='element-container']:has(> div .row-marker-header) + div[data-testid='stHorizontalBlock'] button:hover {
            color: var(--clay-accent) !important;
        }
        div[data-testid='element-container']:has(> div .row-marker-header) + div[data-testid='stHorizontalBlock'] button p {
            font-size: .72rem !important; font-weight: 700 !important; letter-spacing: .06em !important;
            text-transform: uppercase !important; color: inherit !important; margin: 0 !important;
        }
        div[data-testid='element-container']:has(> div .row-marker-item) + div[data-testid='stHorizontalBlock'] {
            background: #FFFFFF; border: 1px solid var(--clay-border); border-radius: 12px;
            padding: .65rem .9rem; margin-bottom: .5rem; align-items: center;
            box-shadow: 0 1px 2px rgba(43,38,32,0.04); transition: box-shadow .15s ease;
        }
        div[data-testid='element-container']:has(> div .row-marker-item) + div[data-testid='stHorizontalBlock']:hover {
            box-shadow: 0 4px 14px rgba(43,38,32,0.09);
        }

        /* Buttons & inputs -------------------------------------------------*/
        .stButton > button, .stFormSubmitButton > button {
            border-radius: 9px; font-weight: 600; border: 1px solid var(--clay-border);
            transition: transform .1s ease, box-shadow .15s ease;
        }
        .stButton > button:hover, .stFormSubmitButton > button:hover { box-shadow: 0 2px 8px rgba(43,38,32,0.12); }
        div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea,
        div[data-baseweb="select"] > div {
            border-radius: 9px !important; border-color: var(--clay-border) !important;
        }

        /* st.page_link back-to-dashboard button ---------------------------*/
        [data-testid="stPageLink"] {
            border: 1px solid var(--clay-border); border-radius: 10px; background: #FFFFFF;
            padding: .35rem .6rem; box-shadow: 0 1px 3px rgba(43,38,32,0.05);
        }
        [data-testid="stPageLink"]:hover { border-color: var(--clay-accent); }

        /* Alerts — soften default saturation to match the palette ---------*/
        div[data-testid="stAlertContainer"] { border-radius: 12px; }

        /* Status pill badges -------------------------------------------- */
        .status-pill {
            display: inline-block; padding: .18rem .65rem; border-radius: 999px;
            font-size: .78rem; font-weight: 700; color: #FFFFFF;
        }

        hr { border-color: var(--clay-border); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def app_header(title: str, eyebrow: str = "AI Marketing Studio") -> None:
    """Hero-style page heading used in place of a plain st.title, framed as
    part of a small brand identity since the app has no sidebar/navbar."""
    st.markdown(
        f"""
        <div class="app-header">
            <span class="app-eyebrow">{eyebrow}</span>
            <div class="app-title">{title}</div>
            <div class="app-title-bar"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_badge(status: str) -> str:
    """Colored pill HTML for a product/version status string. Render with
    unsafe_allow_html=True."""
    color = STATUS_COLORS.get(status, "#7A756C")
    return f"<span class='status-pill' style='background:{color};'>{status}</span>"


def row_marker(kind: str) -> None:
    """Invisible marker placed immediately before a st.columns(...) row so
    inject_theme_css() can style that row as a card via the :has() +
    adjacent-sibling trick already used by colored_button()."""
    st.markdown(f"<span class='row-marker row-marker-{kind}'></span>", unsafe_allow_html=True)


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
        "  background-color: #2F8F5F; border-color: #2F8F5F; color: #fff; border-radius: 9px;"
        "}"
        "div[data-testid='element-container']:has(> div .btn-marker-approve)"
        " + div[data-testid='element-container'] button:hover {"
        "  background-color: #24734B; border-color: #24734B; color: #fff;"
        "}"
        "div[data-testid='element-container']:has(> div .btn-marker-approve)"
        " + div[data-testid='element-container'] button p { color: #fff; }"
        "div[data-testid='element-container']:has(> div .btn-marker-reject)"
        " + div[data-testid='element-container'] button,"
        "div[data-testid='element-container']:has(> div .btn-marker-delete)"
        " + div[data-testid='element-container'] button {"
        "  background-color: #C1443B; border-color: #C1443B; color: #fff; border-radius: 9px;"
        "}"
        "div[data-testid='element-container']:has(> div .btn-marker-reject)"
        " + div[data-testid='element-container'] button:hover,"
        "div[data-testid='element-container']:has(> div .btn-marker-delete)"
        " + div[data-testid='element-container'] button:hover {"
        "  background-color: #9C362E; border-color: #9C362E; color: #fff;"
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
