"""Colour maths, written out so the package needs nothing installed.

Three spaces are in play here and they each do one job.

sRGB is what a hex string holds and what a screen shows. WCAG contrast is
defined on sRGB through a relative luminance, and that is the only thing the
auditor measures, so luminance lives in this file too.

OKLab is perceptually uniform: a step in its lightness looks like the same
size step wherever it is taken. Every operation that moves a colour (raising
a surface, blending a tint, solving a text colour against a threshold) works
in OKLab, because the same step taken in sRGB looks large in the dark and
invisible in the light.

OKLCH is OKLab in polar form. Hue and chroma are separate numbers there, so
rotating a red to an amber, or keeping a hue while changing a lightness, is
one field.
"""
from __future__ import annotations

import math
import re

__all__ = [
    "RGB", "RGBA",
    "parse", "to_hex", "is_hex", "alpha_of",
    "luminance", "contrast", "over",
    "to_oklab", "from_oklab", "to_oklch", "from_oklch",
    "lightness", "with_lightness", "shift_lightness",
    "chroma", "hue", "with_chroma", "with_hue",
    "mix", "is_dark",
]

RGB = tuple[float, float, float]
RGBA = tuple[float, float, float, float]

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


# ── hex in, hex out ─────────────────────────────────────────────────────────
def is_hex(value: str) -> bool:
    """True for ``#abc``, ``#aabbcc`` and ``#aabbccdd``."""
    return bool(_HEX.match(value.strip()))


def parse(value: str) -> RGBA:
    """``#RRGGBB`` or ``#RRGGBBAA`` to four channels in 0..1."""
    if not is_hex(value):
        raise ValueError(f"not a hex colour: {value!r}")
    h = value.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) == 6:
        h += "ff"
    if len(h) != 8:
        raise ValueError(f"not a hex colour: {value!r}")
    try:
        n = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4, 6)]
    except ValueError:
        raise ValueError(f"not a hex colour: {value!r}") from None
    return (n[0], n[1], n[2], n[3])


def to_hex(rgb: RGB | RGBA, alpha: float | None = None) -> str:
    """Back to a hex string, uppercase, with the alpha pair only when it bites."""
    r, g, b = rgb[0], rgb[1], rgb[2]
    a = alpha if alpha is not None else (rgb[3] if len(rgb) == 4 else 1.0)
    out = "#" + "".join(f"{_byte(c):02X}" for c in (r, g, b))
    if a < 1.0:
        out += f"{_byte(a):02X}"
    return out


def alpha_of(value: str) -> float:
    """The alpha of a hex string, 1.0 when it carries none."""
    return parse(value)[3]


def _byte(x: float) -> int:
    return max(0, min(255, int(round(x * 255))))


# ── WCAG ────────────────────────────────────────────────────────────────────
def _to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _to_srgb(c: float) -> float:
    if c <= 0.0031308:
        return c * 12.92
    return 1.055 * (c ** (1 / 2.4)) - 0.055


def luminance(value: str | RGB) -> float:
    """Relative luminance as WCAG 2.2 defines it. Alpha is ignored."""
    r, g, b = _rgb(value)
    return (0.2126 * _to_linear(r) + 0.7152 * _to_linear(g) + 0.0722 * _to_linear(b))


def contrast(fg: str | RGB, bg: str | RGB) -> float:
    """WCAG contrast ratio, 1.0 to 21.0. Order of the two does not matter."""
    a, b = luminance(fg), luminance(bg)
    hi, lo = (a, b) if a > b else (b, a)
    return (hi + 0.05) / (lo + 0.05)


def over(fg: str, bg: str) -> str:
    """``fg`` composited on ``bg``, straight alpha. The result is opaque."""
    fr, fg_, fb, fa = parse(fg)
    br, bg_, bb, _ = parse(bg)
    return to_hex((fr * fa + br * (1 - fa),
                   fg_ * fa + bg_ * (1 - fa),
                   fb * fa + bb * (1 - fa)))


def is_dark(value: str) -> bool:
    """Whether a surface wants light text on it."""
    return luminance(value) < 0.18


# ── OKLab, after Bjorn Ottosson ─────────────────────────────────────────────
def to_oklab(value: str | RGB) -> tuple[float, float, float]:
    r, g, b = (_to_linear(c) for c in _rgb(value))
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = _cbrt(l), _cbrt(m), _cbrt(s)
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def from_oklab(lab: tuple[float, float, float], alpha: float = 1.0) -> str:
    """Back to a hex string. Out of gamut results are clipped per channel."""
    L, a, b = lab
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return to_hex(tuple(min(1.0, max(0.0, _to_srgb(c))) for c in (r, g, bb)), alpha)


def to_oklch(value: str | RGB) -> tuple[float, float, float]:
    """Lightness 0..1, chroma 0..~0.4, hue in degrees 0..360."""
    L, a, b = to_oklab(value)
    return (L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360.0)


def from_oklch(lch: tuple[float, float, float], alpha: float = 1.0) -> str:
    L, C, h = lch
    rad = math.radians(h)
    return from_oklab((L, C * math.cos(rad), C * math.sin(rad)), alpha)


def _cbrt(x: float) -> float:
    return math.copysign(abs(x) ** (1 / 3), x)


# ── the operations palettes are written with ────────────────────────────────
def lightness(value: str) -> float:
    return to_oklch(value)[0]


def chroma(value: str) -> float:
    return to_oklch(value)[1]


def hue(value: str) -> float:
    return to_oklch(value)[2]


def with_lightness(value: str, L: float) -> str:
    """Same hue and chroma at a given OKLab lightness. Alpha survives."""
    _, C, h = to_oklch(value)
    return from_oklch((max(0.0, min(1.0, L)), C, h), alpha_of(value))


def shift_lightness(value: str, delta: float) -> str:
    """Lighter for a positive delta, darker for a negative one."""
    return with_lightness(value, lightness(value) + delta)


def with_chroma(value: str, C: float) -> str:
    L, _, h = to_oklch(value)
    return from_oklch((L, max(0.0, C), h), alpha_of(value))


def with_hue(value: str, h: float) -> str:
    L, C, _ = to_oklch(value)
    return from_oklch((L, C, h % 360.0), alpha_of(value))


def mix(a: str, b: str, t: float) -> str:
    """Blend two colours in OKLab. ``t`` is how much of ``b`` ends up in it."""
    t = max(0.0, min(1.0, t))
    la, lb = to_oklab(a), to_oklab(b)
    aa, ab = alpha_of(a), alpha_of(b)
    return from_oklab(tuple(x + (y - x) * t for x, y in zip(la, lb)),
                      aa + (ab - aa) * t)


def _rgb(value: str | RGB) -> RGB:
    if isinstance(value, str):
        r, g, b, _ = parse(value)
        return (r, g, b)
    return (value[0], value[1], value[2])
