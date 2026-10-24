import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from update import render, update, validate

NOW = datetime(2026, 10, 24, 1, 17, tzinfo=timezone.utc)


def fixture():
    return {"data_mode": "live", "window": "24h", "sort": "growth", "as_of": NOW.isoformat(),
            "repositories": [{"full_name": "example/project", "description": "A | tool <script> [click](bad)",
                              "language": "Python", "stars_count": 1234,
                              "growth": {"status": "ready", "value": 56, "source": "sampled_snapshots",
                                         "baseline_at": (NOW - timedelta(days=1)).isoformat(), "observed_at": NOW.isoformat()}}]}


class ExporterTests(unittest.TestCase):
    def test_content_links_and_untrusted_markdown(self):
        date, report = render(fixture(), NOW)
        self.assertEqual(date, "2026-10-24")
        self.assertIn("+56", report)
        self.assertIn("https://github.com/example/project", report)
        self.assertIn("utm_source=github", report)
        self.assertIn("A \\| tool &lt;script&gt; \\[click\\]\\(bad\\)", report)
        self.assertIn("not GitHub's official", report)

    def test_date_uses_shanghai_timezone(self):
        data = fixture()
        midnight = datetime(2026, 10, 23, 16, 1, tzinfo=timezone.utc)
        data["as_of"] = midnight.isoformat()
        data["repositories"][0]["growth"]["observed_at"] = midnight.isoformat()
        self.assertEqual(render(data, midnight)[0], "2026-10-24")

    def test_source_freshness_boundaries(self):
        for age, valid in [(timedelta(hours=1), True), (timedelta(hours=1, microseconds=1), False),
                           (-timedelta(minutes=5), True), (-timedelta(minutes=5, microseconds=1), False)]:
            data = fixture()
            data["as_of"] = (NOW - age).isoformat()
            data["repositories"][0]["growth"]["observed_at"] = data["as_of"]
            if valid:
                validate(data, NOW)
            else:
                with self.assertRaises(ValueError):
                    validate(data, NOW)

    def test_invalid_input_never_replaces_publication(self):
        cases = []
        for key, value in [("data_mode", "demo"), ("repositories", []), ("window", "7d")]:
            data = fixture()
            data[key] = value
            cases.append(data)
        for status, value in [("stale", 1), ("collecting", None), ("ready", 0), ("ready", -1)]:
            data = fixture()
            data["repositories"][0]["growth"].update(status=status, value=value)
            cases.append(data)
        data = fixture()
        data["repositories"] *= 2
        cases.append(data)
        data = fixture()
        data["repositories"][0]["full_name"] = "example/project](javascript:alert)"
        cases.append(data)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("previous")
            for data in cases:
                with self.subTest(data=data):
                    with self.assertRaises(ValueError):
                        update(root, data, NOW)
                    self.assertEqual((root / "README.md").read_text(), "previous")
                    self.assertFalse((root / "daily").exists())

    def test_daily_archive_is_stable_and_next_day_is_added(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertTrue(update(root, fixture(), NOW))
            original = (root / "README.md").read_bytes()
            data = fixture()
            data["repositories"][0]["growth"]["value"] = 100
            self.assertFalse(update(root, data, NOW))
            self.assertEqual((root / "README.md").read_bytes(), original)
            tomorrow = NOW + timedelta(days=1)
            data["as_of"] = tomorrow.isoformat()
            data["repositories"][0]["growth"].update(baseline_at=NOW.isoformat(), observed_at=tomorrow.isoformat())
            self.assertTrue(update(root, data, tomorrow))
            self.assertTrue((root / "data/2026-10-24.json").exists())
            self.assertIn("daily/2026-10-24.md", (root / "README.md").read_text())


if __name__ == "__main__":
    unittest.main()
