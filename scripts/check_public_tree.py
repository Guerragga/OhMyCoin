"""Heuristic release-tree checks; not a replacement for a secrets scanner/review."""

from pathlib import Path
import re
import subprocess


def main():
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\0")
    patterns = {
        "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
        "AWS access key": re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
        "personal Windows path": re.compile(r"[A-Z]:\\Users\\", re.IGNORECASE),
    }
    email_pattern = re.compile(r"\b[A-Za-z0-9][A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
    failures = []
    for name in filter(None, tracked):
        path = Path(name)
        if path.name == ".env" or path.suffix in {".pem", ".key", ".sqlite3"}:
            failures.append((name, "sensitive file type"))
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in patterns.items():
            if pattern.search(content):
                failures.append((name, label))
        for match in email_pattern.finditer(content):
            if match.group(1).lower() not in {"example.com", "example.org", "example.net", "exemplo.com"}:
                failures.append((name, "non-example email"))
    if failures:
        # Report locations/categories, never the matched potentially sensitive values.
        for name, label in sorted(set(failures)):
            print(f"{name}: {label}")
        raise SystemExit(1)
    print("Tracked source tree passed heuristic secret/path/email checks.")


if __name__ == "__main__":
    main()
