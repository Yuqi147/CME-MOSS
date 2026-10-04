"""CME-MOSS launcher.

Graphical mode by default (double-click / ``python main.py``); headless
searches via ``python -m cmemoss.cli search --start ... --end ...``.
"""

from cmemoss.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
