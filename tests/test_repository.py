"""Tests for the database layer and the scraper's parsing.

These run against a real temporary SQLite file rather than a mock, because the
behaviour worth testing here — cascade deletes, the UNIQUE constraint on URLs,
WAL-mode concurrency — lives in SQLite itself.
"""
from __future__ import annotations

import sqlite3

import pytest

from database.repository import (
    InvalidProductError,
    add_log,
    add_output,
    count_active_jobs,
    count_rejections_by_product,
    create_job,
    create_product,
    create_version,
    delete_product_with_files,
    get_active_job_for_product,
    get_next_pending_job,
    get_product,
    get_scraped_data,
    list_outputs_for_version,
    list_versions_for_product,
    next_version_number,
    reclaim_stale_jobs,
    slugify,
    update_job_status,
    update_version_status,
    upsert_scraped_data,
)

URL = "https://example.com/products/board"


class TestSlugify:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("8.5 Off-Road Pro", "8-5-off-road-pro"),
            ("Classic 6.5  LIMITED EDITION", "classic-6-5-limited-edition"),
            ("  spaced  out  ", "spaced-out"),
            ("Ünïcodé", "n-cod"),
        ],
    )
    def test_produces_a_filesystem_safe_slug(self, name, expected):
        assert slugify(name) == expected

    def test_never_returns_an_empty_slug(self):
        # An all-symbol name would otherwise collapse to "", and every such
        # product would share one output directory.
        assert slugify("!!!") == "product"
        assert slugify("") == "product"


class TestCreateProduct:
    def test_creates_with_an_output_directory(self, temp_db):
        product = create_product("8.5 Off-Road Pro", URL)
        assert product.status == "Pending"
        assert product.output_dir.endswith("8-5-off-road-pro")

    def test_rejects_a_duplicate_url(self, temp_db):
        create_product("Board", URL)
        with pytest.raises(sqlite3.IntegrityError):
            create_product("Board Again", URL)

    @pytest.mark.parametrize("url", ["", "not-a-url", "ftp://example.com/x", "example.com/x"])
    def test_rejects_an_unusable_url(self, temp_db, url):
        with pytest.raises(InvalidProductError):
            create_product("Board", url)

    def test_rejects_a_blank_name(self, temp_db):
        with pytest.raises(InvalidProductError):
            create_product("   ", URL)

    def test_same_name_gets_a_distinct_directory(self, temp_db):
        first = create_product("Classic 6.5", "https://example.com/a/classic")
        second = create_product("Classic 6.5", "https://example.com/b/classic")
        assert first.output_dir != second.output_dir


class TestJobs:
    def test_queue_is_fifo(self, temp_db):
        first = create_product("A", "https://example.com/products/a")
        second = create_product("B", "https://example.com/products/b")
        job_a = create_job(first.id)
        create_job(second.id)
        assert get_next_pending_job().id == job_a.id

    def test_active_count_tracks_pending_and_running(self, temp_db):
        product = create_product("A", URL)
        job = create_job(product.id)
        assert count_active_jobs() == 1
        update_job_status(job.id, "Running")
        assert count_active_jobs() == 1
        update_job_status(job.id, "Completed")
        assert count_active_jobs() == 0

    def test_completion_records_an_error_message(self, temp_db):
        product = create_product("A", URL)
        job = create_job(product.id)
        update_job_status(job.id, "Failed", error_message="boom")
        from database.repository import get_job

        assert get_job(job.id).error_message == "boom"

    def test_reclaims_orphaned_running_jobs(self, temp_db):
        """A worker that died mid-job would otherwise leave count_active_jobs()
        permanently non-zero, disabling every Run button forever."""
        product = create_product("A", URL)
        job = create_job(product.id)
        update_job_status(job.id, "Running")

        assert reclaim_stale_jobs() == [product.id]
        assert count_active_jobs() == 0
        assert reclaim_stale_jobs() == []  # idempotent

    def test_active_job_lookup(self, temp_db):
        product = create_product("A", URL)
        assert get_active_job_for_product(product.id) is None
        job = create_job(product.id)
        assert get_active_job_for_product(product.id).id == job.id


class TestVersions:
    def test_version_numbers_increment_per_product(self, temp_db):
        product = create_product("A", URL)
        assert next_version_number(product.id) == 1
        create_version(product.id, None)
        assert next_version_number(product.id) == 2
        assert create_version(product.id, None).version_number == 2

    def test_next_version_number_does_not_create_a_row(self, temp_db):
        product = create_product("A", URL)
        next_version_number(product.id)
        next_version_number(product.id)
        assert list_versions_for_product(product.id) == []

    def test_versions_are_listed_newest_first(self, temp_db):
        product = create_product("A", URL)
        create_version(product.id, None)
        create_version(product.id, None)
        numbers = [v.version_number for v in list_versions_for_product(product.id)]
        assert numbers == [2, 1]

    def test_rejection_stores_feedback_and_scope(self, temp_db):
        product = create_product("A", URL)
        version = create_version(product.id, None)
        update_version_status(version.id, "Rejected", "too corporate", "caption,hashtags")

        stored = list_versions_for_product(product.id)[0]
        assert stored.status == "Rejected"
        assert stored.reviewer_feedback == "too corporate"
        assert stored.feedback_scope == "caption,hashtags"

    def test_rejection_counts_group_by_product(self, temp_db):
        product = create_product("A", URL)
        for _ in range(2):
            update_version_status(create_version(product.id, None).id, "Rejected", "no")
        assert count_rejections_by_product() == {product.id: 2}


class TestCascadesAndOutputs:
    def test_outputs_are_listed_for_their_version(self, temp_db, tmp_path):
        product = create_product("A", URL)
        version = create_version(product.id, None)
        add_output(version.id, "caption", str(tmp_path / "caption.txt"))
        add_output(version.id, "video", str(tmp_path / "video.mp4"))
        assert {o.output_type for o in list_outputs_for_version(version.id)} == {"caption", "video"}

    def test_deleting_a_product_cascades_and_removes_files(self, temp_db, tmp_path):
        product = create_product("A", URL)
        version = create_version(product.id, None)
        add_output(version.id, "caption", "x.txt")
        create_job(product.id)
        add_log("hello", product_id=product.id)

        directory = tmp_path / "output" / "a"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "video.mp4").write_text("data", encoding="utf-8")

        delete_product_with_files(product.id)

        assert get_product(product.id) is None
        assert list_versions_for_product(product.id) == []
        assert list_outputs_for_version(version.id) == []
        assert count_active_jobs() == 0


class TestScrapedData:
    def test_upsert_overwrites_rather_than_duplicating(self, temp_db):
        product = create_product("A", URL)
        for price in (100.0, 200.0):
            upsert_scraped_data(
                product_id=product.id,
                title="Board",
                description_html="<p>x</p>",
                description_text="x",
                price=price,
                compare_at_price=None,
                image_urls=["https://img/1.jpg"],
                specs={"Range": "45 km"},
            )
        stored = get_scraped_data(product.id)
        assert stored.price == 200.0

    def test_json_columns_round_trip(self, temp_db):
        product = create_product("A", URL)
        upsert_scraped_data(
            product_id=product.id,
            title="Board",
            description_html="",
            description_text="",
            price=None,
            compare_at_price=None,
            image_urls=["https://img/1.jpg", "https://img/2.jpg"],
            specs={"Range": "45 km", "Motor": "700W"},
        )
        stored = get_scraped_data(product.id)
        assert stored.image_urls == ["https://img/1.jpg", "https://img/2.jpg"]
        assert stored.specs["Motor"] == "700W"

    def test_missing_scraped_data_returns_none(self, temp_db):
        product = create_product("A", URL)
        assert get_scraped_data(product.id) is None
