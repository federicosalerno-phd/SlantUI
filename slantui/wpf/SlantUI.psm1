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

Export-ModuleMember -Function Get-SlantDataPath, Get-SlantTokens, Get-SlantPaletteNames,
    Get-SlantPalette, Get-SlantColor, Get-SlantMetric, ConvertTo-SlantColorRef,
    New-SlantBrush, Get-SlantBrushes,
    Get-SlantBandPoints, Get-SlantRoundedPolyPath, Get-SlantBandPath, Get-SlantBandGeometry,
    Format-SlantCoord
