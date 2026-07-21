from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRECTORIES = {".git", ".next", ".pytest_cache", "__pycache__", "node_modules"}
CJK_RANGES = (
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0x20000, 0x3134F),
)
ESCAPED_CODEPOINT = re.compile(r"\\u([0-9a-fA-F]{4})|\\U([0-9a-fA-F]{8})")


def _is_cjk(codepoint: int) -> bool:
    return any(start <= codepoint <= end for start, end in CJK_RANGES)


def _candidate_files() -> list[Path]:
    files: list[Path] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRECTORIES for part in path.relative_to(REPO_ROOT).parts):
            continue
        files.append(path)
    return files


def _find_violations(path: Path) -> list[tuple[int, str]]:
    payload = path.read_bytes()
    if b"\x00" in payload:
        return []
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return []

    violations: list[tuple[int, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        has_literal = any(_is_cjk(ord(character)) for character in line)
        has_escape = any(
            _is_cjk(int(match.group(1) or match.group(2), 16))
            for match in ESCAPED_CODEPOINT.finditer(line)
        )
        if has_literal or has_escape:
            violations.append((line_number, line.strip()))
    return violations


def main() -> int:
    findings: list[tuple[Path, int, str]] = []
    for path in _candidate_files():
        for line_number, line in _find_violations(path):
            findings.append((path.relative_to(REPO_ROOT), line_number, line))

    if findings:
        print("Public English-only check failed:")
        for path, line_number, line in findings:
            print(f"- {path}:{line_number}: {line}")
        return 1

    print("Public English-only check passed: no CJK ideographs found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
