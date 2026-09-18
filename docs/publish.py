"""Carry the pictures the pages show into the repository.

    .venv\\Scripts\\python docs\\publish.py           copy them into docs/img
    .venv\\Scripts\\python docs\\publish.py --check   say what is out of date

``docs/shots`` is written by ``capture.py`` and ignored by git: a full run is
two hundred and fifty one files and six megabytes, and all but a handful of
them illustrate nothing. GitHub draws what is in the repository and nothing
else, so the handful the pages do show is copied into ``docs/img``, which is
tracked.

The pages are the list. Every image a tracked markdown file points at under
``docs/img`` is a picture to carry, and its source is the same path under
``docs/shots``. A file in ``docs/img`` no page points at is deleted here. So a
picture enters the repository by being put in a page and leaves it by being
taken out of one, there is no second list to keep in step, and
``tests/test_readme.py`` fails the build while the folder and the pages
disagree.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SHOTS = HERE / "shots"
IMG = HERE / "img"

# Folders with no page of ours in them.
SKIP = {".git", ".venv", "venv", ".pytest_cache", "build", "dist", "node_modules"}

# ![alt](path), <img src="path">, <source srcset="path">. The title a markdown
# image can carry after the path is dropped, and so is a query string.
_MD_IMAGE = re.compile(r"!\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+[^)]*)?\)")
_HTML_IMAGE = re.compile(r"<(?:img|source)\b[^>]*?\b(?:src|srcset)\s*=\s*\"([^\"]+)\"",
                         re.IGNORECASE)


def pages() -> list[Path]:
    """Every markdown file that would end up in the repository."""
    return sorted(p for p in ROOT.rglob("*.md")
                  if not SKIP & set(p.parts) and not p.name.endswith(".egg-info"))


def image_refs(page: Path) -> list[str]:
    """The paths the images in one page point at, as they are written."""
    text = page.read_text(encoding="utf-8")
    out = [m.group(1) for m in _MD_IMAGE.finditer(text)]
    out += [m.group(1) for m in _HTML_IMAGE.finditer(text)]
    return out


def published(ref: str, page: Path) -> Path | None:
    """The picture ``ref`` names, as a path under ``docs/img``, or ``None``
    when it points somewhere else. A reference is relative to its own page."""
    if ref.startswith(("http:", "https:", "data:", "#")):
        return None
    try:
        target = (page.parent / ref.split("?")[0].split("#")[0]).resolve()
        return target.relative_to(IMG)
    except (ValueError, OSError):
        return None


def wanted() -> dict[Path, list[Path]]:
    """Every picture the pages show, and which pages show it."""
    out: dict[Path, list[Path]] = {}
    for page in pages():
        for ref in image_refs(page):
            rel = published(ref, page)
            if rel is not None:
                out.setdefault(rel, []).append(page)
    return dict(sorted(out.items()))


def carried() -> list[Path]:
    """Every picture the repository is carrying now."""
    if not IMG.is_dir():
        return []
    return sorted(p.relative_to(IMG) for p in IMG.rglob("*") if p.is_file())


def slash(rel: Path) -> str:
    """A path the way a page writes it, whatever the platform."""
    return str(rel).replace("\\", "/")


def prune_empty(folder: Path) -> None:
    for child in sorted(folder.rglob("*"), reverse=True):
        if child.is_dir() and not any(child.iterdir()):
            child.rmdir()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Copy the pictures the pages show into docs/img.")
    p.add_argument("--check", action="store_true",
                   help="say what is out of date and write nothing")
    args = p.parse_args(argv)

    show = wanted()
    have = carried()
    missing = [rel for rel in show if not (SHOTS / rel).is_file()]
    if missing:
        names = "\n  ".join(slash(rel) for rel in missing)
        tour = " --tour" if any(rel.parts[0] == "tour" for rel in missing) else ""
        print(f"the pages show {len(missing)} pictures the capture has not "
              f"written:\n  {names}\n"
              f"run  .venv\\Scripts\\python docs\\capture.py{tour}", file=sys.stderr)
        return 1

    stale = [rel for rel in show
             if not (IMG / rel).is_file()
             or (IMG / rel).read_bytes() != (SHOTS / rel).read_bytes()]
    extra = [rel for rel in have if rel not in show]

    if args.check:
        for rel in stale:
            print(f"out of date  {slash(rel)}")
        for rel in extra:
            print(f"nobody shows {slash(rel)}")
        if stale or extra:
            print("run  .venv\\Scripts\\python docs\\publish.py")
            return 1
        print(f"{len(show)} pictures, all of them current")
        return 0

    for rel in stale:
        (IMG / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SHOTS / rel, IMG / rel)
    for rel in extra:
        (IMG / rel).unlink()
    if IMG.is_dir():
        prune_empty(IMG)

    size = sum((IMG / rel).stat().st_size for rel in show)
    print(f"{len(show)} pictures in docs/img, {size / 1024:.0f} kB "
          f"({len(stale)} written, {len(extra)} dropped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
