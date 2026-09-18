"""Command line access to the token system.

    python -m slantui.tokens audit                 every palette, every pair
    python -m slantui.tokens audit gold-dark -v    one palette, passes included
    python -m slantui.tokens css                   all eight, switchable
    python -m slantui.tokens css gold-dark         one :root block
    python -m slantui.tokens css -o PATH           the same, written to a file
    python -m slantui.tokens metrics -o PATH       the lengths and the fonts
    python -m slantui.tokens roles                 the vocabulary and the tiers
    python -m slantui.tokens list                  the slugs

And, for a toolkit that is not a browser:

    python -m slantui.tokens json                  the whole design as data
    python -m slantui.tokens xaml gold-dark        a WPF ResourceDictionary
    python -m slantui.tokens ps1                   a PowerShell data file
    python -m slantui.tokens uss                   Unity's UI Toolkit
    python -m slantui.tokens band 1280 210         the band's profile, as a path

The two files that ship are written by this, and a test fails while either is
behind the Python:

    python -m slantui.tokens css -o slantui/css/palettes.css
    python -m slantui.tokens metrics -o slantui/css/metrics.css

The exit code of `audit` is 1 when anything falls short, so it can stand in a
hook or a CI step on its own.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..export import TARGETS, render as render_target
from ..geometry import band_path, band_shape
from .contrast import alpha_problems, audit, report
from .css import metrics_stylesheet, render, stylesheet
from .metrics import METRICS
from .palettes import DEFAULT, PALETTES
from .roles import MIN_RATIO, ROLES, TIERS, tier_of

# The targets that key a resource once, so a file holds one palette.
ONE_PALETTE = ("xaml",)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m slantui.tokens",
                                 description="SlantUI design tokens.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("audit", help="measure every text role on every surface")
    a.add_argument("palette", nargs="?", help="a slug, or all of them")
    a.add_argument("-v", "--verbose", action="store_true",
                   help="print the pairs that pass as well")

    c = sub.add_parser("css", help="print a palette as a :root block")
    c.add_argument("palette", nargs="?", help="a slug, or all of them")
    _out(c, "slantui/css/palettes.css")

    m = sub.add_parser("metrics", help="print the lengths and the fonts as CSS")
    _out(m, "slantui/css/metrics.css")

    for name in TARGETS:
        t = sub.add_parser(name, help=_TARGET_HELP[name])
        if name in ONE_PALETTE:
            t.add_argument("palette", nargs="?",
                           help=f"a slug. One palette per file, {DEFAULT.slug} "
                                f"by default")
        else:
            t.add_argument("palette", nargs="?", help="a slug, or all of them")
        _out(t, None)

    b = sub.add_parser("band", help="the title band's profile, as a path")
    b.add_argument("width", nargs="?", type=float, default=1280.0,
                   help="the window's width in pixels")
    b.add_argument("brand", nargs="?", type=float, default=210.0,
                   help="where the application's name ends")

    sub.add_parser("roles", help="print the role vocabulary and the thresholds")
    sub.add_parser("list", help="print the palette slugs")

    args = ap.parse_args(argv)

    if args.cmd == "list":
        for p in PALETTES.values():
            mark = " (default)" if p is DEFAULT else ""
            print(f"{p.slug:<15} {p.scheme:<6} {p.name}{mark}")
        return 0

    if args.cmd == "roles":
        return _print_roles()

    if args.cmd == "metrics":
        return _emit(metrics_stylesheet(), getattr(args, "out", None))

    if args.cmd == "band":
        s = band_shape()
        print(f"height {s.height:g}  thin {s.thin:g}  slant {s.slant:g}  "
              f"join {s.join:g}  drop {s.drop:g}  angle {s.angle:.4f} degrees")
        print(band_path(args.width, args.brand))
        return 0

    chosen = _pick(args.palette)
    if chosen is None:
        return 2

    if args.cmd == "css":
        text = render(chosen[0]) if args.palette else stylesheet(chosen, DEFAULT.slug)
        return _emit(text, args.out)

    if args.cmd in TARGETS:
        if args.cmd in ONE_PALETTE and not args.palette:
            chosen = [DEFAULT]
        return _emit(render_target(args.cmd, chosen, DEFAULT.slug), args.out)

    print(report(chosen, verbose=args.verbose))
    bad = sum(len([c for c in audit(p) if not c.passed]) + len(alpha_problems(p))
              for p in chosen)
    return 1 if bad else 0


_TARGET_HELP = {
    "json": "print the whole design as data: roles, metrics, band, palettes",
    "xaml": "print a WPF ResourceDictionary of brushes and metrics",
    "ps1": "print a PowerShell data file of every palette",
    "uss": "print Unity UI Toolkit style sheets",
}


def _out(parser: argparse.ArgumentParser, ships_as: str | None) -> None:
    note = f". The file that ships is {ships_as}" if ships_as else ""
    parser.add_argument("-o", "--out", metavar="PATH",
                        help=f"write to this file instead of stdout{note}")


def _emit(text: str, out: str | None) -> int:
    if out:
        # newline="\n" on purpose: the file is tracked, and a shell
        # redirect on Windows would have written \r\n or UTF-16.
        Path(out).write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {out}")
    else:
        sys.stdout.write(text)
    return 0


def _print_roles() -> int:
    group = None
    for r in ROLES:
        if r.group != group:
            group = r.group
            print(f"\n[{group}]")
        tag = "extended" if r.extended else "core"
        try:
            tier = f"  >= {MIN_RATIO[tier_of(r.name)]:.1f}:1"
        except KeyError:
            tier = ""
        print(f"  {r.name:<22} {tag:<9}{tier}")
        print(f"  {'':<22} {r.purpose}")
    print()
    for name, why in TIERS.items():
        print(f"{name:<8} {MIN_RATIO[name]:.1f}:1   {why}")
    group = None
    for m in METRICS:
        if m.group != group:
            group = m.group
            print(f"\n[{group}]")
        print(f"  --{m.name:<20} {m.value}")
        print(f"  {'':<22} {m.purpose}")
    return 0


def _pick(slug: str | None):
    if slug is None:
        return list(PALETTES.values())
    if slug not in PALETTES:
        print(f"no palette called {slug!r}. Known: {', '.join(PALETTES)}",
              file=sys.stderr)
        return None
    return [PALETTES[slug]]


if __name__ == "__main__":
    raise SystemExit(main())
