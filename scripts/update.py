"""Publish a dated snapshot of OpenPulse's public rolling-24h leaderboard."""
import argparse
import html
import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

SITE = "https://openpulse.info"
API = SITE + "/api/repositories?" + urlencode({"window": "24h", "view": "trending", "limit": 20, "include_history": "false"})
SHANGHAI = ZoneInfo("Asia/Shanghai")


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Source timestamps must include a timezone")
    return result


def cell(value):
    value = html.escape(" ".join(str(value or "—").split()), quote=True)
    return re.sub(r"([\\`*_{}\[\]()|#!])", r"\\\1", value)


def validate(data, now):
    if data.get("data_mode") != "live" or data.get("window") != "24h" or data.get("sort") != "growth":
        raise ValueError("Expected the live rolling-24h growth leaderboard")
    as_of = timestamp(data["as_of"])
    if not now - timedelta(hours=1) <= as_of <= now + timedelta(minutes=5):
        raise ValueError("The source leaderboard is outdated or has a future timestamp")
    rows = data["repositories"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 20:
        raise ValueError("Refusing to replace a leaderboard with empty or invalid results")
    seen = set()
    for row in rows:
        name, growth = row["full_name"], row["growth"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", name) or name.lower() in seen:
            raise ValueError("Invalid or duplicated repository identity")
        seen.add(name.lower())
        if (growth.get("status") != "ready" or type(growth.get("value")) is not int or growth["value"] <= 0
                or type(row.get("stars_count")) is not int or row["stars_count"] < 0):
            raise ValueError("Only available, positive, measured growth belongs on this leaderboard")
        if growth.get("source") not in ("sampled_snapshots", "github_star_history"):
            raise ValueError("Unknown growth evidence source")
        baseline, observed = timestamp(growth["baseline_at"]), timestamp(growth["observed_at"])
        if baseline >= observed or observed > as_of + timedelta(minutes=5):
            raise ValueError("Invalid growth observation interval")
    return rows


def campaign(path, date, placement):
    return SITE + path + "?" + urlencode({"utm_source": "github", "utm_medium": "daily-leaderboard",
                                         "utm_campaign": date, "utm_content": placement})


def render(data, now):
    rows = validate(data, now)
    date = now.astimezone(SHANGHAI).date().isoformat()
    as_of = timestamp(data["as_of"]).astimezone(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S") + " Asia/Shanghai"
    lines = [f"# GitHub Daily · {date}", "", "Daily open-source discoveries, powered by [OpenPulse](https://openpulse.info).",
             "", f"[Explore the live leaderboard, filters and history →]({campaign('/trending', date, 'header')})", "",
             f"Snapshot: **{as_of}**. Ranked by OpenPulse's rolling-24h Trending view among tracked public repositories.",
             "This is not GitHub's official Trending ranking or a midnight-to-midnight daily total.", "",
             "| # | Repository | Description | Language | Stars | Growth · 24h | History |",
             "| --: | --- | --- | --- | --: | --: | --- |"]
    for rank, row in enumerate(rows, 1):
        name = row["full_name"]
        detail = campaign("/repositories/" + quote(name, safe="/"), date, "repository")
        lines.append(f"| {rank} | [{cell(name)}](https://github.com/{quote(name, safe='/')}) | {cell(row.get('description'))} | "
                     f"{cell(row.get('language'))} | {row['stars_count']:,} | +{row['growth']['value']:,} | [Trend ↗]({detail}) |")
    lines += ["", "## How to read this list", "",
              "- Coverage is limited to repositories tracked by OpenPulse; it is not all of GitHub.",
              "- The order matches the source Trending view, which prioritizes fresh sampled growth before available historical backfills.",
              "- Growth is net star change across each project's available rolling interval. Exact baseline and observation times are included in the JSON snapshot and on the website.",
              "- Unavailable or stale growth is never replaced with zero. If the source fails validation, the previous publication is kept and the workflow fails visibly.",
              "- A leaderboard position describes observed attention, not project quality or an endorsement.", "",
              "## Follow & contribute", "",
              "Star this repository to bookmark it. Browse the dated Markdown archives for earlier snapshots.",
              f"For live updates, topic/language filters and project history, visit [OpenPulse]({campaign('/trending', date, 'footer')}).",
              "Ideas and corrections are welcome in Issues. Please include a project link and a concrete suggestion.", ""]
    return date, "\n".join(lines)


def update(root, data, now):
    date, report = render(data, now)  # Validate everything before modifying any publication.
    daily, snapshots = root / "daily", root / "data"
    daily.mkdir(exist_ok=True)
    snapshots.mkdir(exist_ok=True)
    archive = daily / f"{date}.md"
    # Keep the first successful daily snapshot stable; manual runs verify the
    # workflow without rewriting the day's historical record.
    if archive.exists():
        return False
    snapshot = {"published_at": now.isoformat(), "as_of": data["as_of"], "window": "24h",
                "coverage": data.get("coverage"), "repositories": data["repositories"]}
    archive.write_text(report, encoding="utf-8")
    (snapshots / f"{date}.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    dates = sorted((p.stem for p in daily.glob("????-??-??.md")), reverse=True)
    archives = "\n".join(f"- [{day}](daily/{day}.md) · [JSON](data/{day}.json)" for day in dates[:31])
    (root / "README.md").write_text(report + "\n## Recent archives\n\n" + archives + "\n\n"
                                    "All historical snapshots remain in [`daily/`](daily/) and [`data/`](data/).\n", encoding="utf-8")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    request = urllib.request.Request(API, headers={"User-Agent": "OpenPulse-Daily/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise ValueError("Source API did not return HTTP 200")
        payload = response.read(2_000_001)
        if len(payload) > 2_000_000:
            raise ValueError("Source response exceeded the size limit")
        data = json.loads(payload)
    changed = update(args.output, data, datetime.now(timezone.utc))
    print("Daily snapshot generated." if changed else "Today's snapshot already exists; archive preserved.")


if __name__ == "__main__":
    main()
