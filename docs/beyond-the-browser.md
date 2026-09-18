# The design outside a browser

SlantUI draws its windows with a page inside a Qt shell, and while everything
that wears the design is one of those, that is the whole story. It stops being
the whole story the moment the same look is wanted in WPF: an installer that
draws the oblique band by hand, a window that carries twenty one of these
colours as hex literals in a PowerShell function.

Copying a palette is how a palette goes wrong, and it goes wrong in the way
you would expect. Three of those twenty one values were the ones the contrast
auditor later corrected, so two windows built from one palette had stopped
agreeing with each other before anyone noticed. That is the argument for this
page in one sentence.

So the design leaves the browser as one more output of the Python that
already writes the CSS. The palettes, the metrics and the band's profile have
one source each, and every target below is generated from it.

```
python -m slantui.tokens json                 the whole design as data
python -m slantui.tokens xaml gold-dark       a WPF ResourceDictionary
python -m slantui.tokens ps1                  a PowerShell data file
python -m slantui.tokens uss                  Unity's UI Toolkit
python -m slantui.tokens band 1280 210        the band, as a path
```

None of it needs anything installed. `slantui.tokens` has no dependencies on
purpose, and the export layer is held to the same promise by a test.

## What travels, and what does not

| | Web | WPF | Unity | Anything else |
|---|---|---|---|---|
| The thirty one roles | yes | yes | yes | yes, through `json` |
| The metrics | yes | yes | lengths only | yes |
| The band's profile | yes | yes | the numbers | the numbers, and the recipe below |
| The window's behaviour | yes | yes | no | no |
| The widget set | yes | the window buttons | no | no |

The colours, the shapes and the window travel. The widget set does not, and
pretending otherwise would be the wrong promise: a WPF button is a
ControlTemplate and a Unity button is a UXML element, and neither is a CSS
rule with another syntax. What a toolkit gets is the vocabulary to draw its
own widgets so they look like the others.

The window is the exception, and it earned it. The frameless window, the
band, the buttons, the resize edges and a maximise that never zooms are the
same behaviour on both sides, and it is behaviour and not markup: an
application that wrote it again would be writing the same eight Win32
messages a second time and getting one of them wrong.

## The band

The band is the one part of the design that is a drawing. It runs the whole
width of the window, thick under the application's name, thinning over a
straight oblique, then thin to the right edge where the window buttons sit.
It never breaks. It only gets thinner.

```
0                        x1        x2                          W
+------------------------------------------------------------+  0
|                          \                                  |
|                            \_____________________________   |  --tbar-thin
|                                                            |
+--------------------------+                                 |  --tbar-h
  thick, under the name      the oblique   thin, under the buttons
```

Four numbers, all in `slantui/tokens/metrics.py`:

| Metric | Default | What |
|---|---|---|
| `tbar-h` | 44px | the thick end, on the left |
| `tbar-thin` | 28px | the thin end, on the right |
| `tbar-slant` | 38px | the horizontal run of the oblique |
| `tbar-join` | 8px | the radius the oblique's two vertices are rounded by |

`x1` is where the application's name ends and is measured from the laid out
page, never guessed: the whole point of the shape is that it gets out of the
way of the name. `x2` is `x1 + tbar-slant`, clamped to the window's width, so
a window too narrow to fit the run still has a band.

The six vertices, clockwise from the window's top left corner, are
`(0, 0)`, `(W, 0)`, `(W, thin)`, `(x2, thin)`, `(x1, height)`, `(0, height)`,
and the two in the middle carry the radius. Rounding a corner means replacing
the vertex with a quadratic whose control point is the vertex itself, entered
and left at `min(r, side / 2)` along each side. Trimming to half the side is
what stops two corners on a short edge from each eating all of it.

That is the whole recipe. In Python:

```python
from slantui.geometry import band_path, band_shape

band_path(width=1280, brand_width=210)
band_path(width=1280, brand_width=210, shape=band_shape(height=60))
```

The output is the SVG path mini language, which the page hands to
`clip-path: path()` and WPF hands to `Geometry.Parse` with nothing changed on
the way. There are three implementations of it, in Python, in JavaScript and
in PowerShell, and `tests/test_geometry.py` and `tests/test_wpf.py` run all
three on the same seven windows and compare the strings. They have to agree
character for character, down to the two decimal places.

The two decimal places are worth a warning if you write a fourth. Format the
coordinates the way a browser's `toFixed(2)` does, which is the closest two
place number to the value the double actually holds, with a tie going away
from zero. Multiplying by a hundred and rounding is not that: `2.675` is
really `2.67499999999999982`, the product rounds up to exactly `267.5` on the
way, and the answer comes out a hundredth too high. And format it in the
invariant culture. On a machine set to Italian the obvious call writes
`2,67`, and a path with a comma in it is a different shape or is not a path.

## WPF

Two files ship inside the package. Copy them next to the application, or let
the build step do it:

```python
from slantui.wpf import install
install(r"C:\MyApp\vendor")        # SlantUI.psm1 and SlantUI.Tokens.psd1
```

`SlantUI.Tokens.psd1` is generated and holds every palette, every metric and
the band's four numbers. `SlantUI.psm1` is the module that reads it, and it
is the one file in the repository written by hand in PowerShell.

```powershell
Import-Module .\SlantUI.psm1

$b = Get-SlantBrushes                      # the default palette, as brushes
$window.Background = $b['surface-0']
$header.Background = $b['surface-1']
$label.Foreground  = $b['text-2']
$card.CornerRadius = Get-SlantMetric 'r-md'

# the band, across a title bar 1040 wide whose name ends at 210
$path.Data = Get-SlantBandGeometry -Width 1040 -BrandWidth 210
```

| Function | What it gives back |
|---|---|
| `Get-SlantTokens` | the whole data file, read once and kept |
| `Get-SlantPaletteNames` | the eight slugs |
| `Get-SlantPalette [slug]` | one palette: `Values` in CSS hex, `Wpf` with the alpha moved |
| `Get-SlantColor role [slug]` | one role, as `#AARRGGBB` |
| `Get-SlantMetric name` | one length as a number, or a font as a family list |
| `New-SlantBrush hex` | a frozen `SolidColorBrush`, from either hex order |
| `Get-SlantBrushes [slug]` | all thirty one roles as frozen brushes, by role name |
| `ConvertTo-SlantColorRef hex` | the same colour as the integer the DWM wants |
| `Get-SlantBandPath` | the profile as a path string |
| `Get-SlantBandGeometry` | the same, as a frozen WPF `Geometry` |

The module has a second half, below, that opens the window itself.

WPF is loaded by the calls that draw and by nothing else, so the palette and
the metrics are readable in a PowerShell with no display.

`ConvertTo-SlantColorRef` is there for the one place an application hands
Windows a colour by number instead of by name: `DwmSetWindowAttribute` with
`CAPTION_COLOR`, `TEXT_COLOR` or `BORDER_COLOR`, which takes a COLORREF with
the channels the other way round. Getting the order wrong paints the caption
in the complement of what was meant, which reads as a broken window and not
as a typo.

This is the shape for a window that opens before there is a Python on the
machine, which is what an installer does, and for a WPF window written in
PowerShell, which cannot read a stylesheet at all.

### The whole window

Everything above draws with the design. A WPF window can wear it instead, and
then it is the same window the Qt shell opens: no Windows frame, the oblique
band as the title bar, the buttons, the eight resize edges, and a maximise
that puts the window on the work area without ever letting Windows zoom it.

```powershell
$chrome = Install-SlantWindow -Window $window -Bold 'My' -Name ' App' -Logo $iconPath
$chrome.SetStatus('ready')
$chrome.OnMaximized = { param($on) Save-Setting 'maximised' $on }
```

It takes a window the application has already built and put its own layout
in. What was inside moves down one row and is not touched, so an application
keeps its arrangement and its icon and gains a title bar.

| On `$chrome` | What it is |
|---|---|
| `Element` `Band` `Brand` `Logo` `Name` `Credit` | the parts of the bar |
| `Extras` | a slot for the application's own line or small control, next to the buttons |
| `Buttons` | `min`, `max` and `close`, by name |
| `SetName(bold, name)` `SetStatus(text)` | change what the bar says |
| `Maximize()` `Restore()` `ToggleMaximize()` `Minimize()` `Close()` | the state changes |
| `IsMaximized()` `NormalBounds()` | what to write down when the window closes |
| `OnMaximized` | a scriptblock called with true or false |
| `StateMs` | how long a state change takes. Zero for none |

`NormalBounds()` is the one worth knowing about. It answers with the
rectangle a restore would use, whatever state the window is in, so an
application that remembers where its window was writes that and the
maximised flag and nothing else.

Three things inside are not obvious, and each is a day someone else does not
have to spend.

**The frame is real and is never laid out.** Windows only animates a window
that carries `WS_CAPTION` and `WS_THICKFRAME` when it minimises, restores
and closes, and only such a window gets a shadow. So the window is given
those styles and then answers `WM_NCCALCSIZE` with "the client area is the
whole window", which takes the caption and the borders back out. It is the
technique the browsers use.

**The window never zooms.** A window carrying those styles is placed by
Windows with its frame past the edge of the screen when it zooms, eleven
pixels a side at 150 per cent, and it stays there. For a window whose client
area is the whole window that is eleven pixels of the page cut off on every
side. So maximised is a state the object keeps: the window animates onto the
work area and remembers that it did, `Win+Up` and `Win+Down` and the taskbar
menu arrive as system commands and are answered there, and a zoom Windows
manages anyway is undone the moment WPF reports it. `Test-SlantWindowZoomed`
is the check that says this still holds, and it belongs in an application's
own tests.

**The window procedure is compiled.** A scriptblock handed to a delegate is
given a copy of anything passed by reference, so the `handled` flag an
`HwndSource` hook sets never reaches the caller and the frame stays. The
procedure is C# inside the module for that reason, and the one thing it
hands back to PowerShell is the system command, which needs no reference
parameter.

The credit line the licence asks for is written by the module, not by the
application, and there is no switch for it. That is condition 2 of `LICENSE`
doing what it says.

| Function | What it does |
|---|---|
| `Install-SlantWindow` | all of the above, on a window |
| `New-SlantTitleBar` | the bar on its own, for a window that wants to place it itself |
| `Set-SlantWindowFrame` | the styles and the subclass, on a bare handle |
| `Set-SlantWindowScheme` | tells Windows the palette is dark or light |
| `Set-SlantWindowTransitions` | the system's own state animation, on or off |
| `Get-SlantWorkArea` | the work area of the window's screen, in the units WPF lays out in |
| `Get-SlantWindowStyle` `Get-SlantWindowSizes` | what a test wants to read |
| `Test-SlantWindowZoomed` | false, always, and a test should say so |
| `Get-SlantCreditText` | the line the licence puts in the bar |


The alternative to the module is the ResourceDictionary, for an application
whose look lives in XAML:

```
python -m slantui.tokens xaml gold-dark -o Palette.xaml
```

```xml
<Border Background="{StaticResource SlantSurface1}"
        CornerRadius="{StaticResource SlantRMdCorner}">
  <TextBlock Foreground="{StaticResource SlantText2}"
             FontFamily="{StaticResource SlantFont}"
             FontSize="{StaticResource SlantFs}"/>
</Border>
```

Three things differ from the CSS and each one has a reason. The keys carry a
`Slant` prefix, because a ResourceDictionary is merged into an application
SlantUI does not own, which is the opposite of the page it does. Each role is
both a brush and a Color, since a Background wants the first and an animation
wants the second. And the alpha moves: CSS writes `#RRGGBBAA`, WPF writes
`#AARRGGBB`, and the three roles that carry one are rewritten on the way out.
One ResourceDictionary holds one palette, because a resource is keyed once.

## Unity

Unity's UI Toolkit styles with USS, which is a subset of CSS with custom
properties in it, so the token layer crosses over almost unchanged. A role is
a custom property, a component reads it with `var()`, and the palette switch
survives: USS has no attribute selector, so where the page keys a palette on
`data-palette` a Unity project keys it on a class.

```
python -m slantui.tokens uss -o Assets/UI/slantui.uss
```

```csharp
root.AddToClassList("slant-high-contrast");
```

The fonts are left out. USS wants a font asset through `resource()` or
`url()`, and a family name means nothing to it, so a property carrying one
would silently do nothing. The names the design uses are in the metrics:
`font`, `font-brand` and `mono`.

This target has not been opened in a Unity project. The syntax is USS and the
values are the same ones every other target gets, and that is as far as the
claim goes until someone builds with it.

## Anything else

`python -m slantui.tokens json` writes the vocabulary, not just the values:
every role with the job it does, every metric with what it measures, every
palette with its scheme, and the band. The same document ships inside the
package at `slantui/design.json`, so a reader on GitHub sees it without
running anything.

```json
{
  "slantui": "0.1.0",
  "default": "gold-dark",
  "roles":    [ {"name": "surface-0", "group": "surface", "purpose": "..."} ],
  "metrics":  [ {"name": "tbar-h", "group": "band", "value": "44px"} ],
  "band":     {"height": 44, "thin": 28, "slant": 38, "join": 8,
               "drop": 16, "angle": 22.8337},
  "palettes": {"gold-dark": {"scheme": "dark", "values": {"surface-0": "#0D0D0F"}}}
}
```

With that and the recipe for the band above, the look can be built in a
toolkit this library has never heard of. What it cannot give you is the two
rules that make it look right, and they are worth more than the hex values:
every surface is a fill and nothing is outlined, and nothing is divided by a
line. A panel header, its body and its footer are told apart by being three
shades of the same near black. That is the design. The colours are how it is
spelled.
