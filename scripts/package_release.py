# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Package the PenG project into an open-format source release archive (.tar.gz)."""
import hashlib
import os
from pathlib import Path
import tarfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "dist"
ARCHIVE_NAME = "PenG-1.0.0.tar.gz"
OUTPUT_PATH = DIST_DIR / ARCHIVE_NAME

# Patterns / directory names to exclude from the release bundle
EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    ".opencode",
    ".agents",
    "models",
    "__pycache__",
    ".pytest_cache",
    ".cache",
    "dist",
    "build",
    "uploads",
    "temp",
    "lightrag_data",
    "chroma_data",
    "node_modules",
    ".idea",
    ".vscode",
    ".ipynb_checkpoints",
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".gguf",
    ".db",
    ".sqlite3",
    ".db-wal",
    ".db-shm",
    ".db-journal",
    ".log",
}

EXCLUDE_FILES = {
    ".env",
    "skills-lock.json",
    "AGENTS.md",
    "Plan.md",
    "opencode.json",
    ".DS_Store",
    "Thumbs.db",
}


def should_exclude(rel_path: Path) -> bool:
    """Return True if path matches any exclusion rule."""
    parts = rel_path.parts
    # Check directory names
    for part in parts[:-1]:
        if part in EXCLUDE_DIRS or part.endswith(".egg-info"):
            return True
    if parts[-1] in EXCLUDE_DIRS or parts[-1].endswith(".egg-info"):
        return True

    # Check filename & extension
    filename = parts[-1]
    if filename in EXCLUDE_FILES:
        return True
    _, ext = os.path.splitext(filename)
    if ext.lower() in EXCLUDE_EXTENSIONS:
        return True

    return False


def create_release_archive():
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    if OUTPUT_PATH.exists():
        OUTPUT_PATH.unlink()

    print(f"Packaging open-format release archive: {OUTPUT_PATH}...")
    included_count = 0

    with tarfile.open(OUTPUT_PATH, "w:gz") as tar:
        for root, dirs, files in os.walk(PROJECT_ROOT):
            # Prune excluded directories early for performance
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.endswith(".egg-info")]

            for file in sorted(files):
                file_path = Path(root) / file
                rel_path = file_path.relative_to(PROJECT_ROOT)

                if should_exclude(rel_path):
                    continue

                arcname = str(Path("PenG-1.0.0") / rel_path).replace("\\", "/")
                tar.add(file_path, arcname=arcname)
                included_count += 1

    size_mb = OUTPUT_PATH.stat().st_size / (1024 * 1024)

    # Compute SHA-256
    sha256_hash = hashlib.sha256()
    with open(OUTPUT_PATH, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256_hash.update(chunk)
    checksum = sha256_hash.hexdigest()

    checksum_file = DIST_DIR / f"{ARCHIVE_NAME}.sha256"
    checksum_file.write_text(f"{checksum}  {ARCHIVE_NAME}\n", encoding="utf-8")

    print(f"SUCCESS: Created {OUTPUT_PATH}")
    print(f"Total files included: {included_count}")
    print(f"Archive size: {size_mb:.2f} MB")
    print(f"SHA-256: {checksum}")
    print(f"Checksum written to: {checksum_file}")


if __name__ == "__main__":
    create_release_archive()
