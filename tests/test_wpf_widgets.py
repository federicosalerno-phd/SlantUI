"""The three things the WPF module draws that are not the window: the splash,
the dropdown and the SVG reader.

They arrived from an application that already used them, which is the wrong
way round, and this file is half of what makes them the library's. Each one is
measured by opening a real WPF window and asking it, because none of these
three can be checked by reading the source: a ring that turns is a ring that
turns on a thread, a dropdown that closes on the second click is a routed
event arriving where it was meant to, and a reader that draws nothing looks
exactly like a reader that works until something renders what came out of it.

The windows open twenty thousand pixels off the left of the screen and never
take the focus, so these run with the rest of the suite instead of being
switched on by hand like ``tests/test_window.py``. What they cost is three
PowerShell starts and about ten seconds.

One probe per subject, one PowerShell run each, everything read out of the
JSON it prints: starting the shell costs more than every check in this file
put together.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from slantui.wpf import MODULE, install

pytestmark = pytest.mark.skipif(
    os.name != "nt" or not shutil.which("powershell"),
    reason="the module is for WPF, which is Windows PowerShell")


def _probe(folder: Path, name: str, script: str, args: tuple[str, ...] = ()) -> dict:
    """Write one probe next to a copy of the module, run it, read its JSON.

    The module is installed into the folder and not imported from the package,
    which is how an application gets it and so the shape this should be proved
    in.
    """
    install(folder)
    path = folder / f"{name}.ps1"
    path.write_text(script.format(module=(folder / MODULE).as_posix()),
                    encoding="utf-8")
    run = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-STA", "-ExecutionPolicy",
         "Bypass", "-File", str(path), *args],
        capture_output=True, text=True)
    out = run.stdout.strip().splitlines()
    if run.returncode != 0 or not out:
        pytest.fail(f"the {name} probe did not run:\n{run.stdout}\n{run.stderr}")
    try:
        got = json.loads(out[-1])
    except json.JSONDecodeError:
        pytest.fail(f"the {name} probe printed no JSON:\n{run.stdout}\n{run.stderr}")
    assert "Error" not in got, got.get("Error")
    return got


# ── the splash ──────────────────────────────────────────────────────────────
# Two windows in one run. The first is a window this library dressed, and it
# carries every measurement of the ring; the second is a bare one, which is the
# form that exists for the seconds before an application does.
_SPLASH_PROBE = r"""
param()
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase
Import-Module '{module}' -Force

$out = [ordered]@{{}}

# What the drawing thread has on screen, as one number. Two of these taken at
# the ends of a held thread say whether anything moved in between.
function Get-Print($bmp) {{
    if ($null -eq $bmp) {{ return "" }}
    $stride = $bmp.PixelWidth * 4
    $buf = New-Object byte[] ($stride * $bmp.PixelHeight)
    $bmp.CopyPixels($buf, $stride, 0)
    $md5 = [System.Security.Cryptography.MD5]::Create()
    return [BitConverter]::ToString($md5.ComputeHash($buf)).Replace('-', '')
}}

# ── the dressed window ──────────────────────────────────────────────────────
$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Width="520" Height="380" MinWidth="200" MinHeight="150"
        WindowStartupLocation="Manual" Left="-20000" Top="-20000"
        ShowInTaskbar="False" ShowActivated="False">
  <Grid x:Name="Inside"/>
</Window>
'@
$w = [System.Windows.Markup.XamlReader]::Load((New-Object System.Xml.XmlNodeReader ([xml]$xaml)))
$chrome = Install-SlantWindow -Window $w -Bold 'Slant' -Name ' check'

# Which form each switch belongs to, read off the command and not guessed. The
# two forms have to stay apart: a palette handed to the chrome form would be
# taken and ignored, because a chrome carries its own.
$cmd = Get-Command Show-SlantSplash
$out.Sets = @($cmd.ParameterSets | ForEach-Object {{ $_.Name }} | Sort-Object)
$out.BlurSets = @($cmd.Parameters['Blur'].ParameterSets.Keys | Sort-Object)
$out.PaletteSets = @($cmd.Parameters['Palette'].ParameterSets.Keys | Sort-Object)
$out.LogoSets = @($cmd.Parameters['Logo'].ParameterSets.Keys | Sort-Object)
$out.BusySets = @($cmd.Parameters['Busy'].ParameterSets.Keys | Sort-Object)

# The waiting mode asked for BEFORE the drawing thread exists, which is the
# normal order: -Busy is read at build time or it is read never.
$splash = Show-SlantSplash -Chrome $chrome -Text 'starting' -Busy
$out.BusyAtStart = $splash.IsBusy()

$w.add_ContentRendered({{
    $t = New-Object System.Windows.Threading.DispatcherTimer
    $t.Interval = [TimeSpan]::FromMilliseconds(250)
    $t.add_Tick({{
        param($s, $e)
        $s.Stop()
        try {{
            # --- the ring turns with this thread held down -------------------
            # Half a second of Sleep on the thread WPF beats its animations on.
            # If the ring were animated here, the two prints would be equal.
            $a = Get-Print $splash.Snapshot(1.0)
            [System.Threading.Thread]::Sleep(500)
            $b = Get-Print $splash.Snapshot(1.0)
            $out.TurnA = $a
            $out.TurnB = $b
            $out.BusyStillOn = $splash.IsBusy()

            # --- an announced step ends the wait by itself -------------------
            $splash.SetProgress(0.15, 'reading')
            [System.Threading.Thread]::Sleep(120)
            $out.BusyAfterStep = $splash.IsBusy()

            # --- and the fill never stands still -----------------------------
            # Drawn is sampled every 25 ms across a run of steps with a long
            # silence in the middle. The timestamps go out with the samples,
            # because a timer is asked for 25 ms and gives what it gives.
            $banco = @{{ Campioni = (New-Object System.Collections.ArrayList)
                        T0 = [DateTime]::UtcNow; Fase = 0 }}
            $ritmo = New-Object System.Windows.Threading.DispatcherTimer
            $ritmo.Interval = [TimeSpan]::FromMilliseconds(25)
            $ritmo.add_Tick({{
                param($s2, $e2)
                try {{
                    $ms = ([DateTime]::UtcNow - $banco.T0).TotalMilliseconds
                    [void]$banco.Campioni.Add(@([math]::Round($ms, 1),
                                                [math]::Round($splash.Core.Drawn, 6)))
                    if ($banco.Fase -eq 0 -and $ms -gt 150) {{
                        $banco.Fase = 1; $splash.SetProgress(0.30, 'one')
                    }} elseif ($banco.Fase -eq 1 -and $ms -gt 450) {{
                        $banco.Fase = 2; $splash.SetProgress(0.45, 'two')
                    }} elseif ($banco.Fase -eq 2 -and $ms -gt 1900) {{
                        $banco.Fase = 3; $splash.SetProgress(0.62, 'three')
                    }} elseif ($banco.Fase -eq 3 -and $ms -gt 2400) {{
                        $s2.Stop()
                        $out.Samples = @($banco.Campioni)
                        $out.Composed = $splash.Core.Composed
                        $out.Drawn = $splash.Core.Drawn
                        $out.Announced = $splash.Core.Progress
                        $splash.Hide(120)
                        $via = New-Object System.Windows.Threading.DispatcherTimer
                        $via.Interval = [TimeSpan]::FromMilliseconds(500)
                        $via.add_Tick({{
                            param($s3, $e3)
                            $s3.Stop()
                            $out.LeftBehind = @($chrome.Body.Children |
                                Where-Object {{ $_ -is [SlantVisualHost] }}).Count
                            $out.BlurAfter = $(if ($null -ne $splash.Under -and
                                                   $null -ne $splash.Under.Effect) {{ 1 }} else {{ 0 }})
                            $w.Close()
                        }}.GetNewClosure())
                        $via.Start()
                    }}
                }} catch {{
                    $s2.Stop()
                    $out.Error = "$($_.Exception.Message) @ $($_.InvocationInfo.ScriptLineNumber)"
                    $w.Close()
                }}
            }}.GetNewClosure())
            $ritmo.Start()
        }} catch {{
            $out.Error = "$($_.Exception.Message) @ $($_.InvocationInfo.ScriptLineNumber)"
            $w.Close()
        }}
    }}.GetNewClosure())
    $t.Start()
}}.GetNewClosure())
[void]$w.ShowDialog()

# ── the bare window ─────────────────────────────────────────────────────────
# No band, no blur, the screen on its own, and built before the window has ever
# been shown, which is when whatever starts an application would build it.
$xaml2 = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        WindowStyle="None" ResizeMode="NoResize" ShowInTaskbar="False"
        ShowActivated="False" WindowStartupLocation="Manual"
        Left="-20000" Top="-20000" Width="700" Height="460" Background="#FF0D0D0F">
  <Grid x:Name="Root"><Border x:Name="Was" Background="#FF1B1B22"/></Grid>
</Window>
'@
$b = [System.Windows.Markup.XamlReader]::Load((New-Object System.Xml.XmlNodeReader ([xml]$xaml2)))
$nuda = Show-SlantSplash -Window $b -Palette 'gold-dark' -Busy -Text 'starting'
$out.BareAdded = $b.FindName('Root').Children.Count
$out.BareKeptWhatWasThere = ($b.FindName('Was').Parent -eq $b.FindName('Root'))
$out.BareNoBlur = ($null -eq $nuda.Blur)
$out.BareNoUnder = ($null -eq $nuda.Under)
$out.BareBusy = $nuda.IsBusy()

$b.add_ContentRendered({{
    $t = New-Object System.Windows.Threading.DispatcherTimer
    $t.Interval = [TimeSpan]::FromMilliseconds(400)
    $t.add_Tick({{
        param($s, $e)
        $s.Stop()
        try {{
            $shot = $nuda.Snapshot(1.0)
            $out.BareShot = @($(if ($shot) {{ $shot.PixelWidth }} else {{ 0 }}),
                              $(if ($shot) {{ $shot.PixelHeight }} else {{ 0 }}))
            # it goes from inside ShowDialog, which is where it will be asked to
            $nuda.Hide(120)
            $via = New-Object System.Windows.Threading.DispatcherTimer
            $via.Interval = [TimeSpan]::FromMilliseconds(500)
            $via.add_Tick({{
                param($s3, $e3)
                $s3.Stop()
                $out.BareLeftBehind = @($b.FindName('Root').Children |
                    Where-Object {{ $_ -is [SlantVisualHost] }}).Count
                $b.Close()
            }}.GetNewClosure())
            $via.Start()
        }} catch {{
            $out.Error = "$($_.Exception.Message) @ $($_.InvocationInfo.ScriptLineNumber)"
            $b.Close()
        }}
    }}.GetNewClosure())
    $t.Start()
}}.GetNewClosure())
[void]$b.ShowDialog()

# ── a bare window holding something that is not a Panel ─────────────────────
$xaml3 = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        WindowStyle="None" ShowInTaskbar="False" ShowActivated="False"
        WindowStartupLocation="Manual" Left="-20000" Top="-20000"
        Width="400" Height="300">
  <Border x:Name="Only" Background="#FF1B1B22"/>
</Window>
'@
$c = [System.Windows.Markup.XamlReader]::Load((New-Object System.Xml.XmlNodeReader ([xml]$xaml3)))
$solo = Show-SlantSplash -Window $c -Busy -Text 'starting'
$out.WrappedContent = "$($c.Content.GetType().Name)"
$out.WrappedKept = ($c.FindName('Only').Parent -eq $c.Content)
$out.WrappedChildren = $c.Content.Children.Count
try {{ $solo.Core.Shutdown() }} catch {{ }}

$out | ConvertTo-Json -Depth 6 -Compress
"""


@pytest.fixture(scope="module")
def splash(tmp_path_factory) -> dict:
    return _probe(tmp_path_factory.mktemp("slantsplash"), "splash", _SPLASH_PROBE)


def test_the_two_forms_stay_apart(splash):
    """A chrome carries its own palette, so -Palette with one would be taken
    and then ignored; a bare window has nothing behind the screen, so -Blur
    with one would be taken and do nothing. Everything else belongs to both.
    An application calling the older form with -Blur still binds, which is the
    half of this that must not break."""
    assert splash["Sets"] == ["Chrome", "Window"]
    assert splash["BlurSets"] == ["Chrome"]
    assert splash["PaletteSets"] == ["Window"]
    assert splash["LogoSets"] == ["__AllParameterSets"]
    assert splash["BusySets"] == ["__AllParameterSets"]


def test_the_waiting_mode_holds_when_it_is_asked_for_before_the_thread(splash):
    """SetBusy and then Start is the normal order, and for a while the flag was
    set and then read by nobody: the screen came up measuring and showed one
    per cent of nothing."""
    assert splash["BusyAtStart"] is True
    assert splash["BusyStillOn"] is True


def test_an_announced_step_ends_the_wait_by_itself(splash):
    """Whoever announces a step has something to measure. It is what makes a
    handover work: one screen turns, the next comes up turning, and the first
    announced step turns the ring into a measure with no jump between them."""
    assert splash["BusyAfterStep"] is False


def test_the_ring_turns_while_this_thread_is_held_down(splash):
    """Half a second of Sleep on the thread WPF beats its animations on. The
    drawing thread is not that thread, so the two photographs taken at the ends
    of it are of two different frames. They were once the same picture."""
    assert splash["TurnA"], "no photograph came back at all"
    assert splash["TurnA"] != splash["TurnB"]


def test_the_movement_comes_from_the_compositor(splash):
    """One step per composed frame, from CompositionTarget.Rendering. There is
    a DispatcherTimer behind it for a thread where that event never comes, and
    without this check the good path could rot away under the fallback and
    nobody would see it."""
    assert splash["Composed"] is True


def test_the_fill_never_stands_still(splash):
    """Drawn, every 25 ms, across three steps with a second and a half of
    silence in the middle. No window of 120 ms may show no movement at all: an
    arc that arrives and stops is what the speed was put there to end."""
    samples = [(float(t), float(v)) for t, v in splash["Samples"]]
    assert len(samples) > 40, f"only {len(samples)} samples, so this is not sampling"
    assert samples[-1][0] > 2000, "the run was shorter than the silence it is about"
    stalls = []
    for i, (t0, v0) in enumerate(samples):
        j = next((k for k in range(i + 1, len(samples)) if samples[k][0] - t0 >= 120), None)
        if j is None:
            break
        if samples[j][1] <= v0:
            stalls.append(f"{t0:.0f} ms to {samples[j][0]:.0f} ms: {v0:.5f} to "
                          f"{samples[j][1]:.5f}")
    assert not stalls, ("the arc stood still over these windows:\n  "
                        + "\n  ".join(stalls))


def test_the_arc_is_still_behind_the_last_step_and_climbing(splash):
    """It is never told to jump, so it is always behind what was announced, and
    it never runs past it either."""
    assert 0 < splash["Drawn"] < splash["Announced"] <= 1.0


def test_the_splash_takes_itself_off_when_it_is_hidden(splash):
    assert splash["LeftBehind"] == 0
    assert splash["BlurAfter"] == 0


def test_a_bare_window_wears_the_screen_and_nothing_else(splash):
    """The form for the seconds before an application exists. No band to leave
    sharp and no page to blur, so neither is there; what the window already
    held stays where it was."""
    assert splash["BareAdded"] == 2
    assert splash["BareKeptWhatWasThere"] is True
    assert splash["BareNoBlur"] is True
    assert splash["BareNoUnder"] is True
    assert splash["BareBusy"] is True


def test_a_bare_window_is_covered_before_it_has_ever_been_shown(splash):
    """Nothing has a measured size until a window is shown, and that is exactly
    when this form is called, so what the window was asked to be stands in. A
    ring that starts in the wrong place is seen jumping to the middle."""
    assert splash["BareShot"] == [700, 460]


def test_a_bare_window_lets_go_from_inside_a_dialog(splash):
    """The bare form is put up by something that then calls ShowDialog, so Hide
    has to arrive there. It also has no veil and no page under it, and a throw
    over either of those would have carried off the fade with it."""
    assert splash["BareLeftBehind"] == 0


def test_a_window_holding_one_thing_is_wrapped_and_keeps_it(splash):
    """A window holds one child. When that child cannot take another, it is
    moved into a Grid that can, and it is still there afterwards."""
    assert splash["WrappedContent"] == "Grid"
    assert splash["WrappedKept"] is True
    assert splash["WrappedChildren"] == 2


# ── the dropdown ────────────────────────────────────────────────────────────
_PICKER_PROBE = r"""
param()
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase
Import-Module '{module}' -Force

$out = [ordered]@{{}}

# A press, raised where a press would arrive. The tunnelling events reach the
# handlers on the window first, which is the route the dropdown relies on.
function Send-Press($el, $evento) {{
    $a = New-Object System.Windows.Input.MouseButtonEventArgs(
        [System.Windows.Input.Mouse]::PrimaryDevice, 0, [System.Windows.Input.MouseButton]::Left)
    $a.RoutedEvent = $evento
    $el.RaiseEvent($a)
}}

$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Width="640" Height="420" WindowStartupLocation="Manual"
        Left="-20000" Top="-20000" ShowInTaskbar="False" ShowActivated="False">
  <Grid x:Name="Inside">
    <Border x:Name="Elsewhere" Background="#01000000"/>
    <StackPanel x:Name="Corner" Orientation="Horizontal"
                HorizontalAlignment="Right" VerticalAlignment="Top" Margin="0,8,12,0"/>
  </Grid>
</Window>
'@
$w = [System.Windows.Markup.XamlReader]::Load((New-Object System.Xml.XmlNodeReader ([xml]$xaml)))
$chrome = Install-SlantWindow -Window $w -Bold 'Slant' -Name ' check'

# Forty entries, with names long enough that the list is wider than its button
# and taller than the window it is in: both corrections have to happen, and the
# button sits at the top right, which is where they are needed.
$voci = @()
foreach ($i in 1..40) {{
    $voci += [PSCustomObject]@{{
        Code  = ("e{{0:d2}}" -f $i)
        Tag   = ("E{{0:d2}}" -f $i)
        Label = ("Entry number {{0}} with a name of its own" -f $i)
        Note  = $(if ($i % 3 -eq 0) {{ "needs setup" }} else {{ "" }})
        Dot   = $(if ($i % 3 -eq 0) {{ "#FFCC5555" }} else {{ $null }})
    }}
}}
$cambi = New-Object System.Collections.ArrayList
$picker = New-SlantPicker -Items $voci -Current 'e01' -TagWidth 26 `
    -OnChange {{ param($code) [void]$cambi.Add("$code") }}
[void]$w.FindName('Corner').Children.Add($picker.Element)
$out.BuiltBeforeOpening = $picker.Popup.Child.Child.Content.Children.Count

$w.add_ContentRendered({{
    $t = New-Object System.Windows.Threading.DispatcherTimer
    $t.Interval = [TimeSpan]::FromMilliseconds(300)
    $t.add_Tick({{
        param($s, $e)
        $s.Stop()
        try {{
            $btn = $picker.Element.Children[0]
            $pop = $picker.Popup
            $cornice = $pop.Child
            $lista = $cornice.Child.Content
            $giu = [System.Windows.UIElement]::PreviewMouseLeftButtonDownEvent
            $premuto = [System.Windows.UIElement]::PreviewMouseDownEvent

            $out.Start = $picker.IsDown()
            Send-Press $btn $giu
            $w.UpdateLayout()
            $out.AfterOne = $picker.IsDown()
            $out.RowsBuilt = $lista.Children.Count

            Send-Press $btn $giu
            $out.AfterTwo = $picker.IsDown()

            Send-Press $btn $giu
            $w.UpdateLayout()
            $out.AfterThree = $picker.IsDown()

            # --- and it is inside the window ---------------------------------
            $dove = $btn.TransformToAncestor($w).Transform((New-Object System.Windows.Point(0, 0)))
            $out.WindowW = $w.ActualWidth
            $out.WindowH = $w.ActualHeight
            $out.ButtonX = $dove.X
            $out.ButtonY = $dove.Y
            $out.ButtonH = $btn.ActualHeight
            # the frame carries ten pixels of margin all round, which is the
            # room its shadow needs and is part of what has to fit
            $out.FrameW = $cornice.ActualWidth + $cornice.Margin.Left + $cornice.Margin.Right
            $out.FrameH = $cornice.ActualHeight + $cornice.Margin.Top + $cornice.Margin.Bottom
            $out.OffsetX = $pop.HorizontalOffset
            $out.OffsetY = $pop.VerticalOffset
            $out.ScrollBar = [System.Windows.SystemParameters]::VerticalScrollBarWidth
            $out.Scrolls = ($cornice.Child.ComputedVerticalScrollBarVisibility -eq 'Visible')

            # --- a press anywhere else closes it -----------------------------
            Send-Press ($w.FindName('Elsewhere')) $premuto
            $out.AfterElsewhere = $picker.IsDown()

            # --- Escape closes it, and stops there ---------------------------
            Send-Press $btn $giu
            $w.UpdateLayout()
            $tasto = New-Object System.Windows.Input.KeyEventArgs(
                [System.Windows.Input.Keyboard]::PrimaryDevice,
                (New-Object System.Windows.Interop.HwndSource(0, 0, 0, 0, 0, "k", [IntPtr]::Zero)),
                0, [System.Windows.Input.Key]::Escape)
            $tasto.RoutedEvent = [System.Windows.UIElement]::PreviewKeyDownEvent
            $w.FindName('Elsewhere').RaiseEvent($tasto)
            $out.AfterEscape = $picker.IsDown()
            $out.EscapeHandled = $tasto.Handled

            # --- and a choice reports the code -------------------------------
            Send-Press $btn $giu
            $w.UpdateLayout()
            $scelta = @($lista.Children | Where-Object {{ "$($_.Tag)" -eq 'e07' }})[0]
            Send-Press $scelta ([System.Windows.UIElement]::MouseLeftButtonUpEvent)
            $out.Chose = @($cambi)
            $out.Code = $picker.Code()
            $out.AfterChoice = $picker.IsDown()

            # --- and what it would have been, left alone ---------------------
            # Measured last, because it takes the clamp back off to do it.
            $cornice.MaxHeight = [double]::PositiveInfinity
            $cornice.Measure((New-Object System.Windows.Size([double]::PositiveInfinity,
                                                             [double]::PositiveInfinity)))
            $out.NaturalW = $cornice.DesiredSize.Width
            $out.NaturalH = $cornice.DesiredSize.Height
        }} catch {{
            $out.Error = "$($_.Exception.Message) @ $($_.InvocationInfo.ScriptLineNumber)"
        }}
        $w.Close()
    }}.GetNewClosure())
    $t.Start()
}}.GetNewClosure())

[void]$w.ShowDialog()
$out | ConvertTo-Json -Depth 6 -Compress
"""


@pytest.fixture(scope="module")
def picker(tmp_path_factory) -> dict:
    return _probe(tmp_path_factory.mktemp("slantpicker"), "picker", _PICKER_PROBE)


def test_one_press_opens_the_dropdown_the_next_closes_it(picker):
    """The whole reason the popup does not take the mouse. While it did, the
    press on the button went to the popup, which closed on it, and the release
    found the dropdown shut and opened it again: from outside, a dropdown that
    never closed on the second click."""
    assert picker["Start"] is False
    assert picker["AfterOne"] is True
    assert picker["AfterTwo"] is False
    assert picker["AfterThree"] is True


def test_a_press_anywhere_else_closes_the_dropdown(picker):
    """The window's own handler, which has three cases to tell apart, and this
    is the one that has to reach the closing. The handlers it needs are hooked
    up on the first opening, so this also says they were."""
    assert picker["AfterElsewhere"] is False


def test_escape_closes_the_dropdown_and_stops_there(picker):
    """It closes like everything else in the window closes, and the key does
    not go on to close the view underneath as well."""
    assert picker["AfterEscape"] is False
    assert picker["EscapeHandled"] is True


def test_the_rows_are_built_on_the_first_opening_and_not_before(picker):
    """Drawing forty rows costs, and a window pays for it at the moment it
    opens, which is the moment that has to be free."""
    assert picker["BuiltBeforeOpening"] == 0
    assert picker["RowsBuilt"] == 40


def test_a_choice_reports_the_code_and_closes_the_dropdown(picker):
    assert picker["Chose"] == ["e07"]
    assert picker["Code"] == "e07"
    assert picker["AfterChoice"] is False


def test_forty_entries_would_not_fit_and_are_made_to(picker):
    """The button sits at the top right, so a list of forty is both wider and
    taller than the room below it. Left alone, a popup is a window of the
    system and goes outside the one that opened it."""
    right = picker["ButtonX"] + picker["NaturalW"]
    bottom = picker["ButtonY"] + picker["ButtonH"] + picker["NaturalH"]
    assert right > picker["WindowW"], (
        f"the list wants {picker['NaturalW']} of a window {picker['WindowW']} "
        f"wide from {picker['ButtonX']}, so this is testing nothing")
    assert bottom > picker["WindowH"], (
        f"the list wants {picker['NaturalH']} of a window {picker['WindowH']} "
        f"tall from {picker['ButtonY']}, so this is testing nothing")
    # and it was made to fit by being shortened, not by being cut off
    assert picker["Scrolls"] is True
    assert picker["FrameH"] < picker["NaturalH"]


def test_the_dropdown_stays_inside_the_window(picker):
    """Both edges, and the scrollbar counted in the width: a list that scrolls
    brings its bar with it, and that bar is what used to run over on the right.
    Down the page the frame's own margin and the gap under the button used to
    go uncounted, and the last rows sat under the edge of the window."""
    left = picker["ButtonX"] + picker["OffsetX"]
    top = picker["ButtonY"] + picker["ButtonH"] + picker["OffsetY"]
    assert left >= 0, f"the dropdown starts at {left}"
    assert left + picker["FrameW"] <= picker["WindowW"] + 0.5, (
        f"the dropdown ends at {left + picker['FrameW']} in a window "
        f"{picker['WindowW']} wide")
    assert top >= 0, f"the dropdown starts at {top} down the page"
    assert top + picker["FrameH"] <= picker["WindowH"] + 0.5, (
        f"the dropdown ends at {top + picker['FrameH']} in a window "
        f"{picker['WindowH']} tall")
    assert picker["FrameW"] > picker["ScrollBar"], "no width was measured at all"


# ── the SVG reader ──────────────────────────────────────────────────────────
# The samples are written here and read there. They cover what the reader says
# it does and nothing it says it does not: shapes, nested groups, transforms,
# inherited paint, a path with a fill rule, and a mark with no colour of its
# own for the tint to give it one.
SAMPLES = {
"shapes.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 48">
  <rect x="0" y="0" width="64" height="48" fill="#123456"/>
  <rect x="4" y="4" width="20" height="12" rx="3" fill="#E8B54A"/>
  <circle cx="40" cy="12" r="8" fill="#4AA3E8"/>
  <ellipse cx="14" cy="34" rx="10" ry="6" fill="#7AE84A"/>
  <polygon points="34,26 54,26 44,44" fill="#E84A7A"/>
  <polyline points="28,44 32,38 36,44" fill="none" stroke="#FFFFFF" stroke-width="2"/>
  <line x1="2" y1="46" x2="62" y2="46" stroke="#AAAAAA" stroke-width="2"/>
</svg>
""",
"groups.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 48">
  <rect x="0" y="0" width="64" height="48" fill="#202028"/>
  <g fill="#F5C542">
    <rect x="4" y="4" width="16" height="16"/>
    <g fill="#42C5F5">
      <rect x="24" y="4" width="16" height="16"/>
      <g><circle cx="52" cy="12" r="8"/></g>
    </g>
    <rect x="4" y="28" width="16" height="16"/>
  </g>
</svg>
""",
"transforms.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 48">
  <rect x="0" y="0" width="64" height="48" fill="#101014"/>
  <g transform="translate(8,6)">
    <rect x="0" y="0" width="14" height="14" fill="#D94F4F"/>
  </g>
  <g transform="rotate(25 40 14)">
    <rect x="30" y="4" width="20" height="14" fill="#4FD97F"/>
  </g>
  <g transform="scale(1.5 1)">
    <rect x="4" y="22" width="16" height="10" fill="#4F7FD9"/>
  </g>
  <g transform="matrix(1 0 0.4 1 -6 0)">
    <rect x="36" y="28" width="18" height="14" fill="#D9C24F"/>
  </g>
</svg>
""",
"inherited.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 48" fill="#6EE7B7">
  <rect x="0" y="0" width="64" height="48" fill="#1B1B22"/>
  <g>
    <rect x="6" y="6" width="18" height="12"/>
    <circle cx="46" cy="14" r="9"/>
    <path d="M 8 40 L 24 26 L 40 40 Z"/>
  </g>
</svg>
""",
"paths.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 48">
  <rect width="64" height="48" fill="#F4F4F7"/>
  <path d="M 6 42 C 6 10, 26 10, 26 42 Z" fill="#2D6CDF"/>
  <path fill-rule="evenodd" fill="#DF2D6C"
        d="M 34 8 H 58 V 40 H 34 Z M 40 14 H 52 V 34 H 40 Z"/>
</svg>
""",
"mono.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 48">
  <path d="M 10 38 L 32 8 L 54 38 Z"/>
  <rect x="26" y="20" width="12" height="18"/>
</svg>
""",
# The trap. It has a child, so a check that counts the children of the drawing
# waves it through, and it draws one flat rectangle and nothing at all.
"background-only.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 48">
  <rect x="0" y="0" width="64" height="48" fill="#334455"/>
</svg>
""",
}

DRAWINGS = sorted(n for n in SAMPLES if n != "background-only.svg")

_SVG_PROBE = r"""
param([string]$Folder)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase
Import-Module '{module}' -Force

$out = [ordered]@{{}}
$out.Files = @{{}}

# Rendered at 32 by 24, which is about the size a mark sits at in a row of the
# dropdown, and the size at which a reader that draws nothing and a reader that
# draws the whole thing are hardest to tell apart by eye.
function Measure-Art($img, [int]$w, [int]$h) {{
    $vis = New-Object System.Windows.Media.DrawingVisual
    $dc = $vis.RenderOpen()
    $dc.DrawRectangle([System.Windows.Media.Brushes]::White, $null,
                      (New-Object System.Windows.Rect(0, 0, $w, $h)))
    $dc.DrawImage($img, (New-Object System.Windows.Rect(0, 0, $w, $h)))
    $dc.Close()
    $rtb = New-Object System.Windows.Media.Imaging.RenderTargetBitmap(
        $w, $h, 96, 96, [System.Windows.Media.PixelFormats]::Pbgra32)
    $rtb.Render($vis)
    $stride = $w * 4
    $buf = New-Object byte[] ($stride * $h)
    $rtb.CopyPixels($buf, $stride, 0)
    $visti = New-Object 'System.Collections.Generic.HashSet[int]'
    $md5 = [System.Security.Cryptography.MD5]::Create()
    for ($i = 0; $i -lt $buf.Length; $i += 4) {{
        # the low two bits of each channel go: the antialiasing along an edge
        # makes a hundred near neighbours of one colour, and those are not
        # colours the drawing has, they are the edge of one
        $c = (([int]($buf[$i] -band 0xFC)) -shl 16) -bor
             (([int]($buf[$i + 1] -band 0xFC)) -shl 8) -bor
              ([int]($buf[$i + 2] -band 0xFC))
        [void]$visti.Add($c)
    }}
    return @{{ Colours = $visti.Count
               Print = [BitConverter]::ToString($md5.ComputeHash($buf)).Replace('-', '') }}
}}

foreach ($f in @(Get-ChildItem -LiteralPath $Folder -Filter '*.svg' | Sort-Object Name)) {{
    $r = [ordered]@{{}}
    try {{
        $img = New-SlantVectorImage -Path $f.FullName
        if ($null -eq $img) {{ $r.Read = $false }}
        else {{
            $r.Read = $true
            $r.Frozen = $img.IsFrozen
            $r.Children = $img.Drawing.Children.Count
            $m = Measure-Art $img 32 24
            $r.Colours = $m.Colours
            $r.Print = $m.Print
        }}
    }} catch {{ $r.Error = "$($_.Exception.Message)" }}
    $out.Files[$f.Name] = $r
}}

# a tint, for a mark that declares no colour of its own
$mono = Join-Path $Folder 'mono.svg'
$out.Tinted = (Measure-Art (New-SlantVectorImage -Path $mono -Tint '#FF0000') 32 24)

# and the same file through the door an application uses, which prefers a
# vector to a raster of the same name
$out.ArtSourceType = "$((Get-SlantArtSource -Path $mono).GetType().Name)"

$out | ConvertTo-Json -Depth 6 -Compress
"""


@pytest.fixture(scope="module")
def reader(tmp_path_factory) -> dict:
    folder = tmp_path_factory.mktemp("slantsvg")
    art = folder / "art"
    art.mkdir()
    for name, text in SAMPLES.items():
        (art / name).write_text(text, encoding="utf-8")
    return _probe(folder, "svg", _SVG_PROBE, (str(art),))


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_every_sample_is_read_and_comes_back_frozen(reader, name):
    """Frozen is not a detail: the splash draws on a thread of its own, and a
    frozen Freezable is the one kind of drawing that crosses."""
    got = reader["Files"][name]
    assert got.get("Error") is None, got.get("Error")
    assert got["Read"] is True
    assert got["Frozen"] is True
    assert got["Children"] >= 1


@pytest.mark.parametrize("name", DRAWINGS)
def test_every_sample_actually_draws_something(reader, name):
    """Rendered at 32 by 24 over white, every one of them has to put at least
    two colours on the page. A file with nothing but its background in it
    passes any check that stops at counting the children of the drawing, and
    that is the check this one exists to not be."""
    assert reader["Files"][name]["Colours"] >= 2, (
        f"{name} rendered flat, so nothing in it was drawn")


def test_the_check_would_catch_a_reader_that_drew_nothing(reader):
    """The sample that proves the measure. It has a child, so counting them
    passes it, and one colour, so this does not."""
    flat = reader["Files"]["background-only.svg"]
    assert flat["Children"] == 1
    assert flat["Colours"] == 1


def test_a_tint_reaches_a_mark_that_declares_no_colour(reader):
    """A monochrome icon carries no fill, so a caller gives it one. Without the
    tint arriving, the two renders would be the same picture."""
    assert reader["Tinted"]["Colours"] >= 2
    assert reader["Tinted"]["Print"] != reader["Files"]["mono.svg"]["Print"]


def test_the_door_an_application_uses_gives_back_a_drawing(reader):
    """Get-SlantArtSource is what a caller passes a file to. An .svg comes back
    as drawings and not as pixels."""
    assert reader["ArtSourceType"] == "DrawingImage"
