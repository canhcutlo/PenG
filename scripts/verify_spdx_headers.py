# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Script to verify that all source files contain the required SPDX license header."""
import sys
from pathlib import Path

PYTHON_HEADER = (
    "# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành\n"
    "# SPDX-License-Identifier: MIT"
)

HTML_HEADER = (
    "<!--\n"
    "  Copyright (c) 2026 Team PenG - Nguyễn Trung Thành\n"
    "  SPDX-License-Identifier: MIT\n"
    "-->"
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHECK_DIRS = [
    PROJECT_ROOT / "app",
    PROJECT_ROOT / "tests",
    PROJECT_ROOT / "scripts",
]
HTML_FILE = PROJECT_ROOT / "static" / "index.html"


def verify_headers() -> bool:
    missing_or_invalid = []
    total_py = 0

    for directory in CHECK_DIRS:
        for py_path in sorted(directory.rglob("*.py")):
            if any(part.startswith(".") or part == "__pycache__" for part in py_path.parts):
                continue
            total_py += 1
            content = py_path.read_text(encoding="utf-8")
            # Normalize newlines for inspection
            content_norm = content.replace("\r\n", "\n")
            if not content_norm.startswith(PYTHON_HEADER):
                # Check if shebang is at line 0
                lines = content_norm.split("\n", 2)
                if lines and lines[0].startswith("#!"):
                    sub = content_norm[len(lines[0]) + 1:].lstrip("\n")
                    if not sub.startswith(PYTHON_HEADER):
                        missing_or_invalid.append((py_path, "Python header missing after shebang"))
                else:
                    missing_or_invalid.append((py_path, "Python header missing at file start"))

    # Check static/index.html
    total_html = 0
    if HTML_FILE.exists():
        total_html += 1
        html_content = HTML_FILE.read_text(encoding="utf-8").replace("\r\n", "\n")
        if not html_content.startswith(HTML_HEADER):
            missing_or_invalid.append((HTML_FILE, "HTML header missing at file start"))
    else:
        missing_or_invalid.append((HTML_FILE, "File does not exist"))

    print(f"Scanned {total_py} Python files and {total_html} HTML files.")
    if missing_or_invalid:
        print(f"FAILURE: Found {len(missing_or_invalid)} files with missing or invalid headers:")
        for path, reason in missing_or_invalid:
            print(f"  - {path.relative_to(PROJECT_ROOT)}: {reason}")
        return False

    print("SUCCESS: 100% of source files contain valid SPDX License Headers!")
    return True


if __name__ == "__main__":
    success = verify_headers()
    sys.exit(0 if success else 1)
