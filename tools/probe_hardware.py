"""Standalone read-only hardware probe.

This is a thin wrapper around the same code used by
``python main.py probe --json``.  It never writes to the devices.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from peripheraldock.cli import build_probe_report  # noqa: E402
import json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="PeripheralDock read-only probe")
    parser.add_argument("--json", metavar="PATH", help="write evidence JSON here")
    args = parser.parse_args()

    report = build_probe_report()
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json:
        target = Path(args.json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {target}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
