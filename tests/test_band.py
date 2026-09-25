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


# ── the numbers and the roles are the stylesheets' ──────────────────────────
def test_the_mark_and_the_brand(band):
    logo = rule("layout.css", ".tbar-logo")
    assert number(logo["width"]) == number(logo["height"]) == band.MARK
    assert number(logo["margin-right"]) == band.MARK_GAP
    assert number(logo["border-radius"]) == band.MARK_RADIUS
    pad = rule("layout.css", ".tbar-brand")["padding"].split(" ", 3)
    assert number(pad[1]) == band.BRAND_END
    assert pad[3] == f"calc(var(--tbar-h) / 2 - {band.MARK_INSET:g}px)"


def test_the_disc(band):
    disc = rule("layout.css", ".tbar-logo-btn")
    assert number(disc["width"]) == number(disc["height"]) == band.DISC
    assert disc["border-radius"] == "50%"
    assert role(disc["background"]) == band.ROLE_DISC
    x, y, blur, colour = disc["box-shadow"].split(" ")
    assert (number(x), number(y), number(blur)) == (0, band.DISC_SHADOW_Y, band.DISC_SHADOW_BLUR)
    assert role(colour) == band.ROLE_SHADOW


def test_the_name(band):
    name = rule("layout.css", ".tbar-name")
    assert name["font-family"] == "var(--font-brand)"
    assert number(name["font-size"]) == band.NAME_SIZE
    assert int(name["font-weight"]) == band.NAME_WEIGHT
    assert number(name["letter-spacing"]) == band.NAME_SPACING
    assert role(name["color"]) == band.ROLE_NAME
    strong = rule("layout.css", ".tbar-name b")
    assert int(strong["font-weight"]) == band.STRONG_WEIGHT
    assert number(strong["letter-spacing"]) == band.STRONG_SPACING
    assert role(strong["color"]) == band.ROLE_STRONG


def test_the_line_height_both_lines_inherit(band):
    assert float(rule("base.css", "body")["line-height"]) == band.LINE_HEIGHT
    for sel in (".tbar-name", ".tbar-name b", ".tbar-credit", ".tbar-brand"):
        assert "line-height" not in rule("layout.css", sel), sel


def test_the_credit_line(band):
    credit = rule("layout.css", ".tbar-credit")
    assert credit["font-family"] == "var(--font-credit)"
    assert number(credit["font-size"]) == band.CREDIT_SIZE
    assert int(credit["font-weight"]) == band.NAME_WEIGHT
    assert credit["font-style"] == "italic"
    assert number(credit["letter-spacing"]) == band.CREDIT_SPACING
    assert role(credit["color"]) == band.ROLE_CREDIT
    assert credit["height"] == "var(--tbar-thin)"
    assert (credit["left"], credit["transform"]) == ("50%", "translateX(-50%)")


def test_the_band_and_the_buttons(band):
    assert role(rule("layout.css", ".tbar-band")["background"]) == band.ROLE_BAND
    wbtn = rule("components.css", ".wbtn")
    assert number(wbtn["width"]) == band.BUTTON
    assert role(wbtn["color"]) == band.ROLE_GLYPH
    svg = rule("components.css", ".wbtn svg")
    assert number(svg["width"]) == number(svg["height"]) == band.GLYPH
    assert float(svg["stroke-width"]) == band.GLYPH_STROKE
    hover = rule("components.css", ".wbtn:hover")
    assert (role(hover["background"]), role(hover["color"])) == (band.ROLE_HOVER,
                                                                  band.ROLE_HOVER_GLYPH)
    close = rule("components.css", ".wbtn-close:hover")
    assert (role(close["background"]), role(close["color"])) == (band.ROLE_CLOSE,
                                                                  band.ROLE_CLOSE_GLYPH)
    assert rule("layout.css", ".tbar-btns")["height"] == "var(--tbar-thin)"
    assert rule("components.css", ".wbtn")["height"] == "100%"


def test_the_strips_it_resizes_from(band):
    assert number(rule("components.css", ".rz-n")["height"]) == band.STRIP
    assert number(rule("components.css", ".rz-w")["width"]) == band.STRIP
    nw = rule("components.css", ".rz-nw")
    assert number(nw["width"]) == number(nw["height"]) == band.CORNER
    edges = {e for e, _ in band.EDGES}
    assert edges == {"n", "s", "w", "e", "nw", "ne", "sw", "se"}


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
    from slantui.tokens import PALETTES
    pal = PALETTES["gold-dark"]
    img = band.render_band(1280, 1.0, "gold-dark", _brand(band))
    assert (img.width(), img.height()) == (1280, 44)
    lay = band.band_layout(1280, 1.0, _brand(band))
    assert _px(img, 3, 40) == pal["control"].upper()               # thick, under the name
    assert _px(img, 900, 12) == pal["control"].upper()             # thin, under the buttons
    assert _px(img, 900, 36) == pal["surface-0"].upper()           # the strip under it
    assert _px(img, lay.x1 + 60, 43) == pal["surface-0"].upper()   # past the foot of the oblique
    assert _px(img, lay.x1 - 12, 43) == pal["control"].upper()     # before it


def test_the_oblique_starts_where_the_brand_ends(band, app):
    """x1 is the brand's width, rounded, the page's own arithmetic: the inset,
    the mark and its gap, the runs, and the padding after them."""
    b = band.Brand.of("Name", " rest", None)
    lay = band.band_layout(1280, 1.0, b)
    runs = sum(band._lu_up(line.width) for line in lay.name)
    assert lay.x1 == int(band._round(11 + runs + 16))
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
    from slantui.tokens import PALETTES
    pal = PALETTES["gold-dark"]
    b = _brand(band)
    rest = band.render_band(1280, 1.0, "gold-dark", b)
    lit = band.render_band(1280, 1.0, "gold-dark", b, hover=(0.0, 1.0, 0.0))
    assert _px(lit, 1280 - 84 + 3, 3) == pal["control-hover"].upper()
    assert _px(rest, 1280 - 84 + 3, 3) == pal["control"].upper()
    closing = band.render_band(1280, 1.0, "gold-dark", b, hover=(0.0, 0.0, 1.0))
    assert _px(closing, 1280 - 3, 3) == pal["err"].upper()
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


@show_window
def test_the_window_band_is_the_page_band(band, app, tmp_path):
    from slantui.css import STYLESHEETS
    from slantui.css import path as css_path
    from slantui.js import SCRIPTS
    from slantui.js import path as js_path
    from slantui.geometry import band_path
    from slantui.shell import Window
    from slantui.shell.qt import QColor, QEventLoop, QImage, QTimer
    from slantui.tokens import PALETTES

    mark = QImage(64, 64, QImage.Format.Format_ARGB32)
    mark.fill(QColor(PALETTES["gold-dark"]["accent"]))
    mark.save(str(tmp_path / "mark.png"))
    links = "".join(f'<link rel="stylesheet" href="{css_path(n).as_uri()}">' for n in STYLESHEETS)
    scripts = "".join(f'<script src="{js_path(n).as_uri()}"></script>' for n in SCRIPTS)
    page = tmp_path / "index.html"
    page.write_text(WINDOW_PAGE % (links, scripts), encoding="utf-8")

    def wait(ms):
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

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
        assert c["band"] == _rgb(pal[band.ROLE_BAND])
        assert c["name"] == _rgb(pal[band.ROLE_NAME])
        assert c["strong"] == _rgb(pal[band.ROLE_STRONG])
        assert c["credit"] == _rgb(pal[band.ROLE_CREDIT])
        assert c["glyph"] == _rgb(pal[band.ROLE_GLYPH])

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
    finally:
        # closed and destroyed here, while there is an application: a window
        # left to the garbage collector outlives it, and the process died
        # when pytest let the application go
        QTimer.singleShot(0, win.close)
        wait(200)
        win.deleteLater()
        wait(100)
