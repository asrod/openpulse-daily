"""Emit a short alert only when today's OpenPulse publication is missing."""
import base64
import subprocess
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
REPO = "asrod/openpulse-daily"
TIMER = "openpulse-daily-dispatch.timer"


def local_day(now=None):
    now = now or datetime.now(timezone.utc)
    return now.astimezone(SHANGHAI).date().isoformat()


def readme_has_publication(text, day):
    return (f"# GitHub Daily · {day}" in text
            and f"[{day}](daily/{day}.md)" in text
            and f"[JSON](data/{day}.json)" in text)


def publication_ok(day):
    result = subprocess.run(["gh", "api", f"repos/{REPO}/contents/README.md", "--jq", ".content"],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        return False
    try:
        content = base64.b64decode("".join(result.stdout.split()), validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return False
    return readme_has_publication(content, day)


def timer_ok():
    return subprocess.run(["systemctl", "is-active", "--quiet", TIMER], check=False).returncode == 0


def main():
    day = local_day()
    problems = []
    if not publication_ok(day):
        problems.append(f"README/archive for {day} is missing or incomplete")
    if not timer_ok():
        problems.append(f"systemd timer {TIMER} is not active")
    if problems:
        print("⚠️ OpenPulse daily check (09:30 Asia/Shanghai): " + "; ".join(problems)
              + ". Check `systemctl status openpulse-daily-dispatch.timer` and `journalctl -u openpulse-daily-dispatch.service`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
