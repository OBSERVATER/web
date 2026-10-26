"""Scan GitHub Issue #1 markers; publication is idempotent across Action retries."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

EVENT_RE = re.compile(r"<!-- valuation-event:([A-Za-z0-9_.:-]+) -->")
REPORT_RE = re.compile(r"<!-- valuation-report:(\d{4}-\d{2}-\d{2}) -->")


def scan_text(text: str) -> dict:
    return {"published_events": sorted(set(EVENT_RE.findall(text))),
            "published_reports": sorted(set(REPORT_RE.findall(text)))}


def read_comments(repository: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid GitHub repository")
    response = subprocess.run(
        ["gh", "api", "--paginate", "-q", ".[].body",
         f"repos/{repository}/issues/1/comments"],
        text=True, capture_output=True, check=True)
    return scan_text(response.stdout)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--out", default="out/published-issue.json")
    parser.add_argument("--body", default="out/issue-comment.md")
    args = parser.parse_args()
    repo = os.environ.get("GITHUB_REPOSITORY", "OBSERVATER/web")
    if args.scan:
        observed = read_comments(repo)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(observed, indent=2), encoding="utf-8")
    elif args.publish:
        # Scan again to guard against a succeeded comment / failed state commit.
        observed = read_comments(repo)
        body = Path(args.body).read_text(encoding="utf-8")
        reports = REPORT_RE.findall(body)
        if len(reports) != 1:
            raise ValueError("Exactly one report marker required")
        if reports[0] in observed["published_reports"]:
            print(f"Report {reports[0]} already published; skipping duplicate")
            return
        # A report must not duplicate an alert already sent in another report.
        collision = set(EVENT_RE.findall(body)) & set(observed["published_events"])
        if collision:
            raise ValueError(f"Published event already in report: {sorted(collision)}")
        subprocess.run(["gh", "issue", "comment", "1", "--repo", repo,
                        "--body-file", args.body], check=True)
    else:
        parser.error("Specify --scan or --publish")


if __name__ == "__main__":
    main()
