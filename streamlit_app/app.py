"""Streamlit control center. Products table is the primary view. No AI inference happens here."""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from config.logging_setup import configure_logging
from database.connection import init_db
from database.repository import (
    InvalidProductError,
    count_active_jobs,
    count_rejections_by_product,
    create_job,
    create_product,
    delete_product_with_files,
    get_active_job_for_product,
    get_product,
    list_jobs_for_product,
    list_products,
    request_job_cancel,
    update_product_status,
)
from streamlit_app._shared import (
    STAGE_LABELS,
    app_header,
    colored_button,
    hide_sidebar,
    inject_action_button_css,
    inject_spinner_css,
    inject_theme_css,
    llm_configuration_banner,
    row_marker,
    running_badge,
    stage_progress,
    status_badge,
    tighten_top_padding,
)
from worker.autostart import ensure_worker_running

st.set_page_config(page_title="Dashboard", page_icon="\U0001F4E6", layout="wide")
hide_sidebar()
tighten_top_padding()
inject_theme_css()
inject_spinner_css()
inject_action_button_css()
st.markdown(
    # Streamlit 1.38 has no way to attach a CSS class to a specific
    # st.container() call, so this reuses the marker + `:has()`/adjacent-
    # sibling trick from colored_button() (see inject_action_button_css) to
    # reach the delete-confirmation container and cap its width — otherwise
    # it stretches full-width on this page's wide layout and barely stands
    # out from the page background.
    "<style>"
    "div[data-testid='element-container']:has(> div .box-marker) { display: none; }"
    "div[data-testid='element-container']:has(> div .box-marker-delete-confirm)"
    " + div[data-testid='element-container'] {"
    "  max-width: 480px;"
    "  margin: 1rem auto;"
    "  padding: 0.25rem 0.5rem;"
    "  border-radius: 0.5rem;"
    "  background-color: rgba(255, 90, 90, 0.12);"
    "  border: 1px solid rgba(255, 90, 90, 0.4);"
    "}"
    "</style>",
    unsafe_allow_html=True,
)

configure_logging()
init_db()
ensure_worker_running()

app_header("Dashboard")
st.caption("Control center for product intake, pipeline runs and review.")

# A missing or invalid API key makes every run fail eight nodes deep. Say so
# here, once, at the top — not one failed job at a time.
llm_configuration_banner()

with st.expander("➕ Add Product", expanded=False):
    st.caption(
        "Any public Shopify product URL. The product page is re-scraped at the "
        "start of every run, so the name below is only a placeholder until then."
    )
    with st.form("add_product_form", clear_on_submit=True):
        name = st.text_input("Product name")
        url = st.text_input("Product URL", placeholder="https://…/products/…")
        submitted = st.form_submit_button("Add Product")
    if submitted:
        try:
            product = create_product(name, url)
        except InvalidProductError as exc:
            st.error(str(exc))
        except sqlite3.IntegrityError:
            st.error("A product with this URL already exists.")
        else:
            st.success(f"Added '{product.name}' as product #{product.id}.")
            st.rerun()

st.divider()

products = list_products()
rejection_counts = count_rejections_by_product()

ALL_STATUSES = ["Pending", "Running", "Review", "Approved", "Failed", "Cancelled"]

status_counts: dict[str, int] = {}
for product in products:
    status_counts[product.status] = status_counts.get(product.status, 0) + 1

cols = st.columns(len(ALL_STATUSES))
for col, status in zip(cols, ALL_STATUSES):
    col.metric(status, status_counts.get(status, 0))

st.divider()
st.subheader("Products")

filter_col, search_col = st.columns([2, 3])
with filter_col:
    status_filter = st.multiselect("Filter by status", ALL_STATUSES, default=[])
with search_col:
    search_term = st.text_input("Search by name or URL", placeholder="Type to search…")

filtered = products
if status_filter:
    filtered = [p for p in filtered if p.status in status_filter]
if search_term.strip():
    term = search_term.strip().lower()
    filtered = [p for p in filtered if term in p.name.lower() or term in p.url.lower()]

# A run is already in flight somewhere — the worker only processes one job at a
# time, so every "Run" action is disabled until it finishes. This is checked
# once per page load, so a click always reflects the latest queue state after
# the resulting st.rerun().
any_active_job = count_active_jobs() > 0

RUNNABLE_STATUSES = {"Pending", "Failed", "Cancelled"}


def action_label_for(p) -> str:
    """The text on this row's Action button — used both to render it and, so
    the Action column has something meaningful to sort by, as its sort key."""
    if p.status == "Running":
        return "Cancel"
    if p.status == "Approved":
        return "View Output"
    if p.status in RUNNABLE_STATUSES:
        return "Run" if p.status == "Pending" else "Retry"
    return "Review"


SORT_KEYS = {
    "ID": lambda p: p.id,
    "Name": lambda p: p.name.lower(),
    "Status": lambda p: p.status,
    "Last Updated": lambda p: p.updated_at,
    "Rejections": lambda p: rejection_counts.get(p.id, 0),
    "Action": lambda p: action_label_for(p),
}

sort_col = st.session_state.get("sort_col", "ID")
sort_dir = st.session_state.get("sort_dir", "asc")
filtered = sorted(filtered, key=SORT_KEYS[sort_col], reverse=(sort_dir == "desc"))

if not products:
    st.info("No products yet. Use **Add Product** above to add one.")
elif not filtered:
    st.warning("No products match the current filter/search.")
else:
    if any_active_job:
        st.caption("⏳ A run is already in progress — new runs are disabled until it finishes.")

    confirm_delete_id = st.session_state.get("confirm_delete_id")
    if confirm_delete_id is not None:
        confirm_product = get_product(confirm_delete_id)
        if confirm_product is None:
            st.session_state.pop("confirm_delete_id", None)
        else:
            st.markdown("<span class='box-marker box-marker-delete-confirm'></span>", unsafe_allow_html=True)
            with st.container(border=True):
                st.warning(
                    f"⚠️ Delete **{confirm_product.name}** (#{confirm_product.id})? This "
                    f"permanently removes its database record **and every generated file** "
                    f"under `{confirm_product.output_dir}` (briefs, scripts, video, voiceover, "
                    f"captions, hashtags — all versions). This cannot be undone."
                )
                confirm_col, cancel_col = st.columns(2)
                if colored_button(
                    confirm_col,
                    "🗑️ Yes, delete permanently",
                    key="confirm_delete_yes",
                    marker="delete",
                    use_container_width=True,
                ):
                    delete_product_with_files(confirm_delete_id)
                    st.session_state.pop("confirm_delete_id", None)
                    st.success(f"Deleted '{confirm_product.name}' and its files.")
                    st.rerun()
                if cancel_col.button("Cancel", key="confirm_delete_no", use_container_width=True):
                    st.session_state.pop("confirm_delete_id", None)
                    st.rerun()

    row_marker("header")
    header = st.columns([0.5, 1.8, 2.4, 1.1, 0.8, 1.2, 0.7])
    for col, label in zip(
        header, ["ID", "Name", "Status", "Last Updated", "Rejections", "Action", "Delete"]
    ):
        if label not in SORT_KEYS:
            col.markdown(label)
            continue
        arrow = "" if label != sort_col else (" ▲" if sort_dir == "asc" else " ▼")
        if col.button(label + arrow, key=f"sort_{label}", use_container_width=True):
            if sort_col == label:
                st.session_state["sort_dir"] = "desc" if sort_dir == "asc" else "asc"
            else:
                st.session_state["sort_col"] = label
                st.session_state["sort_dir"] = "asc"
            st.rerun()

    should_poll = False

    for p in filtered:
        row_marker("item")
        row = st.columns([0.5, 1.8, 2.4, 1.1, 0.8, 1.2, 0.7])
        row[0].write(f"#{p.id}")

        running_job = get_active_job_for_product(p.id) if p.status == "Running" else None
        if running_job is not None or p.status == "Running":
            row[1].markdown(running_badge(f"[{p.name}]({p.url})"), unsafe_allow_html=True)
            fraction, label = stage_progress(running_job.current_stage if running_job else None)
            with row[2]:
                st.progress(fraction, text=label)
            should_poll = True
        else:
            row[1].markdown(f"[{p.name}]({p.url})")
            with row[2]:
                st.markdown(status_badge(p.status), unsafe_allow_html=True)
                if p.status == "Failed":
                    # Surface exactly which pipeline node the job died on, plus
                    # the error, so a Failed row is actionable without digging
                    # into logs — current_stage/error_message come from the
                    # most recent job (list_jobs_for_product is newest-first).
                    jobs = list_jobs_for_product(p.id)
                    last_job = jobs[0] if jobs else None
                    if last_job:
                        stage_label = STAGE_LABELS.get(last_job.current_stage, last_job.current_stage)
                        detail = f"Failed at: **{stage_label or 'unknown stage'}**"
                        if last_job.error_message:
                            detail += f" — {last_job.error_message}"
                        st.caption(detail)

        row[3].write(p.updated_at)
        row[4].write(rejection_counts.get(p.id, 0))

        action_col = row[5]
        if p.status == "Running":
            if running_job and action_col.button("✋ Cancel", key=f"cancel_{p.id}", use_container_width=True):
                request_job_cancel(running_job.id)
                st.info(f"Cancel requested for product #{p.id}.")
                st.rerun()
        elif p.status == "Approved":
            if action_col.button("✅ View Output", key=f"view_{p.id}", use_container_width=True):
                st.session_state["review_product_id"] = p.id
                st.switch_page("pages/1_Output.py")
        elif p.status in RUNNABLE_STATUSES:
            label = "▶️ Run" if p.status == "Pending" else "🔁 Retry"
            if action_col.button(
                label, key=f"run_{p.id}", disabled=any_active_job, use_container_width=True
            ):
                create_job(p.id)
                # Reflect "Running" immediately rather than waiting up to
                # WORKER_POLL_INTERVAL_SECONDS for the worker to pick the job
                # up and flip this itself — the row should show the spinner
                # and progress bar on this very rerun, not the next one.
                update_product_status(p.id, "Running")
                st.success(f"Queued a run for product #{p.id}.")
                st.rerun()
        else:
            # Covers "Review" and the rare transient "Rejected" (which flips
            # back to Pending the moment feedback is submitted) — both just
            # need a way into the same Output tab to see the latest version.
            if action_col.button("📝 Review", key=f"review_{p.id}", use_container_width=True):
                st.session_state["review_product_id"] = p.id
                st.switch_page("pages/1_Output.py")

        delete_col = row[6]
        if colored_button(
            delete_col,
            "🗑️",
            key=f"delete_{p.id}",
            marker="delete",
            use_container_width=True,
            disabled=p.status == "Running",
            help="Delete this product, its jobs/versions and all generated files",
        ):
            st.session_state["confirm_delete_id"] = p.id
            st.rerun()

    if should_poll:
        time.sleep(2)
        st.rerun()
