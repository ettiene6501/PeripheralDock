from __future__ import annotations

import json
import unittest
import uuid
from pathlib import Path

from peripheraldock.config import AppConfig, load_config, save_config

TEST_TMP = Path(__file__).with_name("_tmp")
TEST_TMP.mkdir(exist_ok=True)


def scratch_path(name: str = "config.json") -> Path:
    return TEST_TMP / f"{uuid.uuid4().hex}_{name}"


class ConfigTests(unittest.TestCase):
    def test_defaults(self):
        config = AppConfig()
        self.assertEqual(config.low_battery_threshold, 20)
        self.assertEqual(config.poll_interval_seconds, 60)
        self.assertTrue(config.notifications_enabled)
        self.assertFalse(config.autostart_enabled)
        self.assertTrue(config.start_minimized)

    def test_clamps(self):
        config = AppConfig(low_battery_threshold=0, poll_interval_seconds=1)
        self.assertEqual(config.low_battery_threshold, 1)
        self.assertEqual(config.poll_interval_seconds, 15)
        config = AppConfig(low_battery_threshold=200, poll_interval_seconds=99999)
        self.assertEqual(config.low_battery_threshold, 99)
        self.assertEqual(config.poll_interval_seconds, 3600)

    def test_round_trip(self):
        path = scratch_path()
        self.addCleanup(path.unlink, missing_ok=True)
        original = AppConfig(
            low_battery_threshold=25,
            poll_interval_seconds=120,
            notifications_enabled=False,
            autostart_enabled=True,
            start_minimized=False,
        )
        save_config(original, path)
        loaded, loaded_path = load_config(path)
        self.assertEqual(loaded, original)
        self.assertEqual(loaded_path, path)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["low_battery_threshold"], 25)

    def test_missing_file_uses_defaults(self):
        path = scratch_path("missing.json")
        loaded, target = load_config(path)
        self.assertEqual(loaded, AppConfig())
        self.assertEqual(target, path)

    def test_corrupt_file_uses_defaults(self):
        path = scratch_path("bad.json")
        self.addCleanup(path.unlink, missing_ok=True)
        path.write_text("{not json", encoding="utf-8")
        loaded, _ = load_config(path)
        self.assertEqual(loaded, AppConfig())

    def test_unknown_keys_are_ignored(self):
        path = scratch_path()
        self.addCleanup(path.unlink, missing_ok=True)
        path.write_text(
            json.dumps({"low_battery_threshold": 30, "bogus": 1}),
            encoding="utf-8",
        )
        loaded, _ = load_config(path)
        self.assertEqual(loaded.low_battery_threshold, 30)


if __name__ == "__main__":
    unittest.main()
