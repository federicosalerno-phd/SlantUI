<#
  SlantUI for WPF.

  A PowerShell window written with WPF can wear this design without copying a
  hex value out of anything. The colours, the lengths and the band's four
  numbers come out of SlantUI.Tokens.psd1, which the Python writes, and the
  band's profile is built here by the same maths slantui/geometry.py uses.
  A test runs both and compares them, so the two cannot drift.

  Nothing here needs Python at run time. Copy this file and the .psd1 next to
  an application and it works on a machine that has never heard of the
  library.

      Import-Module .\SlantUI.psm1

      $b = Get-SlantBrushes                      # the default palette
      $window.Background = $b['surface-0']
      $header.Background = $b['surface-1']
      $label.Foreground  = $b['text-2']

      # the oblique band, across a title bar 1040 wide whose name ends at 210
      $path.Data = Get-SlantBandGeometry -Width 1040 -BrandWidth 210

  A window can wear the whole thing instead of borrowing its colours. One
  call takes a window an application has already built, takes its Windows
  frame off, and puts the band above what was inside it:

      $chrome = Install-SlantWindow -Window $window -Bold 'My' -Name ' App'

  The window is then frameless, it drags by its band, it resizes from its
  eight edges, and it maximises onto the work area without ever being zoomed
  by Windows. The credit line the licence asks for is written by this module
  and not by the application. Read the notes above Install-SlantWindow before
  changing any of it.

  WPF is loaded only by the calls that draw. Get-SlantPalette and
  Get-SlantMetric work in any PowerShell, including one with no display.
#>

Set-StrictMode -Version 2.0

$script:SlantData = $null
$script:SlantBrushCache = @{}

function Get-SlantDataPath {
    <#  .SYNOPSIS  The data file this module reads.  #>
    Join-Path $PSScriptRoot 'SlantUI.Tokens.psd1'
}

function Get-SlantTokens {
    <#  .SYNOPSIS  The whole data file: roles, metrics, band, palettes.
        Read once and kept, because a window asks for a colour hundreds of
        times while it is being built.  #>
    if ($null -eq $script:SlantData) {
        $script:SlantData = Import-PowerShellDataFile -Path (Get-SlantDataPath)
    }
    return $script:SlantData
}

function Get-SlantPaletteNames {
    <#  .SYNOPSIS  Every palette this library ships, by slug.  #>
    @((Get-SlantTokens).Palettes.Keys | Sort-Object)
}

function Resolve-SlantSlug([string]$Slug) {
    $t = Get-SlantTokens
    if ([string]::IsNullOrWhiteSpace($Slug)) { return $t.Default }
    if (-not $t.Palettes.ContainsKey($Slug)) {
        throw "No palette called '$Slug'. Known: $((Get-SlantPaletteNames) -join ', ')"
    }
    return $Slug
}

function Get-SlantPalette {
    <#  .SYNOPSIS  One palette: a role to CSS hex map, with the WPF form beside it.
        .EXAMPLE   (Get-SlantPalette).Values['accent']        #>
    param([string]$Slug)
    (Get-SlantTokens).Palettes[(Resolve-SlantSlug $Slug)]
}

function Get-SlantColor {
    <#  .SYNOPSIS  One role as a hex string WPF parses, alpha first.  #>
    param([Parameter(Mandatory = $true)][string]$Role, [string]$Slug)
    $p = Get-SlantPalette $Slug
    if (-not $p.Wpf.ContainsKey($Role)) {
        throw "No role called '$Role'. The vocabulary is in Get-SlantTokens().Roles"
    }
    $p.Wpf[$Role]
}

function Get-SlantMetric {
    <#  .SYNOPSIS  One length, as a number with no unit on it.
        .EXAMPLE   Get-SlantMetric 'tbar-h'      44  #>
    param([Parameter(Mandatory = $true)][string]$Name)
    $t = Get-SlantTokens
    if (-not $t.MetricNumbers.ContainsKey($Name)) {
        if ($t.Fonts.ContainsKey($Name)) { return $t.Fonts[$Name] }
        throw "No metric called '$Name'. Known: $(($t.MetricNumbers.Keys | Sort-Object) -join ', ')"
    }
    $t.MetricNumbers[$Name]
}

# ── the drawing half. WPF is loaded here and nowhere above. ─────────────────
function Initialize-SlantWpf {
    if (-not ('System.Windows.Media.Brush' -as [type])) {
        Add-Type -AssemblyName PresentationCore
        Add-Type -AssemblyName PresentationFramework
        Add-Type -AssemblyName WindowsBase
    }
}

function New-SlantBrush {
    <#  .SYNOPSIS  A frozen SolidColorBrush from a hex string.
        Takes either form: #AARRGGBB as this module's data carries it, or the
        #RRGGBBAA a stylesheet would, with the alpha moved for you.  #>
    param([Parameter(Mandatory = $true)][string]$Hex)
    Initialize-SlantWpf
    $h = $Hex.TrimStart('#')
    if ($h.Length -eq 3) { $h = ($h.ToCharArray() | ForEach-Object { "$_$_" }) -join '' }
    $c = [System.Windows.Media.ColorConverter]::ConvertFromString('#' + $h)
    $brush = New-Object System.Windows.Media.SolidColorBrush $c
    $brush.Freeze()
    return $brush
}

function ConvertTo-SlantColorRef {
    <#  .SYNOPSIS  A role as the integer Windows wants, 0x00BBGGRR.

        The DWM takes its colours as a COLORREF and not as a string, and it
        puts the channels in the other order: DwmSetWindowAttribute with
        CAPTION_COLOR, TEXT_COLOR or BORDER_COLOR is the one place an
        application hands Windows a colour by number. Getting the order
        wrong paints the caption in the complement of what was meant, which
        reads as a broken window and not as a typo.

        .EXAMPLE
            $ref = ConvertTo-SlantColorRef (Get-SlantColor 'surface-0')
            [void][Desk.Shell]::DwmSetWindowAttribute($h, 35, [ref]$ref, 4)  #>
    param([Parameter(Mandatory = $true)][string]$Hex)
    $h = $Hex.TrimStart('#')
    if ($h.Length -eq 3) { $h = ($h.ToCharArray() | ForEach-Object { "$_$_" }) -join '' }
    if ($h.Length -eq 8) { $h = $h.Substring(2) }      # #AARRGGBB: the alpha goes
    if ($h.Length -ne 6) { throw "not a colour: '$Hex'" }
    $r = [Convert]::ToInt32($h.Substring(0, 2), 16)
    $g = [Convert]::ToInt32($h.Substring(2, 2), 16)
    $b = [Convert]::ToInt32($h.Substring(4, 2), 16)
    return ($b -shl 16) -bor ($g -shl 8) -bor $r
}

function Get-SlantBrushes {
    <#  .SYNOPSIS  Every role of a palette as a frozen brush, by role name.
        .EXAMPLE   $b = Get-SlantBrushes; $win.Background = $b['surface-0']  #>
    param([string]$Slug)
    $slug = Resolve-SlantSlug $Slug
    if ($script:SlantBrushCache.ContainsKey($slug)) { return $script:SlantBrushCache[$slug] }
    $p = Get-SlantPalette $slug
    $out = @{}
    foreach ($role in $p.Wpf.Keys) { $out[$role] = New-SlantBrush $p.Wpf[$role] }
    $script:SlantBrushCache[$slug] = $out
    return $out
}

# ── the band ────────────────────────────────────────────────────────────────
# The profile and the rounding are slantui/geometry.py, line for line. Keep
# them that way: tests/test_wpf.py runs this module and that module on the
# same widths and compares the paths.

function Format-SlantCoord([double]$v) {
    <#  A coordinate to two places, the way a browser's toFixed writes it:
        the closest two place number to the value the double actually holds,
        and the larger one on a tie.

        Two shortcuts look like that and are not. Multiplying by a hundred
        first turns 2.67499999999999982 into exactly 267.5 on the way, and
        answers 2.68 where a browser says 2.67. Math.Round on the double has
        its own version of the same trouble. So the double is written out at
        full precision, where G17 tells one double from the next, and the
        rounding happens in decimal, which is exact.  #>
    $inv = [Globalization.CultureInfo]::InvariantCulture
    $d = [decimal]::Parse($v.ToString('G17', $inv), [Globalization.NumberStyles]::Float, $inv)
    $r = [Math]::Round($d, 2, [MidpointRounding]::AwayFromZero)
    if ($r -eq 0) { $r = [Math]::Abs($r) }
    return $r.ToString('0.00', $inv)
}

function Get-SlantBandPoints {
    <#  .SYNOPSIS  The six vertices of the band, clockwise from the top left.
        Width is the window's, BrandWidth is where the application's name
        ends: the oblique starts there, so the band is cut to the real
        layout and never to a guess.  #>
    param(
        [Parameter(Mandatory = $true)][double]$Width,
        [Parameter(Mandatory = $true)][double]$BrandWidth,
        [double]$Height = 0, [double]$Thin = 0, [double]$Slant = 0, [double]$Join = -1
    )
    if ($Height -le 0) { $Height = [double](Get-SlantMetric 'tbar-h') }
    if ($Thin -le 0) { $Thin = [double](Get-SlantMetric 'tbar-thin') }
    if ($Slant -le 0) { $Slant = [double](Get-SlantMetric 'tbar-slant') }
    if ($Join -lt 0) { $Join = [double](Get-SlantMetric 'tbar-join') }

    $x1 = $BrandWidth
    $x2 = [Math]::Min($Width, $x1 + $Slant)
    return @(
        @{ X = 0.0;    Y = 0.0;     R = 0.0 },
        @{ X = $Width; Y = 0.0;     R = 0.0 },
        @{ X = $Width; Y = $Thin;   R = 0.0 },
        @{ X = $x2;    Y = $Thin;   R = $Join },
        @{ X = $x1;    Y = $Height; R = $Join },
        @{ X = 0.0;    Y = $Height; R = 0.0 }
    )
}

function Get-SlantRoundedPolyPath {
    <#  .SYNOPSIS  A closed path through the points, each corner rounded by
        its own R. The corner is a quadratic whose control point is the
        vertex, trimmed to half the shorter of the two sides.  #>
    param([Parameter(Mandatory = $true)][array]$Points)
    $n = $Points.Count
    $sb = New-Object System.Text.StringBuilder
    for ($i = 0; $i -lt $n; $i++) {
        $cur = $Points[$i]
        $prev = $Points[(($i - 1) + $n) % $n]
        $next = $Points[($i + 1) % $n]
        $head = 'L'
        if ($i -eq 0) { $head = 'M' }
        if ($cur.R -le 0) {
            [void]$sb.Append(('{0}{1},{2} ' -f $head, (Format-SlantCoord $cur.X), (Format-SlantCoord $cur.Y)))
            continue
        }
        $v1x = $prev.X - $cur.X; $v1y = $prev.Y - $cur.Y
        $v2x = $next.X - $cur.X; $v2y = $next.Y - $cur.Y
        $l1 = [Math]::Sqrt($v1x * $v1x + $v1y * $v1y); if ($l1 -eq 0) { $l1 = 1.0 }
        $l2 = [Math]::Sqrt($v2x * $v2x + $v2y * $v2y); if ($l2 -eq 0) { $l2 = 1.0 }
        $a = [Math]::Min($cur.R, $l1 / 2); $b = [Math]::Min($cur.R, $l2 / 2)
        $p1x = $cur.X + $v1x / $l1 * $a; $p1y = $cur.Y + $v1y / $l1 * $a
        $p2x = $cur.X + $v2x / $l2 * $b; $p2y = $cur.Y + $v2y / $l2 * $b
        [void]$sb.Append(('{0}{1},{2} ' -f $head, (Format-SlantCoord $p1x), (Format-SlantCoord $p1y)))
        [void]$sb.Append(('Q{0},{1} {2},{3} ' -f (Format-SlantCoord $cur.X), (Format-SlantCoord $cur.Y),
                                                 (Format-SlantCoord $p2x), (Format-SlantCoord $p2y)))
    }
    [void]$sb.Append('Z')
    return $sb.ToString()
}

function Get-SlantBandPath {
    <#  .SYNOPSIS  The band as one path string, in the SVG mini language.
        The same string the page puts in clip-path, which is the point: one
        set of numbers, two renderers.  #>
    param(
        [Parameter(Mandatory = $true)][double]$Width,
        [Parameter(Mandatory = $true)][double]$BrandWidth,
        [double]$Height = 0, [double]$Thin = 0, [double]$Slant = 0, [double]$Join = -1
    )
    Get-SlantRoundedPolyPath (Get-SlantBandPoints -Width $Width -BrandWidth $BrandWidth `
        -Height $Height -Thin $Thin -Slant $Slant -Join $Join)
}

function Get-SlantBandGeometry {
    <#  .SYNOPSIS  The same profile as a WPF Geometry, ready for a Path's Data
        or for a Border's Clip.  #>
    param(
        [Parameter(Mandatory = $true)][double]$Width,
        [Parameter(Mandatory = $true)][double]$BrandWidth,
        [double]$Height = 0, [double]$Thin = 0, [double]$Slant = 0, [double]$Join = -1
    )
    Initialize-SlantWpf
    $d = Get-SlantBandPath -Width $Width -BrandWidth $BrandWidth `
        -Height $Height -Thin $Thin -Slant $Slant -Join $Join
    $g = [System.Windows.Media.Geometry]::Parse($d)
    $g.Freeze()
    return $g
}


# ── the window ──────────────────────────────────────────────────────────────
# Everything above draws with the design. This draws the window itself: a
# frameless WPF window whose title bar is the oblique band, with the name on
# the left, the credit line the licence asks for in the middle, and the
# window buttons on the right.
#
#     $chrome = Install-SlantWindow -Window $w -Bold 'My' -Name ' App'
#
# takes a window an application has already built and puts the title bar
# above whatever was inside it, so the application's own layout is untouched
# and gains a row. What comes back carries the parts and the state changes.
#
# Three things in here are not obvious and each has a reason written above it:
# the real Win32 frame behind a frameless window, the hit test that gives the
# edges back, and a maximise that never zooms.

$script:SlantChromeReady = $false
$script:SlantCreditText = 'Layout by Federico Salerno'

# The window procedure is C# and not PowerShell, and that is not a taste.
# A scriptblock converted to a delegate is handed a copy of a parameter
# passed by reference, so the `handled` flag an HwndSource hook sets never
# reaches the caller and WM_NCCALCSIZE goes on being answered by Windows.
# Measured on 2026-09-18: the flag reads back true inside the scriptblock
# and the frame is still there. A subclass whose procedure is compiled has
# no such gap, and it is the same technique the browsers use.
$script:SlantChromeSource = @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

namespace SlantUI
{
    // The Win32 side of a frameless window: the frame that is there so the
    // window still animates, the messages that hide it again, and the edges
    // given back by hand.
    public static class Chrome
    {
        public delegate IntPtr SubclassProc(IntPtr h, uint msg, IntPtr w, IntPtr l, IntPtr id, IntPtr data);

        [DllImport("comctl32.dll")]
        static extern bool SetWindowSubclass(IntPtr h, SubclassProc p, IntPtr id, IntPtr data);
        [DllImport("comctl32.dll")]
        static extern bool RemoveWindowSubclass(IntPtr h, SubclassProc p, IntPtr id);
        [DllImport("comctl32.dll")]
        static extern IntPtr DefSubclassProc(IntPtr h, uint msg, IntPtr w, IntPtr l);
        [DllImport("user32.dll", EntryPoint = "GetWindowLongPtrW")]
        static extern IntPtr GetWindowLongPtr(IntPtr h, int index);
        [DllImport("user32.dll", EntryPoint = "SetWindowLongPtrW")]
        static extern IntPtr SetWindowLongPtr(IntPtr h, int index, IntPtr value);
        [DllImport("user32.dll")]
        static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
        [DllImport("user32.dll")]
        static extern bool GetWindowRect(IntPtr h, out RECT r);
        [DllImport("user32.dll")]
        static extern bool GetClientRect(IntPtr h, out RECT r);
        [DllImport("user32.dll")]
        static extern IntPtr MonitorFromWindow(IntPtr h, int flags);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        static extern bool GetMonitorInfoW(IntPtr monitor, ref MONITORINFO mi);
        [DllImport("user32.dll")]
        public static extern bool IsZoomed(IntPtr h);
        [DllImport("dwmapi.dll")]
        static extern int DwmSetWindowAttribute(IntPtr h, int attr, ref int value, int size);

        [StructLayout(LayoutKind.Sequential)]
        public struct RECT { public int Left, Top, Right, Bottom; }
        [StructLayout(LayoutKind.Sequential)]
        struct MONITORINFO { public int cbSize; public RECT rcMonitor; public RECT rcWork; public int dwFlags; }

        const int GWL_STYLE = -16;
        // caption, thickframe, minimize box, maximize box, system menu
        const long WS_FRAME = 0x00C00000L | 0x00040000L | 0x00020000L | 0x00010000L | 0x00080000L;
        const uint SWP_FRAMECHANGED = 0x0020 | 0x0002 | 0x0001 | 0x0004 | 0x0010;
        const uint WM_NCDESTROY = 0x0082;
        const uint WM_NCCALCSIZE = 0x0083;
        const uint WM_NCHITTEST = 0x0084;
        const uint WM_NCACTIVATE = 0x0086;
        const uint WM_SYSCOMMAND = 0x0112;

        class Win
        {
            public int Border;
            public int Corner;
            public bool Resize;
            public bool Max;
            public Func<IntPtr, int, bool> OnCommand;
            public SubclassProc Proc;
        }

        static readonly Dictionary<IntPtr, Win> _windows = new Dictionary<IntPtr, Win>();
        // The delegate handed to SetWindowSubclass is called from native code
        // long after this method returns, so a reference has to outlive it.
        static readonly List<SubclassProc> _keep = new List<SubclassProc>();

        static Win Of(IntPtr h)
        {
            Win s;
            lock (_windows) { _windows.TryGetValue(h, out s); }
            return s;
        }

        // Give the window the frame styles it needs to be animated by Windows
        // when it minimises, restores and closes, subclass it so the caption
        // and the borders are never laid out, and ask the DWM for the rounded
        // corners a frameless window has to ask for and for no outline.
        public static void Dress(IntPtr h, int border, int corner, bool resize)
        {
            bool first;
            SubclassProc old = null;
            lock (_windows)
            {
                Win had;
                first = !_windows.TryGetValue(h, out had);
                if (had != null) { old = had.Proc; }
                _windows[h] = new Win { Border = border, Corner = corner, Resize = resize };
            }
            if (first)
            {
                SubclassProc p = Proc;
                lock (_keep) { _keep.Add(p); }
                lock (_windows) { _windows[h].Proc = p; }
                SetWindowSubclass(h, p, (IntPtr)1, IntPtr.Zero);
            }
            else
            {
                lock (_windows) { _windows[h].Proc = old; }
            }
            long style = GetWindowLongPtr(h, GWL_STYLE).ToInt64() | WS_FRAME;
            SetWindowLongPtr(h, GWL_STYLE, (IntPtr)style);
            SetWindowPos(h, IntPtr.Zero, 0, 0, 0, 0, SWP_FRAMECHANGED);
            int round = 2;
            DwmSetWindowAttribute(h, 33, ref round, 4);      // DWMWA_WINDOW_CORNER_PREFERENCE
            int none = -2;
            DwmSetWindowAttribute(h, 34, ref none, 4);       // DWMWA_BORDER_COLOR, none at all
        }

        // Take the subclass off and drop the callback. A window that is going
        // away must not be left with a procedure pointing at managed code:
        // the process can be told to stop the moment one arrives after that.
        public static void Forget(IntPtr h)
        {
            Win s;
            lock (_windows)
            {
                if (!_windows.TryGetValue(h, out s)) { return; }
                _windows.Remove(h);
            }
            s.OnCommand = null;
            if (s.Proc != null)
            {
                RemoveWindowSubclass(h, s.Proc, (IntPtr)1);
                lock (_keep) { _keep.Remove(s.Proc); }
            }
        }
        public static bool Knows(IntPtr h) { return Of(h) != null; }

        public static void OnSysCommand(IntPtr h, Func<IntPtr, int, bool> f)
        {
            Win s = Of(h); if (s != null) s.OnCommand = f;
        }
        public static void SetMaximized(IntPtr h, bool on) { Win s = Of(h); if (s != null) s.Max = on; }
        public static void SetResizable(IntPtr h, bool on) { Win s = Of(h); if (s != null) s.Resize = on; }
        public static void SetDark(IntPtr h, bool dark)
        {
            int v = dark ? 1 : 0;
            DwmSetWindowAttribute(h, 20, ref v, 4);          // DWMWA_USE_IMMERSIVE_DARK_MODE
        }
        // Windows' own state transitions scale a snapshot of the last frame,
        // which for a window like this one reads as a jump. A window that
        // animates its own geometry switches them off around the change so
        // nothing plays twice.
        public static void SetTransitions(IntPtr h, bool on)
        {
            int v = on ? 0 : 1;
            DwmSetWindowAttribute(h, 3, ref v, 4);           // DWMWA_TRANSITIONS_FORCEDISABLED
        }

        public static long Style(IntPtr h)
        {
            return GetWindowLongPtr(h, GWL_STYLE).ToInt64() & 0xFFFFFFFFL;
        }
        public static string Describe(IntPtr h)
        {
            RECT w, c;
            GetWindowRect(h, out w); GetClientRect(h, out c);
            return string.Format("style=0x{0:X8} window={1}x{2} client={3}x{4} zoomed={5}",
                Style(h), w.Right - w.Left, w.Bottom - w.Top,
                c.Right - c.Left, c.Bottom - c.Top, IsZoomed(h));
        }
        public static RECT Window(IntPtr h) { RECT r; GetWindowRect(h, out r); return r; }
        public static RECT Client(IntPtr h) { RECT r; GetClientRect(h, out r); return r; }
        public static RECT WorkArea(IntPtr h)
        {
            MONITORINFO mi = new MONITORINFO();
            mi.cbSize = Marshal.SizeOf(typeof(MONITORINFO));
            RECT r = new RECT();
            IntPtr m = MonitorFromWindow(h, 2);              // MONITOR_DEFAULTTONEAREST
            if (m != IntPtr.Zero && GetMonitorInfoW(m, ref mi)) { r = mi.rcWork; }
            return r;
        }

        // What a hit at this screen point would be. Public so a test can ask
        // without a mouse: Hit(h, x, y).
        public static int Hit(IntPtr h, int x, int y)
        {
            return HitTest(h, (IntPtr)(((long)y << 16) | ((long)x & 0xFFFF)));
        }

        // The window says the client area is the whole window, so Windows no
        // longer finds a border to grab. The eight edges are handed back
        // here instead, by measuring against the window rectangle. A
        // maximised window has none, as a maximised window should.
        static int HitTest(IntPtr h, IntPtr l)
        {
            Win s = Of(h);
            if (s == null || !s.Resize || s.Max) return 1;           // HTCLIENT
            long p = l.ToInt64();
            int x = (int)(short)(p & 0xFFFF);
            int y = (int)(short)((p >> 16) & 0xFFFF);
            RECT r; GetWindowRect(h, out r);
            int b = s.Border, c = s.Corner;
            bool left = x < r.Left + b, right = x >= r.Right - b;
            bool top = y < r.Top + b, bottom = y >= r.Bottom - b;
            bool leftish = x < r.Left + c, rightish = x >= r.Right - c;
            bool topish = y < r.Top + c, bottomish = y >= r.Bottom - c;
            if ((top && leftish) || (left && topish)) return 13;     // HTTOPLEFT
            if ((top && rightish) || (right && topish)) return 14;   // HTTOPRIGHT
            if ((bottom && leftish) || (left && bottomish)) return 16;
            if ((bottom && rightish) || (right && bottomish)) return 17;
            if (left) return 10;
            if (right) return 11;
            if (top) return 12;
            if (bottom) return 15;
            return 1;
        }

        static IntPtr Proc(IntPtr h, uint msg, IntPtr w, IntPtr l, IntPtr id, IntPtr data)
        {
            // The window is going for good. Let it finish being destroyed and
            // then take this procedure off it, which is the one moment the
            // documentation names and the one a window closed by Windows and
            // not by the application would otherwise miss.
            if (msg == WM_NCDESTROY)
            {
                IntPtr answer = DefSubclassProc(h, msg, w, l);
                Forget(h);
                return answer;
            }
            // The client area is the whole window, which is what takes the
            // caption and the borders out of the layout while their styles,
            // and with them the animations and the shadow, stay on.
            if (msg == WM_NCCALCSIZE && w != IntPtr.Zero) return IntPtr.Zero;
            // Say the caption is still active, so nothing repaints one.
            if (msg == WM_NCACTIVATE) return DefSubclassProc(h, msg, w, (IntPtr)(-1));
            if (msg == WM_NCHITTEST) return (IntPtr)HitTest(h, l);
            if (msg == WM_SYSCOMMAND)
            {
                Win s = Of(h);
                if (s != null && s.OnCommand != null)
                {
                    int cmd = (int)(w.ToInt64() & 0xFFF0);
                    // The window maximises itself, so Win+Up, Win+Down and
                    // the taskbar menu are offered to it first. An exception
                    // in an application's handler must not take the window
                    // procedure with it.
                    try { if (s.OnCommand(h, cmd)) return IntPtr.Zero; } catch { }
                }
            }
            return DefSubclassProc(h, msg, w, l);
        }
    }
}
'@

function Initialize-SlantChrome {
    <#  .SYNOPSIS  Compile the window procedure, once for the process.  #>
    if ($script:SlantChromeReady) { return }
    Initialize-SlantWpf
    if (-not ('SlantUI.Chrome' -as [type])) {
        Add-Type -TypeDefinition $script:SlantChromeSource
    }
    $script:SlantChromeReady = $true
}

function Get-SlantCreditText {
    <#  .SYNOPSIS  The line the licence puts in the title bar.
        It is written by the library and not by the application, which is
        the point of it. See LICENSE, condition 2.  #>
    $script:SlantCreditText
}

function Set-SlantWindowFrame {
    <#  .SYNOPSIS  Give a window handle the frame styles and the subclass.
        .PARAMETER Border  How far from an edge a drag resizes, in pixels.
        .PARAMETER Corner  How far from a corner a drag resizes both ways.  #>
    param(
        [Parameter(Mandatory = $true)][IntPtr]$Handle,
        [int]$Border = 5, [int]$Corner = 12, [bool]$Resizable = $true)
    Initialize-SlantChrome
    [SlantUI.Chrome]::Dress($Handle, $Border, $Corner, $Resizable)
}

function Set-SlantWindowScheme {
    <#  .SYNOPSIS  Tell Windows whether this window is dark or light, so the
        shadow and anything the system still draws agree with the palette.  #>
    param([Parameter(Mandatory = $true)][IntPtr]$Handle, [string]$Palette)
    Initialize-SlantChrome
    [SlantUI.Chrome]::SetDark($Handle, ((Get-SlantPalette $Palette).Scheme -eq 'dark'))
}

function Set-SlantWindowTransitions {
    <#  .SYNOPSIS  Windows' own state animation, on or off.  #>
    param([Parameter(Mandatory = $true)][IntPtr]$Handle, [bool]$Enabled)
    Initialize-SlantChrome
    [SlantUI.Chrome]::SetTransitions($Handle, $Enabled)
}

function Test-SlantWindowZoomed {
    <#  .SYNOPSIS  Whether Windows has zoomed this window.
        It never should. A window carrying the frame styles is placed by
        Windows with its frame past the edge of the screen when it zooms,
        eleven pixels a side at 150 per cent, and for a window whose client
        area is the whole window that is eleven pixels of the page cut off
        on every side. So maximised is a state the window keeps, and this is
        the check that says the design still holds.  #>
    param([Parameter(Mandatory = $true)][IntPtr]$Handle)
    Initialize-SlantChrome
    [SlantUI.Chrome]::IsZoomed($Handle)
}

function Get-SlantWindowStyle {
    <#  .SYNOPSIS  The window's style word, for a test that wants to see the
        frame styles are really on.  #>
    param([Parameter(Mandatory = $true)][IntPtr]$Handle)
    Initialize-SlantChrome
    [SlantUI.Chrome]::Style($Handle)
}

function Get-SlantWindowSizes {
    <#  .SYNOPSIS  One line: the style, the window, the client area and the
        zoom state. A dressed window has a client area exactly its own size.  #>
    param([Parameter(Mandatory = $true)][IntPtr]$Handle)
    Initialize-SlantChrome
    [SlantUI.Chrome]::Describe($Handle)
}

function Get-SlantWindowHandle {
    <#  .SYNOPSIS  A window's HWND, or zero before it has one.  #>
    param([Parameter(Mandatory = $true)]$Window)
    Initialize-SlantWpf
    (New-Object System.Windows.Interop.WindowInteropHelper($Window)).Handle
}

function Get-SlantWorkArea {
    <#  .SYNOPSIS  The work area of the screen this window is on, in the
        units WPF lays out in.

        Windows answers in real pixels and WPF counts in its own, so the
        rectangle goes through the window's own device transform. Taking
        the scale off SystemParameters instead is right until the window is
        dragged onto a second screen at another scale.  #>
    param([Parameter(Mandatory = $true)]$Window)
    Initialize-SlantChrome
    $handle = Get-SlantWindowHandle $Window
    $r = [SlantUI.Chrome]::WorkArea($handle)
    $source = $null
    if ($handle -ne [IntPtr]::Zero) {
        $source = [System.Windows.Interop.HwndSource]::FromHwnd($handle)
    }
    if ($null -eq $source -or $null -eq $source.CompositionTarget) {
        return (New-Object System.Windows.Rect $r.Left, $r.Top,
                ($r.Right - $r.Left), ($r.Bottom - $r.Top))
    }
    $m = $source.CompositionTarget.TransformFromDevice
    $a = $m.Transform((New-Object System.Windows.Point $r.Left, $r.Top))
    $z = $m.Transform((New-Object System.Windows.Point $r.Right, $r.Bottom))
    return (New-Object System.Windows.Rect $a.X, $a.Y, ($z.X - $a.X), ($z.Y - $a.Y))
}

# ── the title bar ───────────────────────────────────────────────────────────
# The same parts the stylesheet gives a page, built as elements: the band,
# the brand on the left, the credit line centred in the thin half, a slot an
# application can put its own things in, and the window buttons.

# The glyphs are the ones js/titlebar.js draws, written in the path language
# both renderers read. A rectangle with a round corner is four lines and four
# arcs, which is what an SVG rect with an rx is once it is drawn.
$script:SlantGlyphs = @{
    Minimise = 'M2,6 L10,6'
    Close    = 'M3,3 L9,9 M9,3 L3,9'
    Maximise = 'M3.5,2.5 L8.5,2.5 A1,1 0 0 1 9.5,3.5 L9.5,8.5 A1,1 0 0 1 8.5,9.5 ' +
               'L3.5,9.5 A1,1 0 0 1 2.5,8.5 L2.5,3.5 A1,1 0 0 1 3.5,2.5 Z'
    Restore  = 'M2.8,4.2 L6.8,4.2 A1,1 0 0 1 7.8,5.2 L7.8,9.2 A1,1 0 0 1 6.8,10.2 ' +
               'L2.8,10.2 A1,1 0 0 1 1.8,9.2 L1.8,5.2 A1,1 0 0 1 2.8,4.2 Z ' +
               'M4.6,4.2 L4.6,2.8 A1,1 0 0 1 5.6,1.8 L9.2,1.8 A1,1 0 0 1 10.2,2.8 ' +
               'L10.2,6.4 A1,1 0 0 1 9.2,7.4 L8.8,7.4'
}

function New-SlantWindowButton {
    <#  .SYNOPSIS  One window button: a glyph on a fill that answers the
        pointer faster than it lets go, which is the design's motion rule
        and the same two durations the stylesheet uses.  #>
    param(
        [Parameter(Mandatory = $true)][string]$Glyph,
        [Parameter(Mandatory = $true)][string]$Tip,
        [Parameter(Mandatory = $true)][string]$Ink,
        [Parameter(Mandatory = $true)][string]$Hover,
        [Parameter(Mandatory = $true)][string]$HoverInk,
        [double]$Width = 42, [double]$Height = 28)
    Initialize-SlantWpf
    $inTime = [double](Get-SlantTokens).Times['t-in'] / 1000
    $outTime = [double](Get-SlantTokens).Times['t-out'] / 1000
    $inv = [Globalization.CultureInfo]::InvariantCulture
    $markup = @"
<ControlTemplate xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
                 xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" TargetType="Button">
  <Border x:Name="fill">
    <Border.Background><SolidColorBrush Color="#00000000"/></Border.Background>
    <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
  </Border>
  <ControlTemplate.Triggers>
    <Trigger Property="IsMouseOver" Value="True">
      <Setter Property="Foreground" Value="$HoverInk"/>
      <Trigger.EnterActions>
        <BeginStoryboard>
          <Storyboard>
            <ColorAnimation Storyboard.TargetName="fill" Storyboard.TargetProperty="Background.Color"
                            To="$Hover" Duration="0:0:$($inTime.ToString('0.000', $inv))">
              <ColorAnimation.EasingFunction><QuadraticEase EasingMode="EaseOut"/></ColorAnimation.EasingFunction>
            </ColorAnimation>
          </Storyboard>
        </BeginStoryboard>
      </Trigger.EnterActions>
      <Trigger.ExitActions>
        <BeginStoryboard>
          <Storyboard>
            <ColorAnimation Storyboard.TargetName="fill" Storyboard.TargetProperty="Background.Color"
                            To="#00000000" Duration="0:0:$($outTime.ToString('0.000', $inv))">
              <ColorAnimation.EasingFunction><QuadraticEase EasingMode="EaseOut"/></ColorAnimation.EasingFunction>
            </ColorAnimation>
          </Storyboard>
        </BeginStoryboard>
      </Trigger.ExitActions>
    </Trigger>
  </ControlTemplate.Triggers>
</ControlTemplate>
"@
    $button = New-Object System.Windows.Controls.Button
    $button.Width = $Width
    $button.Height = $Height
    $button.ToolTip = $Tip
    $button.Cursor = 'Hand'
    $button.Foreground = New-SlantBrush $Ink
    $button.FocusVisualStyle = $null
    $button.Template = [System.Windows.Markup.XamlReader]::Load(
        (New-Object System.Xml.XmlNodeReader ([xml]$markup)))
    $path = New-Object System.Windows.Shapes.Path
    $path.Data = [System.Windows.Media.Geometry]::Parse($Glyph)
    $path.StrokeThickness = 1.35
    $path.StrokeStartLineCap = 'Round'
    $path.StrokeEndLineCap = 'Round'
    $path.StrokeLineJoin = 'Round'
    $path.Width = 12
    $path.Height = 12
    $binding = New-Object System.Windows.Data.Binding 'Foreground'
    $binding.RelativeSource = New-Object System.Windows.Data.RelativeSource ([System.Windows.Data.RelativeSourceMode]::FindAncestor)
    $binding.RelativeSource.AncestorType = [System.Windows.Controls.Button]
    [void]$path.SetBinding([System.Windows.Shapes.Shape]::StrokeProperty, $binding)
    $button.Content = $path
    return $button
}

function New-SlantTitleBar {
    <#  .SYNOPSIS  The title bar as an element, with its parts.

        .PARAMETER Bold  The part of the name drawn in the strong ink, which
                         is usually the application's own word.
        .PARAMETER Name  The rest of it, in the quieter ink.
        .PARAMETER Logo  A path to an image, a brush, or nothing at all, in
                         which case the square is filled with the accent.

        What comes back has Element, Band, Brand, Logo, Name, Credit, Extras
        and Buttons on it. Extras is the slot for an application's own line
        of text or its own small control, next to the window buttons: it is
        the WPF answer to a page putting an element in its own title bar.  #>
    param(
        [string]$Bold = '', [string]$Name = '', $Logo = $null, [string]$Palette,
        [switch]$NoMinimize, [switch]$NoMaximize)
    Initialize-SlantWpf
    $slug = Resolve-SlantSlug $Palette
    $colour = (Get-SlantPalette $slug).Wpf
    $brush = Get-SlantBrushes $slug
    $tokens = Get-SlantTokens
    $tall = [double]$tokens.MetricNumbers['tbar-h']
    $thin = [double]$tokens.MetricNumbers['tbar-thin']
    $radius = [double]$tokens.MetricNumbers['r']

    $bar = New-Object System.Windows.Controls.Grid
    $bar.Height = $tall
    $bar.Background = $brush['surface-1']

    # The band. Its shape is set from the real width of the brand, which is
    # only known after the first layout pass, so Install-SlantWindow asks for
    # it again on every size change.
    $band = New-Object System.Windows.Shapes.Path
    $band.Fill = $brush['control']
    $band.IsHitTestVisible = $false
    [void]$bar.Children.Add($band)

    # The brand. The measured element is the border, because the padding is
    # part of where the name ends and the oblique begins.
    $brand = New-Object System.Windows.Controls.Border
    $brand.HorizontalAlignment = 'Left'
    $brand.VerticalAlignment = 'Stretch'
    $brand.Padding = New-Object System.Windows.Thickness 14, 0, 16, 0
    $brandRow = New-Object System.Windows.Controls.StackPanel
    $brandRow.Orientation = 'Horizontal'
    $brandRow.VerticalAlignment = 'Center'
    $brand.Child = $brandRow

    $mark = New-Object System.Windows.Controls.Border
    $mark.Width = 22
    $mark.Height = 22
    $mark.CornerRadius = New-Object System.Windows.CornerRadius $radius
    $mark.Margin = New-Object System.Windows.Thickness 0, 0, 11, 0
    $mark.VerticalAlignment = 'Center'
    $mark.Background = $brush['accent']
    $mark.SnapsToDevicePixels = $true
    if ($null -ne $Logo) { Set-SlantLogo -Element $mark -Logo $Logo }
    [void]$brandRow.Children.Add($mark)

    $title = New-Object System.Windows.Controls.TextBlock
    $title.FontFamily = New-Object System.Windows.Media.FontFamily $tokens.Fonts['font-brand']
    $title.FontSize = 14.5
    $title.Foreground = $brush['text-2']
    $title.VerticalAlignment = 'Center'
    $title.TextWrapping = 'NoWrap'
    if ($Bold -ne '') {
        $strong = New-Object System.Windows.Documents.Run $Bold
        $strong.FontWeight = 'SemiBold'
        $strong.Foreground = $brush['text-1']
        [void]$title.Inlines.Add($strong)
    }
    if ($Name -ne '') { [void]$title.Inlines.Add((New-Object System.Windows.Documents.Run $Name)) }
    [void]$brandRow.Children.Add($title)
    [void]$bar.Children.Add($brand)

    # The credit line, centred on the window inside the thin half of the
    # band. The licence says it stays at this size and keeps this text, and
    # the library is what puts it there. See LICENSE, condition 2.
    $creditHost = New-Object System.Windows.Controls.Grid
    $creditHost.Height = $thin
    $creditHost.VerticalAlignment = 'Top'
    $creditHost.HorizontalAlignment = 'Center'
    $creditHost.IsHitTestVisible = $false
    $credit = New-Object System.Windows.Controls.TextBlock
    $credit.Text = Get-SlantCreditText
    $credit.FontFamily = New-Object System.Windows.Media.FontFamily 'Segoe UI Variable Text, Segoe UI'
    $credit.FontSize = 11
    $credit.FontStyle = 'Italic'
    $credit.Foreground = $brush['text-4']
    $credit.VerticalAlignment = 'Center'
    $credit.TextWrapping = 'NoWrap'
    [void]$creditHost.Children.Add($credit)
    [void]$bar.Children.Add($creditHost)

    # The right hand end of the thin half: the application's own slot, then
    # the window buttons.
    $right = New-Object System.Windows.Controls.StackPanel
    $right.Orientation = 'Horizontal'
    $right.HorizontalAlignment = 'Right'
    $right.VerticalAlignment = 'Top'
    $right.Height = $thin
    $extras = New-Object System.Windows.Controls.StackPanel
    $extras.Orientation = 'Horizontal'
    $extras.VerticalAlignment = 'Center'
    $extras.Margin = New-Object System.Windows.Thickness 0, 0, 10, 0
    [void]$right.Children.Add($extras)

    $buttons = @{}
    if (-not $NoMinimize) {
        $buttons['min'] = New-SlantWindowButton -Glyph $script:SlantGlyphs.Minimise -Tip 'Minimise' `
            -Ink $colour['text-3'] -Hover $colour['control-hover'] -HoverInk $colour['text-1'] -Height $thin
        [void]$right.Children.Add($buttons['min'])
    }
    if (-not $NoMaximize) {
        $buttons['max'] = New-SlantWindowButton -Glyph $script:SlantGlyphs.Maximise -Tip 'Maximise' `
            -Ink $colour['text-3'] -Hover $colour['control-hover'] -HoverInk $colour['text-1'] -Height $thin
        [void]$right.Children.Add($buttons['max'])
    }
    # The close button takes the error fill, which is the one place in the
    # design where a status colour is a hover.
    $buttons['close'] = New-SlantWindowButton -Glyph $script:SlantGlyphs.Close -Tip 'Close' `
        -Ink $colour['text-3'] -Hover $colour['err'] -HoverInk $colour['on-status'] -Height $thin
    [void]$right.Children.Add($buttons['close'])
    [void]$bar.Children.Add($right)

    return [PSCustomObject]@{
        Element = $bar
        Band    = $band
        Brand   = $brand
        Row     = $brandRow
        Logo    = $mark
        Name    = $title
        Credit  = $credit
        Extras  = $extras
        Right   = $right
        Buttons = $buttons
        Palette = $slug
    }
}

function Set-SlantLogo {
    <#  .SYNOPSIS  Fill the brand square with an image, a brush, or leave the
        accent behind when the file is not there.  #>
    param([Parameter(Mandatory = $true)]$Element, [Parameter(Mandatory = $true)]$Logo)
    Initialize-SlantWpf
    try {
        if ($Logo -is [System.Windows.Media.Brush]) { $Element.Background = $Logo; return }
        $source = $null
        if ($Logo -is [System.Windows.Media.ImageSource]) { $source = $Logo }
        elseif (Test-Path -LiteralPath "$Logo") {
            $source = [System.Windows.Media.Imaging.BitmapFrame]::Create(
                (New-Object Uri ((Resolve-Path -LiteralPath "$Logo").ProviderPath)), 'None', 'OnLoad')
        }
        if ($null -eq $source) { return }
        $fill = New-Object System.Windows.Media.ImageBrush
        $fill.ImageSource = $source
        $fill.Stretch = 'UniformToFill'
        $Element.Background = $fill
    } catch { }
}

# ── the window, assembled ───────────────────────────────────────────────────
# Maximised is a state this object keeps, not a zoom.
#
# Windows places a zoomed window that carries the frame styles with its frame
# past the edge of the screen, eleven pixels a side at 150 per cent, and it
# keeps it there: the proposed size is asked for and ignored, moving the
# zoomed window is accepted and undone, and dropping the resize style first
# changes nothing. For a window whose client area is the whole window that is
# eleven pixels of the page cut off on every side. So the window is never
# zoomed. It animates onto the work area and remembers that it did, Win+Up,
# Win+Down and the taskbar menu arrive as system commands and are answered
# here, and a zoom Windows manages to do anyway is undone the moment WPF
# reports it.

function Install-SlantWindow {
    <#  .SYNOPSIS  Dress a WPF window in this design's chrome.

        The window loses its Windows frame and gains the oblique band as its
        title bar. Whatever was inside it moves down one row and is not
        touched, so an application keeps its own layout and its own icon.

        .PARAMETER Window   The System.Windows.Window to dress.
        .PARAMETER Bold     The strong part of the name, usually one word.
        .PARAMETER Name     The rest of the name, in the quieter ink.
        .PARAMETER Logo     A path to an image, a brush, or nothing.
        .PARAMETER Palette  A palette slug. The default palette otherwise.
        .PARAMETER StateMs  How long maximise and restore take. Zero for no
                            animation at all, which a window with a heavy
                            tree under it may want.

        .EXAMPLE
            $chrome = Install-SlantWindow -Window $w -Bold 'My' -Name ' App'
            $chrome.SetStatus('ready')
            $chrome.OnMaximized = { param($on) Save-Pref 'maximised' $on }  #>
    param(
        [Parameter(Mandatory = $true)]$Window,
        [string]$Bold = '',
        [string]$Name = '',
        $Logo = $null,
        [string]$Palette,
        [switch]$NoMinimize,
        [switch]$NoMaximize,
        [int]$StateMs = 240,
        [int]$Border = 5,
        [int]$Corner = 12)

    Initialize-SlantChrome
    $slug = Resolve-SlantSlug $Palette
    $brush = Get-SlantBrushes $slug
    $bar = New-SlantTitleBar -Bold $Bold -Name $Name -Logo $Logo -Palette $slug `
        -NoMinimize:$NoMinimize -NoMaximize:$NoMaximize

    $resizable = ($Window.ResizeMode -ne 'NoResize')
    $Window.WindowStyle = 'None'
    $Window.AllowsTransparency = $false
    if ($resizable) { $Window.ResizeMode = 'CanResize' }
    if ($null -eq $Window.Background) { $Window.Background = $brush['surface-0'] }

    # The application's content moves into the second row. A window holds one
    # child, so it has to let go of it first.
    $inside = $Window.Content
    $Window.Content = $null
    $shell = New-Object System.Windows.Controls.Grid
    $top = New-Object System.Windows.Controls.RowDefinition
    $top.Height = 'Auto'
    $rest = New-Object System.Windows.Controls.RowDefinition
    [void]$shell.RowDefinitions.Add($top)
    [void]$shell.RowDefinitions.Add($rest)
    [void]$shell.Children.Add($bar.Element)
    [System.Windows.Controls.Grid]::SetRow($bar.Element, 0)
    if ($null -ne $inside) {
        $body = $inside
        if (-not ($inside -is [System.Windows.UIElement])) {
            $body = New-Object System.Windows.Controls.ContentControl
            $body.Content = $inside
        }
        [void]$shell.Children.Add($body)
        [System.Windows.Controls.Grid]::SetRow($body, 1)
    }
    $Window.Content = $shell

    $chrome = [PSCustomObject]@{
        Window     = $Window
        Element    = $bar.Element
        Band       = $bar.Band
        Brand      = $bar.Brand
        Logo       = $bar.Logo
        Name       = $bar.Name
        Credit     = $bar.Credit
        Extras     = $bar.Extras
        Buttons    = $bar.Buttons
        Body       = $shell
        Status     = $null
        Palette    = $slug
        Brushes    = $brush
        Handle     = [IntPtr]::Zero
        Maximized  = $false
        NormalRect = New-Object System.Windows.Rect 0, 0, 0, 0
        Anim       = $null
        Busy       = $false
        StateMs    = $StateMs
        Border     = $Border
        Corner     = $Corner
        Resizable  = $resizable
        OnMaximized = $null
    }

    # ── the parts that read or write the window ─────────────────────────
    $chrome | Add-Member -MemberType ScriptMethod -Name Attach -Value {
        if ($this.Handle -ne [IntPtr]::Zero) { return }
        $handle = Get-SlantWindowHandle $this.Window
        if ($handle -eq [IntPtr]::Zero) { return }
        $this.Handle = $handle
        Set-SlantWindowFrame -Handle $handle -Border $this.Border -Corner $this.Corner `
            -Resizable $this.Resizable
        Set-SlantWindowScheme -Handle $handle -Palette $this.Palette
        [SlantUI.Chrome]::SetMaximized($handle, $this.Maximized)
        $me = $this
        [SlantUI.Chrome]::OnSysCommand($handle, [Func[IntPtr, int, bool]] {
            param([IntPtr]$hwnd, [int]$command)
            $taken = $false
            try { $taken = [bool]$me.SystemCommand($command) } catch { $taken = $false }
            return $taken
        }.GetNewClosure())
    }

    $chrome | Add-Member -MemberType ScriptMethod -Name Shape -Value {
        <#  The band, cut to the real width of the name.  #>
        $width = $this.Element.ActualWidth
        if ($width -le 0) { return }
        $this.Band.Data = Get-SlantBandGeometry -Width $width `
            -BrandWidth ([Math]::Round($this.Brand.ActualWidth))
    }

    $chrome | Add-Member -MemberType ScriptMethod -Name SetName -Value {
        param([string]$Bold, [string]$Name)
        $this.Name.Inlines.Clear()
        if ("$Bold" -ne '') {
            $strong = New-Object System.Windows.Documents.Run "$Bold"
            $strong.FontWeight = 'SemiBold'
            $strong.Foreground = $this.Brushes['text-1']
            [void]$this.Name.Inlines.Add($strong)
        }
        if ("$Name" -ne '') { [void]$this.Name.Inlines.Add((New-Object System.Windows.Documents.Run "$Name")) }
        $this.Shape()
    }

    $chrome | Add-Member -MemberType ScriptMethod -Name SetStatus -Value {
        <#  One line of the application's own text, in the thin half next to
            the window buttons. Empty takes the space back.  #>
        param([string]$Text)
        if ($null -eq $this.Status) {
            $line = New-Object System.Windows.Controls.TextBlock
            $line.FontFamily = New-Object System.Windows.Media.FontFamily (Get-SlantTokens).Fonts['font']
            $line.FontSize = [double](Get-SlantMetric 'fs-sm')
            $line.Foreground = $this.Brushes['text-3']
            $line.VerticalAlignment = 'Center'
            $line.TextWrapping = 'NoWrap'
            [void]$this.Extras.Children.Add($line)
            $this.Status = $line
        }
        $this.Status.Text = "$Text"
        if ("$Text" -eq '') { $this.Status.Visibility = 'Collapsed' }
        else { $this.Status.Visibility = 'Visible' }
    }

    # ── maximised, which is a state and never a zoom ─────────────────────
    $chrome | Add-Member -MemberType ScriptMethod -Name IsMaximized -Value { $this.Maximized }

    $chrome | Add-Member -MemberType ScriptMethod -Name Remember -Value {
        <#  The size the window goes back to. Read off the window while it is
            a normal window, so a size the person chose is the one restored.  #>
        $w = $this.Window
        if ([double]::IsNaN($w.Left) -or [double]::IsNaN($w.Top)) { return }
        if ($w.ActualWidth -le 0 -or $w.ActualHeight -le 0) { return }
        $this.NormalRect = New-Object System.Windows.Rect $w.Left, $w.Top, $w.ActualWidth, $w.ActualHeight
    }

    $chrome | Add-Member -MemberType ScriptMethod -Name Track -Value {
        <#  Busy is the one that matters and the one that is easy to leave
            out. A window's Left and Width raise their events as they are
            written, so the move onto the work area arrives here while the
            maximised flag is still down, and the size the window should go
            back to is overwritten with the work area. The flag covers the
            whole of a state change, animated or not.  #>
        if ($this.Busy -or $this.Maximized -or $null -ne $this.Anim) { return }
        if ($this.Window.WindowState -ne 'Normal') { return }
        $this.Remember()
    }

    $chrome | Add-Member -MemberType ScriptMethod -Name NormalBounds -Value {
        <#  Where a restore would put the window, whatever state it is in.  #>
        $r = $this.NormalRect
        if ($r.Width -ge 80 -and $r.Height -ge 60) { return $r }
        $work = Get-SlantWorkArea $this.Window
        $wide = [Math]::Max(480, $work.Width * 0.7)
        $tall = [Math]::Max(320, $work.Height * 0.7)
        return (New-Object System.Windows.Rect ($work.X + ($work.Width - $wide) / 2),
            ($work.Y + ($work.Height - $tall) / 2), $wide, $tall)
    }

    $chrome | Add-Member -MemberType ScriptMethod -Name SetMaximized -Value {
        param([bool]$On)
        $this.Maximized = $On
        if ($this.Handle -ne [IntPtr]::Zero) { [SlantUI.Chrome]::SetMaximized($this.Handle, $On) }
        $button = $this.Buttons['max']
        if ($null -ne $button) {
            if ($On) { $button.ToolTip = 'Restore' } else { $button.ToolTip = 'Maximise' }
            if ($button.Content -is [System.Windows.Shapes.Path]) {
                $glyph = $script:SlantGlyphs.Maximise
                if ($On) { $glyph = $script:SlantGlyphs.Restore }
                $button.Content.Data = [System.Windows.Media.Geometry]::Parse($glyph)
            }
        }
        $this.Shape()
        if ($null -ne $this.OnMaximized) { try { & $this.OnMaximized $On } catch { } }
    }

    $chrome | Add-Member -MemberType ScriptMethod -Name Animate -Value {
        <#  Move the window from where it is to a rectangle, over StateMs,
            with an ease out. One timer, one placement a frame, because four
            separate property animations on a window are four calls into
            Windows a frame. A throw inside a tick stops that timer for good,
            so every tick is inside a catch.  #>
        param($To, $Done)
        $w = $this.Window
        if ($null -ne $this.Anim) { $this.Anim.Stop(); $this.Anim = $null; $this.Busy = $false }
        $from = New-Object System.Windows.Rect $w.Left, $w.Top, $w.ActualWidth, $w.ActualHeight
        $jump = ($this.StateMs -le 0 -or [double]::IsNaN($from.X) -or $from.Width -le 0)
        if ($jump) {
            $this.Busy = $true
            try {
                $w.Left = $To.X; $w.Top = $To.Y; $w.Width = $To.Width; $w.Height = $To.Height
            } finally { $this.Busy = $false }
            if ($null -ne $Done) { & $Done }
            return
        }
        $run = @{ Start = [DateTime]::UtcNow; From = $from; To = $To; Ms = [double]$this.StateMs
                  Done = $Done; Owner = $this }
        $this.Busy = $true
        $timer = New-Object System.Windows.Threading.DispatcherTimer
        $timer.Interval = [TimeSpan]::FromMilliseconds(16)
        $timer.add_Tick({
            $step = $run
            try {
                $part = ([DateTime]::UtcNow - $step.Start).TotalMilliseconds / $step.Ms
                if ($part -gt 1) { $part = 1 }
                $ease = 1 - [Math]::Pow(1 - $part, 3)
                $win = $step.Owner.Window
                $win.Left = $step.From.X + ($step.To.X - $step.From.X) * $ease
                $win.Top = $step.From.Y + ($step.To.Y - $step.From.Y) * $ease
                $win.Width = $step.From.Width + ($step.To.Width - $step.From.Width) * $ease
                $win.Height = $step.From.Height + ($step.To.Height - $step.From.Height) * $ease
                if ($part -ge 1) {
                    $args[0].Stop()
                    $step.Owner.Anim = $null
                    $step.Owner.Busy = $false
                    if ($null -ne $step.Done) { & $step.Done }
                }
            } catch {
                try { $args[0].Stop() } catch { }
                $step.Owner.Anim = $null
                $step.Owner.Busy = $false
            }
        }.GetNewClosure())
        $this.Anim = $timer
        $timer.Start()
    }

    $chrome | Add-Member -MemberType ScriptMethod -Name Maximize -Value {
        if ($this.Maximized -or $null -ne $this.Anim) { return }
        if ($this.Window.WindowState -ne 'Normal') { return }
        $this.Remember()
        $me = $this
        $this.Animate((Get-SlantWorkArea $this.Window), { $me.SetMaximized($true) }.GetNewClosure())
    }

    $chrome | Add-Member -MemberType ScriptMethod -Name Restore -Value {
        if (-not $this.Maximized -or $null -ne $this.Anim) { return }
        $target = $this.NormalBounds()
        $this.SetMaximized($false)
        $this.Animate($target, $null)
    }

    $chrome | Add-Member -MemberType ScriptMethod -Name ToggleMaximize -Value {
        if ($null -eq $this.Buttons['max'] -and -not $this.Maximized) { return }
        if ($this.Maximized) { $this.Restore() } else { $this.Maximize() }
    }

    $chrome | Add-Member -MemberType ScriptMethod -Name Minimize -Value {
        $this.Window.WindowState = 'Minimized'
    }

    $chrome | Add-Member -MemberType ScriptMethod -Name Close -Value { $this.Window.Close() }

    $chrome | Add-Member -MemberType ScriptMethod -Name RestoreUnderCursor -Value {
        <#  Back to the normal size at once, with the cursor left at the same
            fraction of the width, so the band stays under the hand. It is
            what Windows does with a real maximised window.  #>
        param([double]$Fraction)
        $w = $this.Window
        $target = $this.NormalBounds()
        $cursor = $w.Left + $w.ActualWidth * $Fraction
        $this.SetMaximized($false)
        $this.Busy = $true
        try {
            $w.Left = $cursor - $target.Width * $Fraction
            $w.Width = $target.Width
            $w.Height = $target.Height
        } finally { $this.Busy = $false }
    }

    $chrome | Add-Member -MemberType ScriptMethod -Name AbsorbZoom -Value {
        <#  Windows zoomed the window without asking. A zoomed window sits
            with its frame past the screen and cannot be moved from there, so
            the zoom is undone at once, with the system transition off so
            nothing plays twice, and the window is put on the work area as
            the normal window it is everywhere else.  #>
        if ($null -ne $this.Anim) { $this.Anim.Stop(); $this.Anim = $null }
        $w = $this.Window
        if ($this.Handle -ne [IntPtr]::Zero) {
            Set-SlantWindowTransitions -Handle $this.Handle -Enabled $false
        }
        $this.Busy = $true
        try {
            $w.WindowState = 'Normal'
            $work = Get-SlantWorkArea $w
            $w.Left = $work.X; $w.Top = $work.Y; $w.Width = $work.Width; $w.Height = $work.Height
        } finally { $this.Busy = $false }
        if ($this.Handle -ne [IntPtr]::Zero) {
            Set-SlantWindowTransitions -Handle $this.Handle -Enabled $true
        }
        $this.SetMaximized($true)
    }

    $chrome | Add-Member -MemberType ScriptMethod -Name SystemCommand -Value {
        <#  Win+Up, Win+Down and the taskbar menu. True means the window has
            taken it and Windows is not to act. Restoring from the taskbar
            stays the system's.  #>
        param([int]$Command)
        if ($this.Window.WindowState -eq 'Minimized') { return $false }
        if ($Command -eq 0xF030) {
            if ($null -eq $this.Buttons['max']) { return $false }
            $this.Maximize()
            return $true
        }
        if ($Command -eq 0xF120 -and $this.Maximized) {
            $this.Restore()
            return $true
        }
        return $false
    }

    # ── wiring ───────────────────────────────────────────────────────────
    $chrome.Attach()
    $Window.add_SourceInitialized({ $chrome.Attach() }.GetNewClosure())
    $Window.add_Loaded({ $chrome.Attach(); $chrome.Shape() }.GetNewClosure())
    $Window.add_ContentRendered({ $chrome.Shape() }.GetNewClosure())
    $bar.Element.add_SizeChanged({ $chrome.Shape() }.GetNewClosure())
    $bar.Brand.add_SizeChanged({ $chrome.Shape() }.GetNewClosure())
    $Window.add_LocationChanged({ $chrome.Track() }.GetNewClosure())
    $Window.add_SizeChanged({ $chrome.Track() }.GetNewClosure())
    $Window.add_StateChanged({
        if ($chrome.Window.WindowState -eq 'Maximized') { $chrome.AbsorbZoom() }
    }.GetNewClosure())
    $Window.add_Closed({
        if ($chrome.Handle -ne [IntPtr]::Zero) { [SlantUI.Chrome]::Forget($chrome.Handle) }
    }.GetNewClosure())

    # Anywhere on the band except the buttons drags the window, and two
    # clicks maximise it. A drag on a maximised window restores it first.
    $bar.Element.add_MouseLeftButtonDown({
        param($source, $click)
        try {
            if ($click.ClickCount -eq 2) {
                $chrome.ToggleMaximize()
                $click.Handled = $true
                return
            }
            if ($null -ne $chrome.Anim) { return }
            if ($chrome.Maximized) {
                $wide = $chrome.Element.ActualWidth
                $fraction = 0.5
                if ($wide -gt 0) { $fraction = $click.GetPosition($chrome.Element).X / $wide }
                $chrome.RestoreUnderCursor($fraction)
            }
            $chrome.Window.DragMove()
        } catch { }
    }.GetNewClosure())

    if ($null -ne $bar.Buttons['min']) {
        $bar.Buttons['min'].add_Click({ $chrome.Minimize() }.GetNewClosure())
    }
    if ($null -ne $bar.Buttons['max']) {
        $bar.Buttons['max'].add_Click({ $chrome.ToggleMaximize() }.GetNewClosure())
    }
    $bar.Buttons['close'].add_Click({ $chrome.Close() }.GetNewClosure())

    return $chrome
}

Export-ModuleMember -Function Get-SlantDataPath, Get-SlantTokens, Get-SlantPaletteNames,
    Get-SlantPalette, Get-SlantColor, Get-SlantMetric, ConvertTo-SlantColorRef,
    New-SlantBrush, Get-SlantBrushes,
    Get-SlantBandPoints, Get-SlantRoundedPolyPath, Get-SlantBandPath, Get-SlantBandGeometry,
    Format-SlantCoord,
    Initialize-SlantChrome, Get-SlantCreditText, Set-SlantWindowFrame, Set-SlantWindowScheme,
    Set-SlantWindowTransitions, Test-SlantWindowZoomed, Get-SlantWindowStyle,
    Get-SlantWindowSizes, Get-SlantWindowHandle, Get-SlantWorkArea,
    New-SlantWindowButton, New-SlantTitleBar, Set-SlantLogo, Install-SlantWindow
