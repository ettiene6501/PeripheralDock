"""Temporary UI preview helper for screenshots (not part of the app)."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from peripheraldock.config import AppConfig  # noqa: E402
from peripheraldock.ui import PeripheralDockApp  # noqa: E402


def main() -> None:
    root = tk.Tk()
    app = PeripheralDockApp(
        root,
        AppConfig(),
        ROOT / "tests" / "_tmp" / "ui-preview.json",
    )
    root.attributes("-topmost", True)
    root.geometry("+0+0")
    root.after(2_500, lambda: root.attributes("-topmost", False))
    root.after(500, app.show_window)
    root.after(120_000, app.quit)
    root.mainloop()


if __name__ == "__main__":
    main()
