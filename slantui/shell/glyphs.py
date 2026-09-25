"""Text drawn the way the page draws it, for the band the window draws.

The band the window puts up until the page has its own (band.py) is worth
something only if nobody can tell the two apart, and for the name and the
credit line that is a question of glyphs. Qt and the page do not draw a glyph
the same way. Qt asks DirectWrite for a rendering mode it can name through a
hinting preference and blends the coverage at the system's font smoothing
gamma; the page is Chromium, which asks DirectWrite for the mode Skia picks
and blends the coverage through Skia's own correcting table. Measured on the
same name at the same place, Qt's strokes came out a fifth lighter along
their edges and a third of a pixel off on some of them, and the window's band
read as the soft one until the page's arrived and brought it into focus.

So on Windows the text is drawn here, with DirectWrite called directly and
Skia's arithmetic written out, and it lands on the page's pixels: at 100, 125,
150 and 175 per cent, every subpixel of the strong run and of the credit line
within one level of the page's. Everything below that is not arithmetic is a
fact about the engine that draws the page, found by measuring it, and each is
written where it is used:

* the rendering mode is Skia's choice for the face and the size (the face's
  ``gasp`` table), with the grid fit on;
* a glyph is placed at a quarter of a pixel across and a whole pixel down;
* a face is asked for at the size Blink keys its font cache by, which keeps
  hundredths of a pixel and drops the rest;
* the coverage goes through Skia's correcting table (SkMaskGamma) with the
  sRGB curve and a contrast of one, into a 5-6-5 mask, and is laid on the
  ground as a plain mix of the two colours;
* an italic the face does not have is the upright face slanted by a quarter,
  which is Skia's synthetic italic.

Anywhere this cannot be done (not Windows, a face DirectWrite does not know,
a weight it would embolden) :func:`draw_line` says so, and band.py draws the
line with Qt, as it always has.
"""
from __future__ import annotations

import functools
import math
import sys

from .qt import QColor, QImage, QPainter

__all__ = ["available", "draw_line", "forget"]


# ── DirectWrite, as much of it as a glyph needs ─────────────────────────────
if sys.platform == "win32":
    import ctypes
    from ctypes import POINTER, byref, c_float, c_int32, c_uint16, c_uint32, c_void_p, wintypes

    class _GUID(ctypes.Structure):
        _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD),
                    ("d", ctypes.c_ubyte * 8)]

    class _GlyphOffset(ctypes.Structure):
        _fields_ = [("advanceOffset", c_float), ("ascenderOffset", c_float)]

    class _GlyphRun(ctypes.Structure):
        _fields_ = [("fontFace", c_void_p), ("fontEmSize", c_float), ("glyphCount", c_uint32),
                    ("glyphIndices", POINTER(c_uint16)), ("glyphAdvances", POINTER(c_float)),
                    ("glyphOffsets", POINTER(_GlyphOffset)), ("isSideways", wintypes.BOOL),
                    ("bidiLevel", c_uint32)]

    class _Matrix(ctypes.Structure):
        _fields_ = [("m11", c_float), ("m12", c_float), ("m21", c_float), ("m22", c_float),
                    ("dx", c_float), ("dy", c_float)]

    class _Rect(ctypes.Structure):
        _fields_ = [("left", c_int32), ("top", c_int32), ("right", c_int32), ("bottom", c_int32)]

# IDWriteFactory2, which is where a glyph run analysis takes a grid fit mode
_IID_FACTORY2 = (0x0439FC60, 0xCA44, 0x4994, (0x8D, 0xEE, 0x3A, 0x9A, 0xF7, 0xB7, 0x32, 0xEC))
_NATURAL, _NATURAL_SYMMETRIC = 4, 5            # DWRITE_RENDERING_MODE
_GRID_ON = 2                                   # DWRITE_GRID_FIT_MODE_ENABLED
_CLEARTYPE = 0                                 # DWRITE_TEXT_ANTIALIAS_MODE_CLEARTYPE
_MEASURE_NATURAL = 0                           # DWRITE_MEASURING_MODE_NATURAL
_TEXTURE_3x1 = 1                               # DWRITE_TEXTURE_CLEARTYPE_3x1
_SIM_OBLIQUE = 2                               # DWRITE_FONT_SIMULATIONS_OBLIQUE
_GASP = ord("g") | ord("a") << 8 | ord("s") << 16 | ord("p") << 24


def _method(obj, index: int, *argtypes):
    """A COM method by its place in the object's table, returning an HRESULT."""
    table = ctypes.cast(ctypes.cast(obj, POINTER(c_void_p))[0], POINTER(c_void_p))
    return functools.partial(ctypes.WINFUNCTYPE(c_int32, c_void_p, *argtypes)(table[index]), obj)


def _slot(obj, index: int, restype):
    """A COM method that answers something other than an HRESULT."""
    table = ctypes.cast(ctypes.cast(obj, POINTER(c_void_p))[0], POINTER(c_void_p))
    return ctypes.WINFUNCTYPE(restype, c_void_p)(table[index])


def _release(obj) -> None:
    if obj:
        _slot(obj, 2, c_uint32)(obj)


def _simulations(font) -> int:
    """What DirectWrite would do to the face to make it the one asked for:
    thicken it (1), lean it (2), or nothing (0)."""
    return _slot(font, 10, c_int32)(font)


class _DirectWrite:
    """The factory, the system's fonts, and the faces asked for so far."""

    def __init__(self):
        a, b, c, d = _IID_FACTORY2
        iid = _GUID(a, b, c, (ctypes.c_ubyte * 8)(*d))
        self.factory = c_void_p()
        fn = ctypes.WinDLL("dwrite").DWriteCreateFactory
        fn.restype = c_int32
        if fn(0, byref(iid), byref(self.factory)) != 0:
            raise OSError("DirectWrite has no factory to give")
        self.fonts = c_void_p()
        if _method(self.factory, 3, POINTER(c_void_p), wintypes.BOOL)(byref(self.fonts), False):
            raise OSError("DirectWrite has no system font collection")
        self.faces: dict = {}
        self.held: list = []

    def close(self) -> None:
        for obj in self.held + [self.fonts, self.factory]:
            _release(obj)
        self.held, self.faces = [], {}
        self.fonts = self.factory = None

    def face(self, family: str, weight: int, italic: bool):
        """(face, slant) for a family, weight and style as the page gets it,
        or None where the page's face would be one this cannot draw.

        The face is the one DirectWrite matches; where the family has no
        italic, DirectWrite would lean it with a simulation of its own and the
        page leans the upright face instead, by a quarter (Skia's synthetic
        italic), so that is what comes back."""
        key = (family.lower(), weight, italic)
        if key not in self.faces:
            self.faces[key] = self._face(family, weight, italic)
        return self.faces[key]

    def _face(self, family: str, weight: int, italic: bool):
        index, exists = c_uint32(), wintypes.BOOL()
        if _method(self.fonts, 5, wintypes.LPCWSTR, POINTER(c_uint32), POINTER(wintypes.BOOL))(
                family, byref(index), byref(exists)) or not exists:
            return None
        fam = c_void_p()
        if _method(self.fonts, 4, c_uint32, POINTER(c_void_p))(index, byref(fam)):
            return None
        self.held.append(fam)
        font = self._match(fam, weight, 2 if italic else 0)
        slant = 0.0
        if font is not None and italic and _simulations(font) & _SIM_OBLIQUE:
            # no italic in the family: the upright face, leaned the page's way
            font, slant = self._match(fam, weight, 0), -0.25
        if font is None or _simulations(font):
            return None             # a face DirectWrite would thicken or lean itself
        face = c_void_p()
        if _method(font, 13, POINTER(c_void_p))(byref(face)):
            return None
        self.held.append(face)
        return face, slant, self._gasp(face)

    def _match(self, fam, weight: int, style: int):
        font = c_void_p()
        if _method(fam, 7, c_int32, c_int32, c_int32, POINTER(c_void_p))(weight, 5, style, byref(font)):
            return None
        self.held.append(font)
        return font

    @staticmethod
    def _gasp(face) -> tuple[tuple[int, int], ...]:
        """The face's gasp ranges, (up to ppem, flags), if it has a table of
        version 1 or later: that table is what Skia decides the mode from."""
        data, size, ctx, exists = c_void_p(), c_uint32(), c_void_p(), wintypes.BOOL()
        if _method(face, 12, c_uint32, POINTER(c_void_p), POINTER(c_uint32), POINTER(c_void_p),
                   POINTER(wintypes.BOOL))(_GASP, byref(data), byref(size), byref(ctx), byref(exists)):
            return ()
        try:
            if not exists or size.value < 4:
                return ()
            raw = ctypes.string_at(data, size.value)
            version, count = int.from_bytes(raw[0:2], "big"), int.from_bytes(raw[2:4], "big")
            if version < 1:
                return ()
            return tuple((int.from_bytes(raw[4 + 4 * i:6 + 4 * i], "big"),
                          int.from_bytes(raw[6 + 4 * i:8 + 4 * i], "big"))
                         for i in range(count) if 8 + 4 * i <= len(raw))
        finally:
            ctypes.WINFUNCTYPE(None, c_void_p, c_void_p)(ctypes.cast(
                ctypes.cast(face, POINTER(c_void_p))[0], POINTER(c_void_p))[13])(face, ctx)

    def coverage(self, face, gasp, glyph: int, size: float, sub_x: float, slant: float):
        """One glyph's ClearType coverage: (left, top, width, height, red,
        green, blue), the three channels a byte a pixel, for a glyph whose
        origin is ``sub_x`` of a pixel to the right of a whole pixel."""
        mode = _mode(gasp, size)
        ids = (c_uint16 * 1)(glyph)
        run = _GlyphRun(face, size, 1, ids, (c_float * 1)(0.0), (_GlyphOffset * 1)(), False, 0)
        xf = _Matrix(1.0, 0.0, slant, 1.0, 0.0, 0.0)
        analysis = c_void_p()
        if _method(self.factory, 30, POINTER(_GlyphRun), POINTER(_Matrix), c_int32, c_int32, c_int32,
                   c_int32, c_float, c_float, POINTER(c_void_p))(
                byref(run), byref(xf), mode, _MEASURE_NATURAL, _GRID_ON, _CLEARTYPE, sub_x, 0.0,
                byref(analysis)):
            raise OSError("DirectWrite would not analyse a glyph")
        try:
            box = _Rect()
            if _method(analysis, 3, c_int32, POINTER(_Rect))(_TEXTURE_3x1, byref(box)):
                raise OSError("DirectWrite gave a glyph no bounds")
            w, h = box.right - box.left, box.bottom - box.top
            if w <= 0 or h <= 0:
                return box.left, box.top, 0, 0, b"", b"", b""
            buf = (ctypes.c_ubyte * (w * h * 3))()
            if _method(analysis, 4, c_int32, POINTER(_Rect), POINTER(ctypes.c_ubyte), c_uint32)(
                    _TEXTURE_3x1, byref(box), buf, len(buf)):
                raise OSError("DirectWrite gave a glyph no coverage")
            raw = bytes(buf)
            return box.left, box.top, w, h, raw[0::3], raw[1::3], raw[2::3]
        finally:
            _release(analysis)


def _mode(gasp, size: float) -> int:
    """The rendering mode Skia picks: symmetric above twenty pixels, and
    below that whatever the face's gasp table says for the size; a face with
    no table of that version gets the asymmetric one."""
    if size > 20:
        return _NATURAL_SYMMETRIC
    ppem = math.floor(round(size * 64) / 64 + 0.5)
    for top, flags in gasp:
        if ppem <= top:
            return _NATURAL_SYMMETRIC if flags & 0x8 else _NATURAL
    return _NATURAL


_DW: list = []                  # the one DirectWrite, once asked for; [None] if it failed


def _dw():
    if not _DW:
        try:
            _DW.append(_DirectWrite() if sys.platform == "win32" else None)
        except OSError:
            _DW.append(None)
    return _DW[0]


def available() -> bool:
    """Whether text can be drawn here the page's way at all."""
    return _dw() is not None


def forget() -> None:
    """Let the faces and the factory go, before the application does."""
    _coverage.cache_clear()
    if _DW and _DW[0] is not None:
        _DW[0].close()
    _DW.clear()


@functools.lru_cache(maxsize=1024)
def _coverage(family: str, weight: int, italic: bool, glyph: int, size: float, sub_x: float):
    dw = _dw()
    found = dw.face(family, weight, italic) if dw is not None else None
    if found is None:
        return None
    face, slant, gasp = found
    return dw.coverage(face, gasp, glyph, size, sub_x, slant)


# ── what the page's engine does with the coverage ───────────────────────────
def page_size(size: float) -> float:
    """The size a face is asked for at: Blink keys its font cache by the size
    in hundredths of a pixel and drops the rest, and draws with the face the
    key found. At 125 per cent the band's name is 18.125 pixels and comes out
    at 18.12, which is three thousandths of a pixel a character: over a name,
    a tenth of a pixel, enough to put a glyph on the next quarter."""
    return math.floor(size * 100 + 1e-6) / 100


def _srgb_to_linear(v: float) -> float:
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(v: float) -> float:
    v = max(v, 0.0)
    return v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


# The contrast Skia's table is built with for the page, and the curve is sRGB.
_CONTRAST = 1.0


@functools.lru_cache(maxsize=64)
def _table(channel: int) -> bytes:
    """Skia's correcting table for one channel of the ink, raw coverage to
    mask value, and the mask cut to its 5-6-5 bits: red and blue keep five,
    green six. The ink is first reduced to three bits a channel (Skia's
    canonical colour), and the table assumes a ground as far from it as can
    be, which is why the same ink gives the same glyph on any band."""
    n = channel >> 5
    lum = ((n << 5) | (n << 2) | (n >> 1)) / 255.0
    ground = 1.0 - lum
    lin_ink, lin_ground = _srgb_to_linear(lum), _srgb_to_linear(ground)
    contrast = _CONTRAST * lin_ground
    out = []
    for i in range(256):
        a = i / 255.0
        a = a + (1.0 - a) * contrast * a
        if abs(lum - ground) < 1 / 256:
            v = a
        else:
            v = (_linear_to_srgb(lin_ink * a + (1.0 - a) * lin_ground) - ground) / (lum - ground)
        out.append(max(0, min(255, math.floor(255.0 * v + 0.5))))
    return bytes(out)


@functools.lru_cache(maxsize=64)
def _mix(ink: int, ground: int, bits: int) -> bytes:
    """A mask value of ``bits`` to the pixel it gives: the value read back as
    a fraction of its own full scale, and the ink laid over the ground by
    that much, rounded."""
    full = (1 << bits) - 1
    return bytes(math.floor(ground + (ink - ground) * ((m >> (8 - bits)) / full) + 0.5)
                 for m in range(256))


_NONZERO = bytes([0] + [255] * 255)


def draw_line(painter: QPainter, line, ink: QColor, ground: QColor, *, family: str) -> bool:
    """Draw one line of band.py's layout onto ``painter`` the page's way, laid
    on ``ground``. False, with nothing drawn, where this cannot be done, and
    the caller draws it another way.

    ``family`` is the face the line asks for; a glyph band.py took from
    another face (a character the first one lacks) says which in
    ``line.faces``."""
    if not available():
        return False
    pieces = []
    for glyph, x, face in zip(line.glyphs, line.xs, line.faces or ("",) * len(line.glyphs)):
        # a quarter of a pixel across, rounded to the nearest; Skia's rounding
        q = math.floor(x * 4 + 0.5) / 4
        whole = math.floor(q)
        cov = _coverage(face or family, line.weight, line.italic, glyph, page_size(line.size),
                        q - whole)
        if cov is None:
            return False
        left, top, w, h, r, g, b = cov
        if w:
            pieces.append((whole + left, int(line.y) + top, w, h, (r, g, b)))
    if not pieces:
        return True
    x0 = min(p[0] for p in pieces)
    y0 = min(p[1] for p in pieces)
    W = max(p[0] + p[2] for p in pieces) - x0
    H = max(p[1] + p[3] for p in pieces) - y0
    # the ink's own table, channel by channel, then every glyph laid into one
    # mask a channel; where two glyphs cover the same pixel the second goes
    # over the first, as it does on the page
    tables = (_table(ink.red()), _table(ink.green()), _table(ink.blue()))
    mask = [bytearray(W * H) for _ in range(3)]
    for gx, gy, w, h, chans in pieces:
        for c in range(3):
            src = chans[c].translate(tables[c])
            dst = mask[c]
            for row in range(h):
                at = (gy - y0 + row) * W + (gx - x0)
                seg = src[row * w:(row + 1) * w]
                old = dst[at:at + w]
                if old.count(0) == w:
                    dst[at:at + w] = seg
                else:
                    dst[at:at + w] = bytes(o + s - (o * s + 127) // 255 for o, s in zip(old, seg))
    bits = (5, 6, 5)
    red = bytes(mask[0]).translate(_mix(ink.red(), ground.red(), bits[0]))
    green = bytes(mask[1]).translate(_mix(ink.green(), ground.green(), bits[1]))
    blue = bytes(mask[2]).translate(_mix(ink.blue(), ground.blue(), bits[2]))
    # only the pixels a glyph touches are written: the rest of the box keeps
    # whatever the band has there
    touched = (int.from_bytes(bytes(mask[0]), "little") | int.from_bytes(bytes(mask[1]), "little")
               | int.from_bytes(bytes(mask[2]), "little")).to_bytes(W * H, "little").translate(_NONZERO)
    pixels = bytearray(W * H * 4)
    pixels[0::4], pixels[1::4], pixels[2::4], pixels[3::4] = blue, green, red, touched
    img = QImage(bytes(pixels), W, H, W * 4, QImage.Format.Format_ARGB32).copy()
    painter.save()
    painter.resetTransform()
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    painter.drawImage(x0, y0, img)
    painter.restore()
    return True
