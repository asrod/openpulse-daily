"""Dispatch the daily publisher and monitor until the dated snapshot appears."""
import base64
import json
import subprocess
import sys
import time
from datetime import datetime, time as wall_time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
REPO = "asrod/openpulse-daily"
WORKFLOW = "daily.yml"
CHECK_INTERVAL = 15
RETRY_AFTER = 90
MAX_DISPATCHES = 5
MAX_WAIT = 20 * 60


def local_day(now=None):
    now = now or datetime.now(timezone.utc)
    return now.astimezone(SHANGHAI).date().isoformat()


def readme_has_publication(readme_text, day):
    return (f"# GitHub Daily · {day}" in readme_text
            and f"[{day}](daily/{day}.md)" in readme_text
            and f"[JSON](data/{day}.json)" in readme_text)


def run_gh(args, check=True):
    result = subprocess.run(["gh", *args], text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"gh exited {result.returncode}"
        raise RuntimeError(detail)
    return result


def publication_exists(day):
    response = run_gh(["api", f"repos/{REPO}/contents/README.md", "--jq", ".content"], check=False)
    if response.returncode:
        return False
    try:
        text = base64.b64decode("".join(response.stdout.split()), validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return False
    return readme_has_publication(text, day)


def runs_since(day_start):
    response = run_gh(["run", "list", "--repo", REPO, "--workflow", WORKFLOW,
                       "--json", "databaseId,status,conclusion,event,headBranch,createdAt", "--limit", "20"])
    runs = json.loads(response.stdout or "[]")
    return [run for run in runs if run.get("event") == "workflow_dispatch"
            and run.get("headBranch") == "main"
            and datetime.fromisoformat(run["createdAt"].replace("Z", "+00:00")) >= day_start]


def dispatch(day, attempt):
    print(f"Dispatching {WORKFLOW} for {day} (attempt {attempt}/{MAX_DISPATCHES}).", flush=True)
    return run_gh(["workflow", "run", WORKFLOW, "--repo", REPO, "--ref", "main"])


def publish_today(now=None, sleep=time.sleep, monotonic=time.monotonic):
    day = local_day(now)
    identity = run_gh(["api", "user", "--jq", ".login"]).stdout.strip()
    if identity.casefold() != "asrod":
        raise RuntimeError(f"Expected GitHub account asrod, got {identity!r}")

    if publication_exists(day):
        print(f"{day} is already published; no dispatch needed.", flush=True)
        return 0

    date_start = datetime.combine(datetime.fromisoformat(day).date(), wall_time.min, tzinfo=SHANGHAI)
    day_start = date_start.astimezone(timezone.utc)
    deadline = monotonic() + MAX_WAIT
    dispatches = 0
    last_dispatch = None

    while monotonic() < deadline:
        if publication_exists(day):
            print(f"Verified {day} publication in README.", flush=True)
            return 0
        try:
            current_runs = runs_since(day_start)
        except (RuntimeError, KeyError, ValueError, json.JSONDecodeError) as exc:
            print(f"Could not inspect workflow state: {exc}; retrying.", flush=True)
            sleep(CHECK_INTERVAL)
            continue

        active = any(run.get("status") in ("queued", "in_progress") for run in current_runs)
        elapsed = monotonic() - last_dispatch if last_dispatch is not None else None
        if not active and dispatches < MAX_DISPATCHES and (last_dispatch is None or (elapsed is not None and elapsed >= RETRY_AFTER)):
            dispatches += 1
            last_dispatch = monotonic()
            try:
                dispatch(day, dispatches)
            except RuntimeError as exc:
                print(f"Dispatch request failed: {exc}; will retry.", flush=True)
        sleep(CHECK_INTERVAL)

    raise RuntimeError(f"No {day} publication appeared after {MAX_DISPATCHES} dispatch attempts / {MAX_WAIT // 60} minutes")


def main():
    try:
        return publish_today()
    except Exception as exc:
        print(f"OpenPulse daily dispatch failed: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
