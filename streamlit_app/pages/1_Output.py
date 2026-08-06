"""Output tab: review the latest generated version for a product, with older
versions available below.

This page reads artifacts off disk and rows out of SQLite. It never imports the
`graph` package and never calls a model — rejecting a version queues a job, and
the worker does the regeneration.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from database.connection import init_db
from database.repository import (
    create_job,
    delete_product_with_files,
    get_active_job_for_product,
    get_product,
    list_jobs_for_product,
    list_outputs_for_version,
    list_versions_for_product,
    update_product_status,
    update_version_status,
)
from streamlit_app._shared import (
    STAGE_LABELS,
    centered_title,
    dashboard_button,
    hide_sidebar,
    inject_spinner_css,
    running_badge,
    stage_progress,
    tighten_top_padding,
)
from worker.autostart import ensure_worker_running

st.set_page_config(page_title="Output", page_icon="\U0001F4C4", layout="wide")
hide_sidebar()
tighten_top_padding()
inject_spinner_css()
st.markdown(
    "<style>"
    # Cap the whole page to a comfortable reading width — on wide monitors the
    # video and text were stretching edge-to-edge, which is what made the
    # page feel oversized rather than laid out for viewing.
    ".block-container { max-width: 1100px; margin-left: auto; margin-right: auto; }"
    ".stVideo video {"
    "  max-width: 340px;"
    "  max-height: 420px;"
    "  width: 100%;"
    "  height: auto;"
    "  margin: 0 auto;"
    "  display: block;"
    "}"
    "</style>",
    unsafe_allow_html=True,
)
init_db()
ensure_worker_running()

dashboard_button()

query_product_id = st.query_params.get("product_id")
product = None
if query_product_id is not None:
    try:
        product = get_product(int(query_product_id))
    except ValueError:
        product = None
if product is None:
    st.info("Open a product from the Dashboard to review its output.")
    st.stop()

centered_title(product.name)

if product.status == "Running":
    st.markdown(running_badge(f"**{product.url} · Status: {product.status}**"), unsafe_allow_html=True)
    running_job = get_active_job_for_product(product.id)
    fraction, label = stage_progress(running_job.current_stage if running_job else None)
    st.progress(fraction, text=f"⏳ Regenerating… {label}")
    st.divider()
    time.sleep(3)
    st.rerun()
else:
    st.caption(f"{product.url} · Status: {product.status}")

    if product.status == "Failed":
        jobs = list_jobs_for_product(product.id)
        last_job = jobs[0] if jobs else None
        if last_job:
            stage_label = STAGE_LABELS.get(last_job.current_stage, last_job.current_stage)
            st.error(
                f"Run failed at: **{stage_label or 'unknown stage'}**\n\n"
                f"{last_job.error_message or 'No error details recorded.'}"
            )

    delete_col, _spacer = st.columns([1, 4])
    if delete_col.button("🗑️ Delete product", key="delete_product_output"):
        st.session_state["confirm_delete_output"] = True
        st.rerun()

    if st.session_state.get("confirm_delete_output"):
        with st.container(border=True):
            st.warning(
                f"⚠️ Delete **{product.name}** (#{product.id})? This permanently removes "
                f"its database record **and every generated file** under "
                f"`{product.output_dir}` (briefs, scripts, video, voiceover, captions, "
                f"hashtags — all versions). This cannot be undone."
            )
            confirm_col, cancel_col = st.columns(2)
            if confirm_col.button("🗑️ Yes, delete permanently", key="confirm_delete_output_yes"):
                delete_product_with_files(product.id)
                st.session_state.pop("confirm_delete_output", None)
                st.success(f"Deleted '{product.name}' and its files.")
                time.sleep(1)
                st.switch_page("app.py")
            if cancel_col.button("Cancel", key="confirm_delete_output_no"):
                st.session_state.pop("confirm_delete_output", None)
                st.rerun()

st.divider()

versions = list_versions_for_product(product.id)
if not versions:
    st.info(
        "No versions yet. Queue a run from the Dashboard — the worker scrapes the "
        "product and then generates a full content version."
    )
    st.stop()


def load_meta(version) -> dict:
    """Provenance sidecar written by the pipeline's finalize node."""
    path = Path(version.output_dir) / "_meta.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def read_text(path_str: str) -> str | None:
    path = Path(path_str)
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def render_primary(by_type: dict, meta: dict) -> None:
    """The one thing a reviewer actually needs to judge: the video, its caption
    and its hashtags. No tabs, no collapsing — everything else is secondary."""
    video_col, copy_col = st.columns([2, 3])

    with video_col:
        if "video" in by_type:
            video_path = Path(by_type["video"].file_path)
            if video_path.exists():
                st.video(str(video_path))
                stats = (meta.get("content", {}) or {}).get("video") or {}
                if stats:
                    st.caption(
                        f"{stats.get('resolution', '?')} · {stats.get('fps', '?')}fps · "
                        f"{stats.get('duration_seconds', '?')}s · "
                        f"{stats.get('scene_count', '?')} scenes"
                    )
            else:
                st.warning("Video file is missing from disk.")
        else:
            st.info("No video generated for this version.")

        if "voiceover" in by_type:
            audio_path = Path(by_type["voiceover"].file_path)
            if audio_path.exists():
                st.audio(str(audio_path))
            else:
                st.warning("Voiceover file is missing from disk.")

    with copy_col:
        if "caption" in by_type:
            st.markdown("**Caption**")
            st.text_area(
                "caption",
                read_text(by_type["caption"].file_path) or "",
                height=320,
                label_visibility="collapsed",
                key=f"caption_{by_type['caption'].id}",
            )
        if "hashtags" in by_type:
            st.markdown("**Hashtags**")
            st.code(
                read_text(by_type["hashtags"].file_path) or "",
                language=None,
                height=200,
            )


def render_details(outputs, by_type: dict, meta: dict) -> None:
    """Everything supporting the primary artifacts, tucked behind one collapsible
    section. Nothing inside here may be another st.expander — Streamlit forbids
    nesting them, which is what used to crash this page."""
    if "campaign_brief" in by_type:
        st.markdown("#### Campaign brief")
        st.markdown(read_text(by_type["campaign_brief"].file_path) or "_file missing_")
        st.divider()

    if "script" in by_type:
        st.markdown("#### Script")
        st.markdown(read_text(by_type["script"].file_path) or "_file missing_")
        st.divider()

    if "video_plan" in by_type:
        st.markdown("#### Video plan (JSON)")
        if st.checkbox("Show raw JSON", key=f"show_plan_{by_type['video_plan'].id}"):
            body = read_text(by_type["video_plan"].file_path)
            st.json(json.loads(body) if body else {})
        st.divider()

    st.markdown("#### Files")
    st.dataframe(
        [{"Type": o.output_type, "File": o.file_path, "Created": o.created_at} for o in outputs],
        use_container_width=True,
        hide_index=True,
    )


def render_review_actions(version) -> None:
    feedback = st.text_area(
        "Feedback (required to reject — it is fed into the next generation)",
        key=f"feedback_{version.id}",
    )
    approve_col, reject_col = st.columns(2)
    if approve_col.button("✅ Approve", key=f"approve_{version.id}", type="primary", use_container_width=True):
        update_version_status(version.id, "Approved")
        update_product_status(product.id, "Approved")
        st.rerun()
    if reject_col.button("🔁 Reject & regenerate", key=f"reject_{version.id}", use_container_width=True):
        if not feedback.strip():
            st.error("Feedback is required to reject — it is what makes the next version different.")
        else:
            update_version_status(version.id, "Rejected", feedback.strip())
            # Queue the regeneration. The worker reads the feedback off the
            # rejected version row and injects it into every agent prompt for
            # the next version.
            job = create_job(product.id)
            # Reflect "Running" immediately rather than waiting up to
            # WORKER_POLL_INTERVAL_SECONDS for the worker to pick the job up
            # and flip this itself — the spinner/progress bar above should
            # show on this very rerun.
            update_product_status(product.id, "Running")
            st.success(f"Queued job #{job.id} to regenerate with your feedback.")
            st.rerun()


def render_version(version, is_latest: bool) -> None:
    meta = load_meta(version)

    if version.reviewer_feedback:
        st.info(f"**Reviewer feedback:** {version.reviewer_feedback}")
    if meta.get("revision_of_feedback"):
        st.caption(f"↩️ Generated in response to: _{meta['revision_of_feedback']}_")

    outputs = list_outputs_for_version(version.id)
    if not outputs:
        st.caption("No output artifacts recorded for this version.")
        return

    by_type = {output.output_type: output for output in outputs}
    render_primary(by_type, meta)

    if st.checkbox("Show details — brief, script, video plan, files", key=f"show_details_{version.id}"):
        render_details(outputs, by_type, meta)

    if version.status == "Review":
        st.divider()
        render_review_actions(version)


def latest_status_label(status: str) -> str:
    """The latest version's status badge is reviewer-facing, so "Rejected"
    never appears here — a reject immediately re-queues a regeneration, so
    the honest state to show is that a new version is on its way."""
    if status == "Approved":
        return "Approved"
    return "Waiting for feedback"


latest = versions[0]
st.subheader(f"Latest version — v{latest.version_number} ({latest_status_label(latest.status)})")
st.caption(f"Output directory: `{latest.output_dir}`")
render_version(latest, is_latest=True)

if len(versions) > 1:
    st.divider()
    st.subheader("Previous versions")
    for version in versions[1:]:
        with st.expander(f"v{version.version_number} — {version.status} ({version.created_at})"):
            render_version(version, is_latest=False)
