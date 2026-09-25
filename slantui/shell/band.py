"""The title band, drawn by the window until the page has drawn its own.

The band is the page's. ``js/titlebar.js`` cuts it to the profile and
``css/layout.css`` fills it, and for every second after the page's first
frame that is where it belongs. The trouble is the seconds before. A window
opens, Chromium starts, reads the page, runs its scripts and only then
paints, and until it has, the top of the window is the colour behind the page
with nothing on it. At a cold start that is several seconds of a window with
no title bar: nobody can see whose it is, and nobody can move it or close it.

So the window draws the band itself, from the first frame it shows, and gives
it up once the page has drawn its own. For that to go unseen it has to be THE
SAME band, and that is most of this file:

* the profile is ``geometry.band_path``, the same string the page clips with;
* every fill and every ink is a role of the palette the window was given;
* the name is set in the face the page's font stack gives on this machine, at
  the page's size, weight and spacing, and laid out the way Chromium lays it
  out. That last part is not cosmetic: where the name ends is where the
  oblique starts, so a name one pixel wider is a ramp one pixel further right.
  Qt rounds a font's size to whole pixels and Chromium does not (14.5 is
  14.5), and a variable font asked for 600 through Qt's weight comes back
  Bold, so the text is shaped here at a large size, scaled down, and drawn
  with a raw font at the exact size, with the weight set on the axis;
* the credit line and the three window buttons are the page's, drawn from the
  same text (``CREDIT_TEXT`` in titlebar.js) and the same four drawings
  (``win-*`` in icons.js).

What it cannot copy is the glyphs' own pixels. Chromium blends ClearType one
way and Qt another, so the same glyph in the same place comes out a few shades
apart along its edges. That is why the handover is not a cut: the window's
band goes over ``--t-chg`` once the page's is on screen under it, and what
changes in those frames is the fringe of a glyph, a little at a time.

The numbers below are the stylesheets'. ``tests/test_band.py`` reads every one
of them back out of layout.css, components.css and base.css, so a change made
on one side and not on the other fails there and not on a screen.
"""
from __future__ import annotations

import functools
import math
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

from ..geometry import band_path
from ..js import path as js_path
from ..tokens import DEFAULT, PALETTES
from ..tokens.metrics import ms, px, value
from .bridge import edges_of
from .qt import (QApplication, QByteArray, QColor, QCursor, QEasingCurve, QFont,
                 QFontDatabase, QGlyphRun, QImage, QPainter, QPainterPath, QPointF, QQuickItem,
                 QQuickPaintedItem, QRadialGradient, QRawFont, QRectF, QSvgRenderer, QTextLayout,
                 Qt, QUrl, QVariantAnimation)

__all__ = ["Brand", "brand_from_page", "BandLayout", "band_layout", "render_band",
           "NativeBand", "Edge", "credit_text", "window_glyphs", "EDGES", "HANDOVER_MS"]

# ── what the stylesheets say ─────────────────────────────────────────────────
MARK = 22.0              # .tbar-logo: width and height
MARK_GAP = 14.0          # .tbar-logo: margin-right
MARK_RADIUS = 5.0        # .tbar-logo: border-radius
MARK_INSET = 11.0        # .tbar-brand: padding-left is --tbar-h / 2 less this
BRAND_END = 16.0         # .tbar-brand: padding-right
DISC = 30.0              # .tbar-logo-btn: width and height, round
DISC_SHADOW_Y = 1.0      # .tbar-logo-btn: box-shadow 0 1px 3px var(--shadow)
DISC_SHADOW_BLUR = 3.0
NAME_SIZE = 14.5         # .tbar-name: font-size
NAME_WEIGHT = 400        # .tbar-name: font-weight
NAME_SPACING = 0.15      # .tbar-name: letter-spacing
STRONG_WEIGHT = 600      # .tbar-name b: font-weight
STRONG_SPACING = 0.4     # .tbar-name b: letter-spacing
CREDIT_SIZE = 11.0       # .tbar-credit: font-size
CREDIT_SPACING = 0.25    # .tbar-credit: letter-spacing
LINE_HEIGHT = 1.45       # base.css: html,body line-height, which both inherit
BUTTON = 42.0            # .wbtn: width
GLYPH = 12.0             # .wbtn svg: width and height
GLYPH_STROKE = 1.35      # .wbtn svg: stroke-width

# Which role each part is filled or written in, with the rule that says so.
ROLE_BAND = "control"            # .tbar-band background
ROLE_STRONG = "text-1"           # .tbar-name b color
ROLE_NAME = "text-2"             # .tbar-name color
ROLE_CREDIT = "text-4"           # .tbar-credit color
ROLE_DISC = "control-hover"      # .tbar-logo-btn background
ROLE_SHADOW = "shadow"           # .tbar-logo-btn box-shadow
ROLE_GLYPH = "text-3"            # .wbtn color
ROLE_HOVER = "control-hover"     # .wbtn:hover background
ROLE_HOVER_GLYPH = "text-1"      # .wbtn:hover color
ROLE_CLOSE = "err"               # .wbtn-close:hover background
ROLE_CLOSE_GLYPH = "on-status"   # .wbtn-close:hover color

# The window's band gives way to the page's over this long: a state changing
# on its own, which is what --t-chg is for.
HANDOVER_MS = ms("t-chg")

# The resize strips, as components.css draws them in the page: five pixels
# along an edge, twelve square at a corner. (edge, cursor)
STRIP = 5.0
CORNER = 12.0
EDGES = (("n", Qt.CursorShape.SizeVerCursor), ("s", Qt.CursorShape.SizeVerCursor),
         ("w", Qt.CursorShape.SizeHorCursor), ("e", Qt.CursorShape.SizeHorCursor),
         ("nw", Qt.CursorShape.SizeFDiagCursor), ("ne", Qt.CursorShape.SizeBDiagCursor),
         ("sw", Qt.CursorShape.SizeBDiagCursor), ("se", Qt.CursorShape.SizeFDiagCursor))


# ── what the scripts say ─────────────────────────────────────────────────────
# Read when a band is first drawn and not when the module is imported: a
# script reformatted so that these no longer find what they look for costs the
# window its own band, and not every application its start.
@functools.lru_cache(maxsize=None)
def credit_text() -> str:
    """The licence's line, out of titlebar.js, which a test holds to LICENSE."""
    src = js_path("titlebar.js").read_text(encoding="utf-8")
    m = re.search(r"const CREDIT_TEXT = '([^']*)';", src)
    if not m:
        raise RuntimeError("titlebar.js no longer defines CREDIT_TEXT")
    return m.group(1)


@functools.lru_cache(maxsize=None)
def window_glyphs() -> dict[str, tuple[str, str]]:
    """The four window drawings out of icons.js, as (viewBox, svg contents).
    They are the same four the page's buttons show, read from where the page
    reads them."""
    src = js_path("icons.js").read_text(encoding="utf-8")
    out = {}
    for name in ("win-minimise", "win-maximise", "win-restore", "win-close"):
        m = re.search(r"'" + re.escape(name) + r"':\s*\{\s*vb:\s*'([^']*)',\s*s:\s*((?:'[^']*'\s*\+?\s*)+)\}",
                      src)
        if not m:
            raise RuntimeError(f"icons.js no longer draws {name}")
        out[name] = (m.group(1), "".join(re.findall(r"'([^']*)'", m.group(2))))
    return out


# ── what the application says ────────────────────────────────────────────────
@dataclass(frozen=True)
class Brand:
    """What the band says and shows: the name, as runs of text in the strong
    ink or the plain one, and the mark.

    ``mark`` is whether there is a mark's square at all, and ``logo`` what is
    drawn in it; ``fill`` says it is stretched to the square, as an ``<img>``
    is, instead of fitted inside it, as a background is. ``action`` is whether
    the page makes the mark a button (``setBrandAction``), which puts it in
    its round disc.
    """
    runs: tuple[tuple[str, bool], ...] = ()
    mark: bool = False
    logo: Path | None = None
    fill: bool = False
    action: bool = False

    @classmethod
    def of(cls, bold: str = "", name: str = "", logo=None, action: bool = False) -> "Brand":
        """The two part name every window in this design has: a strong word
        and the rest, which carries its own leading space."""
        runs = tuple((t, strong) for t, strong in ((bold, True), (name, False)) if t)
        path = Path(logo) if logo else None
        return cls(runs=runs, mark=path is not None, logo=path, action=bool(action))

    @property
    def text(self) -> str:
        return "".join(t for t, _ in self.runs)


_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source",
         "track", "wbr"}


class _Markup(HTMLParser):
    """The brand out of a page's markup, without running it."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool]] = []   # (tag, opens the name)
        self.in_name = 0
        self.strong = 0
        self.runs: list[list] = []
        self.mark = False
        self.logo: str | None = None
        self.img = False                 # the mark is an <img>, stretched to its square

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        if "tbar-logo" in classes and not self.mark:
            self.mark = True
            self.img = tag == "img"
            if tag == "img" and a.get("src"):
                self.logo = a["src"]
        if tag in _VOID:
            return
        opens = "tbar-name" in classes and not self.in_name
        if opens:
            self.in_name += 1
        if self.in_name and tag in ("b", "strong"):
            self.strong += 1
        self.stack.append((tag, opens))

    def handle_endtag(self, tag):
        # A void element was never pushed, and `<img .../>` arrives here as
        # well; an end tag nothing opened closes nothing.
        if tag in _VOID or all(t != tag for t, _ in self.stack):
            return
        while self.stack:
            t, opens = self.stack.pop()
            if self.in_name and t in ("b", "strong"):
                self.strong -= 1
            if opens:
                self.in_name -= 1
            if t == tag:
                break

    def handle_data(self, data):
        if not self.in_name or not data:
            return
        strong = self.strong > 0
        if self.runs and self.runs[-1][1] == strong:
            self.runs[-1][0] += data
        else:
            self.runs.append([data, strong])


def _collapse(runs) -> tuple[tuple[str, bool], ...]:
    """White space the way a nowrap line lays it out: every run of spaces,
    tabs and line breaks is one space, and none at either end of the line.
    A no-break space is text and stays."""
    out: list[list] = []
    prev_space = True                     # the start of the line eats a space
    for text, strong in runs:
        text = re.sub(r"[ \t\n\r\f]+", " ", text)
        if prev_space and text.startswith(" "):
            text = text[1:]
        if text:
            prev_space = text.endswith(" ")
            out.append([text, strong])
    if out and out[-1][0].endswith(" "):
        out[-1][0] = out[-1][0][:-1]
    return tuple((t, s) for t, s in out if t)


def brand_from_page(page: str | Path) -> Brand:
    """What a page's markup says its band carries, read without running it.

    The words inside ``.tbar-name``, in the strong ink inside ``<b>``; the
    mark's square if there is a ``.tbar-logo``, and its picture if that is an
    ``<img>`` with a ``src``. A page that writes its name from a script, or
    paints its mark from a stylesheet, has nothing here to read, and passes
    both to :class:`~slantui.shell.Window` instead.
    """
    path = Path(page)
    parser = _Markup()
    try:
        parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return Brand()
    logo = None
    if parser.logo:
        src = QUrl(parser.logo)
        if src.isLocalFile():
            candidate = Path(src.toLocalFile())
        elif src.scheme():
            candidate = None                     # on the network, or qrc: nothing to read
        else:
            candidate = (path.parent / QUrl.fromPercentEncoding(
                parser.logo.encode("utf-8"))).resolve()
        if candidate is not None and candidate.is_file():
            logo = candidate
    return Brand(runs=_collapse(parser.runs), mark=parser.mark, logo=logo,
                 fill=parser.img, action=False)


# ── the face ─────────────────────────────────────────────────────────────────
# What a CSS generic family is on Windows, where these windows live.
_GENERIC = {"system-ui": "Segoe UI", "-apple-system": "", "sans-serif": "Arial",
            "serif": "Times New Roman", "monospace": "Consolas"}


@functools.lru_cache(maxsize=None)
def family(stack: str) -> str:
    """The family a browser on this machine takes out of a CSS font stack:
    the first one that is installed."""
    installed = {f.lower(): f for f in QFontDatabase.families()}
    for name in stack.split(","):
        name = name.strip().strip("'\"")
        name = _GENERIC.get(name.lower(), name)
        if name and name.lower() in installed:
            return installed[name.lower()]
    return QFont().defaultFamily()


def _font(fam: str, weight: int, italic: bool, pixels: int) -> QFont:
    f = QFont(fam)
    f.setPixelSize(max(1, int(pixels)))
    f.setWeight(QFont.Weight(weight))
    f.setItalic(italic)
    # A variable face asked for 600 through the weight comes back as its
    # Bold instance; asked on the axis it is the Semibold the page gets. A
    # face with no axes ignores it.
    if hasattr(f, "setVariableAxis"):
        f.setVariableAxis(QFont.Tag("wght"), float(weight))
    # Chromium drops the optional ligatures from spaced text, and every run
    # of the name is spaced.
    if hasattr(f, "setFeature"):
        for tag in ("liga", "clig"):
            f.setFeature(QFont.Tag(tag), 0)
    return f


# The size a run is shaped at. Large enough that hinting has nothing left to
# round, so the advances are the design's and scale down exactly.
_SHAPE_PX = 1000


@functools.lru_cache(maxsize=256)
def _shape(text: str, fam: str, weight: int):
    """A run's glyphs, the face each comes from, where each starts, and how
    far the run advances, the lengths as fractions of the em. Kerned, and
    shaped upright: a synthetic italic leans the glyphs and moves none of them.

    A character the face does not have comes from another one, as it would in
    the page, and its glyph number means something only in that face, so the
    face goes with it ("" for the face asked for)."""
    f = _font(fam, weight, False, _SHAPE_PX)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    lay = QTextLayout(text, f)
    lay.beginLayout()
    line = lay.createLine()
    line.setLineWidth(1e7)
    lay.endLayout()
    glyphs: list[int] = []
    faces: list[str] = []
    xs: list[float] = []
    last_raw = None
    for run in lay.glyphRuns():
        raw = run.rawFont()
        face = raw.familyName()
        face = "" if face.lower() == fam.lower() else face
        ids = list(run.glyphIndexes())
        glyphs += ids
        faces += [face] * len(ids)
        xs += [p.x() / _SHAPE_PX for p in run.positions()]
        last_raw = raw
    if not glyphs:
        return (), (), (), 0.0
    last = last_raw.advancesForGlyphIndexes([glyphs[-1]])
    end = xs[-1] + (last[0].x() / _SHAPE_PX if last else 0.0)
    # the runs come a face at a time; the spacing counts glyphs along the line
    order = sorted(range(len(glyphs)), key=lambda i: xs[i])
    end = max(end, xs[order[-1]])
    return (tuple(glyphs[i] for i in order), tuple(faces[i] for i in order),
            tuple(xs[i] for i in order), end)


@functools.lru_cache(maxsize=64)
def _raw(fam: str, weight: int, italic: bool, size: float) -> QRawFont:
    """The face at the exact size, for drawing. Vertical hinting is the
    rendering mode whose glyphs come closest to Chromium's on Windows."""
    f = _font(fam, weight, italic, round(size))
    f.setHintingPreference(QFont.HintingPreference.PreferVerticalHinting)
    raw = QRawFont.fromFont(f)
    raw.setPixelSize(size)
    return raw


def _round(v: float) -> float:
    """Half up, as Skia and Math.round do; Python's round() goes to even."""
    return math.floor(v + 0.5)


def _snap(r: QRectF) -> QRectF:
    """A box as Chromium paints it: each edge moved to the nearest device
    pixel. Boxes are snapped and text is not, so the mark, the disc and the
    buttons are drawn through this and the name and the credit are not."""
    x0, y0 = _round(r.x()), _round(r.y())
    return QRectF(x0, y0, _round(r.x() + r.width()) - x0, _round(r.y() + r.height()) - y0)


def _lu(v: float) -> float:
    """Down to Chromium's layout unit, a sixty fourth of a pixel."""
    return math.floor(v * 64) / 64


def _lu_up(v: float) -> float:
    return math.ceil(v * 64 - 1e-6) / 64


def _baseline(box_top: float, box: float, size: float, raw: QRawFont) -> float:
    """Where the page puts the baseline of one line of text centred in a box,
    in device pixels, and rounded to one, which is where the glyphs land.

    The line is LINE_HEIGHT of the size tall, cut down to layout units, and
    centred with a layout unit division. The font's ascent and descent are
    rounded to whole pixels, and the baseline sits the rounded ascent plus
    half of what the line has left over, cut to a whole pixel, below the top
    of the line. Worked out from the page and checked against it at 100,
    125, 150, 175 and 200 per cent.
    """
    lh = LINE_HEIGHT * size
    top = box_top + _lu((box - _lu(lh)) / 2)
    ascent = _round(raw.ascent())
    descent = _round(raw.descent())
    return _round(top + ascent + math.floor((lh - ascent - descent) / 2))


# ── the layout ───────────────────────────────────────────────────────────────
@dataclass
class _Line:
    raw: QRawFont                  # the face asked for, at the exact size
    glyphs: tuple[int, ...]
    xs: list[float]
    y: float
    role: str
    width: float
    faces: tuple[str, ...] = ()     # per glyph, the face it comes from ("" for raw)
    weight: int = 400
    italic: bool = False
    size: float = 0.0


@dataclass
class BandLayout:
    """Everything the band's drawing needs, in device pixels, for one width
    and one scale. ``x1`` is the page's number, in CSS pixels: where the
    brand ends and the oblique starts."""
    width: float
    scale: float
    height: float
    thin: float
    x1: int
    mark: QRectF | None
    disc: QRectF | None
    name: list[_Line] = field(default_factory=list)
    credit: _Line | None = None
    buttons: list[QRectF] = field(default_factory=list)
    glyphs: list[QRectF] = field(default_factory=list)


def _line(text: str, stack: str, weight: int, italic: bool, size: float, spacing: float,
          x: float, role: str) -> _Line:
    fam = family(stack)
    glyphs, faces, xs, end = _shape(text, fam, weight)
    # letter-spacing follows every character, the last one included
    pos = [x + g * size + i * spacing for i, g in enumerate(xs)]
    return _Line(raw=_raw(fam, weight, italic, size), glyphs=glyphs, xs=pos, y=0.0, role=role,
                 width=end * size + len(text) * spacing, faces=faces, weight=weight,
                 italic=italic, size=size)


def band_layout(width: float, scale: float, brand: Brand) -> BandLayout:
    """Lay the band out as the page does: ``width`` is the window's, in CSS
    pixels, and ``scale`` its device pixel ratio. Chromium lays a page out in
    device pixels and reports CSS ones, so everything here is worked in
    device pixels too."""
    s = float(scale)
    tall, thin = px("tbar-h") * s, px("tbar-thin") * s
    inset = (px("tbar-h") / 2 - MARK_INSET) * s
    x = inset
    mark = disc = None
    if brand.mark:
        box = QRectF(x, (tall - MARK * s) / 2, MARK * s, MARK * s)
        mark = box                          # snapped where it is drawn, see _logo
        if brand.action:
            r = DISC * s / 2
            disc = _snap(QRectF(box.center().x() - r, box.center().y() - r, 2 * r, 2 * r))
        x += (MARK + MARK_GAP) * s
    lines = []
    for text, strong in brand.runs:
        ln = _line(text, value("font-brand"), STRONG_WEIGHT if strong else NAME_WEIGHT, False,
                   NAME_SIZE * s, (STRONG_SPACING if strong else NAME_SPACING) * s, x,
                   ROLE_STRONG if strong else ROLE_NAME)
        ln.y = _baseline(0.0, tall, NAME_SIZE * s, ln.raw)
        lines.append(ln)
        # a run's box is a whole number of layout units, rounded up
        x += _lu_up(ln.width)
    x1 = int(_round((x + BRAND_END * s) / s))

    w = width * s
    credit = _line(credit_text(), value("font-credit"), NAME_WEIGHT, True, CREDIT_SIZE * s,
                   CREDIT_SPACING * s, 0.0, ROLE_CREDIT)
    # left:50%, then back by half its own width (translateX(-50%))
    shift = _lu(w / 2) - _lu_up(credit.width) / 2
    credit.xs = [v + shift for v in credit.xs]
    credit.y = _baseline(0.0, thin, CREDIT_SIZE * s, credit.raw)

    buttons, glyphs = [], []
    for i in range(3):
        left = w - (3 - i) * BUTTON * s
        buttons.append(_snap(QRectF(left, 0.0, BUTTON * s, thin)))
        # the drawing is centred in the button's box before either is snapped
        glyphs.append(_snap(QRectF(left + (BUTTON - GLYPH) / 2 * s, (thin - GLYPH * s) / 2,
                                   GLYPH * s, GLYPH * s)))
    return BandLayout(width=w, scale=s, height=tall, thin=thin, x1=x1, mark=mark, disc=disc,
                      name=lines, credit=credit, buttons=buttons, glyphs=glyphs)


# ── the drawing ──────────────────────────────────────────────────────────────
def _colour(palette: str, role: str) -> QColor:
    """A role as a QColor, with the alpha read the CSS way round (#rrggbbaa)."""
    v = PALETTES[palette][role].lstrip("#")
    c = QColor(int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))
    if len(v) == 8:
        c.setAlpha(int(v[6:8], 16))
    return c


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(round(a.red() + (b.red() - a.red()) * t),
                  round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t))


def _svg_path(d: str, scale: float) -> QPainterPath:
    """The band's path as geometry.py writes it: M, L, Q and Z, absolute."""
    path = QPainterPath()
    for cmd, args in re.findall(r"([MLQZ])([^MLQZ]*)", d):
        n = [float(v) * scale for v in re.findall(r"-?\d+(?:\.\d+)?", args)]
        if cmd == "M":
            path.moveTo(n[0], n[1])
        elif cmd == "L":
            path.lineTo(n[0], n[1])
        elif cmd == "Q":
            path.quadTo(n[0], n[1], n[2], n[3])
        else:
            path.closeSubpath()
    return path


def _normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _disc(p: QPainter, disc: QRectF, s: float, palette: str) -> None:
    """The round button and the shadow under it. The shadow is the disc
    blurred by a Gaussian of sigma half the blur radius, which is what CSS
    means by a blur radius; across a circle that large the edge of it is the
    normal curve, laid out along the radius."""
    r = disc.width() / 2
    sigma = DISC_SHADOW_BLUR / 2 * s
    reach = r + 3 * sigma
    centre = QPointF(disc.center().x(), disc.center().y() + DISC_SHADOW_Y * s)
    shade = _colour(palette, ROLE_SHADOW)
    grad = QRadialGradient(centre, reach)
    for i in range(33):
        d = reach * i / 32
        c = QColor(shade)
        c.setAlphaF(shade.alphaF() * _normal_cdf((r - d) / sigma))
        grad.setColorAt(d / reach, c)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(grad)
    p.drawEllipse(centre, reach, reach)
    p.setBrush(_colour(palette, ROLE_DISC))
    p.drawEllipse(disc)


def _logo(p: QPainter, box: QRectF, logo: Path, fill: bool, s: float) -> None:
    """The mark inside its square, cut to the square's rounded corners.

    ``box`` is the square where the layout put it, between pixels. Chromium
    snaps the square to the pixel grid, fits the picture inside the snapped
    one, and rounds the picture's size and its offset to whole pixels: tried
    against the page at four scales, that is the placement that lands where
    the page's does, and the others are a pixel out somewhere."""
    box = _snap(box)
    clip = QPainterPath()
    clip.addRoundedRect(box, MARK_RADIUS * s, MARK_RADIUS * s)
    svg = QSvgRenderer(str(logo)) if logo.suffix.lower() == ".svg" else None
    img = None if svg is not None else QImage(str(logo))
    if svg is not None:
        if not svg.isValid():
            return
        vb = svg.viewBoxF()
        aw, ah = (vb.width(), vb.height()) if vb.width() > 0 else (1.0, 1.0)
    else:
        if img.isNull():
            return
        aw, ah = float(img.width()), float(img.height())
    if fill:
        target = box
    else:
        k = min(box.width() / aw, box.height() / ah)
        w, h = _round(aw * k), _round(ah * k)
        target = QRectF(box.x() + _round((box.width() - w) / 2),
                        box.y() + _round((box.height() - h) / 2), w, h)
    p.save()
    p.setClipPath(clip)
    if svg is not None:
        svg.render(p, target)
    else:
        scaled = img.scaled(int(target.width()), int(target.height()),
                            Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
        p.drawImage(target, scaled)
    p.restore()


@functools.lru_cache(maxsize=32)
def _glyph_svg(name: str, ink: str) -> QSvgRenderer:
    vb, body = window_glyphs()[name]
    doc = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}"><g fill="none" '
           f'stroke="{ink}" stroke-width="{GLYPH_STROKE}" stroke-linecap="round" '
           f'stroke-linejoin="round">{body}</g></svg>')
    return QSvgRenderer(QByteArray(doc.encode("utf-8")))


def _write(p: QPainter, line: _Line, colour: QColor) -> None:
    """The line's glyphs, a stretch of one face at a time."""
    p.setPen(colour)
    faces = line.faces or ("",) * len(line.glyphs)
    i = 0
    while i < len(line.glyphs):
        j = i
        while j < len(line.glyphs) and faces[j] == faces[i]:
            j += 1
        raw = line.raw if not faces[i] else _raw(faces[i], line.weight, line.italic, line.size)
        run = QGlyphRun()
        run.setRawFont(raw)
        run.setGlyphIndexes(list(line.glyphs[i:j]))
        run.setPositions([QPointF(x, line.y) for x in line.xs[i:j]])
        p.drawGlyphRun(QPointF(0, 0), run)
        i = j


def render_band(width: float, scale: float, palette: str, brand: Brand, *,
                strip: str | QColor | None = None, maximized: bool = False,
                hover: tuple[float, float, float] = (0.0, 0.0, 0.0),
                layout: BandLayout | None = None) -> QImage:
    """The band as a picture, ``tbar-h`` tall and ``width`` wide in CSS
    pixels, drawn at ``scale``.

    ``strip`` is what shows under the thin half: the window's own colour,
    since while this band is up the window is empty. ``hover`` is how far each
    of the three buttons has gone towards its hover state, nought to one.
    """
    lay = layout or band_layout(width, scale, brand)
    s = lay.scale
    img = QImage(max(1, math.ceil(lay.width - 1e-6)), max(1, math.ceil(lay.height - 1e-6)),
                 QImage.Format.Format_RGB32)
    img.fill(QColor(strip) if strip is not None else _colour(palette, "surface-0"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    p.fillPath(_svg_path(band_path(width, lay.x1), s), _colour(palette, ROLE_BAND))
    if lay.disc is not None:
        _disc(p, lay.disc, s, palette)
    if lay.mark is not None and brand.logo is not None:
        _logo(p, lay.mark, brand.logo, brand.fill, s)
    for line in lay.name:
        _write(p, line, _colour(palette, line.role))
    if lay.credit is not None:
        _write(p, lay.credit, _colour(palette, ROLE_CREDIT))

    band = _colour(palette, ROLE_BAND)
    names = ("win-minimise", "win-restore" if maximized else "win-maximise", "win-close")
    for i, (rect, box, name) in enumerate(zip(lay.buttons, lay.glyphs, names)):
        t = hover[i]
        close = i == 2
        if t > 0:
            p.fillRect(rect, _mix(band, _colour(palette, ROLE_CLOSE if close else ROLE_HOVER), t))
        ink = _mix(_colour(palette, ROLE_GLYPH),
                   _colour(palette, ROLE_CLOSE_GLYPH if close else ROLE_HOVER_GLYPH), t)
        _glyph_svg(name, ink.name()).render(p, box)
    p.end()
    img.setDevicePixelRatio(s)
    return img


# ── on the window ────────────────────────────────────────────────────────────
def forget() -> None:
    """Let go of the faces and the drawings kept between one band and the
    next. They are Qt objects, and a module's caches outlive the application:
    left to the interpreter's own exit they are destroyed after Qt is, and the
    process died on its way out. So they go when the application is about to
    quit."""
    _raw.cache_clear()
    _glyph_svg.cache_clear()


_FORGETS = False


def _forget_on_quit() -> None:
    global _FORGETS
    app = QApplication.instance()
    if app is not None and not _FORGETS:
        app.aboutToQuit.connect(forget)
        _FORGETS = True


class NativeBand(QQuickPaintedItem):
    """The band as an item over the page, and the chrome it carries.

    It draws :func:`render_band` and answers the pointer the way the page's
    band does: a press anywhere but on a control moves the window through the
    window manager, so snapping and Win+arrows keep working; a double click
    maximises and restores; the three buttons do what they say. The mark in
    its disc is a control that does nothing yet, because what it does is the
    page's.
    """

    def __init__(self, parent: QQuickItem | None = None, *, palette: str | None = None,
                 brand: Brand | None = None, strip: str | None = None):
        super().__init__(parent)
        _forget_on_quit()
        self.setOpaquePainting(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setAcceptHoverEvents(True)
        self.palette = palette or DEFAULT.slug
        self.brand = brand or Brand()
        self.strip = strip
        self.maximized = False
        self._hover = [0.0, 0.0, 0.0]
        self._under = -1                 # the button under the pointer, or -1
        self._pressed = -1
        self._anims: list = [None, None, None]
        self._image: QImage | None = None
        self._layout: BandLayout | None = None
        self._layout_key = None

    # ── state ───────────────────────────────────────────────────────────
    def set_palette(self, palette: str, strip: str | None = None) -> None:
        self.palette = palette
        self.strip = strip
        self.refresh()

    def set_brand(self, brand: Brand) -> None:
        self.brand = brand
        self._layout_key = None
        self.refresh()

    def set_maximized(self, on: bool) -> None:
        if self.maximized != bool(on):
            self.maximized = bool(on)
            self.refresh()

    def scale(self) -> float:
        w = self.window()
        return float(w.effectiveDevicePixelRatio()) if w is not None else 1.0

    def layout(self) -> BandLayout:
        key = (round(self.width(), 3), self.scale(), self.brand)
        if key != self._layout_key:
            self._layout = band_layout(self.width(), self.scale(), self.brand)
            self._layout_key = key
        return self._layout

    def refresh(self) -> None:
        """Draw the band again, here on the GUI thread; paint() only puts the
        picture on the texture. Not while it is hidden: once the page's band
        has taken over, a live resize would otherwise draw this one at every
        step for nobody. It is drawn again when it is shown."""
        if self.width() <= 0 or not self.isVisible():
            return
        self._image = render_band(self.width(), self.scale(), self.palette, self.brand,
                                  strip=self.strip, maximized=self.maximized,
                                  hover=tuple(self._hover), layout=self.layout())
        self.update()

    def paint(self, painter: QPainter) -> None:
        img = self._image
        if img is not None:
            painter.drawImage(QPointF(0, 0), img)

    def geometryChange(self, new, old) -> None:     # noqa: N802  (Qt's name)
        super().geometryChange(new, old)
        if new.width() != old.width() or new.height() != old.height():
            self.refresh()

    def itemChange(self, change, data) -> None:     # noqa: N802
        super().itemChange(change, data)
        if change in (QQuickItem.ItemChange.ItemSceneChange,
                      QQuickItem.ItemChange.ItemDevicePixelRatioHasChanged):
            self._layout_key = None
            self.refresh()
        elif change == QQuickItem.ItemChange.ItemVisibleHasChanged:
            self.refresh()

    # ── the pointer ─────────────────────────────────────────────────────
    def _button_at(self, pos: QPointF) -> int:
        lay = self.layout()
        s = lay.scale
        for i, r in enumerate(lay.buttons):
            if QRectF(r.x() / s, r.y() / s, r.width() / s, r.height() / s).contains(pos):
                return i
        return -1

    def _on_disc(self, pos: QPointF) -> bool:
        disc = self.layout().disc
        if disc is None:
            return False
        s = self.layout().scale
        c = disc.center()
        return math.hypot(pos.x() - c.x() / s, pos.y() - c.y() / s) <= disc.width() / s / 2

    def _glow(self, i: int, on: bool) -> None:
        """A button answers the pointer faster than it lets go: --t-in on the
        way in, --t-out on the way out, as the page's do."""
        if self._anims[i] is not None:
            self._anims[i].stop()
        a = QVariantAnimation(self)
        a.setStartValue(float(self._hover[i]))
        a.setEndValue(1.0 if on else 0.0)
        a.setDuration(int(ms("t-in") if on else ms("t-out")))
        a.setEasingCurve(QEasingCurve.Type.OutQuad)

        def step(v, i=i):
            self._hover[i] = float(v)
            self.refresh()
        a.valueChanged.connect(step)
        self._anims[i] = a
        a.start()

    def _set_under(self, i: int) -> None:
        if i == self._under:
            return
        if self._under >= 0:
            self._glow(self._under, False)
        self._under = i
        if i >= 0:
            self._glow(i, True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor if i >= 0
                               else Qt.CursorShape.ArrowCursor))

    def hoverMoveEvent(self, event) -> None:        # noqa: N802
        self._set_under(self._button_at(event.position()))

    def hoverEnterEvent(self, event) -> None:       # noqa: N802
        self._set_under(self._button_at(event.position()))

    def hoverLeaveEvent(self, event) -> None:       # noqa: N802
        self._set_under(-1)

    def mousePressEvent(self, event) -> None:       # noqa: N802
        pos = event.position()
        self._pressed = self._button_at(pos)
        event.accept()
        if self._pressed >= 0 or self._on_disc(pos):
            return
        win = self.window()
        if win is not None:
            win.startSystemMove()

    def mouseReleaseEvent(self, event) -> None:     # noqa: N802
        i, self._pressed = self._pressed, -1
        event.accept()
        if i < 0 or self._button_at(event.position()) != i:
            return
        win = self.window()
        if win is None:
            return
        if i == 0:
            win.showMinimized()
        elif i == 1:
            if win.isMaximized():
                win.showNormal()
            else:
                win.showMaximized()
        else:
            win.close()

    def mouseDoubleClickEvent(self, event) -> None:     # noqa: N802
        pos = event.position()
        event.accept()
        if self._button_at(pos) >= 0 or self._on_disc(pos):
            return
        win = self.window()
        if win is None:
            return
        if win.isMaximized():
            win.showNormal()
        else:
            win.showMaximized()


class Edge(QQuickItem):
    """One of the eight strips a window is resized from, while the page's own
    are not there yet: a press hands the edge to the window manager."""

    def __init__(self, edge: str, cursor, parent: QQuickItem | None = None):
        super().__init__(parent)
        self.edge = edge
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(QCursor(cursor))

    def mousePressEvent(self, event) -> None:       # noqa: N802
        event.accept()
        win = self.window()
        if win is not None:
            win.startSystemResize(edges_of(self.edge))

    def place(self, w: float, h: float) -> None:
        e = self.edge
        if e == "n":
            x, y, ew, eh = CORNER, 0.0, w - 2 * CORNER, STRIP
        elif e == "s":
            x, y, ew, eh = CORNER, h - STRIP, w - 2 * CORNER, STRIP
        elif e == "w":
            x, y, ew, eh = 0.0, CORNER, STRIP, h - 2 * CORNER
        elif e == "e":
            x, y, ew, eh = w - STRIP, CORNER, STRIP, h - 2 * CORNER
        else:
            x = 0.0 if e.endswith("w") else w - CORNER
            y = 0.0 if e.startswith("n") else h - CORNER
            ew = eh = CORNER
        self.setX(x)
        self.setY(y)
        self.setWidth(max(0.0, ew))
        self.setHeight(max(0.0, eh))
