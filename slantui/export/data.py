"""The whole design as one JSON document.

This is the target for a toolkit nobody has written an exporter for. It
carries the vocabulary, not just the values: every role with the job it does,
every metric with what it measures, every palette with its scheme, and the
band's four numbers with the angle they make. Someone building the look in a
toolkit this library has never heard of reads this file and the page that
describes the band, and needs nothing else from the repository.

The shape is stable and is part of what the library promises:

    {
      "slantui": "0.1.0",
      "default": "gold-dark",
      "roles":    [ {name, group, purpose, extended, alpha}, ... ],
      "metrics":  [ {name, group, value, purpose, kind}, ... ],
      "band":     {height, thin, slant, join, drop, angle},
      "palettes": { slug: {name, scheme, note, values: {role: hex}}, ... }
    }

Colours are CSS hex, so the three that carry an alpha are eight digits with
the alpha last. A target whose colours put the alpha first converts on the
way in; ``slantui.export.xaml.wpf_hex`` is the one that does.
"""
from __future__ import annotations

import json

from .. import __version__
from ..geometry import band_shape
from ..tokens.metrics import METRICS
from ..tokens.palette import Palette
from ..tokens.palettes import DEFAULT, PALETTES
from ..tokens.roles import ROLES

__all__ = ["design", "as_json"]


def design(palettes: list[Palette] | None = None,
           default_slug: str | None = None) -> dict:
    """The design as plain Python, ready for ``json.dumps`` or for a caller."""
    chosen = list(palettes if palettes is not None else PALETTES.values())
    band = band_shape()
    return {
        "slantui": __version__,
        "default": default_slug or DEFAULT.slug,
        "roles": [
            {"name": r.name, "group": r.group, "purpose": r.purpose,
             "extended": r.extended, "alpha": r.alpha}
            for r in ROLES
        ],
        "metrics": [
            {"name": m.name, "group": m.group, "value": m.value,
             "purpose": m.purpose, "kind": m.kind}
            for m in METRICS
        ],
        "band": {
            "height": band.height, "thin": band.thin, "slant": band.slant,
            "join": band.join, "drop": band.drop, "angle": round(band.angle, 4),
        },
        "palettes": {
            p.slug: {"name": p.name, "scheme": p.scheme, "note": p.note,
                     "values": dict(p.values)}
            for p in chosen
        },
    }


def as_json(palettes: list[Palette] | None = None,
            default_slug: str | None = None) -> str:
    """``design`` as text, indented, with a newline at the end."""
    return json.dumps(design(palettes, default_slug), indent=2,
                      ensure_ascii=False) + "\n"
