"""The pages, and the pictures they show.

``docs/shots`` is written by the capture and ignored by git, so a page that
points into it draws nothing on GitHub. The repository carries a copy of the
handful the pages do show, in ``docs/img``, and ``docs/publish.py`` is what
puts them there. These checks are the other half of that deal: the folder and
the pages have to agree, every picture has to be the one the last capture
wrote, and an ``img`` tag has to carry the width its shot was taken at, or the
page draws it at twice the size.

The two that read ``docs/shots`` skip where it is not there, which is every
clone but the one the pictures are made on.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
IMG = DOCS / "img"
SHOTS = DOCS / "shots"
MANIFEST = SHOTS / "shots.json"

sys.path.insert(0, str(DOCS))
import publish  # noqa: E402  the rule about what a page may show lives there

PAGES = publish.pages()
WANTED = publish.wanted()
CARRIED = publish.carried()

_IMG_TAG = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_ATTR = re.compile(r'(\w+)\s*=\s*"([^"]*)"')
_MD_ALT = re.compile(r"!\[([^\]]*)\]\(")


def _ids(rel: Path) -> str:
    return publish.slash(rel)


def _tags() -> list[tuple[Path, dict[str, str]]]:
    out = []
    for page in PAGES:
        for tag in _IMG_TAG.finditer(page.read_text(encoding="utf-8")):
            out.append((page, dict(_ATTR.findall(tag.group(0)))))
    return out


TAGS = _tags()


def test_the_scan_found_the_pages():
    names = {p.relative_to(ROOT).as_posix() for p in PAGES}
    assert "README.md" in names
    assert len(WANTED) > 20, "the README shows almost nothing, so this is not scanning"


@pytest.mark.parametrize("rel", WANTED, ids=_ids)
def test_a_picture_a_page_shows_is_in_the_repository(rel: Path):
    shown_in = ", ".join(p.relative_to(ROOT).as_posix() for p in WANTED[rel])
    assert (IMG / rel).is_file(), (
        f"{shown_in} shows docs/img/{publish.slash(rel)} and the file is not "
        f"there. Run docs/publish.py.")


def test_nothing_in_the_folder_is_carried_for_nobody():
    extra = [publish.slash(rel) for rel in CARRIED if rel not in WANTED]
    assert not extra, ("docs/img carries pictures no page shows:\n  "
                       + "\n  ".join(extra) + "\nRun docs/publish.py.")


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_a_page_points_at_no_generated_folder(page: Path):
    """A picture drawn from docs/shots is a broken picture on GitHub."""
    stray = []
    for ref in publish.image_refs(page):
        if ref.startswith(("http:", "https:", "data:")):
            continue
        if publish.published(ref, page) is None:
            stray.append(ref)
    assert not stray, (f"{page.relative_to(ROOT).as_posix()} shows pictures from "
                       f"outside docs/img, which the repository does not carry:\n  "
                       + "\n  ".join(stray))


@pytest.mark.parametrize("page,attrs", TAGS,
                         ids=[f"{p.relative_to(ROOT).as_posix()}:{a.get('src', '')}"
                              for p, a in TAGS])
def test_an_img_tag_says_what_it_shows(page: Path, attrs: dict[str, str]):
    assert attrs.get("alt", "").strip(), (
        f"{page.relative_to(ROOT).as_posix()}: an img tag for "
        f"{attrs.get('src', 'nothing')} carries no alt text, so a reader who "
        f"cannot see it is told nothing.")


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_a_markdown_picture_says_what_it_shows(page: Path):
    empty = [m.start() for m in _MD_ALT.finditer(page.read_text(encoding="utf-8"))
             if not m.group(1).strip()]
    assert not empty, (f"{page.relative_to(ROOT).as_posix()}: "
                       f"{len(empty)} pictures with nothing in the brackets.")


@pytest.mark.skipif(not SHOTS.is_dir(), reason="docs/shots is not in this clone")
@pytest.mark.parametrize("rel", WANTED, ids=_ids)
def test_a_picture_is_the_one_the_capture_wrote(rel: Path):
    src, dst = SHOTS / rel, IMG / rel
    if not src.is_file():
        pytest.skip("the capture has not written this one")
    assert dst.is_file() and dst.read_bytes() == src.read_bytes(), (
        f"docs/img/{publish.slash(rel)} is not what the last capture wrote. "
        f"Run docs/publish.py.")


@pytest.mark.skipif(not MANIFEST.is_file(), reason="docs/shots is not in this clone")
@pytest.mark.parametrize("page,attrs", TAGS,
                         ids=[f"{p.relative_to(ROOT).as_posix()}:{a.get('src', '')}"
                              for p, a in TAGS])
def test_an_img_tag_carries_the_width_the_shot_was_taken_at(page: Path,
                                                            attrs: dict[str, str]):
    """The files are at twice their CSS size, which is what keeps them sharp on
    a dense display. A tag with no width, or the wrong one, draws the picture
    at the pixel size instead, and one widget ends up twice the size of the
    next one."""
    rel = publish.published(attrs.get("src", ""), page)
    if rel is None:
        pytest.skip("not one of ours")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    parts = rel.as_posix().split("/")
    if parts[0] == "tour":
        want = manifest["window"]["w"]
    else:
        shot = parts[-1][:-len(".png")]
        if shot not in manifest["shots"]:
            pytest.skip("not a shot the manifest knows")
        want = manifest["shots"][shot]["w"]
    assert attrs.get("width") == str(want), (
        f"{page.relative_to(ROOT).as_posix()}: {rel.as_posix()} is shot at "
        f"{want} CSS px wide and the tag says {attrs.get('width')}.")
