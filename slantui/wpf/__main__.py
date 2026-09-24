"""Where the WPF half of the library is, for a PowerShell application.

    python -m slantui.wpf where       print the folder of SlantUI.psm1
    python -m slantui.wpf register    write it to %LOCALAPPDATA%\\SlantUI\\wpf.path
"""
from __future__ import annotations

import sys

from . import POINTER, register, where


def main(argv: list[str]) -> int:
    command = argv[0] if argv else "where"
    if command == "where":
        print(where())
        return 0
    if command == "register":
        written = register()
        print(f"{where()}  ->  {written}")
        return 0
    print(__doc__.strip(), file=sys.stderr)
    print(f"\nthe pointer lives at {POINTER}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
