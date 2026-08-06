"""Smoke tests that actually render the Streamlit pages.

Streamlit only executes a page's script when a session connects, so a page can
be completely broken while the server still answers HTTP 200. `AppTest` runs the
script for real and exposes the rendered elements, which is the only cheap way
to catch an import error, a bad `st.*` call or a crash in page logic.

The worker autostart is disabled throughout: these tests render pages, they do
not want a background thread polling the job queue.
"""
from __future__ import annotations

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

DASHBOARD = "streamlit_app/app.py"
# switch_page resolves relative to the main script's directory, not the cwd.
OUTPUT = "pages/1_Output.py"


@pytest.fixture(autouse=True)
def no_worker(monkeypatch):
    import worker.autostart

    monkeypatch.setattr(worker.autostart, "ensure_worker_running", lambda: None)


@pytest.fixture
def seeded(temp_db):
    from database.repository import create_product

    return create_product("8.5 Off-Road Pro", "https://radboards.in/products/8-5-off-road-pro")


class TestDashboard:
    def test_renders_without_error(self, seeded):
        app = AppTest.from_file(DASHBOARD, default_timeout=60).run()
        assert not app.exception

    def test_shows_a_status_metric_per_lifecycle_state(self, seeded):
        app = AppTest.from_file(DASHBOARD, default_timeout=60).run()
        metrics = {metric.label: metric.value for metric in app.metric}
        assert metrics["Pending"] == "1"
        assert metrics["Approved"] == "0"

    def test_warns_when_no_api_key_is_configured(self, seeded, monkeypatch):
        from config import settings

        monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
        monkeypatch.setattr(settings, "GEMINI_API_KEY", "")

        app = AppTest.from_file(DASHBOARD, default_timeout=60).run()
        errors = " ".join(error.value for error in app.error)
        assert "GEMINI_API_KEY" in errors
        assert "not configured" in errors.lower()

    def test_no_key_warning_when_configured(self, seeded, monkeypatch):
        from config import settings

        monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
        monkeypatch.setattr(settings, "GEMINI_API_KEY", "AIzaSy-plausible-enough-for-a-test")

        app = AppTest.from_file(DASHBOARD, default_timeout=60).run()
        assert not any("not configured" in error.value.lower() for error in app.error)


def open_output_page(product_id: str | None = None) -> "AppTest":
    """Navigate to the Output page the way the app does.

    The page must be reached *through* the Dashboard rather than loaded
    directly: `AppTest.from_file(OUTPUT)` would make it the main script, and
    its `st.page_link("app.py")` back-button then has no main script to point
    at. Going via `switch_page` also matches how a reviewer actually gets here.
    """
    app = AppTest.from_file(DASHBOARD, default_timeout=60).run()
    if product_id is not None:
        app.query_params["product_id"] = product_id
    return app.switch_page(OUTPUT).run()


class TestOutputPage:
    def test_renders_with_no_product_selected(self, temp_db):
        app = open_output_page()
        assert not app.exception
        assert any("Dashboard" in info.value for info in app.info)

    def test_renders_for_a_product_with_no_versions(self, seeded):
        app = open_output_page(str(seeded.id))
        assert not app.exception
        assert any("No versions yet" in info.value for info in app.info)

    def test_survives_an_unparseable_product_id(self, temp_db):
        app = open_output_page("not-a-number")
        assert not app.exception

    def test_survives_a_product_id_that_does_not_exist(self, temp_db):
        app = open_output_page("99999")
        assert not app.exception
