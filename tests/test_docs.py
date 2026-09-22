"""The documentation says things about the library. This checks them.

Every page here names files, roles, custom properties, command line
subcommands and API names, and quotes numbers: how many roles there are, how
many pairs the auditor measures, how many shots a full capture writes. All of
it is true on the day it is written and none of it stays true on its own.
Phase 8 is the proof: it added one role and one gallery cell, and left the
word "thirty" in eleven files.

So the pages are read here the way a reader reads them, and every claim that
can be checked against the code is checked against the code.

``tests/test_readme.py`` covers the other half, the pictures.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path

import pytest

from slantui.tokens.metrics import METRIC_NAMES
from slantui.tokens.palettes import PALETTES
from slantui.tokens.roles import ON_FILL, ROLE_NAMES, SURFACES, TEXTS

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
GALLERY = DOCS / "gallery.html"
MANIFEST = DOCS / "shots" / "shots.json"


SELF = Path(__file__).resolve()

# A count is quoted in comments as often as in prose, so the number checks read
# the code too. The rest of this file is about pages, which are the .md files.
COUNTED = (".md", ".py", ".js", ".css", ".html", ".psm1")


def _tracked(suffixes: tuple[str, ...]) -> list[Path]:
    """Every file of these kinds that would end up in the repository."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.split("\0")
        paths = [ROOT / p for p in out if p.endswith(suffixes)]
    except (OSError, subprocess.CalledProcessError):
        paths = [p for p in ROOT.rglob("*")
                 if p.suffix in suffixes and not {".git", ".venv"} & set(p.parts)]
    return sorted(p for p in paths if p.is_file() and p.resolve() != SELF)


PAGES = _tracked((".md",))
IDS = [p.relative_to(ROOT).as_posix() for p in PAGES]

_FENCE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")

# The numbers the pages are allowed to quote, and what each one has to equal.
WORDS = {20: "twenty", 21: "twenty one", 29: "twenty nine", 30: "thirty",
         31: "thirty one", 32: "thirty two", 33: "thirty three",
         34: "thirty four"}


def fences(page: Path, lang: str | None = None) -> list[str]:
    out = []
    for m in _FENCE.finditer(page.read_text(encoding="utf-8")):
        if lang is None or m.group(1) == lang:
            out.append(m.group(2))
    return out


def prose() -> list[tuple[Path, str]]:
    """Every file a count can be written in, with the code fences taken out."""
    return [(p, _FENCE.sub("", p.read_text(encoding="utf-8", errors="replace")))
            for p in _tracked(COUNTED)]


def word_for(count: int) -> str:
    assert count in WORDS, f"no word for {count}; add it to WORDS above"
    return WORDS[count]


# ── the numbers the prose quotes ────────────────────────────────────────────
def test_the_role_count_the_prose_gives():
    """Every "<number> roles" in the repository is the number of roles."""
    want = word_for(len(ROLE_NAMES))
    pattern = re.compile(r"\b(" + "|".join(sorted(WORDS.values(), key=len, reverse=True))
                         + r")\s+(roles|concrete values|role names)\b", re.IGNORECASE)
    wrong = []
    for page, text in prose():
        for m in pattern.finditer(text):
            if m.group(1).lower() != want:
                line = text.count("\n", 0, m.start()) + 1
                wrong.append(f"{page.relative_to(ROOT).as_posix()}:{line}  "
                             f"{m.group(0)!r}, and there are {len(ROLE_NAMES)}")
    assert not wrong, ("the prose is behind slantui/tokens/roles.py:\n  "
                       + "\n  ".join(wrong))


def test_the_contrast_numbers_the_prose_gives():
    per = len(SURFACES) * len(TEXTS) + sum(len(f) for f in ON_FILL.values())
    total = per * len(PALETTES)
    wrong = []
    for page, text in prose():
        for m in re.finditer(r"(\d+)\s+pairs per palette", text):
            if int(m.group(1)) != per:
                wrong.append(f"{page.relative_to(ROOT).as_posix()}: "
                             f"{m.group(0)!r}, and the auditor measures {per}")
        for m in re.finditer(r"(\d+)\s+in total, and the (?:test|suite)", text):
            if int(m.group(1)) != total:
                wrong.append(f"{page.relative_to(ROOT).as_posix()}: "
                             f"{m.group(0)!r}, and the auditor measures {total}")
        for m in re.finditer(r"(\d+)\s+contrast checks", text):
            if int(m.group(1)) != total:
                wrong.append(f"{page.relative_to(ROOT).as_posix()}: "
                             f"{m.group(0)!r}, and the auditor measures {total}")
    assert not wrong, "\n  " + "\n  ".join(wrong)


def test_the_shot_count_the_prose_gives():
    """The gallery's cells are what a capture writes, per palette."""
    cells = len(re.findall(r'data-shot="', GALLERY.read_text(encoding="utf-8")))
    want = word_for(cells)
    pattern = re.compile(r"\b(" + "|".join(sorted(WORDS.values(), key=len, reverse=True))
                         + r")\s+shots\b", re.IGNORECASE)
    wrong = []
    for page, text in prose():
        for m in pattern.finditer(text):
            if m.group(1).lower() != want:
                wrong.append(f"{page.relative_to(ROOT).as_posix()}: "
                             f"{m.group(0)!r}, and the gallery has {cells} cells")
    assert not wrong, "\n  " + "\n  ".join(wrong)


@pytest.mark.skipif(not MANIFEST.is_file(), reason="docs/shots is not in this clone")
def test_the_size_of_a_full_run_the_prose_gives():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = len(manifest["shots"]) * len(manifest["palettes"]) + len(manifest["tour"])
    wrong = []
    for page, text in prose():
        for m in re.finditer(r"A full run is (\d+) files", text):
            if int(m.group(1)) != files:
                wrong.append(f"{page.relative_to(ROOT).as_posix()}: "
                             f"{m.group(0)!r}, and a full run writes {files}")
    assert not wrong, "\n  " + "\n  ".join(wrong)


# ── what the pages point at ─────────────────────────────────────────────────
@pytest.mark.parametrize("page", PAGES, ids=IDS)
def test_every_link_points_at_something(page: Path):
    """A link to a file that was renamed is the cheapest kind of broken page."""
    missing = []
    for target in _LINK.findall(page.read_text(encoding="utf-8")):
        if target.startswith(("http:", "https:", "mailto:", "#")):
            continue
        path = (page.parent / target.split("#")[0]).resolve()
        if not path.exists():
            missing.append(target)
    assert not missing, (f"{page.relative_to(ROOT).as_posix()} links to files that "
                         f"are not there:\n  " + "\n  ".join(missing))


@pytest.mark.parametrize("page", PAGES, ids=IDS)
def test_every_custom_property_named_is_a_role_or_a_metric(page: Path):
    """`var(--panel2)` in a page is a reader following the library into a wall."""
    # role and metric stand for any of them, in a sentence about the shape of
    # a rule. The other three are names the pages quote as the kind that could
    # not survive: two that encode a direction, and the prefix this turned down.
    stands_for = {"role", "metric", "panel2", "panel3", "s0", "sl-surface-2"}
    known = set(ROLE_NAMES) | set(METRIC_NAMES) | stands_for
    text = page.read_text(encoding="utf-8")
    unknown = sorted({name for name in re.findall(r"var\(--([a-z0-9-]+)", text)
                      if name not in known})
    assert not unknown, (f"{page.relative_to(ROOT).as_posix()} names custom "
                         f"properties the library does not define: "
                         + ", ".join(unknown))


@pytest.mark.parametrize("page", PAGES, ids=IDS)
def test_every_command_line_the_pages_give_is_a_real_one(page: Path):
    """`python -m slantui.tokens <cmd>` has to be a subcommand that exists."""
    from slantui.export import TARGETS

    source = (ROOT / "slantui" / "tokens" / "__main__.py").read_text(encoding="utf-8")
    # The export targets are added in a loop over TARGETS, so they are not
    # spelled out in the source the way the others are.
    commands = set(re.findall(r'sub\.add_parser\("([a-z0-9-]+)"', source)) | set(TARGETS)
    assert commands, "no subcommands found, so this test is not reading the parser"
    text = page.read_text(encoding="utf-8")
    bad = sorted({cmd for cmd in
                  re.findall(r"python -m slantui\.tokens[^\S\n]+([a-z0-9-]+)", text)
                  if cmd not in commands})
    assert not bad, (f"{page.relative_to(ROOT).as_posix()}: "
                     + ", ".join(bad) + " is not a subcommand. Known: "
                     + ", ".join(sorted(commands)))


# ── the code the pages show ─────────────────────────────────────────────────
@pytest.mark.parametrize("page", PAGES, ids=IDS)
def test_every_python_block_parses(page: Path):
    """A snippet with a syntax error in it was never run by anybody."""
    for i, block in enumerate(fences(page, "python")):
        try:
            ast.parse(block)
        except SyntaxError as exc:
            pytest.fail(f"{page.relative_to(ROOT).as_posix()}, python block {i + 1}: "
                        f"{exc}\n{block}")


@pytest.mark.parametrize("page", PAGES, ids=IDS)
def test_every_name_imported_from_slantui_exists(page: Path):
    """`from slantui.tokens import derive` in a page, checked against the package."""
    import importlib

    missing = []
    for block in fences(page, "python"):
        for m in re.finditer(r"from (slantui[\w.]*) import ([^\n(]+)", block):
            module_name, names = m.group(1), m.group(2)
            try:
                module = importlib.import_module(module_name)
            except ImportError as exc:        # the shell extra is not installed
                pytest.skip(f"{module_name}: {exc}")
            for name in (n.strip() for n in names.split(",")):
                if not name or hasattr(module, name):
                    continue
                try:                          # a submodule, as in `from slantui import css`
                    importlib.import_module(f"{module_name}.{name}")
                except ImportError:
                    missing.append(f"{module_name}.{name}")
    assert not missing, (f"{page.relative_to(ROOT).as_posix()} imports names that are "
                         f"not there: " + ", ".join(missing))


# Names a JavaScript block may call that are the language's or the browser's.
BUILTIN_JS = {
    "console", "document", "window", "JSON", "Math", "Object", "Array", "Number",
    "String", "parseFloat", "parseInt", "setTimeout", "requestAnimationFrame",
    "getElementById", "querySelector", "querySelectorAll", "addEventListener",
    "log", "warn", "error", "getComputedStyle", "function", "if", "for", "while",
    "switch", "catch", "return", "typeof",
}


def _library_js_names() -> set[str]:
    """Everything the four scripts define: functions, and the keys of the two
    objects a page talks to."""
    names: set[str] = set()
    for path in sorted((ROOT / "slantui" / "js").glob("*.js")):
        text = path.read_text(encoding="utf-8")
        names |= set(re.findall(r"^function\s+([A-Za-z_$][\w$]*)", text, re.MULTILINE))
        names |= set(re.findall(r"^const\s+([A-Za-z_$][\w$]*)\s*=", text, re.MULTILINE))
        names |= set(re.findall(r"^\s{2}([A-Za-z_$][\w$]*):\s*function", text, re.MULTILINE))
    return names


@pytest.mark.parametrize("page", PAGES, ids=IDS)
def test_every_library_call_in_a_javascript_block_exists(page: Path):
    """A page that tells you to call `Bridge.ready()` sends you nowhere."""
    known = _library_js_names()
    assert "initTitlebar" in known, "the scan found no functions, so it is not scanning"
    unknown = []
    for block in fences(page, "javascript"):
        for obj, member in re.findall(r"\b(Bridge|Theme)\.([A-Za-z_$][\w$]*)", block):
            if member not in known:
                unknown.append(f"{obj}.{member}")
        for call in re.findall(r"\b([A-Za-z_$][\w$]*)\s*\(", block):
            if call in BUILTIN_JS or call in known:
                continue
            # A name the block defines itself, or a variable it was handed.
            if re.search(r"\b(function|const|let|var)\s+" + re.escape(call) + r"\b", block):
                continue
            unknown.append(call)
    assert not unknown, (f"{page.relative_to(ROOT).as_posix()} calls things the "
                         f"library does not define: " + ", ".join(sorted(set(unknown))))
