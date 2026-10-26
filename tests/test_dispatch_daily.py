import base64
import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from scripts import dispatch_daily


class DispatchDailyTests(unittest.TestCase):
    def test_date_uses_shanghai_boundary(self):
        now = datetime(2026, 10, 25, 16, 30, tzinfo=timezone.utc)
        self.assertEqual(dispatch_daily.local_day(now), "2026-10-26")

    def test_readme_must_link_markdown_and_json(self):
        day = "2026-10-26"
        good = f"# GitHub Daily · {day}\n[{day}](daily/{day}.md) · [JSON](data/{day}.json)"
        self.assertTrue(dispatch_daily.readme_has_publication(good, day))
        self.assertFalse(dispatch_daily.readme_has_publication(good.replace("data/", "missing/"), day))

    def test_runs_since_keeps_only_today_main_manual_runs(self):
        response = [
            {"databaseId": 1, "event": "workflow_dispatch", "headBranch": "main", "status": "queued",
             "createdAt": "2026-10-26T01:18:00Z"},
            {"databaseId": 2, "event": "schedule", "headBranch": "main", "status": "in_progress",
             "createdAt": "2026-10-26T01:18:00Z"},
            {"databaseId": 3, "event": "workflow_dispatch", "headBranch": "main", "status": "completed",
             "createdAt": "2026-10-25T01:18:00Z"},
        ]
        day_start = datetime(2026, 10, 26, 1, 0, tzinfo=timezone.utc)
        with patch.object(dispatch_daily, "run_gh", return_value=SimpleNamespace(stdout=json.dumps(response))):
            selected = dispatch_daily.runs_since(day_start)
        self.assertEqual([run["databaseId"] for run in selected], [1])

    def test_publication_probe_decodes_readme(self):
        day = "2026-10-26"
        readme = f"# GitHub Daily · {day}\n[{day}](daily/{day}.md) · [JSON](data/{day}.json)"
        raw = base64.b64encode(readme.encode()).decode()
        encoded = "\n".join(raw[i:i + 76] for i in range(0, len(raw), 76))
        with patch.object(dispatch_daily, "run_gh", return_value=SimpleNamespace(returncode=0, stdout=encoded)):
            self.assertTrue(dispatch_daily.publication_exists(day))


if __name__ == "__main__":
    unittest.main()
