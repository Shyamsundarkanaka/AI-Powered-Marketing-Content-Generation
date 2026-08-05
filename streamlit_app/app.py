"""Streamlit control center. Products table is the primary view. No AI inference happens here."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from database.connection import init_db
from database.repository import (
    count_rejections_by_product,
    create_job,
    create_product,
    list_products,
)

st.set_page_config(page_title="Marketing Content Generator", page_icon="\U0001F4E6", layout="wide")

init_db()

st.title("AI-Powered Marketing Content Generation")
st.caption("Control center for product intake, pipeline runs and review.")

with st.expander("➕ Add Product", expanded=False):
    with st.form("add_product_form", clear_on_submit=True):
        name = st.text_input("Product name")
        url = st.text_input("Product URL")
        submitted = st.form_submit_button("Add Product")
    if submitted:
        if not name.strip() or not url.strip():
            st.error("Both product name and URL are required.")
        else:
            try:
                product = create_product(name.strip(), url.strip())
                st.success(f"Added '{product.name}' as product #{product.id}.")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("A product with this URL already exists.")

st.divider()

products = list_products()
rejection_counts = count_rejections_by_product()

ALL_STATUSES = ["Pending", "Running", "Review", "Approved", "Rejected", "Failed", "Cancelled"]

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

if not products:
    st.info("No products yet. Use **Add Product** above to add one.")
elif not filtered:
    st.warning("No products match the current filter/search.")
else:
    table_rows = [
        {
            "ID": p.id,
            "Name": p.name,
            "URL": p.url,
            "Status": p.status,
            "Last Updated": p.updated_at,
            "Rejections": rejection_counts.get(p.id, 0),
            "View Output": f"Output?product_id={p.id}",
        }
        for p in filtered
    ]
    st.dataframe(
        table_rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "URL": st.column_config.LinkColumn("URL", display_text="Open ↗"),
            "View Output": st.column_config.LinkColumn("View Output", display_text="View Output ↗"),
        },
    )

if products:
    st.divider()
    with st.expander("▶️ Queue Run", expanded=False):
        queue_options = {f"#{p.id} — {p.name} ({p.status})": p.id for p in products}
        selected_label = st.selectbox("Product", list(queue_options.keys()), key="queue_run_select")
        if st.button("Queue Run"):
            product_id = queue_options[selected_label]
            create_job(product_id)
            st.success(f"Queued a run for product #{product_id}.")
            st.rerun()
