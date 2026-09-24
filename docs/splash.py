"""The picture of the loading screen, which no browser can take.

    .venv\\Scripts\\python docs\\splash.py                 all eight palettes
    .venv\\Scripts\\python docs\\splash.py --palettes gold-dark,gold-light

``docs/capture.py`` opens the gallery in a Qt window and grabs frames out of
it. The splash is not in that window and never will be: it is the WPF half of
the library, it draws on a thread of its own through a ``HostVisual``, and a
``RenderTargetBitmap`` of a window does not contain the drawing of a
``HostVisual`` at all, because that drawing lives somewhere else. A picture of
it taken the ordinary way is a window with a hole where the screen should be.

So this takes two pictures and lays one on the other. The window renders
itself, band and all, and the drawing thread hands over what
it has on screen through ``Snapshot``. Both come back at the same scale and
the two are composited into one frame, which is then cut to the corner radius
Windows cuts a window to, the way ``capture.py`` cuts its own.

Under the screen is the gallery's own window shot with its band cropped off,
put back into a real window as its page, and the screen hides it: while an
application loads, its window is seen empty, which is what the picture has to
show. The page is there so that the picture is of a real window and not of a
screen laid over nothing.

The output lands in ``docs/shots/<palette>/splash.png``, next to everything
``capture.py`` writes, and ``docs/publish.py`` carries it into ``docs/img``
from there like any other picture a page shows.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from slantui.tokens import PALETTES                      # noqa: E402
from slantui.tokens.metrics import px                    # noqa: E402
from slantui.wpf import MODULE, install                  # noqa: E402

SHOTS = HERE / "shots"

# The same window the gallery is shot in, so a picture of the loading screen
# drops into the same page beside a picture of the loaded one.
WINDOW = (1240, 800)
SCALE = 4.0
CORNER = 8

# The library's own mark, which is the one the gallery's band wears. It is
# written out as an SVG and read back by the library's reader, so the brand in
# the middle of the ring is drawn at the size the ring gives it.
MARK = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <path d="M2 5.8h20v5.6h-6.1L9.6 18.2H2z" fill="{accent}"/>
</svg>
"""

# Where the arc is put for the picture. Far enough along to be a measure and
# not so far that the ring reads as finished.
STEP = 0.62
LINE = "reading the folders"

_SHOT = r"""
param([string]$Module, [string]$Palette, [string]$Page, [string]$Logo,
      [string]$Out, [double]$Scale, [double]$Band, [double]$Corner,
      [double]$Step, [string]$Line, [double]$W, [double]$H)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase
Import-Module $Module -Force

# The page under the veil: the gallery's window shot with its band cropped
# off, because the window this builds draws a band of its own and two of them
# is one too many.
$src = New-Object System.Windows.Media.Imaging.BitmapImage
$src.BeginInit()
$src.UriSource = New-Object Uri($Page)
$src.CacheOption = 'OnLoad'
$src.EndInit()
$src.Freeze()
$giu = [int][math]::Round($Band * ($src.PixelWidth / $W))
$corpo = New-Object System.Windows.Media.Imaging.CroppedBitmap($src,
    (New-Object System.Windows.Int32Rect(0, $giu, $src.PixelWidth, ($src.PixelHeight - $giu))))
$corpo.Freeze()
$pagina = New-Object System.Windows.Controls.Image
$pagina.Source = $corpo
$pagina.Stretch = 'Fill'

$fin = New-Object System.Windows.Window
$fin.WindowStartupLocation = 'Manual'
$fin.Left = -20000; $fin.Top = -20000
$fin.Width = $W; $fin.Height = $H
$fin.ShowInTaskbar = $false
$fin.ShowActivated = $false
$fin.Content = $pagina

$chrome = Install-SlantWindow -Window $fin -Bold 'SlantUI' -Name '  Gallery' `
    -Palette $Palette -Logo $Logo

# What the run has to say goes in here and is printed after the dialog, not
# from inside the tick: the output of a scriptblock run as an event handler
# goes to the event's own stream and reaches nobody.
$esito = @{ Said = "" }

$fin.add_ContentRendered({
    # The screen goes up once the window has a size, so the ring starts in the
    # middle instead of being seen walking there, and the arc then walks to the
    # step it was given: the picture waits for it to arrive instead of guessing
    # how long that takes.
    $splash = Show-SlantSplash -Chrome $chrome -Logo $Logo -Text $Line
    $splash.SetProgress($Step, $Line)

    # These are for the tick's closure, which is born inside this one and sees
    # only the LOCAL variables of this block. Without copying them the wait
    # below reads nulls, fires on its first beat, and the picture is of
    # whatever the arc happened to be on. It is the trip every nested handler
    # in this library takes once.
    $laFinestra = $fin
    $loSplash = $splash
    $ilPasso = $Step
    $laScala = $Scale
    $laBanda = $Band
    $ilRaggio = $Corner
    $laLarghezza = $W
    $lAltezza = $H
    $ilFondo = New-SlantBrush (Get-SlantColor 'surface-0' $Palette)
    $ilFile = $Out
    $ilEsito = $esito

    $attesa = @{ N = 0 }
    $t = New-Object System.Windows.Threading.DispatcherTimer
    $t.Interval = [TimeSpan]::FromMilliseconds(40)
    $t.add_Tick({
        param($s, $e)
        $attesa.N++
        if ($loSplash.Core.Drawn -lt $ilPasso -and $attesa.N -lt 150) { return }
        $s.Stop()
        try {
            # The drawing thread's own frame first, and quickly: the window
            # render below takes a moment, and the arc goes on drifting while
            # it does, so the two halves would be of two different instants.
            $sopra = $loSplash.Snapshot($laScala)
            $dove = $loSplash.Core.Drawn
            $laFinestra.UpdateLayout()
            $px = [int][math]::Round($laLarghezza * $laScala)
            $py = [int][math]::Round($lAltezza * $laScala)
            # the window: band, page, blur, everything it draws itself
            $sotto = New-Object System.Windows.Media.Imaging.RenderTargetBitmap(
                $px, $py, (96 * $laScala), (96 * $laScala),
                [System.Windows.Media.PixelFormats]::Pbgra32)
            $sotto.Render($laFinestra.Content)

            $vis = New-Object System.Windows.Media.DrawingVisual
            $dc = $vis.RenderOpen()
            $tutto = New-Object System.Windows.Rect(0, 0, $laLarghezza, $lAltezza)
            $dc.PushClip((New-Object System.Windows.Media.RectangleGeometry(
                $tutto, $ilRaggio, $ilRaggio)))
            $dc.DrawRectangle($ilFondo, $null, $tutto)
            $dc.DrawImage($sotto, $tutto)
            if ($null -ne $sopra) {
                $dc.DrawImage($sopra, (New-Object System.Windows.Rect(
                    0, $laBanda, $laLarghezza, ($lAltezza - $laBanda))))
            }
            $dc.Pop()
            $dc.Close()
            $fuori = New-Object System.Windows.Media.Imaging.RenderTargetBitmap(
                $px, $py, (96 * $laScala), (96 * $laScala),
                [System.Windows.Media.PixelFormats]::Pbgra32)
            $fuori.Render($vis)

            $enc = New-Object System.Windows.Media.Imaging.PngBitmapEncoder
            [void]$enc.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($fuori))
            $fs = [System.IO.File]::Create($ilFile)
            try { $enc.Save($fs) } finally { $fs.Dispose() }
            $ilEsito.Said = ("{0}x{1} at {2:P0}" -f $fuori.PixelWidth, $fuori.PixelHeight, $dove)
        } catch {
            $ilEsito.Said = "ERROR $($_.Exception.Message) @ $($_.InvocationInfo.ScriptLineNumber)"
        }
        $laFinestra.Close()
    }.GetNewClosure())
    $t.Start()
}.GetNewClosure())

[void]$fin.ShowDialog()
if (-not $esito.Said) { $esito.Said = "ERROR the window closed without drawing" }
Write-Output $esito.Said
"""


def shoot(palette: str, work: Path, module: Path) -> str:
    """One palette, one picture. Returns the size it came out at."""
    page = SHOTS / palette / "window.png"
    if not page.is_file():
        raise SystemExit(
            f"{page} is not there. The loading screen is shot over the window "
            f"shot, so run  .venv\\Scripts\\python docs\\capture.py  first.")
    accent = PALETTES[palette].get("accent")
    mark = work / f"mark-{palette}.svg"
    mark.write_text(MARK.format(accent=accent), encoding="utf-8")
    out = SHOTS / palette / "splash.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    script = work / "splash.ps1"
    script.write_text(_SHOT, encoding="utf-8")
    run = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-STA", "-ExecutionPolicy",
         "Bypass", "-File", str(script),
         "-Module", str(module), "-Palette", palette, "-Page", str(page),
         "-Logo", str(mark), "-Out", str(out), "-Scale", str(SCALE),
         "-Band", str(px("tbar-h")), "-Corner", str(CORNER), "-Step", str(STEP),
         "-Line", LINE, "-W", str(WINDOW[0]), "-H", str(WINDOW[1])],
        capture_output=True, text=True)
    said = run.stdout.strip().splitlines()
    last = said[-1] if said else ""
    if run.returncode != 0 or not last or last.startswith("ERROR"):
        raise SystemExit(f"{palette}: the shot failed\n{run.stdout}\n{run.stderr}")
    return last


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Write docs/shots/<palette>/splash.png, the loading screen.")
    p.add_argument("--palettes", default="",
                   help="comma separated slugs; all of them otherwise")
    args = p.parse_args(argv)

    if sys.platform != "win32" or not shutil.which("powershell"):
        raise SystemExit("the splash is WPF, so this needs Windows PowerShell.")

    slugs = [s.strip() for s in args.palettes.split(",") if s.strip()] or list(PALETTES)
    unknown = [s for s in slugs if s not in PALETTES]
    if unknown:
        raise SystemExit(f"no palette called {', '.join(unknown)}. "
                         f"Known: {', '.join(PALETTES)}")

    with tempfile.TemporaryDirectory(prefix="slantsplash-") as tmp:
        work = Path(tmp)
        install(work)
        for slug in slugs:
            size = shoot(slug, work, work / MODULE)
            print(f"{slug:<14} {size}  docs/shots/{slug}/splash.png")
    print(f"{len(slugs)} loading screens. Run docs\\publish.py to carry them over.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
