"""Wipe the database and generated files back to a clean install.

    python -m database.reset            # ask first, then wipe and re-seed
    python -m database.reset --yes      # no prompt (for scripts)
    python -m database.reset --keep-cache   # leave downloaded product photos

This is destructive and says so: it removes every product, job, version, log
row and every generated artifact on disk. It exists because the alternative —
deleting `data/app.db` by hand and then wondering why `output/` still has
directories for products that no longer exist — leaves the two out of sync.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from config.logging_setup import configure_logging
from config.settings import ASSET_CACHE_DIR, DATABASE_PATH, OUTPUT_DIR, ensure_directories
from database.connection import init_db
from database.seed_products import SEED_PRODUCTS, seed


def _remove_children(directory: Path) -> int:
    """Empty a directory without removing the directory itself."""
    if not directory.is_dir():
        return 0
    removed = 0
    for child in directory.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)
        removed += 1
    return removed


def reset(*, keep_cache: bool = False, reseed: bool = True) -> None:
    # SQLite in WAL mode keeps two sidecar files; leaving them behind next to a
    # deleted database is what produces "file is not a database" on next open.
    for suffix in ("", "-wal", "-shm"):
        Path(str(DATABASE_PATH) + suffix).unlink(missing_ok=True)
    print(f"  - removed database {DATABASE_PATH.name}")

    print(f"  - removed {_remove_children(OUTPUT_DIR)} entries from {OUTPUT_DIR}")
    if keep_cache:
        print(f"  = kept cached product images in {ASSET_CACHE_DIR}")
    else:
        print(f"  - removed {_remove_children(ASSET_CACHE_DIR)} cached images")

    ensure_directories()
    init_db()
    print("  + created an empty database")

    if reseed:
        print(f"\nSeeding {len(SEED_PRODUCTS)} products…")
        seed()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    parser.add_argument("--keep-cache", action="store_true", help="Keep downloaded product images.")
    parser.add_argument("--no-seed", action="store_true", help="Leave the product table empty.")
    args = parser.parse_args()

    configure_logging()
    if not args.yes:
        print("This deletes ALL products, jobs, versions, logs and generated files.")
        print(f"  database: {DATABASE_PATH}")
        print(f"  output:   {OUTPUT_DIR}")
        if input("Type 'reset' to continue: ").strip().lower() != "reset":
            raise SystemExit("Cancelled — nothing was changed.")

    print("\nResetting…")
    reset(keep_cache=args.keep_cache, reseed=not args.no_seed)
    print("\nDone.")


if __name__ == "__main__":
    main()
