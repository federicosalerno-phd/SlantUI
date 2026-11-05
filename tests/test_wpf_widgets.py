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
            # where the ring is while it waits, in the screen's coordinates
            $c0 = $splash.Core.RingCentre
            $out.CentreBusy = @([math]::Round($c0.X, 2), [math]::Round($c0.Y, 2))

            # --- an announced step ends the wait by itself -------------------
            $splash.SetProgress(0.15, 'reading')
            [System.Threading.Thread]::Sleep(120)
            $out.BusyAfterStep = $splash.IsBusy()
            $c1 = $splash.Core.RingCentre
            $out.CentreStep = @([math]::Round($c1.X, 2), [math]::Round($c1.Y, 2))

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
                        $out.Pair = @($splash.Core.DrawnPair)
                        $c2 = $splash.Core.RingCentre
                        $out.CentreLate = @([math]::Round($c2.X, 2), [math]::Round($c2.Y, 2))
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


def test_the_ring_stays_put_from_waiting_to_measuring(splash):
    """Waiting, the ring turns with no number under it; measuring, the number
    is there. The number used to be Collapsed while waiting, so the block under
    the ring was one line shorter and the ring, centred with it, climbed by half
    that line at the first announced step (about 17 pixels, 2026-11-05: "the
    ring must never move"). It is Hidden now, and the centre is the same to a
    tenth of a pixel in both modes and after three more steps."""
    busy, step, late = splash["CentreBusy"], splash["CentreStep"], splash["CentreLate"]
    for x in busy + step + late:
        assert x == x, (busy, step, late)          # not NaN: the ring was laid out
    for got in (step, late):
        assert abs(got[0] - busy[0]) < 0.1 and abs(got[1] - busy[1]) < 0.1, (busy, step, late)


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


def test_the_fill_never_races(splash):
    """The pace is the expected length of the load, and the steps only nudge
    it. An arc that chased each step raced to it and then crawled: no window
    of 120 ms may cover more than two and a half times the median stretch."""
    samples = [(float(t), float(v)) for t, v in splash["Samples"]]
    gains = []
    for i, (t0, v0) in enumerate(samples):
        j = next((k for k in range(i + 1, len(samples)) if samples[k][0] - t0 >= 120), None)
        if j is None:
            break
        gains.append((samples[j][1] - v0) / (samples[j][0] - t0))
    assert len(gains) > 20
    median = sorted(gains)[len(gains) // 2]
    assert median > 0
    assert max(gains) <= 2.5 * median, (max(gains), median)


def test_the_bar_is_the_ring_drawn_straight(splash):
    """One way of loading: the bar under the line fills with the ring, the
    same number in the same frame, and not a shuttle in a style of its own."""
    ring, bar = splash["Pair"]
    assert ring > 0
    assert bar == ring


def test_nothing_widens_out_of_the_ring_or_the_mark():
    """No thin circle let go at the end, and no ripple out of the hub of the
    mark (2026-11-05: "take away that thin circle that widens")."""
    from slantui.wpf import path
    text = path("SlantUI.Splash.cs").read_text(encoding="utf-8")
    assert "BeginAnimation(SlantRing.BurstProperty" not in text
    assert "double b = Burst;" not in text
    flow = text.split("private void DrawFlow(DrawingContext dc)", 1)[1].split("public int Settle()", 1)[0]
    assert "_rippleColor" not in flow


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


# ── the brand in parts ──────────────────────────────────────────────────────
# A mark the probe draws itself, so nothing here depends on anybody's logo:
# three triangles pointing out of a hub, with the hub second in drawing order,
# so it is found by where it sits and not by where it comes in the file. The
# triangles point left, right and down; their lines are read off the drawing.
_MOTION_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <polygon points="50,50 10,30 10,70" fill="#7354F7"/>
  <circle cx="50" cy="50" r="10" fill="#F3EEE2"/>
  <polygon points="50,50 90,30 90,70" fill="#17BEB8"/>
  <polygon points="50,50 30,90 70,90" fill="#FC5A6C"/>
</svg>
"""

_MOTION_PROBE = r"""
param([string]$Mark)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase
Import-Module '{module}' -Force

$out = [ordered]@{{}}
$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Width="520" Height="380" WindowStartupLocation="Manual" Left="-20000" Top="-20000"
        ShowInTaskbar="False" ShowActivated="False">
  <Grid x:Name="Inside"/>
</Window>
'@
$w = [System.Windows.Markup.XamlReader]::Load((New-Object System.Xml.XmlNodeReader ([xml]$xaml)))
$chrome = Install-SlantWindow -Window $w -Bold 'Slant' -Name ' check'
$cmd = Get-Command Show-SlantSplash
$out.MotionSets = @($cmd.Parameters['Motion'].ParameterSets.Keys | Sort-Object)
$out.MotionOptionsSets = @($cmd.Parameters['MotionOptions'].ParameterSets.Keys | Sort-Object)
$out.Presets = @($cmd.Parameters['Motion'].Attributes |
    Where-Object {{ $_ -is [System.Management.Automation.ValidateSetAttribute] }} |
    ForEach-Object {{ $_.ValidValues }})

function Close-Splash($sp) {{
    try {{ $sp.Core.Shutdown() }} catch {{ }}
    try {{ [void]$chrome.Body.Children.Remove($sp.Element) }} catch {{ }}
    try {{ if ($sp.Under) {{ $sp.Under.Effect = $null }} }} catch {{ }}
}}

$w.add_ContentRendered({{
    $t = New-Object System.Windows.Threading.DispatcherTimer
    $t.Interval = [TimeSpan]::FromMilliseconds(150)
    $t.add_Tick({{
        param($s, $e)
        $s.Stop()
        try {{
            # --- breathe, as it comes --------------------------------------
            $a = Show-SlantSplash -Chrome $chrome -Logo $Mark -Text 'starting' -Motion breathe
            # read straight away: the parts open from home, so the first frame
            # is the mark whole
            $out.AmountAtStart = $a.Core.MotionAmount
            [System.Threading.Thread]::Sleep(700)
            $out.Parts = $a.Core.MarkParts
            $out.Moving = $a.Core.MarkMoving
            $out.Ways = $a.Core.MarkWays
            $out.AmountOpen = $a.Core.MotionAmount
            # this thread held down for 400 ms: the clock is on the other one
            $c1 = $a.Core.MotionClock
            [System.Threading.Thread]::Sleep(400)
            $c2 = $a.Core.MotionClock
            $out.Offsets = @($a.Core.MarkOffsets())
            $c3 = $a.Core.MotionClock
            $out.Clock = @($c1, $c2, $c3)
            $out.SettleMs = $a.Core.Settle()
            $out.SettleAgain = $a.Core.Settle()
            [System.Threading.Thread]::Sleep(450)
            $out.Home = @($a.Core.MarkOffsets())
            Close-Splash $a

            # --- pulse, with the first triangle held still ------------------
            $b = Show-SlantSplash -Chrome $chrome -Logo $Mark -Text 'starting' -Motion pulse `
                                  -MotionOptions @{{ Still = @(0); Arrive = 0; Period = 1.5 }}
            [System.Threading.Thread]::Sleep(250)
            $out.PulseWays = $b.Core.MarkWays
            $out.PulseOffsets = @($b.Core.MarkOffsets())
            Close-Splash $b

            # --- the smooth curve: the same ends, a rest at either one -------
            $sm = Show-SlantSplash -Chrome $chrome -Logo $Mark -Text 'starting' -Motion pulse `
                                   -MotionOptions @{{ Arrive = 0; Period = 3.0; Curve = 'smooth' }}
            [System.Threading.Thread]::Sleep(250)
            $sa = $sm.Core.MotionClock
            $out.SmoothOffsets = @($sm.Core.MarkOffsets())
            $sb = $sm.Core.MotionClock
            $out.SmoothClock = @($sa, $sb)
            Close-Splash $sm

            # --- flow, the choreography -------------------------------------
            $fl = Show-SlantSplash -Chrome $chrome -Logo $Mark -Text 'starting' -Motion flow
            [System.Threading.Thread]::Sleep(250)
            $out.FlowParts = $fl.Core.MarkParts
            $out.FlowMoving = $fl.Core.MarkMoving
            $out.FlowWays = $fl.Core.MarkWays
            $fa = $fl.Core.MotionClock
            [System.Threading.Thread]::Sleep(400)
            $fb = $fl.Core.MotionClock
            $out.FlowClock = @($fa, $fb)
            $out.FlowSteps = @($fl.Core.MarkFlowSteps(0.4, 8.0, 0.001))
            $fr1 = $fl.Core.FlowTime
            $fl.Core.MotionFromNow()
            [System.Threading.Thread]::Sleep(120)
            $out.FlowRestart = @($fr1, $fl.Core.FlowTime)
            $out.FlowSettle = $fl.Core.Settle()
            Close-Splash $fl

            # --- flow held until the window is uncovered (Wait) --------------
            $fw = Show-SlantSplash -Chrome $chrome -Logo $Mark -Text 'starting' -Motion flow `
                                   -MotionOptions @{{ Wait = $true }}
            [System.Threading.Thread]::Sleep(300)
            $out.WaitHeld = @($fw.Core.FlowHeld, $fw.Core.FlowTime)
            $fw.Core.MotionFromNow()
            [System.Threading.Thread]::Sleep(150)
            $out.WaitGone = @($fw.Core.FlowHeld, $fw.Core.FlowTime)
            Close-Splash $fw

            # --- no motion asked for: the mark is one image, as before -----
            $n = Show-SlantSplash -Chrome $chrome -Logo $Mark -Text 'starting'
            [System.Threading.Thread]::Sleep(150)
            $out.NoneParts = $n.Core.MarkParts
            $out.NoneSettle = $n.Core.Settle()
            Close-Splash $n

            # --- and Hide waits for the parts to come home ------------------
            $h = Show-SlantSplash -Chrome $chrome -Logo $Mark -Text 'starting' -Motion breathe `
                                  -MotionOptions @{{ Arrive = 0 }}
            [System.Threading.Thread]::Sleep(200)
            $h.Hide(120)
            # Timers, not Sleep: the screen is taken off on this thread, so a
            # Sleep here would keep it on whatever Hide did. A fade of 120 ms
            # with nothing to wait for is over well inside 220; with the parts
            # coming home first it has not started yet.
            $prima = New-Object System.Windows.Threading.DispatcherTimer
            $prima.Interval = [TimeSpan]::FromMilliseconds(220)
            $prima.add_Tick({{
                param($s2, $e2)
                $s2.Stop()
                $out.HiddenStillThere = $chrome.Body.Children.Contains($h.Element)
            }}.GetNewClosure())
            $prima.Start()
            $via = New-Object System.Windows.Threading.DispatcherTimer
            $via.Interval = [TimeSpan]::FromMilliseconds(900)
            $via.add_Tick({{
                param($s3, $e3)
                $s3.Stop()
                $out.HiddenLeftBehind = @($chrome.Body.Children |
                    Where-Object {{ $_ -is [SlantVisualHost] }}).Count
                $w.Close()
            }}.GetNewClosure())
            $via.Start()
        }} catch {{
            $out.Error = "$($_.Exception.Message) @ $($_.InvocationInfo.ScriptLineNumber)"
            $w.Close()
        }}
    }}.GetNewClosure())
    $t.Start()
}}.GetNewClosure())
[void]$w.ShowDialog()
$out | ConvertTo-Json -Depth 6 -Compress
"""


@pytest.fixture(scope="module")
def motion(tmp_path_factory) -> dict:
    folder = tmp_path_factory.mktemp("slantmotion")
    mark = folder / "mark.svg"
    mark.write_text(_MOTION_SVG, encoding="utf-8")
    return _probe(folder, "motion", _MOTION_PROBE, ("-Mark", str(mark)))


def test_the_motion_belongs_to_both_forms(motion):
    assert motion["MotionSets"] == ["__AllParameterSets"]
    assert motion["MotionOptionsSets"] == ["__AllParameterSets"]
    assert sorted(motion["Presets"]) == ["breathe", "flow", "none", "pulse"]


def test_flow_reads_the_same_parts_and_keeps_its_own_clock(motion):
    """The choreography moves the same parts on the same lines as the breath,
    from the drawing's own shapes; its frames come from the drawing thread, so
    the clock goes on while this one sleeps; and it comes home before a fade
    like the others."""
    assert motion["FlowParts"] == 4
    assert motion["FlowMoving"] == 3
    assert motion["FlowWays"] == motion["Ways"]
    a, b = motion["FlowClock"]
    assert 0.3 < (b - a) % 1.8 < 0.7, motion["FlowClock"]
    assert motion["FlowSettle"] > 0


def test_flow_never_jumps_and_starts_over_when_asked(motion):
    """Past the first rush of the entrance, no part moves more in a
    millisecond than the lift does at its fastest (2026-11-05: where the cycle
    took over, the last part jumped two hundredths of the mark's height in one
    frame, a hundred times the lift's pace). And MotionFromNow puts the
    entrance back at its start, for a window that was covered while the first
    of it went by."""
    d, s, rot, op, _ = motion["FlowSteps"]
    assert d < 0.0005, motion["FlowSteps"]
    assert s < 0.0015, motion["FlowSteps"]
    assert rot < 0.02, motion["FlowSteps"]
    assert op == 0, motion["FlowSteps"]
    before, after = motion["FlowRestart"]
    assert before > 0.5, motion["FlowRestart"]
    assert 0 < after < 0.4, motion["FlowRestart"]


def test_a_held_flow_draws_nothing_until_asked(motion):
    """Wait holds the entrance at its first frame, where nothing of the mark
    is drawn, until MotionFromNow (2026-11-05: restarted after the cover, the
    entrance had already run under it, and the first frames on screen showed
    the mark whole before it vanished and came in again)."""
    held, t = motion["WaitHeld"]
    assert held is True and t == 0, motion["WaitHeld"]
    held, t = motion["WaitGone"]
    assert held is False and 0 < t < 0.4, motion["WaitGone"]


def test_the_parts_are_read_off_the_drawing(motion):
    """Four shapes, three of them moving. The hub is second in the file and is
    found by sitting on the middle of the mark; each triangle moves along the
    line from the hub through its own centroid."""
    assert motion["Parts"] == 4
    assert motion["Moving"] == 3
    assert motion["Ways"] == "-1.000,0.000;still;1.000,0.000;0.000,1.000"


def test_the_mark_comes_up_whole_and_then_opens(motion):
    assert motion["AmountAtStart"] < 0.5
    assert motion["AmountOpen"] == pytest.approx(1.0)


def test_the_mark_moves_while_this_thread_is_held_down(motion):
    c1, c2, _ = motion["Clock"]
    gone = (c2 - c1) % 2.4
    assert 0.3 < gone < 0.7, motion["Clock"]


def test_each_part_is_where_the_formula_puts_it(motion):
    """d = height * (Offset + Amplitude * sin(2 pi t / 2.4 - k * 120 degrees)),
    on a mark 100 tall, with the hub at zero. The clock is read on both sides
    of the offsets, and the formula has to hold somewhere between the two."""
    import math
    _, c2, c3 = motion["Clock"]
    got = motion["Offsets"]
    assert got[1] == 0
    breath = 100 * 8.0 / 238.92

    def at(t):
        return [breath * (1 + math.sin(2 * math.pi * t / 2.4 - k * 2 * math.pi / 3))
                for k in range(3)]

    lo, hi = at(c2), at(c3)
    for g, a, b in zip([got[0], got[2], got[3]], lo, hi):
        assert min(a, b) - 0.05 <= g <= max(a, b) + 0.05, (got, lo, hi)


def test_the_parts_come_home_once_and_say_how_long_it_takes(motion):
    assert motion["SettleMs"] == 260
    assert motion["SettleAgain"] == 0
    assert all(abs(v) < 1e-6 for v in motion["Home"]), motion["Home"]


def test_pulse_moves_every_part_in_step_and_holds_the_ones_asked(motion):
    assert motion["PulseWays"] == "still;still;1.000,0.000;0.000,1.000"
    off = motion["PulseOffsets"]
    assert off[0] == 0 and off[1] == 0
    assert off[2] == pytest.approx(off[3], abs=1e-9)


def test_the_smooth_curve_rests_at_the_ends_and_keeps_the_cycle(motion):
    """The sine through a smoothstep: at a given time the part is where that
    formula puts it, which is never further out than the sine would take it,
    and the two ends (0 and twice the breath) are the same."""
    import math
    a, b = motion["SmoothClock"]
    got = motion["SmoothOffsets"]
    breath = 100 * 8.0 / 238.92

    def at(t):
        w = math.sin(2 * math.pi * t / 3.0)
        u = (1 + w) / 2
        u = u * u * (3 - 2 * u)
        return breath * (1 + (2 * u - 1))

    lo, hi = at(a), at(b)
    assert got[1] == 0
    for g in (got[0], got[2], got[3]):
        assert min(lo, hi) - 0.05 <= g <= max(lo, hi) + 0.05, (got, lo, hi)
        assert -1e-6 <= g <= 2 * breath + 1e-6


def test_no_motion_means_one_image_as_before(motion):
    assert motion["NoneParts"] == 0
    assert motion["NoneSettle"] == 0


def test_hide_waits_for_the_parts_and_then_takes_the_screen_off(motion):
    """220 ms after Hide the parts are still on their way home (260 ms), so
    the fade has not begun and the screen is there; a 120 ms fade with nothing
    to wait for would have been over by then. Once it has run, it is gone."""
    assert motion["HiddenStillThere"] is True
    assert motion["HiddenLeftBehind"] == 0


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


# ── the plain pill and the anchored dropdown ────────────────────────────────
# Two shapes for a dropdown of words only. The plain pill is the pill without
# its circle: same height, a radius of half of it, the caption and the chevron,
# and at a fixed width the caption is cut while the chevron stays at the right
# end. The anchored one opens from an element of the application's own (a word
# on a white page) and leaves that element exactly as it found it.
_PLAIN_PROBE = r"""
param()
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase
Import-Module '{module}' -Force

$out = [ordered]@{{}}
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
    <StackPanel x:Name="Row" Orientation="Vertical" HorizontalAlignment="Left" VerticalAlignment="Top" Margin="20">
      <Border x:Name="Word" Background="#FFF4EFE3" CornerRadius="10" Padding="10,1,9,2" HorizontalAlignment="Left">
        <TextBlock Text="Major revision" Foreground="#FF222222"/>
      </Border>
    </StackPanel>
  </Grid>
</Window>
'@
$w = [System.Windows.Markup.XamlReader]::Load((New-Object System.Xml.XmlNodeReader ([xml]$xaml)))
$row = $w.FindName('Row')
$word = $w.FindName('Word')

$voci = @(
    [PSCustomObject]@{{ Code = 'state'; Tag = 'by state' }},
    [PSCustomObject]@{{ Code = 'date'; Tag = 'by date of the last change, newest first' }},
    [PSCustomObject]@{{ Code = 'name'; Tag = 'by name' }})
$cambi = New-Object System.Collections.ArrayList
$plain = New-SlantPicker -Items $voci -Current 'date' -Plain -Width 180 `
    -OnChange {{ param($c) [void]$cambi.Add("p:$c") }}
[void]$row.Children.Add($plain.Element)
$short = New-SlantPicker -Items $voci -Current 'state' -Plain -Height 22
[void]$row.Children.Add($short.Element)

$scelte = @('Accept', 'Minor revision', 'Major revision', 'Reject') | ForEach-Object {{ [PSCustomObject]@{{ Code = $_; Tag = $_ }} }}
$anchored = New-SlantPicker -Items $scelte -Current 'Major revision' -Anchor $word `
    -OnChange {{ param($c) [void]$cambi.Add("a:$c") }}
[void]$row.Children.Add($anchored.Element)
$out.AnchorParentKept = [object]::ReferenceEquals($word.Parent, $row)
$out.AnchorTipBefore = "$($word.ToolTip)"

$w.add_ContentRendered({{
    $t = New-Object System.Windows.Threading.DispatcherTimer
    $t.Interval = [TimeSpan]::FromMilliseconds(250)
    $t.add_Tick({{
        param($s, $e)
        $s.Stop()
        try {{
            $giu = [System.Windows.UIElement]::PreviewMouseLeftButtonDownEvent
            $btn = $plain.Element.Children[0]
            $w.UpdateLayout()
            # Prime pays the first opening and leaves the dropdown shut
            $plain.Prime()
            $out.PrimedClosed = (-not $plain.IsDown() -and -not $plain.Popup.IsOpen)
            $out.PrimedOpacity = $plain.Popup.Child.Opacity
            $out.PrimedRows = $plain.Popup.Child.Child.Content.Children.Count
            $out.PlainHeight = $btn.ActualHeight
            $out.PlainWidth = $btn.ActualWidth
            $out.PlainRadius = $btn.CornerRadius.TopLeft
            $riga = $btn.Child
            $out.PlainChildren = @($riga.Children | ForEach-Object {{ $_.GetType().Name }})
            $out.PlainCircles = @($riga.Children | Where-Object {{ $_ -is [System.Windows.Controls.Border] -and $_.Visibility -eq 'Visible' }}).Count
            $sigla = @($riga.Children | Where-Object {{ $_ -is [System.Windows.Controls.TextBlock] }})[0]
            $out.PlainCaption = "$($sigla.Text)"
            $out.PlainTrimming = "$($sigla.TextTrimming)"
            $freccia = @($riga.Children | Where-Object {{ $_ -is [System.Windows.Shapes.Path] }})[0]
            $fx = $freccia.TransformToAncestor($btn).Transform((New-Object System.Windows.Point($freccia.ActualWidth, 0))).X
            $out.ChevronGapRight = $btn.ActualWidth - $fx
            $out.ShortHeight = $short.Element.Children[0].ActualHeight
            $out.ShortRadius = $short.Element.Children[0].CornerRadius.TopLeft

            Send-Press $btn $giu
            $w.UpdateLayout()
            $out.PlainOpen = $plain.IsDown()
            $lista = $plain.Popup.Child.Child.Content
            $out.PlainRows = $lista.Children.Count
            $sc = @($lista.Children | Where-Object {{ "$($_.Tag)" -eq 'name' }})[0]
            Send-Press $sc ([System.Windows.UIElement]::MouseLeftButtonUpEvent)
            $out.PlainCode = $plain.Code()
            $out.PlainAfter = $plain.IsDown()

            $fondo = "$($word.Background)"
            Send-Press $word $giu
            $w.UpdateLayout()
            $out.AnchorOpen = $anchored.IsDown()
            $out.AnchorBackgroundSame = ("$($word.Background)" -eq $fondo)
            $out.AnchorPlacement = [object]::ReferenceEquals($anchored.Popup.PlacementTarget, $word)
            $lista2 = $anchored.Popup.Child.Child.Content
            $out.AnchorRows = $lista2.Children.Count
            Send-Press $word $giu
            $out.AnchorSecond = $anchored.IsDown()
            Send-Press $word $giu
            $w.UpdateLayout()
            $sc2 = @($lista2.Children | Where-Object {{ "$($_.Tag)" -eq 'Reject' }})[0]
            Send-Press $sc2 ([System.Windows.UIElement]::MouseLeftButtonUpEvent)
            $out.AnchorCode = $anchored.Code()
            $out.AnchorAfter = $anchored.IsDown()
            $out.AnchorTipAfter = "$($word.ToolTip)"
            $out.AnchorParentAfter = [object]::ReferenceEquals($word.Parent, $row)
            $out.Changes = @($cambi)
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
def plain(tmp_path_factory) -> dict:
    return _probe(tmp_path_factory.mktemp("slantplain"), "plain", _PLAIN_PROBE)


def test_the_plain_pill_is_a_pill_without_a_circle(plain):
    """30 high with a radius of half of it, like the pill with the icon, and
    nothing in it but the caption and the chevron."""
    assert plain["PlainHeight"] == 30
    assert plain["PlainRadius"] == 15
    assert plain["PlainCircles"] == 0
    assert plain["ShortHeight"] == 22
    assert plain["ShortRadius"] == 11


def test_a_fixed_width_cuts_the_caption_and_keeps_the_chevron_at_the_end(plain):
    assert plain["PlainWidth"] == 180
    assert plain["PlainTrimming"] == "CharacterEllipsis"
    assert plain["PlainCaption"].startswith("by date")
    # the padding on the right is 10: the chevron ends there, not after the text
    assert plain["ChevronGapRight"] == pytest.approx(10, abs=1.0)


def test_prime_pays_the_first_opening_and_leaves_it_shut(plain):
    """Opened invisible and closed at once: afterwards nothing is down, the
    frame is opaque again for the real opening, and the rows are built."""
    assert plain["PrimedClosed"] is True
    assert plain["PrimedOpacity"] == 1
    assert plain["PrimedRows"] == 3


def test_the_plain_pill_opens_and_chooses_like_the_others(plain):
    assert plain["PlainOpen"] is True
    assert plain["PlainRows"] == 3
    assert plain["PlainCode"] == "name"
    assert plain["PlainAfter"] is False


def test_an_anchor_opens_the_dropdown_and_is_left_as_it_was(plain):
    """The word on the page keeps its colours, its place and its tooltip, and
    the press on it toggles the dropdown the way the picker's own button does."""
    assert plain["AnchorParentKept"] is True
    assert plain["AnchorOpen"] is True
    assert plain["AnchorBackgroundSame"] is True
    assert plain["AnchorPlacement"] is True
    assert plain["AnchorRows"] == 4
    assert plain["AnchorSecond"] is False
    assert plain["AnchorCode"] == "Reject"
    assert plain["AnchorAfter"] is False
    assert plain["AnchorTipAfter"] == plain["AnchorTipBefore"]
    assert plain["AnchorParentAfter"] is True
    assert plain["Changes"] == ["p:name", "a:Reject"]


# ── the disc in the pill ────────────────────────────────────────────────────
# The flag of a language in the circle of its pill, and the mark of an engine
# on its coin, measured on the pixels. The coin is painted magenta, which no
# flag has, so every pixel that is not magenta is drawing: its weight is how
# far it is from magenta (the antialiased rim weighs by its coverage), and from
# there the centroid, the area, the bounding box and the radius in eight
# directions. Measured at 1x, 2x and 3x, in the pill and in a row of the open
# dropdown, because those are two different discs that must look the same.
_DISC_PROBE = r"""
param([string]$Flag, [string]$Mark)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase
Import-Module '{module}' -Force
$out = [ordered]@{}

function Find-Coin($root, [double]$size) {
    $q = New-Object System.Collections.Queue; $q.Enqueue($root)
    while ($q.Count -gt 0) {
        $x = $q.Dequeue()
        if ($x -is [System.Windows.Controls.Border] -and $x.Width -eq $size -and $x.CornerRadius.TopLeft -eq $size / 2) { return $x }
        if ($x -is [System.Windows.Controls.Grid] -and "$($x.Tag)" -like 'slant-disc:*' -and $x.Width -eq $size) { return $x }
        $n = [System.Windows.Media.VisualTreeHelper]::GetChildrenCount($x)
        for ($i = 0; $i -lt $n; $i++) { $q.Enqueue([System.Windows.Media.VisualTreeHelper]::GetChild($x, $i)) }
    }
    return $null
}

function Measure-Coin($root, [double]$size, [double]$scale) {
    $coin = Find-Coin $root $size
    if (-not $coin) { return @{ Error = 'no coin' } }
    $magenta = New-Object System.Windows.Media.SolidColorBrush([System.Windows.Media.Color]::FromRgb(255, 0, 255))
    if ($coin -is [System.Windows.Controls.Border]) { $coin.Background = $magenta }
    else { $coin.Children[0].Fill = $magenta }
    # The bitmap is of the root of the tree the coin is in: the window, or
    # the popup's own root for a row of the open list. A child rendered on its
    # own comes with its offset inside its parent and lands off the bitmap,
    # and a VisualBrush frames what is drawn and not the layout box.
    $top = $coin
    while ($true) {
        $su = [System.Windows.Media.VisualTreeHelper]::GetParent($top)
        if ($null -eq $su) { break }
        $top = $su
    }
    $top.UpdateLayout()
    $p = $coin.TransformToAncestor($top).Transform((New-Object System.Windows.Point(0, 0)))
    $cx = ($p.X + $size / 2) * $scale; $cy = ($p.Y + $size / 2) * $scale
    $W = [int][Math]::Ceiling($top.ActualWidth * $scale); $H = [int][Math]::Ceiling($top.ActualHeight * $scale)
    $dpi = 96.0 * $scale
    $rtb = New-Object System.Windows.Media.Imaging.RenderTargetBitmap -ArgumentList $W, $H, $dpi, $dpi, ([System.Windows.Media.PixelFormats]::Pbgra32)
    $rtb.Render($top)
    $stride = $W * 4; $px = New-Object byte[] ($stride * $H)
    $rtb.CopyPixels($px, $stride, 0)
    $peso = { param($o) [Math]::Max([Math]::Max($px[$o + 1] / 255.0, (255 - $px[$o + 2]) / 255.0), (255 - $px[$o]) / 255.0) }
    $r = $size / 2 * $scale; $lim = $r - 0.75 * $scale
    $sx = 0.0; $sy = 0.0; $sw = 0.0; $x0 = 1e9; $x1 = -1e9; $y0 = 1e9; $y1 = -1e9
    for ($yy = [int]($cy - $r); $yy -le [int]($cy + $r); $yy++) {
        for ($xx = [int]($cx - $r); $xx -le [int]($cx + $r); $xx++) {
            $dx = $xx + 0.5 - $cx; $dy = $yy + 0.5 - $cy
            if ($dx * $dx + $dy * $dy -gt $lim * $lim) { continue }
            $w = & $peso ($yy * $stride + $xx * 4)
            if ($w -lt 0.03) { continue }
            $w = [Math]::Min(1.0, $w * 1.6)
            $sx += $w * ($xx + 0.5); $sy += $w * ($yy + 0.5); $sw += $w
            if ($w -ge 0.5) {
                if ($xx -lt $x0) { $x0 = $xx }; if ($xx + 1 -gt $x1) { $x1 = $xx + 1 }
                if ($yy -lt $y0) { $y0 = $yy }; if ($yy + 1 -gt $y1) { $y1 = $yy + 1 }
            }
        }
    }
    if ($sw -le 0) { return @{ Error = 'nothing drawn' } }
    $reach = @()
    foreach ($d in 0, 45, 90, 135, 180, 225, 270, 315) {
        $a = $d * [Math]::PI / 180.0; $t = 0.0
        while ($t -lt $r) {
            $xx = [int][Math]::Floor($cx + [Math]::Cos($a) * $t); $yy = [int][Math]::Floor($cy + [Math]::Sin($a) * $t)
            # 0.3 and not 0.5: two bands that meet on a fraction of a pixel
            # leave a seam a quarter transparent, and that is not the edge
            if ((& $peso ($yy * $stride + $xx * 4)) -lt 0.3) { break }
            $t += 0.25
        }
        $reach += [Math]::Round($t / $scale, 3)
    }
    return @{ CentroidX = ($sx / $sw - $cx) / $scale; CentroidY = ($sy / $sw - $cy) / $scale
              BoxX = (($x0 + $x1) / 2.0 - $cx) / $scale; BoxY = (($y0 + $y1) / 2.0 - $cy) / $scale
              BoxW = ($x1 - $x0) / $scale; BoxH = ($y1 - $y0) / $scale
              Area = $sw / ($scale * $scale); Reach = $reach }
}

try {
    $w = New-Object System.Windows.Window
    $w.WindowStyle = 'None'; $w.ShowInTaskbar = $false; $w.ShowActivated = $false
    $w.Left = -20000; $w.Top = -20000; $w.Width = 360; $w.Height = 200
    $w.Background = [System.Windows.Media.Brushes]::Black
    $g = New-Object System.Windows.Controls.Grid
    $w.Content = $g
    $w.Show()
    $flagImg = New-SlantVectorImage -Path $Flag
    $markImg = New-SlantVectorImage -Path $Mark
    foreach ($caso in @(
        @{ Name = 'flag'; Item = [PSCustomObject]@{ Code = 'f'; Tag = 'F'; Label = 'flag'; Disc = $flagImg } }
        @{ Name = 'mark'; Item = [PSCustomObject]@{ Code = 'm'; Tag = 'M'; Label = 'mark'; Disc = { $markImg }.GetNewClosure(); DiscFit = 'Contain' } })) {
        $pk = New-SlantPicker -Items @($caso.Item) -Current $caso.Item.Code -Pill
        $g.Children.Clear(); [void]$g.Children.Add($pk.Element)
        $w.UpdateLayout()
        $btn = $pk.Element.Children[0]
        foreach ($s in 1, 2, 3) { $out["$($caso.Name)Pill$s"] = Measure-Coin $btn 22 $s }
        $pk.Toggle()
        # the popup is a window of its own and lays itself out on the
        # dispatcher: everything queued above idle runs before this returns
        # and it comes in with a fade and from 96.5 per cent: measured during
        # those 210 ms it is a smaller, paler disc
        $sw0 = [Diagnostics.Stopwatch]::StartNew()
        while ($sw0.ElapsedMilliseconds -lt 450) {
            $w.Dispatcher.Invoke([action] { }, [System.Windows.Threading.DispatcherPriority]::ApplicationIdle)
            Start-Sleep -Milliseconds 15
        }
        $riga = $pk.Popup.Child.Child.Content.Children[0]
        $riga.UpdateLayout()
        foreach ($s in 1, 2, 3) { $out["$($caso.Name)Row$s"] = Measure-Coin $riga 18 $s }
        # and no thread of a border inside the disc: the only things in it
        # are the coin and the drawing
        $coin = Find-Coin $btn 22
        $out["$($caso.Name)Pieces"] = @($coin.Child.Children | ForEach-Object { $_.GetType().Name })
        $pk.Close()
    }
    $w.Close()
} catch { $out.Error = "$($_.Exception.Message) @ $($_.InvocationInfo.ScriptLineNumber)" }
$out | ConvertTo-Json -Depth 6 -Compress
"""

# a flag in the proportions of the real ones, 4:3, three bands; and a mark
# taller than it is wide, whose ears a disc filled edge to edge would cut off
_DISC_FLAG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480">
  <path fill="#009246" d="M0 0h213.3v480H0z"/>
  <path fill="#ffffff" d="M213.3 0h213.4v480H213.3z"/>
  <path fill="#ce2b37" d="M426.7 0H640v480H426.7z"/>
</svg>"""
_DISC_MARK = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <path fill="#FFFFFF" d="M8 2h3v6h2V2h3v20H8z"/>
</svg>"""


@pytest.fixture(scope="module")
def disc(tmp_path_factory) -> dict:
    folder = tmp_path_factory.mktemp("slantdisc")
    (folder / "flag.svg").write_text(_DISC_FLAG, encoding="utf-8")
    (folder / "mark.svg").write_text(_DISC_MARK, encoding="utf-8")
    script = (_DISC_PROBE.replace("{", "{{").replace("}", "}}")
              .replace("{{module}}", "{module}"))
    return _probe(folder, "disc", script,
                  ("-Flag", str(folder / "flag.svg"), "-Mark", str(folder / "mark.svg")))


@pytest.mark.parametrize("where", ["Pill", "Row"])
@pytest.mark.parametrize("scale", [1, 2, 3])
def test_a_flag_is_a_disc_centred_on_its_circle(disc, where, scale):
    """The centroid of the coloured area on the centre of the circle, within a
    tenth of a pixel at 3x (a quarter at 1x, where a pixel is a pixel); the
    area of a full disc of 14, and not the 14 by 12 the bordered box left
    behind, whose border stayed inside the circle as a flat band above and
    another below."""
    m = disc[f"flag{where}{scale}"]
    assert "Error" not in m, m
    tol = 0.1 if scale == 3 else 0.25
    assert abs(m["CentroidX"]) <= tol, m
    assert abs(m["CentroidY"]) <= tol, m
    assert abs(m["Area"] - 3.14159 * 49) <= 0.04 * 3.14159 * 49, m


@pytest.mark.parametrize("where", ["Pill", "Row"])
def test_the_disc_is_round_with_no_flat_sides(disc, where):
    """The radius walked out from the centre in eight directions, at 3x: a
    circle gives the same number eight times, a disc with a band across the top
    gives a short one straight up and straight down."""
    reach = disc[f"flag{where}3"]["Reach"]
    assert max(reach) - min(reach) <= 0.34, reach
    assert min(reach) >= 6.6, reach


def test_nothing_but_the_coin_and_the_drawing_is_in_the_circle(disc):
    """No box with a border scaled into the circle: the drawing is the fill of
    an ellipse, so there is no thread of an outline to sit off centre."""
    assert disc["flagPieces"] == ["Ellipse"], disc["flagPieces"]
    assert disc["markPieces"] == ["Rectangle"], disc["markPieces"]


@pytest.mark.parametrize("where", ["Pill", "Row"])
@pytest.mark.parametrize("scale", [1, 2, 3])
def test_a_mark_sits_whole_and_centred_on_its_coin(disc, where, scale):
    """A mark is centred on its own bounds, not on its weight (a llama has its
    ears up top), and is never cut by the circle: its box is the inner square,
    taller than wide like the drawing, with room left all round."""
    m = disc[f"mark{where}{scale}"]
    assert "Error" not in m, m
    tol = 0.17 if scale == 3 else 0.5
    assert abs(m["BoxX"]) <= tol, m
    assert abs(m["BoxY"]) <= tol, m
    inner = 12
    assert m["BoxH"] <= inner + 0.5, m
    assert m["BoxH"] > m["BoxW"], m


# ── the strip under the band ────────────────────────────────────────────────
# Under the thin half of the band the bar has no colour of its own: it takes
# whatever is under it, like js/titlebar.js on the web. A window whose stage
# is surface-0 with a bar painted surface-1 above it shows a grey row under
# the band, and the band reads as twice as tall as it is.
_STRIP_PROBE = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase
Import-Module '{module}' -Force
$out = [ordered]@{}
$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        Width="900" Height="400" WindowStartupLocation="Manual" Left="-20000" Top="-20000"
        ShowInTaskbar="False" ShowActivated="False" Background="#0D0D0F">
  <Grid>
    <Grid.ColumnDefinitions><ColumnDefinition Width="300"/><ColumnDefinition/></Grid.ColumnDefinitions>
    <Border x:Name="Rail" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" Background="#101013"/>
    <Border Grid.Column="1" Background="#0D0D0F"><TextBlock Text="stage" Foreground="White"/></Border>
  </Grid>
</Window>
'@
$w = [System.Windows.Markup.XamlReader]::Load((New-Object System.Xml.XmlNodeReader ([xml]$xaml)))
$chrome = Install-SlantWindow -Window $w -Bold 'Slant' -Name ' check'
$w.add_ContentRendered({
    $t = New-Object System.Windows.Threading.DispatcherTimer
    $t.Interval = [TimeSpan]::FromMilliseconds(400)
    $t.add_Tick({
        param($s, $e)
        $s.Stop()
        try {
            $b = $chrome.Element.Background
            $out.Kind = $b.GetType().Name
            if ($b -is [System.Windows.Media.LinearGradientBrush]) {
                $out.Stops = @($b.GradientStops | ForEach-Object { "$($_.Color)@$([Math]::Round($_.Offset * $chrome.Body.ActualWidth))" })
            } else { $out.Colour = "$($b.Color)" }
            $sw = [Diagnostics.Stopwatch]::StartNew(); $chrome.StripColours = ''; $chrome.PaintStrip(); $out.PaintMs = [int]$sw.ElapsedMilliseconds
            # una pagina tutta di un colore
            $w.Content.Children[1].Children[0].Background = (New-Object System.Windows.Media.BrushConverter).ConvertFromString('#0D0D0F')
            $w.UpdateLayout()
            $sw = [Diagnostics.Stopwatch]::StartNew(); $chrome.PaintStrip(); $out.PaintOneMs = [int]$sw.ElapsedMilliseconds
            $b2 = $chrome.Element.Background
            $out.Kind2 = $b2.GetType().Name; $out.Colour2 = "$($b2.Color)"
        } catch { $out.Error = "$($_.Exception.Message) @ $($_.InvocationInfo.ScriptLineNumber)" }
        $w.Close()
    }.GetNewClosure())
    $t.Start()
}.GetNewClosure())
[void]$w.ShowDialog()
$out | ConvertTo-Json -Compress
"""


@pytest.fixture(scope="module")
def strip(tmp_path_factory) -> dict:
    script = (_STRIP_PROBE.replace("{", "{{").replace("}", "}}")
              .replace("{{module}}", "{module}"))
    return _probe(tmp_path_factory.mktemp("slantstrip"), "strip", script)


def test_the_strip_takes_the_colours_under_the_bar(strip):
    """A rail on the left and the stage on the right: the strip is the rail's
    colour as far as the rail goes, to the pixel, and the stage's after."""
    assert strip["Kind"] == "LinearGradientBrush", strip
    assert strip["Stops"] == ["#FF101013@0", "#FF101013@300",
                              "#FF0D0D0F@300", "#FF0D0D0F@900"], strip


def test_one_colour_under_the_bar_is_one_fill_and_cheap(strip):
    """The common case, a page of one colour, is three hit tests."""
    assert strip["Kind2"] == "SolidColorBrush", strip
    assert strip["Colour2"] == "#FF0D0D0F", strip
    assert strip["PaintOneMs"] < 50, strip


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
