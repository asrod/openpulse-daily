import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from scripts import check_daily_publication


class CheckDailyPublicationTests(unittest.TestCase):
    def test_shanghai_date_and_readme_validation(self):
        now = datetime(2026, 10, 25, 16, 30, tzinfo=timezone.utc)
        self.assertEqual(check_daily_publication.local_day(now), "2026-10-26")
        day = "2026-10-26"
        valid = f"# GitHub Daily · {day}\n[{day}](daily/{day}.md) · [JSON](data/{day}.json)"
        self.assertTrue(check_daily_publication.readme_has_publication(valid, day))
        self.assertFalse(check_daily_publication.readme_has_publication(valid.replace("[JSON]", ""), day))

    def test_missing_publication_prints_alert(self):
        with patch.object(check_daily_publication, "publication_ok", return_value=False), \
             patch.object(check_daily_publication, "timer_ok", return_value=True), \
             patch.object(check_daily_publication, "local_day", return_value="2026-10-26"), \
             patch("builtins.print") as emit:
            self.assertEqual(check_daily_publication.main(), 0)
        emit.assert_called_once()
        self.assertIn("2026-10-26", emit.call_args.args[0])

    def test_published_and_active_timer_emit_no_alert(self):
        with patch.object(check_daily_publication, "publication_ok", return_value=True), \
             patch.object(check_daily_publication, "timer_ok", return_value=True), \
             patch("builtins.print") as emit:
            self.assertEqual(check_daily_publication.main(), 0)
        emit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
