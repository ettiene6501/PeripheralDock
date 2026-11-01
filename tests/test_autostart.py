from __future__ import annotations

import unittest
import uuid

from peripheraldock.autostart import build_autostart_command, is_enabled, quote_windows_argument, set_enabled


class AutostartTests(unittest.TestCase):
    def test_quotes_spaces(self):
        self.assertEqual(quote_windows_argument(r"C:\Program Files\App\app.exe"), r'"C:\Program Files\App\app.exe"')

    def test_rejects_embedded_quote(self):
        with self.assertRaises(ValueError):
            quote_windows_argument('C:\\bad"path\\app.exe')

    def test_frozen_command(self):
        command = build_autostart_command(
            frozen=True, executable=r"C:\Apps\PeripheralDock.exe"
        )
        self.assertEqual(command, r'"C:\Apps\PeripheralDock.exe" --minimized')
        self.assertIn("--minimized", command)

    def test_dev_command_contains_script(self):
        command = build_autostart_command(
            frozen=False,
            executable=r"C:\Python311\python.exe",
            script=r"C:\Tools\PeripheralDock\main.py",
        )
        self.assertEqual(
            command,
            r'"C:\Python311\python.exe" "C:\Tools\PeripheralDock\main.py" --minimized',
        )

    def test_real_hkcu_entry_round_trip(self):
        name = f"PeripheralDockSelfTest_{uuid.uuid4().hex}"
        try:
            set_enabled(False, name)
            self.assertFalse(is_enabled(name))
            set_enabled(True, name)
            self.assertTrue(is_enabled(name))
            set_enabled(False, name)
            self.assertFalse(is_enabled(name))
        except PermissionError:
            self.skipTest("目前沙箱不允許寫入 HKCU Run；需在一般桌面工作階段驗證")
        finally:
            try:
                set_enabled(False, name)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
