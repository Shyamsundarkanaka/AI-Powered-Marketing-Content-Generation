"""Typed dataclasses mirroring the SQLite schema."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Optional

PRODUCT_STATUSES = ("Pending", "Running", "Review", "Approved", "Rejected", "Failed", "Cancelled")
JOB_STATUSES = ("Pending", "Running", "Completed", "Failed", "Cancelled")
VERSION_STATUSES = ("Review", "Approved", "Rejected")
OUTPUT_TYPES = ("campaign_brief", "script", "caption", "hashtags", "voiceover", "video_plan", "video")
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


@dataclass
class Product:
    id: int
    name: str
    url: str
    status: str
    output_dir: str
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Product":
        return cls(**dict(row))


@dataclass
class Job:
    id: int
    product_id: int
    status: str
    error_message: Optional[str]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    current_stage: Optional[str]
    cancel_requested: bool

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Job":
        data = dict(row)
        data["cancel_requested"] = bool(data.get("cancel_requested", 0))
        return cls(**data)


@dataclass
class Version:
    id: int
    product_id: int
    job_id: Optional[int]
    version_number: int
    status: str
    reviewer_feedback: Optional[str]
    feedback_scope: Optional[str]
    output_dir: str
    created_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Version":
        data = dict(row)
        data.setdefault("feedback_scope", None)
        return cls(**data)


@dataclass
class Output:
    id: int
    version_id: int
    output_type: str
    file_path: str
    created_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Output":
        return cls(**dict(row))


@dataclass
class ScrapedData:
    id: int
    product_id: int
    title: str
    description_html: str
    description_text: str
    price: Optional[float]
    compare_at_price: Optional[float]
    image_urls: list[str]
    specs: dict[str, str]
    scraped_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "ScrapedData":
        data = dict(row)
        data["image_urls"] = json.loads(data["image_urls"])
        data["specs"] = json.loads(data["specs"])
        return cls(**data)


@dataclass
class LogEntry:
    id: int
    product_id: Optional[int]
    job_id: Optional[int]
    level: str
    message: str
    created_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "LogEntry":
        return cls(**dict(row))
