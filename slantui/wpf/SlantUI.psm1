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
        // The modal loop Windows runs while a window is being dragged by an
        // edge or by its band. Everything between these two is one gesture.
        const uint WM_ENTERSIZEMOVE = 0x0231;
        const uint WM_EXITSIZEMOVE = 0x0232;
        const uint SWP_NOZORDER = 0x0004;
        const uint SWP_NOACTIVATE = 0x0010;
        const uint SWP_NOOWNERZORDER = 0x0200;

        class Win
        {
            public int Border;
            public int Corner;
            public bool Resize;
            public bool Max;
            public Func<IntPtr, int, bool> OnCommand;
            public Action<IntPtr, bool> OnSizing;
            public bool Sizing;
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
            s.OnSizing = null;
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
        // A window moved and resized in one call.
        //
        // Writing Left, Top, Width and Height on a WPF window is four calls
        // into Windows, and each one is a WM_WINDOWPOSCHANGED that makes the
        // whole tree measure and arrange again. On a window with a document
        // in it that is four layout passes a frame, and it is what a state
        // change looked like: a stutter, not a move. One SetWindowPos is one
        // layout pass, and WPF reads its own Left, Top, Width and Height back
        // out of the message, so nothing drifts.
        //
        // Sizes are in real pixels here, not in the units WPF lays out in:
        // the caller converts.
        public static void Place(IntPtr h, int x, int y, int cx, int cy)
        {
            SetWindowPos(h, IntPtr.Zero, x, y, cx, cy,
                SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOOWNERZORDER);
        }

        // Told when a drag of an edge, or of the band, starts and ends, so an
        // application can stop its text reflowing on every pixel and let it
        // settle once at the end. The window procedure calls this; the return
        // value is nothing, so unlike the WM_NCCALCSIZE case a delegate made
        // from a scriptblock is fine here.
        public static void OnSizing(IntPtr h, Action<IntPtr, bool> f)
        {
            Win s = Of(h); if (s != null) s.OnSizing = f;
        }
        public static bool IsSizing(IntPtr h) { Win s = Of(h); return s != null && s.Sizing; }
        // The same signal, raised by the library itself around a state change
        // it animates: to the application a maximise and a drag of an edge
        // are the same thing, a size that is about to keep changing.
        public static void RaiseSizing(IntPtr h, bool active)
        {
            Win s = Of(h); if (s == null) return;
            if (s.Sizing == active) return;
            s.Sizing = active;
            if (s.OnSizing != null) { try { s.OnSizing(h, active); } catch { } }
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
            // A drag of an edge or of the band starts a modal loop, and every
            // pixel of it is a WM_SIZE. An application told where the loop
            // begins and ends can freeze what would otherwise rewrap under
            // the hand, and reflow once when the hand lets go.
            if (msg == WM_ENTERSIZEMOVE) { RaiseSizing(h, true); }
            if (msg == WM_EXITSIZEMOVE) { RaiseSizing(h, false); }
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
    # The rule in this design is that the pointer says what can be clicked: a
    # hand over anything that answers a click, and nothing over anything that
    # does not. The band answers a click, but to be dragged and to be
    # double-clicked, which is not the same thing, so it says so: an arrow,
    # set on purpose, where saying nothing would leave it to chance. The
    # window buttons on it carry
    # the hand, and so does anything else in this library that is pressed.
    $bar.Cursor = 'Arrow'

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

$script:SlantVectorCache = @{}

# ── plain SVG, read as drawings ─────────────────────────────────────────────
# Enough of SVG to draw a flag, an icon or a logo, and no more: shapes, groups,
# transforms, inherited paint. No <use>, no gradients, no clip paths, no CSS.
# What it does cover it covers properly, because the alternative is a picture:
# a drawing is redrawn at whatever size is asked for, and a picture is not.
#
# The syntax of the d attribute is the syntax Geometry.Parse takes, which is
# why no path parser is needed here. The rest of the shapes are written out as
# geometries of their own, and a group becomes a DrawingGroup, which is where
# transform and opacity belong.

function ConvertTo-SlantSvgNumber([string]$v, [double]$fallback = 0.0) {
    if (-not "$v") { return $fallback }
    $m = [regex]::Match("$v", '^\s*(-?[\d.]+(?:[eE][-+]?\d+)?)')
    if (-not $m.Success) { return $fallback }
    try { return [double]::Parse($m.Groups[1].Value, [System.Globalization.CultureInfo]::InvariantCulture) }
    catch { return $fallback }
}

function ConvertTo-SlantSvgTransform([string]$spec) {
    <#  .SYNOPSIS  An SVG transform list as one WPF matrix.

        translate, scale, rotate, skewX, skewY and matrix, applied left to
        right as SVG applies them. Anything else is skipped instead of being
        guessed at.  #>
    Initialize-SlantWpf
    $m = New-Object System.Windows.Media.Matrix
    if (-not "$spec") { return $null }
    foreach ($pezzo in [regex]::Matches("$spec", '([a-zA-Z]+)\s*\(([^)]*)\)')) {
        $nome = $pezzo.Groups[1].Value.ToLower()
        $n = @(([regex]::Matches($pezzo.Groups[2].Value, '-?[\d.]+(?:[eE][-+]?\d+)?')) |
               ForEach-Object { ConvertTo-SlantSvgNumber $_.Value })
        $t = New-Object System.Windows.Media.Matrix
        switch ($nome) {
            'translate' { $t.Translate($n[0], $(if ($n.Count -gt 1) { $n[1] } else { 0.0 })) }
            'scale'     { $t.Scale($n[0], $(if ($n.Count -gt 1) { $n[1] } else { $n[0] })) }
            'rotate'    {
                if ($n.Count -ge 3) { $t.RotateAt($n[0], $n[1], $n[2]) } else { $t.Rotate($n[0]) }
            }
            'skewx'     { $t.Skew($n[0], 0.0) }
            'skewy'     { $t.Skew(0.0, $n[0]) }
            'matrix'    {
                if ($n.Count -ge 6) {
                    $t = New-Object System.Windows.Media.Matrix($n[0], $n[1], $n[2], $n[3], $n[4], $n[5])
                }
            }
            default { continue }
        }
        $m = [System.Windows.Media.Matrix]::Multiply($t, $m)
    }
    if ($m.IsIdentity) { return $null }
    return (New-Object System.Windows.Media.MatrixTransform($m))
}

function Get-SlantSvgBrush([string]$spec, [double]$opacity, $bc) {
    <#  .SYNOPSIS  A brush from a paint value. "#a>#b" is a diagonal gradient,
        which is how a two-colour mark is tinted without a second file.  #>
    if (-not "$spec" -or "$spec" -eq 'none') { return $null }
    try {
        $b = $null
        if ("$spec" -match '>') {
            $parti = @("$spec" -split '>' | Where-Object { "$_".Trim() })
            $g = New-Object System.Windows.Media.LinearGradientBrush
            $g.StartPoint = New-Object System.Windows.Point(0, 0)
            $g.EndPoint = New-Object System.Windows.Point(1, 1)
            for ($i = 0; $i -lt $parti.Count; $i++) {
                $off = $(if ($parti.Count -le 1) { 0.0 } else { $i / ($parti.Count - 1.0) })
                $col = ([System.Windows.Media.SolidColorBrush]$bc.ConvertFromString($parti[$i].Trim())).Color
                [void]$g.GradientStops.Add((New-Object System.Windows.Media.GradientStop($col, $off)))
            }
            $b = $g
        } else {
            $b = $bc.ConvertFromString("$spec")
        }
        if ($null -ne $b -and $opacity -lt 0.999) { $b.Opacity = [Math]::Max(0.0, $opacity) }
        if ($null -ne $b -and $b.CanFreeze) { $b.Freeze() }
        return $b
    } catch { return $null }
}

function Get-SlantSvgGeometry($nodo) {
    <#  .SYNOPSIS  The geometry of one SVG shape, or nothing for a tag this
        reader does not draw.  #>
    $nome = "$($nodo.LocalName)".ToLower()
    $a = {
        param([string]$k)
        $v = $nodo.GetAttribute($k)
        return "$v"
    }
    switch ($nome) {
        'path' {
            $d = & $a 'd'
            if (-not $d) { return $null }
            # F0 is evenodd and F1 is nonzero: WPF says it at the head of the
            # data, which saves touching the geometry afterwards
            $rule = & $a 'fill-rule'
            $pref = $(if ($rule -eq 'evenodd') { 'F0 ' } else { 'F1 ' })
            try { return [System.Windows.Media.Geometry]::Parse($pref + $d) } catch { return $null }
        }
        'rect' {
            $w = ConvertTo-SlantSvgNumber (& $a 'width')
            $h = ConvertTo-SlantSvgNumber (& $a 'height')
            if ($w -le 0 -or $h -le 0) { return $null }
            $r = New-Object System.Windows.Rect((ConvertTo-SlantSvgNumber (& $a 'x')),
                                                (ConvertTo-SlantSvgNumber (& $a 'y')), $w, $h)
            $rx = ConvertTo-SlantSvgNumber (& $a 'rx')
            $ry = ConvertTo-SlantSvgNumber (& $a 'ry') $rx
            return (New-Object System.Windows.Media.RectangleGeometry($r, $rx, $ry))
        }
        'circle' {
            $rr = ConvertTo-SlantSvgNumber (& $a 'r')
            if ($rr -le 0) { return $null }
            $c = New-Object System.Windows.Point((ConvertTo-SlantSvgNumber (& $a 'cx')),
                                                 (ConvertTo-SlantSvgNumber (& $a 'cy')))
            return (New-Object System.Windows.Media.EllipseGeometry($c, $rr, $rr))
        }
        'ellipse' {
            $rx = ConvertTo-SlantSvgNumber (& $a 'rx')
            $ry = ConvertTo-SlantSvgNumber (& $a 'ry')
            if ($rx -le 0 -or $ry -le 0) { return $null }
            $c = New-Object System.Windows.Point((ConvertTo-SlantSvgNumber (& $a 'cx')),
                                                 (ConvertTo-SlantSvgNumber (& $a 'cy')))
            return (New-Object System.Windows.Media.EllipseGeometry($c, $rx, $ry))
        }
        'line' {
            $p0 = New-Object System.Windows.Point((ConvertTo-SlantSvgNumber (& $a 'x1')),
                                                  (ConvertTo-SlantSvgNumber (& $a 'y1')))
            $p1 = New-Object System.Windows.Point((ConvertTo-SlantSvgNumber (& $a 'x2')),
                                                  (ConvertTo-SlantSvgNumber (& $a 'y2')))
            return (New-Object System.Windows.Media.LineGeometry($p0, $p1))
        }
        { $_ -eq 'polygon' -or $_ -eq 'polyline' } {
            $n = @(([regex]::Matches((& $a 'points'), '-?[\d.]+(?:[eE][-+]?\d+)?')) |
                   ForEach-Object { ConvertTo-SlantSvgNumber $_.Value })
            if ($n.Count -lt 4) { return $null }
            $d = "M $($n[0]),$($n[1])"
            for ($i = 2; $i + 1 -lt $n.Count; $i += 2) { $d += " L $($n[$i]),$($n[$i + 1])" }
            if ($nome -eq 'polygon') { $d += " Z" }
            $rule = & $a 'fill-rule'
            $pref = $(if ($rule -eq 'evenodd') { 'F0 ' } else { 'F1 ' })
            try { return [System.Windows.Media.Geometry]::Parse($pref + $d) } catch { return $null }
        }
    }
    return $null
}

function Add-SlantSvgNode($nodo, $ospite, $eredita, [string]$Tint, $bc) {
    <#  .SYNOPSIS  Walk one element and hang what it draws on the host group.

        Paint is inherited the way SVG inherits it: an attribute on a group
        holds for the shapes inside unless one of them says otherwise. Groups
        become DrawingGroups, which is where a transform and a group opacity
        can live without being applied to each shape by hand.  #>
    foreach ($figlio in $nodo.ChildNodes) {
        if ($figlio.NodeType -ne [System.Xml.XmlNodeType]::Element) { continue }
        $nome = "$($figlio.LocalName)".ToLower()
        if ($nome -in @('defs', 'clippath', 'mask', 'style', 'title', 'desc', 'metadata',
                        'lineargradient', 'radialgradient', 'filter', 'symbol', 'use',
                        'text', 'tspan', 'switch', 'animate', 'script')) { continue }

        $mio = @{}
        foreach ($k in $eredita.Keys) { $mio[$k] = $eredita[$k] }
        foreach ($k in @('fill', 'fill-rule', 'fill-opacity', 'stroke', 'stroke-width',
                         'stroke-opacity', 'opacity')) {
            $v = "$($figlio.GetAttribute($k))"
            if ($v) { $mio[$k] = $v }
        }
        $trasf = ConvertTo-SlantSvgTransform "$($figlio.GetAttribute('transform'))"

        if ($nome -eq 'g' -or $nome -eq 'svg' -or $nome -eq 'a') {
            $dentro = New-Object System.Windows.Media.DrawingGroup
            if ($trasf) { $dentro.Transform = $trasf }
            $op = ConvertTo-SlantSvgNumber "$($figlio.GetAttribute('opacity'))" 1.0
            if ($op -lt 0.999) {
                $dentro.Opacity = $op
                $mio.Remove('opacity')      # already applied to the group
            }
            Add-SlantSvgNode $figlio $dentro $mio $Tint $bc
            if ($dentro.Children.Count -gt 0) { [void]$ospite.Children.Add($dentro) }
            continue
        }

        $geo = Get-SlantSvgGeometry $figlio
        if ($null -eq $geo) { continue }
        # Geometry.Parse hands back a frozen geometry for the simple cases, and
        # a frozen one refuses every change without a word about which: the
        # error reads as the path data being read-only
        if ($geo.IsFrozen) { $geo = $geo.Clone() }
        # fill-rule can be inherited from a group, and Geometry.Parse only saw
        # the shape's own attribute
        if (-not "$($figlio.GetAttribute('fill-rule'))" -and "$($mio['fill-rule'])" -eq 'evenodd' -and
            $geo -is [System.Windows.Media.PathGeometry]) {
            $geo.FillRule = 'EvenOdd'
        }
        if ($trasf) { $geo.Transform = $trasf }

        $fill = "$($mio['fill'])"
        # a monochrome icon declares no colour at all: the tint is used when one
        # was given, and the SVG default of black when it was not
        if (-not $fill -or $fill -eq 'currentColor') { $fill = $(if ($Tint) { $Tint } else { 'black' }) }
        $op = (ConvertTo-SlantSvgNumber "$($mio['opacity'])" 1.0) *
              (ConvertTo-SlantSvgNumber "$($mio['fill-opacity'])" 1.0)

        $dis = New-Object System.Windows.Media.GeometryDrawing
        $dis.Geometry = $geo
        $dis.Brush = Get-SlantSvgBrush $fill $op $bc
        $stroke = "$($mio['stroke'])"
        if ($stroke -and $stroke -ne 'none') {
            $sop = (ConvertTo-SlantSvgNumber "$($mio['opacity'])" 1.0) *
                   (ConvertTo-SlantSvgNumber "$($mio['stroke-opacity'])" 1.0)
            $pen = Get-SlantSvgBrush $stroke $sop $bc
            if ($pen) {
                $sw = ConvertTo-SlantSvgNumber "$($mio['stroke-width'])" 1.0
                $dis.Pen = New-Object System.Windows.Media.Pen($pen, $sw)
            }
        }
        if ($null -ne $dis.Brush -or $null -ne $dis.Pen) { [void]$ospite.Children.Add($dis) }
    }
}

function New-SlantVectorImage {
    <#  .SYNOPSIS  Read a plain SVG into a frozen drawing.

        Shapes, groups, transforms and inherited paint; no <use>, no gradients
        defined in <defs>, no clip paths, no CSS. Those are the parts of the
        format a design system does not need, and leaving them out is what
        keeps this a hundred lines instead of a library.

        Why it matters. A logo shipped as a PNG is drawn at one size and scaled
        to every other: on the splash, where the brand sits at 68 points inside
        the ring, a 1385 pixel master is squeezed down by the graphics card and
        the edges go soft. Read as drawings it is drawn at the size asked for,
        which also means a screenshot at three times the scale is redrawn
        instead of blown up.

        What comes back is frozen, so it can be handed to another thread: the
        splash draws on one of its own, and a frozen Freezable is the one kind
        of drawing that crosses.

        .PARAMETER Path   The .svg file.
        .PARAMETER Tint   A colour for a monochrome icon that declares none.
                          "#4285F4>#9B72CB" gives a diagonal gradient.
        .OUTPUTS  A DrawingImage, or nothing when the file cannot be read.  #>
    param([Parameter(Mandatory = $true)][string]$Path, [string]$Tint = "")
    Initialize-SlantWpf
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $stamp = ""
    try {
        $f = Get-Item -LiteralPath $Path
        $stamp = "$($f.Length)|$($f.LastWriteTimeUtc.Ticks)"
    } catch { }
    $key = "$Path|$Tint|$stamp"
    if ($script:SlantVectorCache.ContainsKey($key)) { return $script:SlantVectorCache[$key] }

    $doc = New-Object System.Xml.XmlDocument
    $doc.XmlResolver = $null          # no network, no local entity lookups
    try { $doc.Load($Path) } catch { return $null }
    $radice = $doc.DocumentElement
    if ($null -eq $radice) { return $null }

    # the viewBox is the space the shapes are drawn in: it gives the aspect and
    # the clip, so nothing spills outside the rectangle it declares
    $vb = @(([regex]::Matches("$($radice.GetAttribute('viewBox'))", '-?[\d.]+(?:[eE][-+]?\d+)?')) |
            ForEach-Object { ConvertTo-SlantSvgNumber $_.Value })
    if ($vb.Count -lt 4) {
        $vb = @(0.0, 0.0, (ConvertTo-SlantSvgNumber "$($radice.GetAttribute('width'))"),
                (ConvertTo-SlantSvgNumber "$($radice.GetAttribute('height'))"))
    }
    if ($vb[2] -le 0 -or $vb[3] -le 0) { return $null }

    $bc = New-Object System.Windows.Media.BrushConverter
    $gruppo = New-Object System.Windows.Media.DrawingGroup
    $eredita = @{}
    foreach ($k in @('fill', 'fill-rule', 'fill-opacity', 'stroke', 'stroke-width',
                     'stroke-opacity', 'opacity')) {
        $v = "$($radice.GetAttribute($k))"
        if ($v) { $eredita[$k] = $v }
    }
    Add-SlantSvgNode $radice $gruppo $eredita $Tint $bc
    if ($gruppo.Children.Count -eq 0) { return $null }

    $box = New-Object System.Windows.Rect($vb[0], $vb[1], $vb[2], $vb[3])
    $gruppo.ClipGeometry = New-Object System.Windows.Media.RectangleGeometry($box)
    $gruppo.Freeze()
    $img = New-Object System.Windows.Media.DrawingImage($gruppo)
    $img.Freeze()
    $script:SlantVectorCache[$key] = $img
    return $img
}

function Get-SlantArtSource {
    <#  .SYNOPSIS  An image source for a path, vector whenever there is one.

        A caller passes the file it has. If that is an SVG, or if an SVG of the
        same name sits beside it, the drawing is read from there; a raster is
        decoded only when there is no vector to read. An application gains the
        sharp version by dropping a .svg next to its .png and changing nothing
        else.  #>
    param([string]$Path, [string]$Tint = "")
    Initialize-SlantWpf
    if (-not "$Path") { return $null }
    $svg = ""
    if ([System.IO.Path]::GetExtension("$Path") -eq '.svg') { $svg = "$Path" }
    else {
        $twin = [System.IO.Path]::ChangeExtension("$Path", '.svg')
        if ($twin -and (Test-Path -LiteralPath $twin)) { $svg = $twin }
    }
    if ($svg) {
        $img = New-SlantVectorImage -Path $svg -Tint $Tint
        if ($img) { return $img }
    }
    if (-not (Test-Path -LiteralPath "$Path")) { return $null }
    try {
        return [System.Windows.Media.Imaging.BitmapFrame]::Create(
            (New-Object Uri ((Resolve-Path -LiteralPath "$Path").ProviderPath)), 'None', 'OnLoad')
    } catch { return $null }
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
        else { $source = Get-SlantArtSource -Path "$Logo" }
        if ($null -eq $source) { return }
        $fill = New-Object System.Windows.Media.ImageBrush
        $fill.ImageSource = $source
        # A photograph fills the square and is cropped to it; a drawing is a
        # mark with nothing around it, and cropping one takes a slice off the
        # mark itself. The brand here is taller than it is wide, so
        # UniformToFill would eat the top and the bottom of it.
        $fill.Stretch = $(if ($source -is [System.Windows.Media.DrawingImage]) { 'Uniform' } else { 'UniformToFill' })
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
                            animation at all. A window that turns out not to
                            be able to keep up finishes the move at once by
                            itself, so this rarely needs setting.
        .PARAMETER SlowMs   A frame slower than this, twice running, ends the
                            animation early. 40 ms is under thirty frames a
                            second, which is where a move stops reading as
                            one and starts reading as steps.

        .EXAMPLE
            $chrome = Install-SlantWindow -Window $w -Bold 'My' -Name ' App'
            $chrome.SetStatus('ready')
            $chrome.OnMaximized = { param($on) Save-Pref 'maximised' $on }
            # freeze what would rewrap under the hand, and let it settle once
            $chrome.OnSizing = { param($active) $view.FreezeText($active) }  #>
    param(
        [Parameter(Mandatory = $true)]$Window,
        [string]$Bold = '',
        [string]$Name = '',
        $Logo = $null,
        [string]$Palette,
        [switch]$NoMinimize,
        [switch]$NoMaximize,
        [int]$StateMs = 240,
        [int]$SlowMs = 40,
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
        Device     = $null
        OnSizing   = $null
        StateMs    = $StateMs
        SlowMs     = $SlowMs
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
        # A drag of an edge is a modal loop of Windows, and every pixel is a
        # WM_SIZE. An application that knows where that loop starts and where it
        # ends can freeze whatever would otherwise rewrap under the fingers, and
        # lay it out once at the end.
        [SlantUI.Chrome]::OnSizing($handle, [Action[IntPtr, bool]] {
            param([IntPtr]$hwnd, [bool]$active)
            if ($null -ne $me.OnSizing) { try { & $me.OnSizing $active } catch { } }
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

    $chrome | Add-Member -MemberType ScriptMethod -Name StopAnim -Value {
        <#  Take the frame handler off. It is a static event, so a handler
            left on it goes on being raised for the life of the process, on
            every frame, for a window that has finished moving.  #>
        $run = $this.Anim
        $this.Anim = $null
        if ($null -eq $run) { return }
        try { [System.Windows.Media.CompositionTarget]::remove_Rendering($run.Handler) } catch { }
        $this.Busy = $false
    }

    $chrome | Add-Member -MemberType ScriptMethod -Name Place -Value {
        <#  The window put exactly there, in one call.

            Writing Left, Top, Width and Height is four calls into Windows
            and four layout passes. During a move that is a frame's whole
            budget spent four times over, and it is what a maximise looked
            like on a window with a document in it. One SetWindowPos is one
            pass, and WPF reads its own properties back out of the message.

            Windows counts in real pixels and WPF in its own, so the
            rectangle goes through the window's device transform, the same
            way Get-SlantWorkArea brings one back the other way. Without a
            handle there is nothing to call, and the properties are written
            instead.  #>
        param($To)
        $w = $this.Window
        $m = $this.Device
        if ($this.Handle -eq [IntPtr]::Zero -or $null -eq $m) {
            $w.Left = $To.X; $w.Top = $To.Y; $w.Width = $To.Width; $w.Height = $To.Height
            return
        }
        $a = $m.Transform((New-Object System.Windows.Point $To.X, $To.Y))
        $z = $m.Transform((New-Object System.Windows.Point ($To.X + $To.Width), ($To.Y + $To.Height)))
        [SlantUI.Chrome]::Place($this.Handle,
            [int][Math]::Round($a.X), [int][Math]::Round($a.Y),
            [int][Math]::Round($z.X - $a.X), [int][Math]::Round($z.Y - $a.Y))
    }

    $chrome | Add-Member -MemberType ScriptMethod -Name Sizing -Value {
        <#  The size is about to keep changing, or it has stopped. Raised by
            the window procedure around a drag of an edge, and by the library
            around a state change it animates: to an application the two are
            the same thing, and there is one thing to do about both.  #>
        param([bool]$Active)
        if ($this.Handle -ne [IntPtr]::Zero) {
            [SlantUI.Chrome]::RaiseSizing($this.Handle, $Active)
            return
        }
        if ($null -ne $this.OnSizing) { try { & $this.OnSizing $Active } catch { } }
    }

    $chrome | Add-Member -MemberType ScriptMethod -Name Animate -Value {
        <#  Move the window from where it is to a rectangle, over StateMs,
            with an ease out.

            The clock is the compositor's, not a timer's. A DispatcherTimer
            asked for sixteen milliseconds is handed twenty to forty, because
            it queues behind layout and input at the same priority, and the
            jitter is the whole of what a stutter is. Rendering is raised
            once per composed frame, right before the frame goes out, so a
            rectangle written in it lands in that frame and in no other.

            One placement a frame, through SetWindowPos, for the reason
            written above Place.

            And a window that cannot keep up does not stutter, it snaps.
            Measured on 2026-09-20, on a window with a hundred and twenty
            paragraphs of wrapping text in it: one step of a resize costs
            78 ms, because WPF lays the whole tree out inside the size
            message. Two hundred and forty milliseconds of hand animation
            over that is three visible steps, which reads worse than no
            animation at all. So the first frames are measured, and if they
            come in slower than SlowMs the rest of the move is done at once.
            The animation is for windows that can afford it.

            A throw inside a handler on a static event is worse than one in a
            timer, so every frame is inside a catch and the handler takes
            itself off.  #>
        param($To, $Done)
        $w = $this.Window
        if ($null -ne $this.Anim) { $this.StopAnim() }
        $from = New-Object System.Windows.Rect $w.Left, $w.Top, $w.ActualWidth, $w.ActualHeight
        $jump = ($this.StateMs -le 0 -or [double]::IsNaN($from.X) -or $from.Width -le 0)
        if ($jump) {
            $this.Busy = $true
            try { $this.Place($To) } finally { $this.Busy = $false }
            if ($null -ne $Done) { & $Done }
            return
        }

        # the scale factor is read once and not on every frame
        $this.Device = $null
        if ($this.Handle -ne [IntPtr]::Zero) {
            $src = [System.Windows.Interop.HwndSource]::FromHwnd($this.Handle)
            if ($null -ne $src -and $null -ne $src.CompositionTarget) {
                $this.Device = $src.CompositionTarget.TransformToDevice
            }
        }

        $run = [PSCustomObject]@{
            Start = [DateTime]::UtcNow; From = $from; To = $To; Ms = [double]$this.StateMs
            Done = $Done; Owner = $this; Handler = $null
            Last = [DateTime]::UtcNow; Frames = 0; Slow = 0
        }
        $this.Busy = $true
        # the application is told before the geometry starts moving: that way
        # whatever would rewrap is already frozen on the first frame
        $this.Sizing($true)
        $handler = [System.EventHandler] {
            param($sender, $e)
            $step = $run
            try {
                $ora = [DateTime]::UtcNow
                $part = ($ora - $step.Start).TotalMilliseconds / $step.Ms
                if ($part -gt 1) { $part = 1 }
                # what the frame before cost. Two slow ones running and the
                # animation stops: better one jump than three jerks
                $step.Frames++
                if ($step.Frames -gt 1) {
                    $costo = ($ora - $step.Last).TotalMilliseconds
                    if ($costo -gt $step.Owner.SlowMs) { $step.Slow++ } else { $step.Slow = 0 }
                    if ($step.Slow -ge 2) { $part = 1 }
                }
                $step.Last = $ora
                $ease = 1 - [Math]::Pow(1 - $part, 3)
                $r = New-Object System.Windows.Rect `
                    ($step.From.X + ($step.To.X - $step.From.X) * $ease),
                    ($step.From.Y + ($step.To.Y - $step.From.Y) * $ease),
                    ($step.From.Width + ($step.To.Width - $step.From.Width) * $ease),
                    ($step.From.Height + ($step.To.Height - $step.From.Height) * $ease)
                $step.Owner.Place($r)
                if ($part -ge 1) {
                    $owner = $step.Owner
                    $owner.StopAnim()
                    # the last word to WPF's own properties: the conversion
                    # into pixels rounds, and the size that is kept has to be
                    # exact
                    $owner.Busy = $true
                    try {
                        $win = $owner.Window
                        $win.Left = $step.To.X; $win.Top = $step.To.Y
                        $win.Width = $step.To.Width; $win.Height = $step.To.Height
                    } finally { $owner.Busy = $false }
                    $owner.Sizing($false)
                    if ($null -ne $step.Done) { & $step.Done }
                }
            } catch {
                try { $step.Owner.StopAnim() } catch { }
                try { $step.Owner.Sizing($false) } catch { }
            }
        }.GetNewClosure()
        $run.Handler = $handler
        $this.Anim = $run
        [System.Windows.Media.CompositionTarget]::add_Rendering($handler)
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
        if ($null -ne $this.Anim) { $this.StopAnim() }
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

# ── the widgets that belong to the design, not to one application ──────────
# An application that wears this look should not have to draw its own dropdown
# and its own hover: those are the design, the same way the band and the
# palette are, and two applications that drew them separately would drift
# apart within a month. They live here, they are exported, and an application
# calls them.
#
# The colours come from the roles, not from names an application invented, so
# a palette change reaches them without anyone touching a widget.

function Get-SlantWidgetColours {
    <#  .SYNOPSIS  The handful of roles the widgets in this file draw with. #>
    $c = (Get-SlantPalette).Values
    $w = (Get-SlantPalette).Wpf
    return @{
        Panel3    = $c['surface-3']
        Line      = $c['control-active']
        Hover     = $c['control-hover']
        TextSoft  = $c['text-2']
        TextDim   = $c['text-3']
        TextFaint = $c['text-4']
        Accent    = $c['accent']
        Overlay   = $w['overlay']      # it has an alpha: the Wpf form, not the CSS one
    }
}

# The log belongs to the application and not to the library: if it has one it
# says so, and from that moment the widgets write into it too.
$script:SlantLogger = $null

function Set-SlantLogger {
    <#  .SYNOPSIS  Give the library somewhere to write when a widget has
        something to report. Without one, it keeps quiet.  #>
    param([scriptblock]$Write)
    $script:SlantLogger = $Write
}

function Write-SlantNote([string]$riga) {
    $l = $script:SlantLogger
    if ($l) { try { & $l "slantui: $riga" } catch { } }
}

# --- the one hover --------------------------------------------------------------
# Under the pointer the background lightens a little: a ColorAnimation of 120 ms
# going in and 180 coming out, QuadraticEase, on the colour of the background and
# on nothing else. No border appearing, no change of size. It holds for
# everything: the Borders built by hand and the templated buttons, where the
# first Border of the template is the one animated. The animation sits ON TOP of
# the property and does not replace it: coming out it stops (FillBehavior Stop)
# and the background goes back to what setters and triggers say at that moment
# (the yellow of a tab that was chosen while the pointer was over it, the grey of
# a button that is off). Before this every template had its own IsMouseOver
# trigger, switching at once, and the Borders built by hand had nothing.
function Get-SlantHoverColor([System.Windows.Media.Color]$c, [double]$quanto) {
    # on a transparent background it lays down a pale veil
    if ($c.A -eq 0) { return [System.Windows.Media.Color]::FromArgb(0x1C, 0xFF, 0xFF, 0xFF) }
    $r = [byte][math]::Min(255, $c.R + (255 - $c.R) * $quanto)
    $g = [byte][math]::Min(255, $c.G + (255 - $c.G) * $quanto)
    $b = [byte][math]::Min(255, $c.B + (255 - $c.B) * $quanto)
    return [System.Windows.Media.Color]::FromArgb($c.A, $r, $g, $b)
}

# The Border to animate: the element itself, or the first Border in the template
# of a button (which has to be applied, if it has not been yet).
function Find-SlantHoverTarget($el) {
    if ($el -is [System.Windows.Controls.Border]) { return $el }
    if ($el -is [System.Windows.Controls.Control]) { try { [void]$el.ApplyTemplate() } catch { } }
    $coda = New-Object System.Collections.Generic.Queue[object]
    $coda.Enqueue($el)
    $n = 0
    while ($coda.Count -gt 0 -and $n -lt 80) {
        $x = $coda.Dequeue()
        $n++
        if (-not [object]::ReferenceEquals($x, $el) -and $x -is [System.Windows.Controls.Border]) { return $x }
        $k = 0
        try { $k = [System.Windows.Media.VisualTreeHelper]::GetChildrenCount($x) } catch { $k = 0 }
        for ($i = 0; $i -lt $k; $i++) { $coda.Enqueue([System.Windows.Media.VisualTreeHelper]::GetChild($x, $i)) }
    }
    return $null
}

function New-SlantHoverStoryboard($target, [System.Windows.Media.Color]$to, [int]$ms, [string]$fill, $from = $null) {
    $a = New-Object System.Windows.Media.Animation.ColorAnimation
    if ($null -ne $from) { $a.From = [System.Windows.Media.Color]$from }
    $a.To = $to
    $a.Duration = [TimeSpan]::FromMilliseconds($ms)
    $a.EasingFunction = New-Object System.Windows.Media.Animation.QuadraticEase
    $a.FillBehavior = $fill
    [System.Windows.Media.Animation.Storyboard]::SetTarget($a, $target)
    [System.Windows.Media.Animation.Storyboard]::SetTargetProperty($a, (New-Object System.Windows.PropertyPath("(0).(1)",
        @([System.Windows.Controls.Border]::BackgroundProperty, [System.Windows.Media.SolidColorBrush]::ColorProperty))))
    $sb = New-Object System.Windows.Media.Animation.Storyboard
    [void]$sb.Children.Add($a)
    return $sb
}

# The BASE colour of a brush: not the one that is seen, which during a hover or
# a transition is animated. A brush that is not frozen is animated in place (the
# Border holds the same object), so .Color would give the animated value and a
# comparison "the same colour?" would fail every time under the pointer.
function Get-SlantBaseBrushColor($brush) {
    try { return [System.Windows.Media.Color]$brush.GetAnimationBaseValue([System.Windows.Media.SolidColorBrush]::ColorProperty) }
    catch { return $brush.Color }
}

# Change a Border's background with a colour transition (140 ms) instead of
# switching at once: the base becomes the new colour straight away, and the
# animation runs from the old to the new and then stops, so the hover always
# reads the right base.
function Set-SlantBorderColor($border, [string]$hex, [bool]$animato = $true) {
    $bc = New-Object System.Windows.Media.BrushConverter
    $nuovo = $bc.ConvertFromString($hex)
    $vecchio = $null
    try {
        $bb = $border.GetAnimationBaseValue([System.Windows.Controls.Border]::BackgroundProperty)
        if ($bb -is [System.Windows.Media.SolidColorBrush]) { $vecchio = Get-SlantBaseBrushColor $bb }
    } catch { }
    # the same colour: nothing is touched. Assigning an equal brush would
    # detach the hover animation that is running (it lives on the brush), and the
    # button under the pointer would go back to unlit on every redraw
    if ($null -ne $vecchio -and $vecchio -eq $nuovo.Color) { return }
    $border.Background = $nuovo
    if ($animato -and $null -ne $vecchio) {
        try { (New-SlantHoverStoryboard $border $nuovo.Color 140 'Stop' $vecchio).Begin($border, $true) } catch { }
    }
}

function Add-SlantHover {
    param($Element, $Target = $null, [double]$Amount = 0.10)
    if (-not $Element) { return }
    # what lights up under the pointer is what gets clicked, so the hand belongs
    # here too: a button that does not show it reads as a label
    try { if (-not $Element.Cursor) { $Element.Cursor = 'Hand' } } catch { }
    $stato = [PSCustomObject]@{ Target = $Target; Quanto = $Amount }
    $Element.add_MouseEnter({
        param($src, $e)
        try {
            $t = $stato.Target
            if (-not $t) { $t = Find-SlantHoverTarget $src; if (-not $t) { $global:SlantHoverLast = "enter: no Border under $($src.GetType().Name)"; return }; $stato.Target = $t }
            $bb = $t.GetAnimationBaseValue([System.Windows.Controls.Border]::BackgroundProperty)
            if ($bb -isnot [System.Windows.Media.SolidColorBrush]) { $global:SlantHoverLast = "enter: background is not a SolidColorBrush on $($src.GetType().Name)"; return }
            $a = Get-SlantHoverColor (Get-SlantBaseBrushColor $bb) $stato.Quanto
            $sb = New-SlantHoverStoryboard $t $a 120 'HoldEnd'
            $sb.Begin($t, $true)
            # a trace for the smoke test and for the log: the last hover started
            $global:SlantHoverLast = "enter: $($src.GetType().Name) $($bb.Color) -> $a"
        } catch { $global:SlantHoverLast = "enter: error $($_.Exception.Message)" }
    }.GetNewClosure())
    $Element.add_MouseLeave({
        param($src, $e)
        try {
            $t = $stato.Target
            if (-not $t) { return }
            $bb = $t.GetAnimationBaseValue([System.Windows.Controls.Border]::BackgroundProperty)
            if ($bb -isnot [System.Windows.Media.SolidColorBrush]) { return }
            $sb = New-SlantHoverStoryboard $t (Get-SlantBaseBrushColor $bb) 180 'Stop'
            $sb.Begin($t, $true)
        } catch { }
    }.GetNewClosure())
}


# Is one element inside another? The visual tree is walked up from the real
# source of the click (which is always the leaf: a TextBlock, a Path) until it is
# found. The dropdown needs it to know whether a press landed on its own button,
# inside itself, or outside both; and it is the visual tree that has to be walked
# and not the logical one, because the content of a Popup lives in a tree of its
# own that starts at the PopupRoot.
function Test-SlantVisualAncestor($nodo, $radice) {
    if ($null -eq $nodo -or $null -eq $radice) { return $false }
    try {
        $x = $nodo
        if ($x -is [System.Windows.FrameworkContentElement]) { $x = $x.Parent }
        $n = 0
        while ($null -ne $x -and $n -lt 200) {
            if ([object]::ReferenceEquals($x, $radice)) { return $true }
            $n++
            $su = $null
            if ($x -is [System.Windows.Media.Visual] -or $x -is [System.Windows.Media.Media3D.Visual3D]) {
                $su = [System.Windows.Media.VisualTreeHelper]::GetParent($x)
            }
            if ($null -eq $su -and $x -is [System.Windows.FrameworkElement]) { $su = $x.Parent }
            $x = $su
        }
    } catch { }
    return $false
}

function New-SlantPicker {
    param(
        [array]$Items,
        [string]$Current = "",
        [double]$TagWidth = 0,
        [scriptblock]$OnChange = $null,
        [scriptblock]$OnOpen = $null,
        # How tall the dropdown is allowed to get. With six entries it is not
        # needed; with forty it is: a list as tall as the window is a wall, and
        # the last rows are under the edge anyway. Shorter, and scrolling, reads
        # better, and the row that is current brings itself into view when it
        # opens.
        [double]$MaxHeight = 0
    )
    $pal = Get-SlantWidgetColours
    $bc = New-Object System.Windows.Media.BrushConverter
    $font = New-Object System.Windows.Media.FontFamily("Segoe UI")

    $radice = New-Object System.Windows.Controls.Grid
    $radice.HorizontalAlignment = 'Left'

    $btn = New-Object System.Windows.Controls.Border
    $btn.Background = $bc.ConvertFromString($pal.Panel3)
    $btn.CornerRadius = New-Object System.Windows.CornerRadius(5)
    $btn.Height = 26
    $btn.Padding = New-Object System.Windows.Thickness(9, 0, 9, 0)
    $btn.Cursor = 'Hand'
    $riga = New-Object System.Windows.Controls.StackPanel
    $riga.Orientation = 'Horizontal'
    $riga.VerticalAlignment = 'Center'
    $ospiteIcona = New-Object System.Windows.Controls.ContentControl
    $ospiteIcona.VerticalAlignment = 'Center'
    $sigla = New-Object System.Windows.Controls.TextBlock
    $sigla.FontSize = 11.5
    $sigla.FontFamily = $font
    $sigla.Foreground = $bc.ConvertFromString($pal.TextSoft)
    $sigla.VerticalAlignment = 'Center'
    $sigla.Margin = New-Object System.Windows.Thickness(7, 0, 0, 0)
    if ($TagWidth -gt 0) { $sigla.Width = $TagWidth }
    # the status dot, when an entry has one: it says whether the work stays on
    # this machine or leaves it, and it is the most important thing this dropdown
    # has to say
    $punto = New-Object System.Windows.Shapes.Ellipse
    $punto.Width = 6; $punto.Height = 6
    $punto.VerticalAlignment = 'Center'
    $punto.Margin = New-Object System.Windows.Thickness(7, 0, 0, 0)
    $punto.Visibility = 'Collapsed'
    $freccia = New-Object System.Windows.Shapes.Path
    $freccia.Data = [System.Windows.Media.Geometry]::Parse("M 0,0 L 7,0 L 3.5,4.5 Z")
    $freccia.Fill = $bc.ConvertFromString($pal.TextDim)
    $freccia.VerticalAlignment = 'Center'
    $freccia.Margin = New-Object System.Windows.Thickness(9, 1, 0, 0)
    [void]$riga.Children.Add($ospiteIcona)
    [void]$riga.Children.Add($sigla)
    [void]$riga.Children.Add($punto)
    [void]$riga.Children.Add($freccia)
    $btn.Child = $riga
    [void]$radice.Children.Add($btn)
    Add-SlantHover $btn

    # An open dropdown is a state, and it has to be seen once the pointer has
    # gone elsewhere: while it stays down the button's background sits on the
    # lighter colour, and goes back to its own when it closes again (on a second
    # click, on a choice, or on a click outside, which are all Closed on the
    # popup). The pointer goes on lightening it the way it lightens every other
    # button: it lightens from there, because Add-SlantHover starts at the base
    # value, and the base value is what this function rewrites.
    $fondoBase = ([System.Windows.Media.SolidColorBrush]$bc.ConvertFromString($pal.Panel3)).Color
    $fondoAcceso = Get-SlantHoverColor $fondoBase 0.14
    $accendi = {
        param([bool]$giu)
        try {
            $vecchio = $null
            $bb = $btn.GetAnimationBaseValue([System.Windows.Controls.Border]::BackgroundProperty)
            if ($bb -is [System.Windows.Media.SolidColorBrush]) { $vecchio = Get-SlantBaseBrushColor $bb }
            $target = $(if ($giu) { $fondoAcceso } else { $fondoBase })
            $btn.Background = New-Object System.Windows.Media.SolidColorBrush($target)
            if ($null -ne $vecchio -and $vecchio -ne $target) {
                $ms = $(if ($giu) { 120 } else { 180 })
                (New-SlantHoverStoryboard $btn $target $ms 'Stop' $vecchio).Begin($btn, $true)
            }
        } catch { }
    }.GetNewClosure()

    $pop = New-Object System.Windows.Controls.Primitives.Popup
    $pop.PlacementTarget = $btn
    $pop.Placement = 'Bottom'
    # StaysOpen is True, and that is what makes the click predictable. With
    # False it is the popup that takes the mouse: the press on the button goes to
    # IT, it closes on the MouseDown, and the release that follows finds the
    # dropdown already closed and opens it again. From outside this looked like a
    # dropdown that never closed on the second click, and the cure before this
    # one was to guess where the close had come from by looking at whether the
    # button was held down over the button: it worked almost every time, and
    # "almost" is not enough for a button. Now there is nothing to guess. The
    # dropdown has a state of its own ($stato.Giu), the button toggles it on the
    # press, and closing it for a click elsewhere is the job of a handler on the
    # window that can tell three cases apart: inside the button (the button
    # decides), inside the dropdown (a choice), outside both (it closes).
    $pop.StaysOpen = $true
    $pop.AllowsTransparency = $true
    # no system PopupAnimation: its fade starts from nothing and the content
    # lays itself out while it runs, which is exactly the flicker to be rid of.
    # The frame does the animation, on Opened, when the content already has its
    # size: it rises six pixels and opens from 96 per cent, which is the movement
    # a menu makes when it comes down.
    $pop.PopupAnimation = 'None'
    $pop.VerticalOffset = 4
    $cornice = New-Object System.Windows.Controls.Border
    $cornice.Background = $bc.ConvertFromString($pal.Overlay)
    $cornice.BorderThickness = New-Object System.Windows.Thickness(0)
    $cornice.CornerRadius = New-Object System.Windows.CornerRadius(6)
    $cornice.Padding = New-Object System.Windows.Thickness(4)
    $cornice.Margin = New-Object System.Windows.Thickness(10)   # room for the shadow
    $cornice.RenderTransformOrigin = New-Object System.Windows.Point(0.5, 0)
    $cornice.SnapsToDevicePixels = $true
    $cornice.UseLayoutRounding = $true
    $ombra = New-Object System.Windows.Media.Effects.DropShadowEffect
    $ombra.BlurRadius = 18; $ombra.ShadowDepth = 0; $ombra.Opacity = 0.55
    $ombra.Color = [System.Windows.Media.Colors]::Black
    $cornice.Effect = $ombra
    # the list scrolls instead of growing past the edge of the window
    $scorri = New-Object System.Windows.Controls.ScrollViewer
    $scorri.VerticalScrollBarVisibility = 'Auto'
    $scorri.HorizontalScrollBarVisibility = 'Disabled'
    $scorri.CanContentScroll = $false
    $scorri.Padding = New-Object System.Windows.Thickness(0)
    $lista = New-Object System.Windows.Controls.StackPanel
    $scorri.Content = $lista
    $cornice.Child = $scorri
    $pop.Child = $cornice
    [void]$radice.Children.Add($pop)

    # The state in a shared object: inside a closure $script: is the module
    # scope of the closure and not the one of this file, and a write in there
    # goes nowhere. Giu is the logical state of the dropdown, and it does not
    # agree with Popup.IsOpen while the way out is animating.
    $stato = [PSCustomObject]@{ Code = "$Current"; Voci = @($Items); Riempita = $false
                                Giu = $false; Chiudendo = $false; Agganciato = $false
                                Chiudi = $null }

    # the way in and the way out. The transform group is built once and reused,
    # so transforms do not pile up on every opening
    $scalaPop = New-Object System.Windows.Media.ScaleTransform(1.0, 1.0)
    $slittaPop = New-Object System.Windows.Media.TranslateTransform(0.0, 0.0)
    $gruppoPop = New-Object System.Windows.Media.TransformGroup
    [void]$gruppoPop.Children.Add($scalaPop)
    [void]$gruppoPop.Children.Add($slittaPop)
    $cornice.RenderTransform = $gruppoPop
    # The way in: the fade comes first and is short (110 ms), the movement lasts
    # almost twice as long (210) and ends on a quintic, which starts quickly and
    # settles without stopping dead. The two lengths differ on purpose: with one
    # length the panel looks like it slides in already opaque, and the end of the
    # movement is seen as a break.
    $entra = {
        try {
            $morbida = New-Object System.Windows.Media.Animation.QuinticEase
            $morbida.EasingMode = 'EaseOut'
            $piana = New-Object System.Windows.Media.Animation.QuadraticEase
            $piana.EasingMode = 'EaseOut'
            $cornice.BeginAnimation([System.Windows.UIElement]::OpacityProperty, $null)
            $op = New-Object System.Windows.Media.Animation.DoubleAnimation(0.0, 1.0, [TimeSpan]::FromMilliseconds(110))
            $op.EasingFunction = $piana
            $cornice.BeginAnimation([System.Windows.UIElement]::OpacityProperty, $op)
            $su = New-Object System.Windows.Media.Animation.DoubleAnimation(-7.0, 0.0, [TimeSpan]::FromMilliseconds(210))
            $su.EasingFunction = $morbida
            $slittaPop.BeginAnimation([System.Windows.Media.TranslateTransform]::YProperty, $su)
            foreach ($pr in @([System.Windows.Media.ScaleTransform]::ScaleXProperty,
                              [System.Windows.Media.ScaleTransform]::ScaleYProperty)) {
                $sc = New-Object System.Windows.Media.Animation.DoubleAnimation(0.965, 1.0, [TimeSpan]::FromMilliseconds(210))
                $sc.EasingFunction = $morbida
                $scalaPop.BeginAnimation($pr, $sc)
            }
        } catch { }
    }.GetNewClosure()
    $pop.add_Opened({ & $entra }.GetNewClosure())

    # The way out. A dropdown that vanishes at once reads as an error, and to
    # animate it the popup has to be held open while it goes: the real close
    # comes from a timer of 130 ms and not from the animation's Completed,
    # because a Completed that for whatever reason does not arrive would leave
    # the dropdown open for ever. The timer beats once and stops, and its body is
    # in a try/catch, which is the rule of this house: an exception inside a tick
    # stops that timer for ever.
    $chiusura = New-Object System.Windows.Threading.DispatcherTimer
    $chiusura.Interval = [TimeSpan]::FromMilliseconds(130)
    $chiusura.add_Tick({
        try {
            $chiusura.Stop()
            if ($stato.Chiudendo) {
                $stato.Chiudendo = $false
                $pop.IsOpen = $false
                $cornice.BeginAnimation([System.Windows.UIElement]::OpacityProperty, $null)
                $cornice.Opacity = 1.0
            }
        } catch { }
    }.GetNewClosure())

    $esce = {
        try {
            $dentro = New-Object System.Windows.Media.Animation.QuadraticEase
            $dentro.EasingMode = 'EaseIn'
            $op = New-Object System.Windows.Media.Animation.DoubleAnimation(0.0, [TimeSpan]::FromMilliseconds(120))
            $op.EasingFunction = $dentro
            $cornice.BeginAnimation([System.Windows.UIElement]::OpacityProperty, $op)
            $giu = New-Object System.Windows.Media.Animation.DoubleAnimation(-5.0, [TimeSpan]::FromMilliseconds(120))
            $giu.EasingFunction = $dentro
            $slittaPop.BeginAnimation([System.Windows.Media.TranslateTransform]::YProperty, $giu)
            foreach ($pr in @([System.Windows.Media.ScaleTransform]::ScaleXProperty,
                              [System.Windows.Media.ScaleTransform]::ScaleYProperty)) {
                $sc = New-Object System.Windows.Media.Animation.DoubleAnimation(0.985, [TimeSpan]::FromMilliseconds(120))
                $sc.EasingFunction = $dentro
                $scalaPop.BeginAnimation($pr, $sc)
            }
        } catch { }
        $chiusura.Stop()
        $chiusura.Start()
    }.GetNewClosure()

    $mostra = {
        param([string]$code)
        $voce = @($stato.Voci | Where-Object { $_.Code -eq $code }) | Select-Object -First 1
        if (-not $voce -and @($stato.Voci).Count -gt 0) { $voce = @($stato.Voci)[0] }
        if (-not $voce) { return }
        $stato.Code = "$($voce.Code)"
        $ospiteIcona.Content = $(if ($voce.Visual) { & $voce.Visual } else { $null })
        $sigla.Text = $(if ($voce.Tag) { "$($voce.Tag)" } else { $stato.Code.ToUpper() })
        if ($voce.Dot) {
            $punto.Fill = $bc.ConvertFromString("$($voce.Dot)")
            $punto.Visibility = 'Visible'
        } else { $punto.Visibility = 'Collapsed' }
        if ($voce.Tip) { $btn.ToolTip = "$($voce.Tip)" }
    }.GetNewClosure()

    # The rows are built on the FIRST opening and not at startup. Drawing five
    # flags costs: the SVGs sit on a synced drive and the first read pulls them
    # down, and the Spanish coat of arms on its own is 542 paths. At the opening
    # of the window that would be eight tenths of a second of ice, against the
    # rule that nothing over a tenth of a second belongs on the drawing thread.
    $riempi = {
        if ($stato.Riempita) { return }
        $stato.Riempita = $true
        # These are for the closure of the single row, which is born inside
        # this one: in there only the LOCAL variables of this block are visible,
        # not the ones of the function. Without copying them, $pop, $mostra and
        # $OnChange arrived null, the click on an entry did nothing and the catch
        # below swallowed the error: the dropdown stayed open and the value
        # stayed where it was. It is the same trip the handlers further down
        # take, and it is written out again there.
        $ilPop = $pop
        $ilMostra = $mostra
        $ilCambia = $OnChange
        $ilAccendi = $accendi
        $loStato = $stato
        # Every row is a grid and not a stack, and the four columns share their
        # measure with the ones of the other rows (SharedSizeGroup, inside the
        # scope that is the list): logo, tag, name and note all start at the same
        # x. Stacked, every row laid itself out on its own and each note ended up
        # at a different distance from the left, which is what the dropdown
        # looked like: the notes scattered down the right hand side.
        [System.Windows.Controls.Grid]::SetIsSharedSizeScope($lista, $true)
        $gruppi = @('pkIcon', 'pkTag', 'pkLabel', 'pkNote')
        foreach ($l in @($stato.Voci)) {
            $codice = "$($l.Code)"
            $vr = New-Object System.Windows.Controls.Border
            $vr.Background = [System.Windows.Media.Brushes]::Transparent
            $vr.CornerRadius = New-Object System.Windows.CornerRadius(4)
            $vr.Padding = New-Object System.Windows.Thickness(8, 5, 12, 5)
            $vr.Cursor = 'Hand'
            $sp = New-Object System.Windows.Controls.Grid
            foreach ($g in $gruppi) {
                $cd = New-Object System.Windows.Controls.ColumnDefinition
                $cd.Width = New-Object System.Windows.GridLength(0, 'Auto')
                $cd.SharedSizeGroup = $g
                [void]$sp.ColumnDefinitions.Add($cd)
            }
            if ($l.Visual) {
                $vis = & $l.Visual
                if ($vis) {
                    [System.Windows.Controls.Grid]::SetColumn($vis, 0)
                    [void]$sp.Children.Add($vis)
                }
            }
            $tc = New-Object System.Windows.Controls.TextBlock
            $tc.Text = $(if ($l.Tag) { "$($l.Tag)" } else { $codice.ToUpper() })
            $tc.FontSize = 11.5
            $tc.FontFamily = $font
            $tc.MinWidth = $(if ($TagWidth -gt 0) { $TagWidth } else { 26 })
            $tc.Foreground = $bc.ConvertFromString($pal.TextSoft)
            $tc.VerticalAlignment = 'Center'
            $tc.Margin = New-Object System.Windows.Thickness(8, 0, 0, 0)
            [System.Windows.Controls.Grid]::SetColumn($tc, 1)
            $tn = New-Object System.Windows.Controls.TextBlock
            $tn.Text = "$($l.Label)"
            $tn.FontSize = 11.5
            $tn.FontFamily = $font
            $tn.Foreground = $bc.ConvertFromString($pal.TextDim)
            $tn.VerticalAlignment = 'Center'
            $tn.Margin = New-Object System.Windows.Thickness(8, 0, 0, 0)
            [System.Windows.Controls.Grid]::SetColumn($tn, 2)
            [void]$sp.Children.Add($tc)
            [void]$sp.Children.Add($tn)
            # the note on the right: where the work ends up, or that the entry
            # still needs setting up
            if ($l.Note) {
                $tz = New-Object System.Windows.Controls.TextBlock
                $tz.Text = "$($l.Note)"
                $tz.FontSize = 10.5
                $tz.FontFamily = $font
                $tz.Foreground = $bc.ConvertFromString($(if ($l.Dot) { "$($l.Dot)" } else { $pal.TextFaint }))
                $tz.VerticalAlignment = 'Center'
                $tz.HorizontalAlignment = 'Right'
                $tz.Margin = New-Object System.Windows.Thickness(18, 0, 0, 0)
                [System.Windows.Controls.Grid]::SetColumn($tz, 3)
                [void]$sp.Children.Add($tz)
            }
            $vr.Child = $sp
            # the entry's code on the row: the label does not say it (an entry
            # can read "English" and be called 'en'), and without this an
            # automated check cannot pick out one row in particular
            $vr.Tag = $codice
            # the current row carries the lit background: in a list of forty
            # entries, knowing where you are is worth more than anything else
            if ($codice -eq $loStato.Code) { $vr.Background = $bc.ConvertFromString($pal.Panel3) }
            if ($l.Tip) { $vr.ToolTip = "$($l.Tip)" }
            Add-SlantHover $vr
            $vr.add_MouseLeftButtonUp({
                param($src, $e)
                try {
                    if ($loStato.Chiudi) { & $loStato.Chiudi $false }
                    else { $ilPop.IsOpen = $false }
                    & $ilAccendi $false
                    & $ilMostra $codice
                    if ($ilCambia) { & $ilCambia $codice }
                } catch {
                    # an error here means the click did nothing: into the log,
                    # not into nowhere
                    $log = Get-Command Write-SlantNote -ErrorAction SilentlyContinue
                    if ($log) { & $log "picker: entry $codice did not answer: $($_.Exception.Message)" }
                }
            }.GetNewClosure())
            [void]$lista.Children.Add($vr)
        }
    }.GetNewClosure()

    # The popup is a window of the system: left to itself it goes out of the
    # application's window, to the right and downwards, because the button that
    # opens it sits at the top right. Before it opens, how big it wants to be is
    # measured, where the button sits inside the window is read, and it is moved
    # by as much as it takes to stay inside. No placement delegates: a callback
    # built from a scriptblock does not run while the runspace is busy.
    $sistema = {
        $fin = [System.Windows.Window]::GetWindow($btn)
        if (-not $fin) { return }
        $margine = 10.0
        $cornice.MaxHeight = [double]::PositiveInfinity
        $cornice.Measure((New-Object System.Windows.Size([double]::PositiveInfinity, [double]::PositiveInfinity)))
        $vuole = $cornice.DesiredSize
        $dove = $btn.TransformToAncestor($fin).Transform((New-Object System.Windows.Point(0, 0)))
        $largo = $fin.ActualWidth
        $alto = $fin.ActualHeight
        # A list taller than the room it has scrolls, and a list that scrolls
        # brings its bar with it: that width has to be counted BEFORE deciding
        # where the dropdown goes, or it runs over to the right by those pixels.
        # With five entries it did not happen, with forty it does.
        $stanza = [Math]::Max($alto - ($dove.Y + $btn.ActualHeight) - $margine, $dove.Y - $margine)
        if ($MaxHeight -gt 0 -and $stanza -gt $MaxHeight) { $stanza = $MaxHeight }
        if ($vuole.Height -gt $stanza) {
            $vuole = New-Object System.Windows.Size(
                ($vuole.Width + [System.Windows.SystemParameters]::VerticalScrollBarWidth), $vuole.Height)
        }
        # across: the dropdown starts under the button, and if its right edge
        # would go outside it is pulled back until it fits
        $dx = 0.0
        $destra = $dove.X + $vuole.Width
        if ($destra -gt ($largo - $margine)) { $dx = -($destra - ($largo - $margine)) }
        if (($dove.X + $dx) -lt $margine) { $dx = $margine - $dove.X }
        # down: under the button if it fits, above it otherwise; and if it fits
        # neither above nor below, it is shortened and scrolls
        $stacco = 4.0
        $bordo = $cornice.Margin.Top + $cornice.Margin.Bottom
        $sotto = $alto - ($dove.Y + $btn.ActualHeight) - $margine
        $sopra = $dove.Y - $margine
        $inSu = ($vuole.Height -gt $sotto -and $sopra -gt $sotto)
        $tetto = $(if ($inSu) { $sopra } else { $sotto })
        if ($tetto -lt 80) { $tetto = 80 }
        # MaxHeight is the frame's own height, and the room measured here is the
        # popup's: the frame, the margin that carries its shadow, and the gap it
        # sits away from the button by. Setting the one straight from the other
        # put the last rows of a long list under the edge of the window, by
        # exactly those two. With five entries the list was shorter than the
        # room and it never showed; with forty it does.
        $altezza = [Math]::Max(60, $tetto - $bordo - $stacco)
        if ($MaxHeight -gt 0 -and $altezza -gt $MaxHeight) { $altezza = $MaxHeight }
        $cornice.MaxHeight = $altezza
        # and going up, the popup is hung from its own bottom edge, so where it
        # starts follows from the height it ends up with and not from the height
        # it asked for
        $dy = $stacco
        if ($inSu) {
            $dy = -($btn.ActualHeight + $stacco +
                    [Math]::Min($vuole.Height, ($altezza + $bordo)))
        }
        $pop.HorizontalOffset = $dx
        $pop.VerticalOffset = $dy
    }.GetNewClosure()

    $chiudi = {
        param([bool]$subito = $false)
        $stato.Giu = $false
        & $accendi $false
        if (-not $pop.IsOpen) { return }
        if ($subito) {
            $stato.Chiudendo = $false
            $chiusura.Stop()
            $pop.IsOpen = $false
            $cornice.BeginAnimation([System.Windows.UIElement]::OpacityProperty, $null)
            $cornice.Opacity = 1.0
            return
        }
        if ($stato.Chiudendo) { return }
        $stato.Chiudendo = $true
        & $esce
    }.GetNewClosure()

    $stato.Chiudi = $chiudi

    # The click outside. The popup no longer takes the mouse, so it is the
    # window that recognises it: a handler on the way down, which goes before
    # anyone else, and three cases. On the button it does nothing, because the
    # button already knows what it has to do and this would be the work twice
    # over (closed from here, opened again by it, which is exactly the fault from
    # before). Inside the dropdown it does nothing, because that is a choice.
    # Outside both, it closes. The handlers are hooked up on the first opening
    # and not at construction: before that the window is not there yet, and a
    # dropdown nobody ever opened needs none of it.
    $aggancia = {
        if ($stato.Agganciato) { return }
        $fin = [System.Windows.Window]::GetWindow($btn)
        if ($null -eq $fin) { return }
        $stato.Agganciato = $true
        $ilBtn = $btn
        $laCornice = $cornice
        $loStato = $stato
        $ilChiudi = $chiudi
        # Every handler ends with GetNewClosure, and that is not a detail: a
        # scriptblock passed as a delegate without a closure is run in the
        # script's scope, where these variables do not exist. It raises nothing,
        # reads $null, and the click outside does not close the dropdown: which
        # is exactly what it used to do.
        $fuoriClic = {
            param($src, $e)
            try {
                if (-not $loStato.Giu) { return }
                if (Test-SlantVisualAncestor $e.OriginalSource $ilBtn) { return }
                if (Test-SlantVisualAncestor $e.OriginalSource $laCornice) { return }
                & $ilChiudi $false
            } catch { }
        }.GetNewClosure()
        $fin.AddHandler([System.Windows.UIElement]::PreviewMouseDownEvent,
                        [System.Windows.Input.MouseButtonEventHandler]$fuoriClic, $true)
        # Escape closes it the way it closes everything else in this window, and
        # the key stops here: otherwise it would close the view underneath too
        $viaCol = {
            param($src, $e)
            try {
                if ($loStato.Giu -and $e.Key -eq 'Escape') { & $ilChiudi $false; $e.Handled = $true }
            } catch { }
        }.GetNewClosure()
        $fin.AddHandler([System.Windows.UIElement]::PreviewKeyDownEvent,
                        [System.Windows.Input.KeyEventHandler]$viaCol, $true)
        # a dropdown is anchored to its button: if the window moves, resizes or
        # goes to the back, it would be left hanging in the air
        $viaSubito = { try { if ($loStato.Giu) { & $ilChiudi $true } } catch { } }.GetNewClosure()
        $fin.add_Deactivated($viaSubito)
        $fin.add_LocationChanged($viaSubito)
        $fin.add_SizeChanged($viaSubito)
    }.GetNewClosure()

    $apri = {
        $stato.Chiudendo = $false
        $chiusura.Stop()
        # The state goes up first, before anything is built: if a row will not
        # draw, the dropdown stays open and wrong instead of staying shut and
        # looking dead to the click. An error here used to end up in the button's
        # catch and the dropdown never opened again, without saying anything to
        # anybody.
        $stato.Giu = $true
        # OnOpen BEFORE filling: whoever uses it remakes the entries with
        # SetItems, which empties the list and marks it to be built again.
        # Filling first, that emptying arrived afterwards and the dropdown opened
        # empty, every time.
        if ($OnOpen) { try { & $OnOpen } catch { } }
        try { & $riempi } catch {
            $log = Get-Command Write-SlantNote -ErrorAction SilentlyContinue
            if ($log) { & $log "picker: the list will not build: $($_.Exception.Message)" }
        }
        try { & $sistema } catch { }
        & $aggancia
        # the lit background follows the current choice, which can have been
        # changed after the list was already built
        try {
            foreach ($r in @($lista.Children)) {
                $suo = ("$($r.Tag)" -eq "$($stato.Code)")
                $r.Background = $(if ($suo) { $bc.ConvertFromString($pal.Panel3) }
                                  else { [System.Windows.Media.Brushes]::Transparent })
            }
        } catch { }
        if ($pop.IsOpen) { & $entra }   # it was closing: back in from where it was
        else { $pop.IsOpen = $true }
        & $accendi $true
        # and it brings itself into view, which in a list that scrolls is the
        # difference between finding yourself and looking for yourself
        try {
            $sua = @($lista.Children | Where-Object { "$($_.Tag)" -eq "$($stato.Code)" })[0]
            if ($sua) { [void]$sua.BringIntoView() }
        } catch { }
    }.GetNewClosure()

    # On the press and not on the release: a release also reaches whatever was
    # dragged over with the button already down, and a button that opens that way
    # opens when nobody asked it to.
    $btn.add_PreviewMouseLeftButtonDown({
        param($src, $e)
        try {
            if ($stato.Giu) { & $chiudi $false } else { & $apri }
            $e.Handled = $true
        } catch { }
    }.GetNewClosure())

    # whoever closes the popup, even going around everything above, leaves the
    # button unlit and the state clean
    $pop.add_Closed({
        $stato.Giu = $false
        $stato.Chiudendo = $false
        & $accendi $false
    }.GetNewClosure())

    & $mostra $Current

    $picker = [PSCustomObject]@{ Element = $radice; Popup = $pop }
    $picker | Add-Member -MemberType ScriptMethod -Name Code -Value { return "$($stato.Code)" }.GetNewClosure()
    # The logical state: true from the moment it opens to the moment it is
    # closed. Popup.IsOpen stays true for the 130 ms the way out is animating, so
    # whoever wants to know whether the dropdown is down asks this.
    $picker | Add-Member -MemberType ScriptMethod -Name IsDown -Value { return [bool]$stato.Giu }.GetNewClosure()
    $picker | Add-Member -MemberType ScriptMethod -Name Close -Value {
        param([bool]$subito = $true)
        & $chiudi $subito
    }.GetNewClosure()
    $picker | Add-Member -MemberType ScriptMethod -Name Toggle -Value {
        if ($stato.Giu) { & $chiudi $false } else { & $apri }
    }.GetNewClosure()
    $picker | Add-Member -MemberType ScriptMethod -Name Set -Value {
        param([string]$code)
        & $mostra $code
    }.GetNewClosure()
    # the entries change when what they describe changes: one that was not set
    # up before and is now has to stop saying "needs setup" without the window
    # being opened again
    $picker | Add-Member -MemberType ScriptMethod -Name SetItems -Value {
        param([array]$voci, [string]$code = "")
        $stato.Voci = @($voci)
        $stato.Riempita = $false
        $lista.Children.Clear()
        & $mostra $(if ($code) { $code } else { $stato.Code })
    }.GetNewClosure()
    # to warm the list once the window has drawn: whoever opens the window does
    # it after the first render, the way a scan of the folders is done
    $picker | Add-Member -MemberType ScriptMethod -Name Warm -Value { & $riempi }.GetNewClosure()
    return $picker
}

# A language chooser is this picker with a flag for an icon.

# ── the splash, for the seconds before an application is ready ─────────────
# An application that reads a folder before it can show anything has a few
# seconds with nothing to show. Hiding the window until then is worse than
# showing it: the window is the proof that the click worked. So the window
# opens at once and wears this over its body: the page it is about to show,
# blurred and darkened, with the brand in the middle of a ring that fills as
# the work goes.
#
# None of it is drawn on the application's thread. WPF beats its animations
# on the Dispatcher and not on the composition thread, so a load that holds
# the thread stops every animation the window has; the splash therefore draws
# on a thread of its own, through a HostVisual, and SlantUI.Splash.cs is
# where that is explained and done.
#
# The screen says two things, and it says them in two places, because they
# are two different things. The ring is the measure: one arc from twelve
# o'clock, which moves when the work moves and at no other time. The thin bar
# under the line is the pulse: two lozenges crossing it, with no scale and no
# beginning, saying only that something is still going on. They used to share
# one circle, a measuring arc with a short arc turning over it, and a circle
# carrying two readings at once reads as neither.
#
#     $splash = Show-SlantSplash -Chrome $chrome -Logo $svg -Text 'starting'
#     $splash.SetProgress(0.4, 'reading the folders')
#     $splash.Hide()
#
# The logo is read as vector art when there is any: pass an .svg, or a raster
# with an .svg of the same name beside it, and the brand is drawn at the size
# the ring gives it instead of being a picture scaled down to it.

function New-SlantArcGeometry {
    <#  .SYNOPSIS  A stroked arc of a circle, from twelve o'clock, clockwise.
        .PARAMETER Radius   The radius, in pixels.
        .PARAMETER From     Where the arc starts, as a turn (0 is the top).
        .PARAMETER Sweep    How much of the turn it covers, 0 to 1.
        .PARAMETER Offset   Where the circle's box starts. Half the stroke
                            width, usually: a stroke is drawn astride its
                            geometry, so an arc drawn from zero loses half a
                            stroke off the right and the bottom of the box
                            that holds it.  #>
    param([double]$Radius, [double]$From = 0.0, [double]$Sweep = 1.0, [double]$Offset = 0.0)
    Initialize-SlantWpf
    $sweep = [Math]::Max(0.0, [Math]::Min(0.9999, $Sweep))
    $a0 = ($From - 0.25) * 2 * [Math]::PI
    $a1 = ($From + $sweep - 0.25) * 2 * [Math]::PI
    $cx = $Offset + $Radius
    $p0 = New-Object System.Windows.Point(($cx + $Radius * [Math]::Cos($a0)),
                                          ($cx + $Radius * [Math]::Sin($a0)))
    $p1 = New-Object System.Windows.Point(($cx + $Radius * [Math]::Cos($a1)),
                                          ($cx + $Radius * [Math]::Sin($a1)))
    $fig = New-Object System.Windows.Media.PathFigure
    $fig.StartPoint = $p0
    $fig.IsClosed = $false
    $arc = New-Object System.Windows.Media.ArcSegment
    $arc.Point = $p1
    $arc.Size = New-Object System.Windows.Size($Radius, $Radius)
    $arc.SweepDirection = 'Clockwise'
    $arc.IsLargeArc = ($sweep -gt 0.5)
    [void]$fig.Segments.Add($arc)
    $geo = New-Object System.Windows.Media.PathGeometry
    [void]$geo.Figures.Add($fig)
    return $geo
}

$script:SlantSplashReady = $false

function Initialize-SlantSplash {
    <#  .SYNOPSIS  Compile the splash's drawing thread, once per machine.

        The DLL lives in the user's local data, not next to the module: a
        module can sit on a synced drive, and a synced drive locks a DLL that
        is loaded, so the next build fails with "access denied".  #>
    if ($script:SlantSplashReady) { return $true }
    try {
        if ('SlantSplashCore' -as [type]) { $script:SlantSplashReady = $true; return $true }
    } catch { }
    $src = Join-Path $PSScriptRoot 'SlantUI.Splash.cs'
    if (-not (Test-Path -LiteralPath $src)) { return $false }
    $dir = Join-Path $env:LOCALAPPDATA 'SlantUI'
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    # The name carries a stamp of the source, and that is not a flourish: a DLL
    # another window of the same application already has loaded cannot be
    # written over, so after an edit the build failed with "access denied" and
    # the second window came up with no splash at all. A path nobody has opened
    # yet is never in use, and the stamp changes only when the source does.
    $f = Get-Item -LiteralPath $src
    $stamp = "{0:x}{1:x}" -f $f.Length, ($f.LastWriteTimeUtc.Ticks -band 0xFFFFFFFF)
    $dll = Join-Path $dir "SlantUI.Splash.$stamp.dll"
    if (-not (Test-Path -LiteralPath $dll)) {
        $refs = @('WindowsBase', 'PresentationCore', 'PresentationFramework', 'System.Xaml')
        try { Add-Type -Path $src -OutputAssembly $dll -ReferencedAssemblies $refs -ErrorAction Stop }
        catch { try { Add-Type -Path $src -OutputAssembly $dll -ErrorAction Stop } catch { } }
    }
    if (-not (Test-Path -LiteralPath $dll)) {
        # last resort: a build of an older source. An application with an old
        # splash is better off than one with none.
        $prima = @(Get-ChildItem -LiteralPath $dir -Filter 'SlantUI.Splash*.dll' -ErrorAction SilentlyContinue |
                   Sort-Object LastWriteTime -Descending)
        if ($prima.Count -eq 0) { return $false }
        $dll = $prima[0].FullName
    }
    try { [void][Reflection.Assembly]::LoadFrom($dll) } catch { return $false }
    # the earlier builds go when they can: one another window still holds stays
    # where it is, and nothing about that matters
    foreach ($v in @(Get-ChildItem -LiteralPath $dir -Filter 'SlantUI.Splash*.dll' -ErrorAction SilentlyContinue |
                     Where-Object { $_.FullName -ne $dll })) {
        try { Remove-Item -LiteralPath $v.FullName -Force -ErrorAction Stop } catch { }
    }
    $script:SlantSplashReady = $true
    return $true
}

# Where the host goes in a window this library did not dress. A window holds
# one child, so the screen has to share it with whatever is already inside: a
# Panel takes another child and the screen goes on top of the rest, and
# anything else is wrapped in a Grid that can. An empty window gets the Grid
# too, and a window that already holds a Panel is left exactly as it was.
function Get-SlantSplashHost($Window) {
    $inside = $Window.Content
    if ($inside -is [System.Windows.Controls.Panel]) { return $inside }
    $grid = New-Object System.Windows.Controls.Grid
    if ($null -ne $inside) {
        $Window.Content = $null
        if ($inside -is [System.Windows.UIElement]) { [void]$grid.Children.Add($inside) }
        else {
            $slot = New-Object System.Windows.Controls.ContentControl
            $slot.Content = $inside
            [void]$grid.Children.Add($slot)
        }
    }
    $Window.Content = $grid
    return $grid
}

# A size that has not been given yet reads as NaN, and NaN is not a size.
function Get-SlantUsableSize([double]$v) {
    if ([double]::IsNaN($v) -or [double]::IsInfinity($v)) { return 0.0 }
    return $v
}

function Show-SlantSplash {
    <#  .SYNOPSIS  Cover an application's body while it gets ready.

        It comes in two forms, and they draw the same screen.

        With -Chrome it covers the body of a window this library dressed: the
        page underneath blurred under the scrim, the band left sharp so the
        window can still be moved and closed while it loads.

        With -Window it covers a bare System.Windows.Window and nothing else:
        no band, no blur, the screen on its own. That form is for the seconds
        before an application exists, when whatever starts it wants this on
        screen the moment the icon is clicked. Pair it with -Busy and the ring
        turns; the application then puts its own up in the same mode a moment
        later, and between the two there is no jump, because they are the same
        screen drawn by the same code.

        .PARAMETER Chrome   What Install-SlantWindow returned.
        .PARAMETER Window   A bare window to cover instead of a chrome. Its
                            content is left where it is and the screen is laid
                            over it.
        .PARAMETER Palette  Which palette to draw in, with -Window. The default
                            palette if nothing is named. A chrome carries its
                            own and does not take this.
        .PARAMETER Logo     A path to an .svg, to an image, or an ImageSource.
                            The band's own logo if nothing is passed and there
                            is a band. A vector is read as paths and drawn at
                            the ring's size; a raster with an .svg of the same
                            name beside it is read from the .svg.
        .PARAMETER Text     The first line under the ring.
        .PARAMETER Blur     How far the page behind goes out of focus. It
                            belongs to the -Chrome form: a bare window has
                            nothing behind the screen to blur.
        .PARAMETER Size     The outer size of the ring.
        .PARAMETER Busy     A wait with nothing to measure: no figure, and the
                            ring turns instead of filling. The bar underneath
                            stays, because that is the one thing such a wait
                            has to say. The first announced step turns it back
                            into a measure.

        .EXAMPLE
            $splash = Show-SlantSplash -Chrome $chrome -Logo .\brand.svg -Text 'starting'
            $splash.SetProgress(0.4, 'reading the folders')
            $splash.Hide()

        .EXAMPLE
            # before there is an application to dress
            $splash = Show-SlantSplash -Window $w -Logo .\brand.png -Busy -Text 'starting'
            $splash.Hide(190)

        .OUTPUTS  An object with SetProgress(fraction, text), SetText(text),
                  SetBusy(on), IsBusy(), Draw(fraction), Hide([ms]),
                  Snapshot(scale) and Visible.  #>
    [CmdletBinding(DefaultParameterSetName = 'Chrome')]
    param(
        [Parameter(ParameterSetName = 'Chrome', Mandatory = $true, Position = 0)]$Chrome,
        [Parameter(ParameterSetName = 'Window', Mandatory = $true)][System.Windows.Window]$Window,
        [Parameter(ParameterSetName = 'Window')][string]$Palette = "",
        $Logo = $null,
        [string]$Text = "",
        [Parameter(ParameterSetName = 'Chrome')][double]$Blur = 14,
        [double]$Size = 132,
        [switch]$Busy
    )
    Initialize-SlantWpf
    if (-not (Initialize-SlantSplash)) { throw "SlantUI: the splash's drawing thread would not build" }

    $nuda = ($PSCmdlet.ParameterSetName -eq 'Window')
    $sotto = $null
    $sfoca = $null
    if ($nuda) {
        $wpf = (Get-SlantPalette $Palette).Wpf
        $shell = Get-SlantSplashHost $Window
        $Blur = 0
    } else {
        $wpf = (Get-SlantPalette $Chrome.Palette).Wpf
        $shell = $Chrome.Body

        # the application's own content is the second row of the shell; the band
        # stays sharp and its buttons stay live, so the window can still be moved
        # or closed while it loads
        foreach ($child in $shell.Children) {
            if ([System.Windows.Controls.Grid]::GetRow($child) -eq 1) { $sotto = $child; break }
        }
        $sfoca = New-Object System.Windows.Media.Effects.BlurEffect
        $sfoca.Radius = 0
        $sfoca.KernelType = 'Gaussian'
        $sfoca.RenderingBias = 'Performance'
        if ($null -ne $sotto) { $sotto.Effect = $sfoca }
    }

    # The brand. It is read here, once, and handed over frozen: a frozen
    # Freezable is the one kind of drawing that crosses threads, and from a
    # vector it means the mark is drawn at the size the ring gives it instead
    # of being a 1385 pixel picture squeezed down to 68 points. What cannot be
    # frozen travels as a path and the drawing thread decodes its own copy,
    # because an ImageSource belongs to the thread that built it.
    $arte = $null
    $quale = ""
    if ($Logo -is [System.Windows.Media.ImageSource]) {
        $arte = $Logo
    } elseif ("$Logo") {
        $quale = "$Logo"
        $arte = Get-SlantArtSource -Path "$Logo"
    } elseif (-not $nuda -and $null -ne $Chrome.Logo -and
              $Chrome.Logo.Background -is [System.Windows.Media.ImageBrush]) {
        # nothing was passed: the band is already wearing the application's
        # mark, and when that is vector art it is exactly what this wants
        try {
            $sorgente = $Chrome.Logo.Background.ImageSource
            if ($sorgente -is [System.Windows.Media.DrawingImage]) { $arte = $sorgente }
            elseif ($sorgente -and $sorgente.UriSource) { $quale = $sorgente.UriSource.LocalPath }
        } catch { }
    }
    if ($null -ne $arte -and -not $arte.IsFrozen) {
        try { $arte = $arte.Clone(); $arte.Freeze() } catch { $arte = $null }
    }

    $core = New-Object SlantSplashCore(
        "$($wpf['accent'])", "$($wpf['control-active'])", "$($wpf['scrim'])", "$($wpf['text-3'])",
        $Size, $quale, "Segoe UI")

    if ($null -ne $arte) { try { $core.SetLogoSource($arte) } catch { } }
    if ($Busy) { try { $core.SetBusy($true) } catch { } }

    $ospite = New-Object SlantVisualHost($core.Host)
    if ($nuda) {
        # over everything that is already in there, and across all of it: a
        # Grid puts a child with no row and no column in the first cell, which
        # in a laid out window is a corner of it and not the window
        if ($shell -is [System.Windows.Controls.Grid]) {
            [System.Windows.Controls.Grid]::SetRow($ospite, 0)
            [System.Windows.Controls.Grid]::SetColumn($ospite, 0)
            [System.Windows.Controls.Grid]::SetRowSpan($ospite,
                [Math]::Max(1, $shell.RowDefinitions.Count))
            [System.Windows.Controls.Grid]::SetColumnSpan($ospite,
                [Math]::Max(1, $shell.ColumnDefinitions.Count))
        }
        [System.Windows.Controls.Panel]::SetZIndex($ospite, 2147483000)
    } else {
        [System.Windows.Controls.Grid]::SetRow($ospite, 1)
    }
    [void]$shell.Children.Add($ospite)
    $shell.UpdateLayout()

    # The first frame has to be in the right place already, or the ring is seen
    # jumping to the middle. A window that has not been shown yet has no
    # measured size at all, and the bare form is called exactly then, so what
    # the window was asked to be stands in until the first layout corrects it.
    $largo = $ospite.ActualWidth
    $alto = $ospite.ActualHeight
    if ($largo -le 1) { $largo = $shell.ActualWidth }
    if ($nuda) {
        if ($alto -le 1) { $alto = $shell.ActualHeight }
        if ($largo -le 1) { $largo = Get-SlantUsableSize $Window.Width }
        if ($alto -le 1) { $alto = Get-SlantUsableSize $Window.Height }
        if ($largo -le 1) { $largo = Get-SlantUsableSize $Window.ActualWidth }
        if ($alto -le 1) { $alto = Get-SlantUsableSize $Window.ActualHeight }
        $largo = [Math]::Max(1, $largo)
        $alto = [Math]::Max(1, $alto)
    } else {
        if ($alto -le 1) { $alto = [Math]::Max(1, $shell.ActualHeight - 40) }
    }
    $core.Start($largo, $alto, $Text)

    # the host has no say in its own size, so it is told when the window
    # changes: the veil covers the body whatever the window does
    $ospite.add_SizeChanged({
        param($src, $e)
        try { $core.SetSize($e.NewSize.Width, $e.NewSize.Height) } catch { }
    }.GetNewClosure())

    # The blur is there from the first frame, and it is not animated in. It
    # used to be, and the animation was never seen: it starts in the very
    # moment the application takes the thread to load, and an effect lives on
    # that thread, so it froze a third of the way in. There is nothing to ease
    # into either, because a page that has not loaded yet is an empty page.
    # Going out is another matter, and that one is animated: by then the work
    # is done and the thread is free.
    if ($null -ne $sfoca) { $sfoca.Radius = $Blur }

    $splash = [PSCustomObject]@{
        Element = $ospite
        Core    = $core
        Percent = 0.0
        Visible = $true
        Blur    = $sfoca
        BlurMax = $Blur
        Under   = $sotto
        Shell   = $shell
        Text    = $Text
    }

    $splash | Add-Member -MemberType ScriptMethod -Name SetProgress -Value {
        param([double]$frazione, [string]$testo = "")
        if ([double]::IsNaN($frazione)) { return }
        $this.Percent = [Math]::Max(0.0, [Math]::Min(1.0, $frazione))
        if ($testo) { $this.Text = "$testo" }
        if (-not $this.Visible) { return }
        try { $this.Core.SetProgress($this.Percent, $(if ($testo) { "$testo" } else { $null })) } catch { }
    }

    # for the callers that only move the ring, without a new line
    $splash | Add-Member -MemberType ScriptMethod -Name Draw -Value {
        param([double]$quanto)
        $this.SetProgress($quanto, "")
    }

    # the two modes can be swapped later too: a wait that at some point knows
    # how much is left stops turning and starts measuring
    $splash | Add-Member -MemberType ScriptMethod -Name SetBusy -Value {
        param([bool]$acceso)
        try { $this.Core.SetBusy($acceso) } catch { }
    }

    # and which of the two it is in now. An announced step ends the wait by
    # itself, so a caller that asked for one is not always still in it.
    $splash | Add-Member -MemberType ScriptMethod -Name IsBusy -Value {
        try { return [bool]$this.Core.Waiting } catch { return $false }
    }

    $splash | Add-Member -MemberType ScriptMethod -Name SetText -Value {
        param([string]$testo)
        $this.Text = "$testo"
        try { $this.Core.SetText("$testo") } catch { }
    }

    # what the drawing thread has on screen right now, for a screenshot: the
    # rest of the window renders itself, a HostVisual does not, because its
    # content lives somewhere else
    $splash | Add-Member -MemberType ScriptMethod -Name Snapshot -Value {
        param([double]$scala = 1.0)
        try { return $this.Core.Snapshot($scala) } catch { return $null }
    }

    # The handover. The veil fades on the drawing thread, so it is smooth
    # whatever the application is doing; the blur comes back here, and it
    # starts once the dispatcher has nothing left queued, because a fade that
    # begins under a busy thread is a fade nobody sees.
    $splash | Add-Member -MemberType ScriptMethod -Name Hide -Value {
        param([int]$ms = 420)
        if (-not $this.Visible) { return }
        $this.Visible = $false
        $me = $this
        $durata = $ms
        $parti = {
            try {
                if ($null -ne $me.Under) { $me.Under.UpdateLayout() }
                if ($durata -gt 0) {
                    $ease = New-Object System.Windows.Media.Animation.CubicEase
                    $ease.EasingMode = 'EaseOut'
                    # A bare window has no veil and no page under the screen, so
                    # both of these are absent there and only the screen's own
                    # fade is left. They are guarded one at a time, because a
                    # throw here would carry off the FadeOut below with it and
                    # the screen would never leave at all.
                    if ($null -ne $me.Blur) {
                        $torna = New-Object System.Windows.Media.Animation.DoubleAnimation(
                            $me.BlurMax, 0, [TimeSpan]::FromMilliseconds($durata))
                        $torna.EasingFunction = $ease
                        $me.Blur.BeginAnimation(
                            [System.Windows.Media.Effects.BlurEffect]::RadiusProperty, $torna)
                    }
                    # And the page arrives: it comes in from half a per cent
                    # larger and settles on its own size, in the same time and on
                    # the same curve the veil leaves on. It is not a zoom, it is
                    # six pixels in a thousand: it feels like a focus being
                    # found, which is exactly what is happening.
                    if ($null -ne $me.Under) {
                        $prima = $me.Under.RenderTransform
                        $origine = $me.Under.RenderTransformOrigin
                        $posa = New-Object System.Windows.Media.ScaleTransform(1.006, 1.006)
                        $me.Under.RenderTransformOrigin = New-Object System.Windows.Point(0.5, 0.5)
                        $me.Under.RenderTransform = $posa
                        foreach ($pr in @([System.Windows.Media.ScaleTransform]::ScaleXProperty,
                                          [System.Windows.Media.ScaleTransform]::ScaleYProperty)) {
                            $giu = New-Object System.Windows.Media.Animation.DoubleAnimation(
                                1.006, 1.0, [TimeSpan]::FromMilliseconds($durata))
                            $giu.EasingFunction = $ease
                            $posa.BeginAnimation($pr, $giu)
                        }
                        # the transform comes off as soon as it is done:
                        # leaving it there would mean leaving the application
                        # inside a transform it never asked for
                        $finita = New-Object System.Windows.Threading.DispatcherTimer
                        $finita.Interval = [TimeSpan]::FromMilliseconds($durata + 60)
                        $finita.add_Tick({
                            param($src, $e)
                            try {
                                $src.Stop()
                                $me.Under.RenderTransform = $prima
                                $me.Under.RenderTransformOrigin = $origine
                            } catch { }
                        }.GetNewClosure())
                        $finita.Start()
                    }
                }
                $me.Core.FadeOut([Math]::Max(1, $durata), [Action] {
                    try {
                        [void]$me.Shell.Children.Remove($me.Element)
                        if ($null -ne $me.Under) { $me.Under.Effect = $null }
                    } catch { }
                })
            } catch { }
        }.GetNewClosure()
        if ($ms -le 0) { & $parti; return }
        # Background, which is smoothed out after layout and after drawing:
        # the last step of a load usually leaves work queued, and those few
        # frames are the ones this transition needs. Not ApplicationIdle,
        # which a window with timers on it can keep waiting for.
        try {
            $this.Shell.Dispatcher.BeginInvoke(
                [System.Windows.Threading.DispatcherPriority]::Background, [action]$parti) | Out-Null
        } catch { & $parti }
    }

    return $splash
}

Export-ModuleMember -Function Get-SlantDataPath, Get-SlantTokens, Get-SlantPaletteNames,
    Get-SlantPalette, Get-SlantColor, Get-SlantMetric, ConvertTo-SlantColorRef,
    New-SlantBrush, Get-SlantBrushes,
    Get-SlantBandPoints, Get-SlantRoundedPolyPath, Get-SlantBandPath, Get-SlantBandGeometry,
    Format-SlantCoord,
    Initialize-SlantChrome, Get-SlantCreditText, Set-SlantWindowFrame, Set-SlantWindowScheme,
    Set-SlantWindowTransitions, Test-SlantWindowZoomed, Get-SlantWindowStyle,
    Get-SlantWindowSizes, Get-SlantWindowHandle, Get-SlantWorkArea,
    New-SlantWindowButton, New-SlantTitleBar, Set-SlantLogo, Install-SlantWindow,
    New-SlantVectorImage, Get-SlantArtSource, ConvertTo-SlantSvgTransform,
    Get-SlantWidgetColours, Set-SlantLogger, Write-SlantNote,
    Get-SlantHoverColor, Find-SlantHoverTarget, New-SlantHoverStoryboard,
    Get-SlantBaseBrushColor, Add-SlantHover, Set-SlantBorderColor, Test-SlantVisualAncestor,
    New-SlantPicker,
    New-SlantArcGeometry, Show-SlantSplash, Initialize-SlantSplash
