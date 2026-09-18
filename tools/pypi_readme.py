"""Write PYPI.md, which is README.md with its links pointing somewhere.

    python tools\\pypi_readme.py            write PYPI.md
    python tools\\pypi_readme.py --check    say whether it is behind README.md

The package description on an index is the README, and an index is not a
repository: a picture at `docs/img/...` and a link to `docs/roles.md` resolve
against the project page and find nothing, so the page shows broken images and
dead links. GitHub resolves both, which is why the README is written that way
and stays that way.

So the copy that ships in the package metadata has every repository relative
path rewritten to an absolute one: pictures to raw.githubusercontent.com,
because that is what serves a file's bytes, and everything else to the blob
view a reader expects to land on.

`pyproject.toml` points `readme` here, and `tests/test_package.py` fails while
this file is behind README.md, the same deal as every other generated file in
this repository.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "README.md"
TARGET = ROOT / "PYPI.md"

REPO = "https://github.com/federicosalerno-phd/SlantUI"
BRANCH = "main"
RAW = f"https://raw.githubusercontent.com/federicosalerno-phd/SlantUI/{BRANCH}"
BLOB = f"{REPO}/blob/{BRANCH}"

# ![alt](path), <img src="path">, [text](path). The first two are pictures and
# want the bytes; the third is a link and wants the page.
_MD_IMAGE = re.compile(r"(!\[[^\]]*\]\()([^)\s]+)(\))")
_HTML_IMAGE = re.compile(r"(<img\b[^>]*?\bsrc=\")([^\"]+)(\")", re.IGNORECASE)
_MD_LINK = re.compile(r"(?<!!)(\[[^\]]*\]\()([^)\s]+)(\))")

ABSOLUTE = ("http:", "https:", "data:", "mailto:", "#")


def _absolute(path: str, base: str) -> str:
    if path.startswith(ABSOLUTE):
        return path
    return f"{base}/{path.lstrip('./')}"


def render(text: str) -> str:
    text = _MD_IMAGE.sub(lambda m: m.group(1) + _absolute(m.group(2), RAW) + m.group(3), text)
    text = _HTML_IMAGE.sub(lambda m: m.group(1) + _absolute(m.group(2), RAW) + m.group(3), text)
    text = _MD_LINK.sub(lambda m: m.group(1) + _absolute(m.group(2), BLOB) + m.group(3), text)
    return text


def current() -> str:
    return render(SOURCE.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write the README the index shows.")
    ap.add_argument("--check", action="store_true",
                    help="say whether PYPI.md is behind README.md and write nothing")
    args = ap.parse_args(argv)

    want = current()
    if args.check:
        have = TARGET.read_text(encoding="utf-8") if TARGET.is_file() else ""
        if have != want:
            print("PYPI.md is behind README.md. Run\n"
                  "    python tools\\pypi_readme.py", file=sys.stderr)
            return 1
        print("PYPI.md is current")
        return 0

    TARGET.write_text(want, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)}, {len(want) / 1024:.1f} kB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
