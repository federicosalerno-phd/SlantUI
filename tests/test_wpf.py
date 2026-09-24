"""The PowerShell module, run by PowerShell.

Two of his applications are WPF windows written in PowerShell, so the module
in ``slantui/wpf`` is the face the library shows them. It holds the only
second implementation of anything in this repository: the band's profile,
written again in PowerShell because a window being built cannot call Python.

Phase 2 took the same trade for ``theme.js`` against ``color.py`` and paid
for it the same way, with a test that runs both and compares them. This is
that test. It needs Windows PowerShell, which is where these applications
run, and skips anywhere else.

The rounding is worth one line of warning to whoever edits either side. The
machine this was written on formats a number as ``2,67``, so every number
the module writes goes through InvariantCulture. A path with a comma in it
parses as a different shape, or as none.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from slantui.export.xaml import wpf_hex
from slantui.geometry import band_path, band_shape
from slantui.tokens import DEFAULT, PALETTES
from slantui.tokens.metrics import LENGTHS, px
from slantui.wpf import DATA, FILES, MODULE, install, path

ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(
    os.name != "nt" or not shutil.which("powershell"),
    reason="the module is for WPF, which is Windows PowerShell")

# The same spread as tests/test_geometry.py, so the three implementations are
# compared on one set of windows and not on three.
CASES = ((1280, 210), (1024, 187.4), (2480, 333.333), (640, 620), (300, 296),
         (1440, 0), (900, 12.5))

_PROBE = r"""
$ErrorActionPreference = 'Stop'
Import-Module '{module}' -Force
$out = [ordered]@{{}}
$out.Default   = (Get-SlantTokens).Default
$out.Palettes  = @(Get-SlantPaletteNames)
$out.Roles     = @((Get-SlantTokens).Roles)
$out.Colors    = @{{}}
foreach ($r in (Get-SlantTokens).Roles) {{ $out.Colors[$r] = Get-SlantColor $r }}
$out.Metrics   = @{{}}
foreach ($m in @({lengths})) {{ $out.Metrics[$m] = Get-SlantMetric $m }}
$out.Bands     = @()
foreach ($c in @({cases})) {{
    $out.Bands += Get-SlantBandPath -Width $c[0] -BrandWidth $c[1]
}}
$out.Cornered  = @()
foreach ($c in @({cases})) {{
    $out.Cornered += Get-SlantBandPath -Width $c[0] -BrandWidth $c[1] -Corner 22
}}
$out.Tall = Get-SlantBandPath -Width 1000 -BrandWidth 200 -Height 60
$out.Refs = @{{}}
foreach ($r in @('surface-0', 'accent', 'text-2', 'scrim')) {{
    $out.Refs[$r] = ConvertTo-SlantColorRef (Get-SlantColor $r)
}}
$out | ConvertTo-Json -Depth 6 -Compress
"""


@pytest.fixture(scope="module")
def probe(tmp_path_factory) -> dict:
    """One PowerShell run, everything read out of it. Starting the shell
    costs more than every check in this file put together."""
    folder = tmp_path_factory.mktemp("slantwpf")
    install(folder)
    lengths = ",".join(f"'{n}'" for n in LENGTHS)
    cases = ",".join(f"@({w},{b})" for w, b in CASES)
    script = folder / "probe.ps1"
    script.write_text(
        _PROBE.format(module=(folder / MODULE).as_posix(), lengths=lengths,
                      cases=cases),
        encoding="utf-8")
    run = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
         "Bypass", "-File", str(script)],
        capture_output=True, text=True)
    if run.returncode != 0:
        pytest.fail(f"the module did not load:\n{run.stdout}\n{run.stderr}")
    return json.loads(run.stdout)


# ── the files ───────────────────────────────────────────────────────────────
def test_both_files_are_in_the_package():
    for name in FILES:
        assert path(name).is_file(), name


def test_install_puts_both_of_them_somewhere(tmp_path):
    landed = install(tmp_path / "vendor")
    assert sorted(p.name for p in landed) == sorted(FILES)
    assert all(p.is_file() for p in landed)


def test_the_module_documents_what_it_exports():
    text = path(MODULE).read_text(encoding="utf-8")
    exported = text.split("Export-ModuleMember -Function", 1)[1]
    for name in ("Get-SlantPalette", "Get-SlantBrushes", "Get-SlantBandPath",
                 "Get-SlantBandGeometry", "Get-SlantMetric"):
        assert name in exported, name
        assert f"function {name} " in text or f"function {name}(" in text, name


def test_the_module_never_formats_a_number_without_a_culture():
    """An Italian machine writes 2,67. A path with a comma in it is a
    different shape, or is not a path at all."""
    text = path(MODULE).read_text(encoding="utf-8")
    body = text.split("function Format-SlantCoord", 1)[1].split("\nfunction ", 1)[0]
    assert body.count("$inv") >= 3


# ── the data, read by PowerShell ────────────────────────────────────────────
def test_the_data_file_parses(probe):
    assert probe["Default"] == DEFAULT.slug
    assert sorted(probe["Palettes"]) == sorted(PALETTES)


def test_powershell_reads_every_role(probe):
    assert sorted(probe["Roles"]) == sorted(PALETTES[DEFAULT.slug].values)


def test_every_colour_comes_back_in_the_wpf_form(probe):
    for role, value in PALETTES[DEFAULT.slug].values.items():
        assert probe["Colors"][role] == wpf_hex(value), role


def test_every_length_comes_back_as_a_number(probe):
    for name in LENGTHS:
        assert float(probe["Metrics"][name]) == px(name), name


# ── the band, drawn by PowerShell ───────────────────────────────────────────
@pytest.mark.parametrize("i,case", list(enumerate(CASES)), ids=[f"{w}x{b}" for w, b in CASES])
def test_powershell_draws_the_same_band(probe, i, case):
    """The cases go over by position. Naming them by the number would put
    the number through PowerShell's own formatting, and on this machine that
    writes 187,4."""
    assert probe["Bands"][i] == band_path(*case), (
        "slantui/wpf/SlantUI.psm1 and slantui/geometry.py no longer draw the "
        "same band")


@pytest.mark.parametrize("i,case", list(enumerate(CASES)), ids=[f"{w}x{b}" for w, b in CASES])
def test_powershell_cuts_the_same_corner(probe, i, case):
    """The window's corner, an arc round the mark, is the same arc here."""
    assert probe["Cornered"][i] == band_path(*case, corner=22), (
        "slantui/wpf/SlantUI.psm1 and slantui/geometry.py no longer cut the "
        "same corner")


def test_powershell_takes_a_band_of_another_height(probe):
    assert probe["Tall"] == band_path(1000, 200, band_shape(height=60))


@pytest.mark.parametrize("role", ["surface-0", "accent", "text-2", "scrim"])
def test_a_colour_as_the_dwm_wants_it(probe, role):
    """Windows takes a colour by number for the caption, the caption's text
    and the border, and it puts the channels the other way round. Getting
    that wrong paints the caption in the complement of what was meant, which
    reads as a broken window and not as a typo."""
    h = PALETTES[DEFAULT.slug][role].lstrip("#")
    if len(h) == 8:
        h = h[:6]                      # the alpha has no place in a COLORREF
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    assert probe["Refs"][role] == (b << 16) | (g << 8) | r


def test_the_data_file_is_the_one_the_python_writes():
    from slantui.export import as_powershell
    assert path(DATA).read_text(encoding="utf-8") == as_powershell()


# ── the window half ─────────────────────────────────────────────────────────
WINDOW_EXPORTS = (
    "Initialize-SlantChrome", "Get-SlantCreditText", "Set-SlantWindowFrame",
    "Set-SlantWindowScheme", "Set-SlantWindowTransitions", "Test-SlantWindowZoomed",
    "Get-SlantWindowStyle", "Get-SlantWindowSizes", "Get-SlantWindowHandle",
    "Get-SlantWorkArea", "New-SlantWindowButton", "New-SlantTitleBar",
    "Set-SlantLogo", "Install-SlantWindow",
)


def test_the_window_half_is_exported():
    text = path(MODULE).read_text(encoding="utf-8")
    exported = text.split("Export-ModuleMember -Function", 1)[1]
    for name in WINDOW_EXPORTS:
        assert name in exported, name
        assert f"function {name} " in text, name


def test_the_credit_text_is_the_licence_text():
    """The licence says the line is drawn by the library and says what it
    reads. Both halves of the library write the same string, and the other
    one is held to LICENSE in tests/test_scripts.py."""
    lic = (ROOT / "LICENSE").read_text(encoding="utf-8")
    m = re.search(r"It\s+reads:\s*\n\s*\n[ \t]+(.+?)[ \t]*\n", lic)
    assert m, "LICENSE no longer says what the credit line reads"
    text = path(MODULE).read_text(encoding="utf-8")
    assert f"$script:SlantCreditText = '{m.group(1)}'" in text


def test_the_title_bar_writes_the_credit_itself():
    """A caller cannot leave it out: there is no switch for it."""
    text = path(MODULE).read_text(encoding="utf-8")
    bar = text.split("function New-SlantTitleBar", 1)[1].split("\nfunction ", 1)[0]
    assert "$credit.Text = Get-SlantCreditText" in bar


def test_the_window_procedure_answers_the_four_messages():
    """WM_NCCALCSIZE is what takes the frame out of the layout, WM_NCHITTEST
    is what gives the resize edges back, WM_SYSCOMMAND is how Win+Up reaches
    a window that maximises itself, and WM_NCDESTROY is where the subclass
    comes off. Losing any of them is a window that looks right and behaves
    wrongly, which is the hardest kind to notice."""
    text = path(MODULE).read_text(encoding="utf-8")
    for name, value in (("WM_NCCALCSIZE", "0x0083"), ("WM_NCHITTEST", "0x0084"),
                        ("WM_NCACTIVATE", "0x0086"), ("WM_SYSCOMMAND", "0x0112"),
                        ("WM_NCDESTROY", "0x0082")):
        assert f"const uint {name} = {value};" in text, name
        assert f"msg == {name}" in text, name


def test_the_window_is_never_zoomed_by_the_module():
    """Maximised is a state the object keeps. A window that carries the frame
    styles is placed by Windows past the edge of the screen when it zooms, so
    nothing here may ask for that state."""
    text = path(MODULE).read_text(encoding="utf-8")
    assert "WindowState = 'Maximized'" not in text
    assert "$w.WindowState = 'Normal'" in text          # the absorbed zoom


def test_the_subclass_delegate_is_kept_and_then_taken_off():
    """A delegate handed to SetWindowSubclass is called from native code long
    after the call returns, and a window that goes away with a procedure
    pointing at managed code can stop the process."""
    text = path(MODULE).read_text(encoding="utf-8")
    assert "static readonly List<SubclassProc> _keep" in text
    assert "RemoveWindowSubclass(h, s.Proc, (IntPtr)1);" in text


def test_the_hit_test_names_every_edge():
    """Eight edges and the client area. HTCLIENT everywhere else is what
    keeps the window buttons reachable: a window carrying WS_CAPTION would
    otherwise have Windows claim the top strip as its caption."""
    text = path(MODULE).read_text(encoding="utf-8")
    hit = text.split("static int HitTest(", 1)[1].split("\n        }", 1)[0]
    for code in ("10", "11", "12", "13", "14", "15", "16", "17"):
        assert f"return {code};" in hit, code
    assert "if (s == null || !s.Resize || s.Max) return 1;" in hit


def test_the_buttons_take_the_two_durations_the_stylesheet_uses():
    """A control answers the pointer faster than it lets go. The numbers come
    out of the data file, not out of this module."""
    text = path(MODULE).read_text(encoding="utf-8")
    button = text.split("function New-SlantWindowButton", 1)[1].split("\nfunction ", 1)[0]
    assert "Times['t-in']" in button and "Times['t-out']" in button


def test_the_window_glyphs_are_paths_and_not_characters():
    """A glyph from a font is a font that has to be there. These are drawn."""
    text = path(MODULE).read_text(encoding="utf-8")
    block = text.split("$script:SlantGlyphs = @{", 1)[1].split("}", 1)[0]
    for name in ("Minimise", "Close", "Maximise", "Restore"):
        assert name in block, name
    assert block.count("'M") >= 4


# ── the real window ─────────────────────────────────────────────────────────
# Switched on by hand, the way tests/test_window.py is, because it opens a
# window. It is the only check that sees the frame from outside the process.
_WINDOW_PROBE = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase
Import-Module '{module}' -Force

$out = [ordered]@{{}}
$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="check" Width="1040" Height="700" MinWidth="600" MinHeight="400"
        WindowStartupLocation="Manual" Left="-20000" Top="-20000">
  <Grid x:Name="Inside"/>
</Window>
'@
$w = [System.Windows.Markup.XamlReader]::Load((New-Object System.Xml.XmlNodeReader ([xml]$xaml)))
$chrome = Install-SlantWindow -Window $w -Bold 'Slant' -Name ' check'
$chrome.SetStatus('slot')

$w.add_Loaded({{
    $t = New-Object System.Windows.Threading.DispatcherTimer
    $t.Interval = [TimeSpan]::FromMilliseconds(400)
    $t.add_Tick({{
        try {{
            $args[0].Stop()
            $h = $chrome.Handle
            $fin = [SlantUI.Chrome]::Window($h)
            $cli = [SlantUI.Chrome]::Client($h)
            $out.Style = [SlantUI.Chrome]::Style($h)
            $out.WindowSize = @(($fin.Right - $fin.Left), ($fin.Bottom - $fin.Top))
            $out.ClientSize = @(($cli.Right - $cli.Left), ($cli.Bottom - $cli.Top))
            $out.Credit = $chrome.Credit.Text
            $out.Status = $chrome.Status.Text
            $out.Buttons = @($chrome.Buttons.Keys | Sort-Object)
            $out.BarHeight = $chrome.Element.ActualHeight
            $out.BrandWidth = [math]::Round($chrome.Brand.ActualWidth)
            $out.BandPath = "$($chrome.Band.Data)"
            # Parsed, not the raw path: a Geometry writes its numbers its own
            # way, so the two are compared as shapes. That the module and the
            # Python write the same string is checked further up.
            $out.WantedPath = "$([System.Windows.Media.Geometry]::Parse((Get-SlantBandPath `
                -Width $chrome.Element.ActualWidth `
                -BrandWidth ([math]::Round($chrome.Brand.ActualWidth)))))"
            $out.Rows = $chrome.Body.Children.Count
            $out.InsideKept = ($w.FindName('Inside').IsDescendantOf($chrome.Body))
            $xa = [int]$fin.Left; $ya = [int]$fin.Top; $xz = [int]$fin.Right; $yz = [int]$fin.Bottom
            $out.Hits = @(
                [SlantUI.Chrome]::Hit($h, $xa + 1, $ya + 1),
                [SlantUI.Chrome]::Hit($h, $xz - 2, $ya + 1),
                [SlantUI.Chrome]::Hit($h, $xa + 1, $yz - 2),
                [SlantUI.Chrome]::Hit($h, $xz - 2, $yz - 2),
                [SlantUI.Chrome]::Hit($h, $xa + 1, $ya + 300),
                [SlantUI.Chrome]::Hit($h, $xz - 2, $ya + 300),
                [SlantUI.Chrome]::Hit($h, $xa + 400, $ya + 1),
                [SlantUI.Chrome]::Hit($h, $xa + 400, $yz - 2),
                [SlantUI.Chrome]::Hit($h, $xa + 400, $ya + 300),
                [SlantUI.Chrome]::Hit($h, $xa + 400, $ya + 20))
            $chrome.StateMs = 0
            $work = Get-SlantWorkArea $w
            $before = $chrome.NormalBounds()
            $chrome.Maximize()
            $w.UpdateLayout()
            $out.Work = @($work.X, $work.Y, $work.Width, $work.Height)
            $out.Maximised = @($w.Left, $w.Top, $w.Width, $w.Height)
            $out.Zoomed = [SlantUI.Chrome]::IsZoomed($h)
            $out.MaxFlag = $chrome.IsMaximized()
            $out.MaxState = "$($w.WindowState)"
            $out.EdgeWhileMax = [SlantUI.Chrome]::Hit($h, [int]$work.X + 1, [int]$work.Y + 1)
            $out.MaxTip = "$($chrome.Buttons['max'].ToolTip)"
            $out.TookWinDown = $chrome.SystemCommand(0xF120)
            $w.UpdateLayout()
            $out.Restored = @($w.Width, $w.Height)
            $out.Wanted = @($before.Width, $before.Height)
            $w.WindowState = 'Maximized'
            $w.UpdateLayout()
            $out.AfterZoom = @([SlantUI.Chrome]::IsZoomed($h), $chrome.IsMaximized(), "$($w.WindowState)")
            $chrome.Restore()

            # Place: the window put exactly there, in one call.
            $chrome.StateMs = 0
            $vuole = New-Object System.Windows.Rect 140, 120, 900, 620
            $chrome.Place($vuole)
            $w.UpdateLayout()
            $out.Placed = @($w.Left, $w.Top, $w.ActualWidth, $w.ActualHeight)
            $out.PlaceWanted = @($vuole.X, $vuole.Y, $vuole.Width, $vuole.Height)
            $out.SizingAtRest = [SlantUI.Chrome]::IsSizing($h)

            # The animated maximise, which cannot finish inside this tick: it
            # needs frames, and frames only arrive if the thread goes back to
            # composing. It starts here and is watched by a second timer, which
            # closes the window once it is done.
            $chrome.StateMs = 240
            $segni = New-Object System.Collections.ArrayList
            $chrome.OnSizing = {{ param($attivo) [void]$segni.Add([bool]$attivo) }}.GetNewClosure()
            $conta = @{{ N = 0 }}
            $tela = [System.EventHandler] {{ param($s, $e) $conta.N++ }}.GetNewClosure()
            [System.Windows.Media.CompositionTarget]::add_Rendering($tela)
            $inizio = [DateTime]::UtcNow
            $chrome.Maximize()

            $t2 = New-Object System.Windows.Threading.DispatcherTimer
            $t2.Interval = [TimeSpan]::FromMilliseconds(30)
            $t2.add_Tick({{
                try {{
                    $scaduto = (([DateTime]::UtcNow - $inizio).TotalMilliseconds -gt 4000)
                    if ($null -ne $chrome.Anim -and -not $scaduto) {{ return }}
                    $args[0].Stop()
                    [System.Windows.Media.CompositionTarget]::remove_Rendering($tela)
                    $lavoro = Get-SlantWorkArea $w
                    $out.AnimMs = [int]([DateTime]::UtcNow - $inizio).TotalMilliseconds
                    $out.AnimFrames = $conta.N
                    $out.AnimLanded = @($w.Left, $w.Top, $w.Width, $w.Height)
                    $out.AnimWanted = @($lavoro.X, $lavoro.Y, $lavoro.Width, $lavoro.Height)
                    $out.AnimTimedOut = $scaduto
                    $out.SizingSeq = @($segni)
                    $out.SizingAfter = [SlantUI.Chrome]::IsSizing($chrome.Handle)
                }} catch {{
                    $out.Error = "$($_.Exception.Message) @ $($_.InvocationInfo.ScriptLineNumber)"
                }}
                $w.Close()
            }}.GetNewClosure())
            $t2.Start()
            return
        }} catch {{
            $out.Error = "$($_.Exception.Message) @ $($_.InvocationInfo.ScriptLineNumber)"
        }}
        $w.Close()
    }})
    $t.Start()
}})
[void]$w.ShowDialog()
$out | ConvertTo-Json -Depth 6 -Compress
"""


@pytest.fixture(scope="module")
def window(tmp_path_factory) -> dict:
    if os.environ.get("SLANTUI_SHOW_WINDOW", "") != "1":
        pytest.skip("opens a real window; set SLANTUI_SHOW_WINDOW=1 to run it")
    folder = tmp_path_factory.mktemp("slantwindow")
    install(folder)
    script = folder / "window.ps1"
    script.write_text(_WINDOW_PROBE.format(module=(folder / MODULE).as_posix()),
                      encoding="utf-8")
    run = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-STA", "-ExecutionPolicy",
         "Bypass", "-File", str(script)],
        capture_output=True, text=True)
    if run.returncode != 0 or not run.stdout.strip():
        pytest.fail(f"the window did not open:\n{run.stdout}\n{run.stderr}")
    got = json.loads(run.stdout)
    assert "Error" not in got, got.get("Error")
    return got


WS_FRAME = 0x00C00000 | 0x00040000 | 0x00020000 | 0x00010000 | 0x00080000


def test_the_window_carries_the_frame_styles(window):
    """Without them Windows does not animate the window when it minimises,
    restores or closes, and there is no shadow."""
    assert window["Style"] & WS_FRAME == WS_FRAME


def test_the_client_area_is_the_whole_window(window):
    """Which is the other half of the technique: the styles are there and
    nothing is laid out for them."""
    assert window["ClientSize"] == window["WindowSize"]


def test_the_band_is_the_one_the_library_draws(window):
    assert window["BarHeight"] == px("tbar-h")
    assert window["BrandWidth"] > 0
    assert window["BandPath"].replace(" ", "") == window["WantedPath"].replace(" ", "")


def test_the_credit_line_is_written(window):
    lic = (ROOT / "LICENSE").read_text(encoding="utf-8")
    m = re.search(r"It\s+reads:\s*\n\s*\n[ \t]+(.+?)[ \t]*\n", lic)
    assert window["Credit"] == m.group(1)


def test_the_application_keeps_what_was_inside(window):
    """The window gains a row and loses nothing."""
    assert window["Rows"] == 2
    assert window["InsideKept"] is True
    assert window["Status"] == "slot"
    assert window["Buttons"] == ["close", "max", "min"]


def test_the_eight_edges_answer_and_nothing_else_does(window):
    corners_sides = window["Hits"][:8]
    assert corners_sides == [13, 14, 16, 17, 10, 11, 12, 15]
    assert window["Hits"][8] == 1                  # the middle of the page
    assert window["Hits"][9] == 1                  # the band, which drags


def test_maximised_is_the_work_area_and_never_a_zoom(window):
    for got, want in zip(window["Maximised"], window["Work"]):
        assert abs(got - want) < 1
    assert window["Zoomed"] is False
    assert window["MaxFlag"] is True
    assert window["MaxState"] == "Normal"
    assert window["EdgeWhileMax"] == 1             # no edges while maximised
    assert window["MaxTip"] == "Restore"


def test_a_system_command_restores_the_size_the_window_had(window):
    assert window["TookWinDown"] is True
    for got, want in zip(window["Restored"], window["Wanted"]):
        assert abs(got - want) < 2


def test_a_zoom_windows_did_by_itself_is_undone(window):
    zoomed, flag, state = window["AfterZoom"]
    assert zoomed is False
    assert flag is True
    assert state == "Normal"


def test_one_call_puts_the_window_exactly_there(window):
    """Place goes through SetWindowPos with all four numbers at once, and
    WPF reads its own Left, Top, Width and Height back out of the message.
    A pixel of rounding is allowed: the call counts in real pixels and WPF
    counts in its own."""
    for got, want in zip(window["Placed"], window["PlaceWanted"]):
        assert abs(got - want) <= 1, (window["Placed"], window["PlaceWanted"])
    assert window["SizingAtRest"] is False


def test_an_animated_state_change_runs_on_the_frame_clock(window):
    """It lands on the work area, it takes about as long as it was asked to,
    and it drew a frame for roughly every frame the compositor sent. A
    handful is what a DispatcherTimer used to manage in the same time."""
    assert window["AnimTimedOut"] is False
    for got, want in zip(window["AnimLanded"], window["AnimWanted"]):
        assert abs(got - want) < 1, (window["AnimLanded"], window["AnimWanted"])
    assert 200 <= window["AnimMs"] <= 1500, window["AnimMs"]
    assert window["AnimFrames"] >= 6, window["AnimFrames"]


def test_the_application_is_told_a_size_is_about_to_move(window):
    """Once before the geometry starts moving and once after it has
    settled, so what would rewrap on every frame can be frozen and let go.
    The same signal a drag of an edge raises."""
    assert window["SizingSeq"] == [True, False]
    assert window["SizingAfter"] is False
