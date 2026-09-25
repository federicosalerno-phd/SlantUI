"""The band the window draws until the page has drawn its own (shell/band.py).

It is a second drawing of something the page already draws, and the whole
point of it is that nobody can tell the two apart when one hands over to the
other. So this file holds it to the page from three sides.

The text level checks always run: every number and every role band.py draws
with is read back out of the stylesheet rule it copies, the credit line and
the four window drawings are the scripts' own, and the page and the window
agree on the name of the attribute that says the band is drawn.

The drawing checks need Qt and a font, and no window.

The last check opens the real window, as test_window.py does, and is switched
on the same way:

    set SLANTUI_SHOW_WINDOW=1
    .venv\\Scripts\\python -m pytest tests/test_band.py -q

It lays the window's band and the page's side by side in one window and fails
if they part: where the oblique starts, the profile, the colours, the words,
and where every character of the name sits.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "slantui" / "css"
JS = ROOT / "slantui" / "js"


def _css(name: str) -> str:
    return re.sub(r"/\*.*?\*/", "", (CSS / name).read_text(encoding="utf-8"), flags=re.S)


def rule(sheet: str, selector: str) -> dict[str, str]:
    """What the sheet declares for ``selector``: every rule whose selector
    list holds it, a later one winning over an earlier one, as the cascade
    has it when the specificity is the same."""
    out: dict[str, str] = {}
    found = False
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", _css(sheet)):
        if selector in [s.strip() for s in sel.split(",")]:
            found = True
            for decl in body.split(";"):
                if ":" in decl:
                    k, v = decl.split(":", 1)
                    out[k.strip()] = v.strip()
    assert found, f"{sheet} has no rule for {selector}"
    return out


def number(v: str) -> float:
    m = re.fullmatch(r"(-?[\d.]+)(px)?", v.strip())
    assert m, f"not a plain length: {v!r}"
    return float(m.group(1))


def role(v: str) -> str:
    m = re.fullmatch(r"var\(--([a-z0-9-]+)\)", v.strip())
    assert m, f"not a role: {v!r}"
    return m.group(1)


@pytest.fixture(scope="module")
def band():
    pytest.importorskip("slantui.shell")
    from slantui.shell import band as module
    return module


# ── every part of the band reads a metric, and band.py writes none ──────────
def decl(selector: str) -> dict[str, str]:
    from slantui.css import declarations
    out = declarations(selector)
    assert out, f"no stylesheet has a rule for {selector}"
    return out


def test_the_mark_and_the_brand():
    logo = decl(".tbar-logo")
    assert logo["width"] == logo["height"] == "var(--tbar-mark)"
    assert logo["margin-right"] == "var(--tbar-mark-gap)"
    assert logo["border-radius"] == "var(--r)"
    assert decl(".tbar-brand")["padding"] == \
        "0 var(--tbar-name-end) 0 calc(var(--tbar-h) / 2 - var(--tbar-mark) / 2)"


def test_the_disc_is_the_mark_and_a_ring_and_gives_back_its_room():
    disc = decl(".tbar-logo-btn")
    side = "calc(var(--tbar-mark) + 2 * var(--tbar-ring))"
    assert disc["width"] == disc["height"] == side
    ring = "calc(0px - var(--tbar-ring))"
    assert disc["margin"] == f"{ring} calc(var(--tbar-mark-gap) - var(--tbar-ring)) {ring} {ring}"
    assert disc["border-radius"] == "50%"
    assert disc["box-shadow"] == "0 var(--tbar-lift) var(--tbar-lift-blur) var(--shadow)"


def test_the_name_and_the_credit_line():
    name = decl(".tbar-name")
    assert (name["font-family"], name["font-size"], name["font-weight"], name["letter-spacing"]) == \
        ("var(--font-brand)", "var(--fs-brand)", "var(--w)", "var(--ls-brand)")
    strong = decl(".tbar-name b")
    assert (strong["font-weight"], strong["letter-spacing"]) == ("var(--w-strong)", "var(--ls-strong)")
    credit = decl(".tbar-credit")
    assert (credit["font-family"], credit["font-size"], credit["font-weight"],
            credit["letter-spacing"], credit["font-style"]) == \
        ("var(--font-credit)", "var(--fs-credit)", "var(--w)", "var(--ls-credit)", "italic")
    assert credit["height"] == "var(--tbar-thin)"
    assert (credit["left"], credit["transform"]) == ("50%", "translateX(-50%)")


def test_the_line_height_both_lines_inherit():
    assert decl("body")["line-height"] == "var(--lh)"
    for sel in (".tbar-name", ".tbar-name b", ".tbar-credit", ".tbar-brand"):
        assert "line-height" not in decl(sel), sel


def test_the_buttons_and_the_strips():
    assert decl(".wbtn")["width"] == "var(--tbar-button)"
    assert decl(".wbtn")["height"] == "100%"
    svg = decl(".wbtn svg")
    assert svg["width"] == svg["height"] == "var(--tbar-glyph)"
    assert svg["stroke-width"] == "var(--tbar-stroke)"
    assert decl(".tbar-btns")["height"] == "var(--tbar-thin)"
    assert decl(".rz-n")["height"] == decl(".rz-w")["width"] == "var(--rz)"
    nw = decl(".rz-nw")
    assert nw["width"] == nw["height"] == "var(--rz-corner)"


def test_every_part_is_in_one_role_the_stylesheet_names():
    from slantui.css import BAND_PARTS, band_roles
    from slantui.tokens.roles import ROLE_NAMES
    roles = band_roles()
    assert set(roles) == set(BAND_PARTS)
    assert set(roles.values()) <= set(ROLE_NAMES)


def test_band_py_writes_no_length_and_no_role(band):
    """No number of the design and no role at module level, and no role name
    written anywhere in the file: the lengths are asked of the metrics and the
    roles of the stylesheet where they are used. The one number it keeps is
    the size a run is shaped at, which is a fact about hinting and not about
    the band."""
    import ast
    from slantui.tokens.roles import ROLE_NAMES
    tree = ast.parse((ROOT / "slantui" / "shell" / "band.py").read_text(encoding="utf-8"))
    numbers = [t.id for node in tree.body if isinstance(node, ast.Assign)
               and isinstance(node.value, ast.Constant) and isinstance(node.value.value, (int, float))
               and not isinstance(node.value.value, bool)
               for t in node.targets if isinstance(t, ast.Name)]
    assert numbers == ["_SHAPE_PX"], numbers
    roles = sorted({n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
                    and isinstance(n.value, str) and n.value in ROLE_NAMES})
    assert not roles, f"band.py names roles: {roles}"


def test_every_band_metric_is_read_by_a_stylesheet():
    """A metric of the band that the page does not read would be one the page
    does not draw with, and the window's band and WPF's would draw with it
    alone. A rule reads it, or titlebar.js does, for the profile it cuts."""
    from slantui.css import bundle
    from slantui.tokens.metrics import METRICS
    code = re.sub(r"/\*.*?\*/", "", bundle(), flags=re.S)
    script = (JS / "titlebar.js").read_text(encoding="utf-8")
    for m in METRICS:
        if m.group in ("band", "frame"):
            assert f"var(--{m.name})" in code or f"'--{m.name}'" in script, m.name


# ── the words and the drawings are the scripts' ─────────────────────────────
def test_the_credit_is_the_licence_line(band):
    lic = (ROOT / "LICENSE").read_text(encoding="utf-8")
    m = re.search(r"It\s+reads:\s*\n\s*\n[ \t]+(.+?)[ \t]*\n", lic)
    assert m and band.credit_text() == m.group(1)


def test_the_window_drawings_are_the_pages(band):
    src = (JS / "icons.js").read_text(encoding="utf-8")
    for name in ("win-minimise", "win-maximise", "win-restore", "win-close"):
        vb, body = band.window_glyphs()[name]
        assert vb == "0 0 12 12", name
        for piece in re.findall(r"<[^>]+>", body):
            assert piece in src, (name, piece)


def test_the_page_and_the_window_name_the_same_attribute():
    """titlebar.js says the band is drawn and window.py asks for it: one
    attribute, one value, and the page also marks the credit line it times."""
    titlebar = (JS / "titlebar.js").read_text(encoding="utf-8")
    window = (ROOT / "slantui" / "shell" / "window.py").read_text(encoding="utf-8")
    assert "setAttribute('data-band', 'shown')" in titlebar
    assert "getAttribute('data-band') === 'shown'" in window
    assert "el.setAttribute('elementtiming', BAND_TIMING)" in titlebar
    # the empty document before the page is not the page
    assert "about:blank" in window


def test_the_shell_does_not_take_two_frames_for_a_drawn_band():
    """Two requestAnimationFrame callbacks are not a presented frame: the
    page runs them while the browser still holds its first frame back. The
    moment is the one Element Timing reports."""
    titlebar = (JS / "titlebar.js").read_text(encoding="utf-8")
    body = titlebar[titlebar.index("function _sayWhenDrawn"):]
    body = body[:body.index("\n}\n")]
    assert "requestAnimationFrame" not in body
    assert "type: 'element'" in body


# ── the markup, read without running it ─────────────────────────────────────
PAGE = """<!doctype html><html><body><div class="app"><div class="titlebar">
<div class="tbar-band"></div>
<div class="tbar-brand">%s<span class="tbar-name">%s</span></div>
<div class="tbar-btns"></div></div></div></body></html>"""


def test_a_name_written_in_the_markup(band, tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "logo.png").write_bytes(b"\x89PNG")
    page = tmp_path / "index.html"
    page.write_text(PAGE % ('<img class="tbar-logo" src="assets/logo.png" alt="">',
                            "\n  <b>Name</b>&nbsp;&nbsp;The   rest \n"), encoding="utf-8")
    b = band.brand_from_page(page)
    assert b.runs == (("Name", True), ("\xa0\xa0The rest", False))
    assert b.mark and b.fill and not b.action
    assert b.logo == (tmp_path / "assets" / "logo.png").resolve()


def test_a_name_a_script_writes_is_not_in_the_markup(band, tmp_path):
    page = tmp_path / "index.html"
    page.write_text(PAGE % ('<div class="tbar-logo" id="icon"></div>',
                            '<b data-t="a.key"></b> <span data-t="b.key"></span>'),
                    encoding="utf-8")
    b = band.brand_from_page(page)
    assert b.runs == ()                 # a lone space is no name
    assert b.mark and b.logo is None


def test_an_element_that_closes_itself_closes_nothing_else(band, tmp_path):
    """`<img .../>` arrives as an end tag of something never opened, and a
    stray end tag the same: neither may close the name around it."""
    page = tmp_path / "index.html"
    page.write_text(PAGE % ('<img class="tbar-logo" src="nowhere.png"/>',
                            "<b>Name</b><img src=\"x.svg\"/></p> and the rest"), encoding="utf-8")
    b = band.brand_from_page(page)
    assert b.runs == (("Name", True), (" and the rest", False))
    assert b.mark and b.fill and b.logo is None     # an <img>, with nothing to read


def test_no_mark_no_square(band, tmp_path):
    page = tmp_path / "index.html"
    page.write_text(PAGE % ("", "<b>Only</b> words"), encoding="utf-8")
    b = band.brand_from_page(page)
    assert not b.mark and b.runs == (("Only", True), (" words", False))


def test_the_words_a_script_writes_are_the_applications(band, tmp_path):
    """The markup is read by the library; what an empty element will say is
    the application's, asked with the element's attributes and the page's
    language. Every element is a run of its own, the lone space included."""
    page = tmp_path / "index.html"
    page.write_text(("<!doctype html><html lang=\"it\"><body>" + PAGE.split("<body>", 1)[1]) % (
        '<div class="tbar-logo"></div>',
        '<b data-t="a.key"></b> <span data-t="b.key">stale</span>'), encoding="utf-8")
    asked = []

    def words(attrs, lang):
        asked.append((attrs.get("data-t"), lang))
        return {"a.key": "Nome", "b.key": "il resto"}.get(attrs.get("data-t"))
    b = band.brand_from_page(page, words)
    assert b.runs == (("Nome", True), (" ", False), ("il resto", False))
    assert ("a.key", "it") in asked and ("b.key", "it") in asked


def test_what_the_application_says(band):
    b = band.Brand.of("Name", " the rest", "mark.svg", True)
    assert b.runs == (("Name", True), (" the rest", False))
    assert b.mark and b.action and not b.fill and b.logo == Path("mark.svg")


# ── the drawing ─────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def app():
    """Session scope, for the reason test_window.py gives: an application
    handed to the garbage collector when its module ends takes the next
    module's windows with it. And the band's faces and drawings are let go of
    at the end, while there is still an application: the window does that on
    aboutToQuit, and a test run never quits one."""
    pytest.importorskip("slantui.shell")
    from slantui.shell import Application, band
    from slantui.shell.qt import QApplication
    existing = QApplication.instance()
    yield existing if existing is not None else Application(
        "SlantUI band test", app_id="SlantUI.BandTest")
    band.forget()


def _brand(band):
    return band.Brand.of("Name", " and the rest of it")


def _px(img, x, y):
    from slantui.shell.qt import QColor
    c = QColor(img.pixel(x, y))
    return c.name().upper()


def test_the_picture_is_the_profile_in_the_palettes_roles(band, app):
    from slantui.css import band_roles
    from slantui.tokens import PALETTES
    pal = {part: PALETTES["gold-dark"][role] for part, role in band_roles().items()}
    img = band.render_band(1280, 1.0, "gold-dark", _brand(band))
    assert (img.width(), img.height()) == (1280, 44)
    lay = band.band_layout(1280, 1.0, _brand(band))
    assert _px(img, 3, 40) == pal["band"].upper()               # thick, under the name
    assert _px(img, 900, 12) == pal["band"].upper()             # thin, under the buttons
    assert _px(img, 900, 36) == pal["strip"].upper()            # the strip under it
    assert _px(img, lay.x1 + 60, 43) == pal["strip"].upper()    # past the foot of the oblique
    assert _px(img, lay.x1 - 12, 43) == pal["band"].upper()     # before it


def test_the_oblique_starts_where_the_brand_ends(band, app):
    """x1 is the brand's width, rounded, the page's own arithmetic: the inset,
    the mark and its gap, the runs, and the padding after them."""
    b = band.Brand.of("Name", " rest", None)
    lay = band.band_layout(1280, 1.0, b)
    runs = sum(band._lu_up(line.width) for line in lay.name)
    inset = band.px("tbar-h") / 2 - band.px("tbar-mark") / 2
    assert lay.x1 == int(band._round(inset + runs + band.px("tbar-name-end")))
    with_mark = band.band_layout(1280, 1.0, band.Brand(runs=b.runs, mark=True))
    assert with_mark.x1 - lay.x1 in (35, 36, 37)


@pytest.mark.parametrize("scale", [1.25, 1.5, 2.0])
def test_the_oblique_starts_in_the_same_place_at_every_scale(band, app, scale):
    b = band.Brand.of("Name", " and the rest of it", None, True)
    assert band.band_layout(1280, scale, b).x1 == band.band_layout(1280, 1.0, b).x1


def test_a_weight_is_a_weight(band, app):
    """600 through the axis of a variable face is its Semibold; through the
    weight alone it came back Bold and the name was two pixels wider."""
    fam = band.family(band.value("font-brand"))
    w400 = band._shape("Name", fam, 400)[3]
    w600 = band._shape("Name", fam, 600)[3]
    assert w600 > w400


def test_the_buttons_light_and_the_middle_one_restores(band, app):
    from slantui.css import band_roles
    from slantui.tokens import PALETTES
    pal = {part: PALETTES["gold-dark"][role] for part, role in band_roles().items()}
    b = _brand(band)
    rest = band.render_band(1280, 1.0, "gold-dark", b)
    lit = band.render_band(1280, 1.0, "gold-dark", b, hover=(0.0, 1.0, 0.0))
    assert _px(lit, 1280 - 84 + 3, 3) == pal["hover"].upper()
    assert _px(rest, 1280 - 84 + 3, 3) == pal["band"].upper()
    closing = band.render_band(1280, 1.0, "gold-dark", b, hover=(0.0, 0.0, 1.0))
    assert _px(closing, 1280 - 3, 3) == pal["close"].upper()
    maxed = band.render_band(1280, 1.0, "gold-dark", b, maximized=True)
    assert maxed != rest


# ── the window's band against the page's, in a real window ─────────────────
show_window = pytest.mark.skipif(
    os.environ.get("SLANTUI_SHOW_WINDOW", "") != "1",
    reason="opens a real window; set SLANTUI_SHOW_WINDOW=1 to run it")

WINDOW_PAGE = """<!doctype html>
<html data-palette="gold-dark"><head><meta charset="utf-8"><title>band test</title>%s</head>
<body><div class="app">
  <div class="titlebar">
    <div class="tbar-band"></div>
    <div class="tbar-brand"><img class="tbar-logo" src="mark.png" alt="">
      <span class="tbar-name"><b>Name</b>&nbsp;&nbsp;and the rest of it</span></div>
    <div class="tbar-drag"></div>
    <div class="tbar-btns">
      <button class="wbtn wbtn-min"></button><button class="wbtn wbtn-max"></button>
      <button class="wbtn wbtn-close"></button>
    </div>
  </div>
  <div class="work"><div class="main"><div class="stage"></div></div></div>
</div>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>%s
<script>
  setIcon(document.querySelector('.wbtn-min'), 'win-minimise');
  setIcon(document.querySelector('.wbtn-close'), 'win-close');
  Bridge.init(); initTitlebar();
</script></body></html>"""

MEASURE = r"""JSON.stringify((function () {
  var q = function (s) { return document.querySelector(s); };
  var chars = [];
  var walk = document.createTreeWalker(q('.tbar-name'), NodeFilter.SHOW_TEXT), n;
  while ((n = walk.nextNode())) for (var i = 0; i < n.textContent.length; i++) {
    var r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + 1);
    chars.push(r.getBoundingClientRect().left);
  }
  var cs = function (s, p) { return getComputedStyle(q(s))[p]; };
  return {brand: q('.tbar-brand').getBoundingClientRect().width, clip: q('.tbar-band').style.clipPath,
          name: q('.tbar-name').textContent, strong: q('.tbar-name b').textContent,
          credit: q('.tbar-credit').textContent, chars: chars, dpr: devicePixelRatio,
          colours: {band: cs('.tbar-band', 'backgroundColor'), name: cs('.tbar-name', 'color'),
                    strong: cs('.tbar-name b', 'color'), credit: cs('.tbar-credit', 'color'),
                    glyph: cs('.wbtn', 'color')}};
})())"""


def _rgb(hex_colour: str) -> str:
    v = hex_colour.lstrip("#")
    return "rgb(%d, %d, %d)" % tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def _page(tmp_path):
    from slantui.css import STYLESHEETS
    from slantui.css import path as css_path
    from slantui.js import SCRIPTS
    from slantui.js import path as js_path
    from slantui.shell.qt import QColor, QImage
    from slantui.tokens import PALETTES

    mark = QImage(64, 64, QImage.Format.Format_ARGB32)
    mark.fill(QColor(PALETTES["gold-dark"]["accent"]))
    mark.save(str(tmp_path / "mark.png"))
    links = "".join(f'<link rel="stylesheet" href="{css_path(n).as_uri()}">' for n in STYLESHEETS)
    scripts = "".join(f'<script src="{js_path(n).as_uri()}"></script>' for n in SCRIPTS)
    page = tmp_path / "index.html"
    page.write_text(WINDOW_PAGE % (links, scripts), encoding="utf-8")
    return page


def _wait(ms):
    from slantui.shell.qt import QEventLoop, QTimer
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _text_boxes(lay) -> dict[str, tuple[int, int, int, int]]:
    """Where the name and the credit line are, in device pixels, with a
    pixel of air round the glyphs."""
    def box(first, last):
        return (int(first.xs[0]) - 2, int(first.y - first.size * 1.2),
                int(last.xs[0] + last.width) + 2, int(first.y + first.size * 0.4))
    return {"name": box(lay.name[0], lay.name[-1]), "credit line": box(lay.credit, lay.credit)}


def _worst(a, b, x0, y0, x1, y1) -> tuple[int, int, tuple[int, int]]:
    """The worst channel difference in a box, how many pixels differ by more
    than two levels, and where the worst one is."""
    worst, many, where = 0, 0, (x0, y0)
    for y in range(max(0, y0), min(a.height(), b.height(), y1)):
        for x in range(max(0, x0), min(a.width(), b.width(), x1)):
            p, q = a.pixel(x, y), b.pixel(x, y)
            d = max(abs(((p >> k) & 255) - ((q >> k) & 255)) for k in (0, 8, 16))
            many += d > 2
            if d > worst:
                worst, where = d, (x, y)
    return worst, many, where


def _covered(a, b, x0, y0, x1, y1, level: int = 60) -> int:
    """How many pixels of a box one picture has changed from another by more
    than ``level`` in some channel."""
    many = 0
    for y in range(max(0, y0), min(a.height(), b.height(), y1)):
        for x in range(max(0, x0), min(a.width(), b.width(), x1)):
            p, q = a.pixel(x, y), b.pixel(x, y)
            many += max(abs(((p >> k) & 255) - ((q >> k) & 255)) for k in (0, 8, 16)) > level
    return many


def _fringes(img, x0, y0, x1, y1) -> int:
    """The colour fringes in a box, summed: ClearType puts them along every
    glyph's edges, and grey scale antialiasing puts none."""
    total = 0
    for y in range(max(0, y0), min(img.height(), y1)):
        for x in range(max(0, x0), min(img.width(), x1)):
            c = img.pixel(x, y)
            r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
            total += max(0, max(r, g, b) - min(r, g, b) - 6)
    return total


@show_window
def test_the_window_band_is_the_page_band(band, app, tmp_path):
    from slantui.css import band_roles
    from slantui.geometry import band_path
    from slantui.shell import Window, glyphs
    from slantui.shell.qt import QColor, QEventLoop, QTimer
    from slantui.tokens import PALETTES

    page = _page(tmp_path)
    wait = _wait
    win = Window(page, title="band test", size=(1100, 700), min_size=(600, 400))
    win.setPosition(90, 70)
    win.show()
    try:
        for _ in range(200):
            wait(50)
            if not win.band_up:
                break
        assert not win.band_up, "the page never said its band was drawn"
        wait(300)
        box = []
        loop = QEventLoop()
        win.run_js(MEASURE, lambda v: (box.append(v), loop.quit()))
        QTimer.singleShot(4000, loop.quit)
        loop.exec()
        page_band = json.loads(box[0])
        lay = win.band.layout()
        pal = PALETTES[win.palette_slug]

        # where the oblique starts, and the whole profile
        assert lay.x1 == int(page_band["brand"] + 0.5), (lay.x1, page_band["brand"])
        ours = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", band_path(win.band.width(), lay.x1))]
        theirs = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", page_band["clip"])]
        assert ours == pytest.approx(theirs, abs=0.006), (ours, theirs)

        # the colours
        c = page_band["colours"]
        roles = band_roles()
        for part in ("band", "name", "strong", "credit", "glyph"):
            assert c[part] == _rgb(pal[roles[part]]), part

        # the words
        assert page_band["name"] == win.band.brand.text
        assert page_band["strong"] == "".join(t for t, s in win.band.brand.runs if s)
        assert page_band["credit"] == band.credit_text()

        # where every character of the name sits
        s = lay.scale
        xs = [x / s for line in lay.name for x in line.xs]
        assert len(xs) == len(page_band["chars"])
        worst = max(abs(a - b) for a, b in zip(xs, page_band["chars"]))
        assert worst < 0.05, f"a character of the name is {worst:.3f} px from the page's"

        # and the pixels where there is no glyph: the band, the thin half, the strip
        after = win.grabWindow()
        win.band.setVisible(True)
        win.band.setOpacity(1.0)
        win.band.refresh()
        wait(300)
        before = win.grabWindow()
        W = after.width()
        worst = 0
        for x, y in [(3, 40), (W // 2 + 200, 5), (W - 200, 12), (W - 200, 20), (W - 200, 36),
                     (lay.x1 - 12, 42), (lay.x1 + 45, 10)]:
            a, b = QColor(after.pixel(int(x * s), int(y * s))), QColor(before.pixel(int(x * s), int(y * s)))
            worst = max(worst, abs(a.red() - b.red()), abs(a.green() - b.green()),
                        abs(a.blue() - b.blue()))
        assert worst == 0, f"the band itself differs by {worst}"

        # and the words, pixel by pixel: the window draws its glyphs the way
        # the page does (glyphs.py), so the two are the same to a level or two
        if glyphs.available():
            for name, (x0, y0, x1, y1) in _text_boxes(lay).items():
                diff, many, where = _worst(after, before, x0, y0, x1, y1)
                assert diff <= 3, (f"the {name} differs from the page's by {diff} levels at "
                                   f"{where}, {many} pixels by more than two")
    finally:
        # closed and destroyed here, while there is an application: a window
        # left to the garbage collector outlives it, and the process died
        # when pytest let the application go
        QTimer.singleShot(0, win.close)
        wait(200)
        win.deleteLater()
        wait(100)


@show_window
def test_the_page_band_keeps_its_cleartype_through_the_reveal(band, app, tmp_path):
    """The loading screen goes and the page comes into focus under the band,
    and the band stays as sharp as it was: its text keeps the colour fringes
    ClearType puts on it in every frame of the reveal. It lost them for the
    whole reveal while the page's pane moved its blur on the compositor, and
    the band came into focus with the page as if it had been blurred too.

    Photographed off the screen as it is composed, which is what anybody
    looking sees, so the window is kept in front for the few seconds this
    takes."""
    from slantui.shell import Splash, Window
    from slantui.shell.qt import QTimer, Qt

    win = Window(_page(tmp_path), title="band test", size=(1100, 700), min_size=(600, 400))
    win.setFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    win.setPosition(90, 70)
    splash = Splash(window=win, text="starting", busy=True)
    splash.show()
    win.show()
    shots = []
    timer = QTimer()

    def shoot():
        g = win.geometry()
        shots.append(win.screen().grabWindow(0, g.x(), g.y(), g.width(), int(band.px("tbar-h"))
                                             ).toImage())
    timer.timeout.connect(shoot)
    try:
        for _ in range(200):
            _wait(50)
            if not win.band_up:
                break
        assert not win.band_up, "the page never said its band was drawn"
        _wait(400)
        lay = win.band.layout()
        s = lay.scale
        shoot()
        x0, y0, x1, y1 = _text_boxes(lay)["name"]
        box = (int(x0 / s), int(y0 / s), int(x1 / s) + 1, int(y1 / s))   # on the screen
        before = _fringes(shots[-1], *box)
        if before < 1000:
            pytest.skip("this screen draws text without ClearType, so there are no fringes to keep")
        shots.clear()
        timer.start(15)
        splash.hide()
        # until the screen has gone, however long it takes to start going
        for _ in range(int(3 * band.ms("t-reveal") / 50)):
            _wait(50)
            if not splash.visible:
                break
        assert not splash.visible, "the loading screen never went"
        _wait(300)
        timer.stop()
        after = _fringes(shots[-1], *box)
        during = [_fringes(img, *box) for img in shots]
        assert len(during) > 40, f"only {len(during)} frames photographed"
        assert after >= 0.8 * before, f"the band came out of the reveal with {after} against {before}"
        worst = min(during)
        assert worst >= 0.8 * before, (
            f"the band's name lost its ClearType during the reveal: {worst} against {before} "
            f"before it and {after} after, over {len(during)} frames")
    finally:
        timer.stop()
        QTimer.singleShot(0, win.close)
        _wait(200)
        win.deleteLater()
        _wait(100)


@show_window
def test_the_window_comes_up_already_sharp(band, app, tmp_path):
    """No frame of the opening shows the band scaled. Windows brings a new
    window in with an animation of its own, a little smaller and growing,
    and for those frames the band's words were soft; the window switches it
    off for its appearance (window.py, showEvent), so the first frame it is
    seen in is the frame it stays."""
    from slantui.shell import Window
    from slantui.shell.qt import QColor, QQuickView, QRect, QTimer, Qt

    # a backdrop of our own, still, so that what changes on the screen is the
    # window and not whatever the desktop behind it is doing
    backdrop = QQuickView()
    backdrop.setFlag(Qt.WindowType.FramelessWindowHint, True)
    backdrop.setFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    backdrop.setColor(QColor(255, 0, 255))
    backdrop.setGeometry(QRect(70, 50, 660, 100))
    backdrop.show()
    win = Window(_page(tmp_path), title="band test", size=(1100, 700), min_size=(600, 400))
    win.setFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    win.setPosition(90, 70)
    screen = win.screen()
    h = int(band.px("tbar-h"))
    shots = []
    timer = QTimer()
    timer.timeout.connect(lambda: shots.append(screen.grabWindow(0, 90, 70, 600, h).toImage()))
    try:
        _wait(400)
        timer.start(5)
        _wait(60)
        before = screen.grabWindow(0, 90, 70, 600, h).toImage()
        win.show()
        _wait(700)
        timer.stop()
        settled = shots[-1]
        lay = win.band.layout()
        x0, y0, x1, y1 = _text_boxes(lay)["name"]
        s = lay.scale
        box = (int(x0 / s), int(y0 / s), min(600, int(x1 / s) + 1), int(y1 / s))
        # a frame the window is in covers the name's box with something that
        # is not the backdrop: its shadow arriving first, or the backdrop
        # losing the focus, changes it by a few tens of levels and is not it
        area = (box[2] - box[0]) * (box[3] - box[1])
        seen = [img for img in shots if _covered(img, before, *box) > 0.3 * area]
        assert seen, "the window never came up"
        worst = max(_worst(img, settled, *box)[0] for img in seen)
        assert worst <= 3, (f"the band came up {worst} levels away from how it settles, over "
                            f"{len(seen)} frames: the opening was animated")
    finally:
        timer.stop()
        QTimer.singleShot(0, win.close)
        backdrop.close()
        _wait(200)
        win.deleteLater()
        backdrop.deleteLater()
        _wait(100)
