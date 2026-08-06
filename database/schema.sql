-- SQLite is the source of truth for products, jobs, versions, outputs and logs.
-- Product lifecycle: Pending -> Running -> Review -> Approved | Rejected | Failed | Cancelled

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    url             TEXT NOT NULL UNIQUE,
    status          TEXT NOT NULL DEFAULT 'Pending'
                        CHECK (status IN ('Pending', 'Running', 'Review', 'Approved',
                                           'Rejected', 'Failed', 'Cancelled')),
    output_dir      TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'Pending'
                        CHECK (status IN ('Pending', 'Running', 'Completed', 'Failed', 'Cancelled')),
    error_message   TEXT,
    current_stage   TEXT,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    started_at      TEXT,
    completed_at    TEXT
);

CREATE TABLE IF NOT EXISTS versions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id          INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    job_id              INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
    version_number      INTEGER NOT NULL,
    status              TEXT NOT NULL DEFAULT 'Review'
                            CHECK (status IN ('Review', 'Approved', 'Rejected')),
    reviewer_feedback   TEXT,
    feedback_scope      TEXT,
    output_dir          TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (product_id, version_number)
);

CREATE TABLE IF NOT EXISTS outputs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id      INTEGER NOT NULL REFERENCES versions(id) ON DELETE CASCADE,
    output_type     TEXT NOT NULL
                        CHECK (output_type IN ('campaign_brief', 'script', 'caption', 'hashtags',
                                                'voiceover', 'video_plan', 'video')),
    file_path       TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS scraped_data (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id          INTEGER NOT NULL UNIQUE REFERENCES products(id) ON DELETE CASCADE,
    title               TEXT NOT NULL,
    description_html    TEXT NOT NULL DEFAULT '',
    description_text    TEXT NOT NULL DEFAULT '',
    price               REAL,
    compare_at_price    REAL,
    image_urls          TEXT NOT NULL DEFAULT '[]',
    specs               TEXT NOT NULL DEFAULT '{}',
    scraped_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER REFERENCES products(id) ON DELETE CASCADE,
    job_id          INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    level           TEXT NOT NULL DEFAULT 'INFO'
                        CHECK (level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR')),
    message         TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_product_id ON jobs(product_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_versions_product_id ON versions(product_id);
CREATE INDEX IF NOT EXISTS idx_outputs_version_id ON outputs(version_id);
CREATE INDEX IF NOT EXISTS idx_logs_product_id ON logs(product_id);
