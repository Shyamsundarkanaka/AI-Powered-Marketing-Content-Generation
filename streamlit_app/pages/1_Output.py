"""Output tab: every version generated for a product, latest first."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from database.connection import init_db
from database.repository import (
    get_product,
    list_outputs_for_version,
    list_products,
    list_versions_for_product,
    update_product_status,
    update_version_status,
)

st.set_page_config(page_title="Output", page_icon="\U0001F4C4", layout="wide")
init_db()

st.title("Output")

products = list_products()
if not products:
    st.info("No products yet. Add one from the Products tab.")
    st.stop()

query_product_id = st.query_params.get("product_id")
options = {f"#{p.id} — {p.name}": p.id for p in products}
default_index = 0
if query_product_id is not None:
    for i, p in enumerate(products):
        if str(p.id) == str(query_product_id):
            default_index = i
            break

selected_label = st.selectbox("Select a product", list(options.keys()), index=default_index)
product_id = options[selected_label]
product = get_product(product_id)

st.subheader(product.name)
st.write(f"**URL:** {product.url}")
st.write(f"**Status:** {product.status}")
st.write(f"**Output directory:** {product.output_dir}")

st.divider()

versions = list_versions_for_product(product.id)
if not versions:
    st.info("No versions yet. This product hasn't been through a pipeline run.")
    st.stop()

latest = versions[0]
st.subheader(f"Latest version — v{latest.version_number} ({latest.status})")


def render_version(version, is_latest: bool) -> None:
    label = f"v{version.version_number} — {version.status} ({version.created_at})"
    with st.expander(label, expanded=is_latest):
        st.write(f"Output directory: {version.output_dir}")
        if version.reviewer_feedback:
            st.write(f"Reviewer feedback: {version.reviewer_feedback}")

        outputs = list_outputs_for_version(version.id)
        if outputs:
            st.dataframe(
                [{"Type": o.output_type, "File": o.file_path, "Created": o.created_at} for o in outputs],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("No output artifacts recorded for this version yet.")

        if version.status == "Review":
            feedback = st.text_area("Feedback (required to reject)", key=f"feedback_{version.id}")
            approve_col, reject_col = st.columns(2)
            if approve_col.button("Approve", key=f"approve_{version.id}"):
                update_version_status(version.id, "Approved")
                update_product_status(product.id, "Approved")
                st.rerun()
            if reject_col.button("Reject", key=f"reject_{version.id}"):
                update_version_status(version.id, "Rejected", feedback or None)
                update_product_status(product.id, "Rejected")
                st.rerun()


render_version(latest, is_latest=True)

if len(versions) > 1:
    st.divider()
    st.subheader("Previous versions")
    for version in versions[1:]:
        render_version(version, is_latest=False)
