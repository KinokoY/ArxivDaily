"""Check Git's public candidate set without printing any credential values."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess


PATTERNS = (
    re.compile(rb"\bsk-[A-Za-z0-9]{24,}\b"),
    re.compile(rb"\bSCT\d{5,}[A-Za-z0-9]{16,}\b"),
)
PRIVATE_PARTS = {".secrets", ".runtime", ".state", "__pycache__", ".pytest_cache"}


def check(root: Path, *, tracked_only: bool = False) -> tuple[int, list[str]]:
    command = ["git", "ls-files", "-z", "--cached"]
    if not tracked_only:
        command += ["--others", "--exclude-standard"]
    paths = subprocess.run(command, cwd=root, check=True, capture_output=True).stdout
    names = sorted(set(name.decode("utf-8") for name in paths.split(b"\0") if name))
    findings = []
    for name in names:
        relative = Path(name)
        if PRIVATE_PARTS.intersection(relative.parts) or relative.name == ".env" or relative.name.startswith(".env.") and relative.name != ".env.example":
            findings.append(f"{name}: private runtime file")
            continue
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            findings.append(f"{name}: invalid public file")
            continue
        data = path.read_bytes()
        if any(pattern.search(data) for pattern in PATTERNS):
            findings.append(f"{name}: credential-shaped value")
    return len(names), findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracked-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    count, findings = check(root, tracked_only=args.tracked_only)
    print(f"Checked {count} public Git candidates; {len(findings)} findings.")
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
