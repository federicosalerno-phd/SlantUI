using System;
using System.Globalization;
using System.Threading;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Media.Imaging;
using System.Windows.Threading;

// SlantUI's splash: the screen an application wears while it gets ready,
// drawn by a thread of its own.
//
// Why the drawing lives on its own thread. WPF animations do NOT run on the
// composition thread: the TimeManager beats on the Dispatcher, at Render
// priority, so an application that reads a folder on its UI thread stops
// every animation it has going. The ring here was once described as
// "composed, so it keeps turning": it was not true, and it showed. It turned
// in steps, one for each time the load gave the thread back, ten or fifteen
// times a second at best.
//
// The cure is to put the drawing where the load cannot reach. A HostVisual
// sits in the window's tree; the VisualTarget attached to it lives on another
// thread with a Dispatcher nobody blocks. The animations of that thread beat
// on every frame whatever the main thread is doing.
//
// What stays on the main thread is the blur of the page underneath, which is
// an effect on an element of that tree and cannot be moved. That is no loss:
// it arrives at the start, when nothing is loading yet, and leaves at the
// end, when the load is over.
//
// What the screen says, and why it is laid out this way. A load has two
// things to tell, and they are not the same thing: how far it has got, and
// that it is still going. They used to share one circle, an arc for the first
// and a short turning arc for the second, and a circle carrying two readings
// at once reads as neither: the eye cannot tell the measure from the motion.
// So they are apart now.
//
//   * The ring measures. One arc from twelve o'clock, with a lit head, and
//     nothing on that circle moves unless the work moves. The figure under it
//     is the same number: it is written by the arc's own animation, frame by
//     frame, so the two can never disagree.
//   * The shuttle under the line is the pulse. A thin bar with no scale to it,
//     whose two lozenges grow out of one edge, cross, and are drawn out of the
//     other: it says "still going" and cannot be read as a quantity. It fades
//     the moment the work reaches the end, and the ring lets one ripple out to
//     say so.
//
// The arc also creeps. When a step is announced the arc walks to it and then
// drifts on, slower and slower, towards a third of what is left: a load with
// nothing to report for four seconds should not look like a load that has
// stopped. It never walks backwards, so a step announcing less than the creep
// has already drawn is taken as a line of text and no more.

// The element that, in the window's tree, holds the place of a drawing that
// lives on another thread. It takes no mouse: there is nothing to click up
// here, and letting the click through leaves the pointer to the page below.
public class SlantVisualHost : FrameworkElement
{
    private readonly HostVisual _host;

    public SlantVisualHost(HostVisual host)
    {
        _host = host;
        IsHitTestVisible = false;
        AddVisualChild(_host);
    }

    protected override int VisualChildrenCount { get { return 1; } }

    protected override Visual GetVisualChild(int index) { return _host; }
}

// The ring: track, the arc of the measure with its lit head, the brand in the
// middle, and the ripple that marks the end. Progress is the only thing that
// moves it, and Progress is animated on a thread that never stalls.
public class SlantRing : FrameworkElement
{
    public static readonly DependencyProperty ProgressProperty =
        DependencyProperty.Register("Progress", typeof(double), typeof(SlantRing),
            new FrameworkPropertyMetadata(0.0, FrameworkPropertyMetadataOptions.AffectsRender,
                new PropertyChangedCallback(OnProgressChanged)));

    public static readonly DependencyProperty BurstProperty =
        DependencyProperty.Register("Burst", typeof(double), typeof(SlantRing),
            new FrameworkPropertyMetadata(0.0, FrameworkPropertyMetadataOptions.AffectsRender));

    // The turning arc, for a wait with nothing to measure. It is the opposite
    // case from the one the ring was split up for: when there is no quantity
    // to show, motion is the only thing on the circle and cannot be mistaken
    // for one.
    public static readonly DependencyProperty SpinProperty =
        DependencyProperty.Register("Spin", typeof(double), typeof(SlantRing),
            new FrameworkPropertyMetadata(0.0, FrameworkPropertyMetadataOptions.AffectsRender));

    public static readonly DependencyProperty IndeterminateProperty =
        DependencyProperty.Register("Indeterminate", typeof(bool), typeof(SlantRing),
            new FrameworkPropertyMetadata(false, FrameworkPropertyMetadataOptions.AffectsRender));

    // Called on every animated frame of Progress, on the drawing thread. The
    // figure under the ring is written from here and from nowhere else: a
    // timer of its own would drift against the arc, and the two would be
    // saying different numbers about the same thing.
    public Action<double> ProgressChanged;

    private static void OnProgressChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        SlantRing r = d as SlantRing;
        if (r == null || r.ProgressChanged == null) return;
        try { r.ProgressChanged((double)e.NewValue); }
        catch { }
    }

    public double Progress
    {
        get { return (double)GetValue(ProgressProperty); }
        set { SetValue(ProgressProperty, value); }
    }

    public double Burst
    {
        get { return (double)GetValue(BurstProperty); }
        set { SetValue(BurstProperty, value); }
    }

    public double Spin
    {
        get { return (double)GetValue(SpinProperty); }
        set { SetValue(SpinProperty, value); }
    }

    public bool Indeterminate
    {
        get { return (bool)GetValue(IndeterminateProperty); }
        set { SetValue(IndeterminateProperty, value); }
    }

    private readonly Pen _track;
    private readonly Pen _arc;
    private readonly Brush _head;
    private readonly Brush _halo;
    private readonly Color _accent;
    private readonly ImageSource _logo;
    private readonly double _thickness;
    private readonly double _logoSide;

    public SlantRing(double size, double thickness, Color accent, Color track, ImageSource logo)
    {
        Width = size;
        Height = size;
        _thickness = thickness;
        _accent = accent;
        _logo = logo;
        _logoSide = Math.Round(size * 0.52);

        SolidColorBrush tb = new SolidColorBrush(track);
        tb.Opacity = 0.38;
        tb.Freeze();
        // the track is thinner than the arc: the measure is what should carry
        // the weight, and a track of equal stroke competes with it
        _track = new Pen(tb, Math.Max(1.0, thickness * 0.55));
        _track.Freeze();

        // The arc is not one flat colour: it runs from a lighter accent to the
        // accent itself. The gradient is mapped to the box and not to the
        // geometry, because a gradient that belongs to the arc's own bounds
        // swings around as the arc grows.
        LinearGradientBrush ab = new LinearGradientBrush();
        ab.MappingMode = BrushMappingMode.Absolute;
        ab.StartPoint = new Point(size * 0.10, 0.0);
        ab.EndPoint = new Point(size * 0.90, size);
        ab.GradientStops.Add(new GradientStop(Lift(accent, 0.38), 0.0));
        ab.GradientStops.Add(new GradientStop(accent, 0.65));
        ab.Freeze();
        _arc = new Pen(ab, thickness);
        _arc.StartLineCap = PenLineCap.Round;
        _arc.EndLineCap = PenLineCap.Round;
        _arc.Freeze();

        SolidColorBrush hb = new SolidColorBrush(Lift(accent, 0.30));
        hb.Freeze();
        _head = hb;

        RadialGradientBrush halo = new RadialGradientBrush();
        halo.GradientStops.Add(new GradientStop(Color.FromArgb(76, accent.R, accent.G, accent.B), 0.0));
        halo.GradientStops.Add(new GradientStop(Color.FromArgb(24, accent.R, accent.G, accent.B), 0.55));
        halo.GradientStops.Add(new GradientStop(Color.FromArgb(0, accent.R, accent.G, accent.B), 1.0));
        halo.Freeze();
        _halo = halo;
    }

    private static Color Lift(Color c, double k)
    {
        return Color.FromRgb(
            (byte)Math.Round(c.R + (255 - c.R) * k),
            (byte)Math.Round(c.G + (255 - c.G) * k),
            (byte)Math.Round(c.B + (255 - c.B) * k));
    }

    // An arc of a circle, from twelve o'clock, clockwise. Sweep is a fraction
    // of a turn.
    private static Geometry Arc(Point c, double r, double from, double sweep)
    {
        if (sweep > 0.9999) sweep = 0.9999;
        double a0 = (from - 0.25) * 2 * Math.PI;
        double a1 = (from + sweep - 0.25) * 2 * Math.PI;
        PathFigure fig = new PathFigure();
        fig.StartPoint = new Point(c.X + r * Math.Cos(a0), c.Y + r * Math.Sin(a0));
        fig.IsClosed = false;
        ArcSegment seg = new ArcSegment();
        seg.Point = new Point(c.X + r * Math.Cos(a1), c.Y + r * Math.Sin(a1));
        seg.Size = new Size(r, r);
        seg.SweepDirection = SweepDirection.Clockwise;
        seg.IsLargeArc = sweep > 0.5;
        fig.Segments.Add(seg);
        PathGeometry geo = new PathGeometry();
        geo.Figures.Add(fig);
        return geo;
    }

    protected override Size MeasureOverride(Size available)
    {
        return new Size(Width, Height);
    }

    protected override void OnRender(DrawingContext dc)
    {
        double side = Math.Min(Width, Height);
        if (side <= 0) return;
        double r = (side - _thickness) / 2.0;
        Point c = new Point(side / 2.0, side / 2.0);

        dc.DrawEllipse(null, _track, c, r, r);

        if (Indeterminate)
        {
            // a fifth of the circle, turning, with its head lit like the arc's:
            // the same drawing language, saying "no idea how long" instead of
            // "this far"
            dc.PushTransform(new RotateTransform(Spin, c.X, c.Y));
            dc.DrawGeometry(null, _arc, Arc(c, r, 0.0, 0.2));
            double ah = (0.2 - 0.25) * 2 * Math.PI;
            Point hh = new Point(c.X + r * Math.Cos(ah), c.Y + r * Math.Sin(ah));
            dc.DrawEllipse(_halo, null, hh, _thickness * 2.3, _thickness * 2.3);
            dc.DrawEllipse(_head, null, hh, _thickness * 0.46, _thickness * 0.46);
            dc.Pop();
            DrawLogo(dc, c);
            return;
        }

        double p = Progress;
        if (p > 1.0) p = 1.0;
        if (p > 0.0025)
        {
            dc.DrawGeometry(null, _arc, Arc(c, r, 0.0, p));
            // The head is where the eye goes. It is what makes a growing arc
            // read as something moving, and not as a shape that happens to be
            // longer than it was a moment ago.
            double a = (p - 0.25) * 2 * Math.PI;
            Point h = new Point(c.X + r * Math.Cos(a), c.Y + r * Math.Sin(a));
            double halo = _thickness * 2.3;
            dc.DrawEllipse(_halo, null, h, halo, halo);
            dc.DrawEllipse(_head, null, h, _thickness * 0.46, _thickness * 0.46);
        }

        // The one flourish on the whole screen, and it lasts half a second: at
        // the end the ring lets a thin circle go outwards and fade.
        double b = Burst;
        if (b > 0.001 && b < 0.999)
        {
            double k = 1.0 - b;
            byte alpha = (byte)Math.Round(150.0 * k * k);
            SolidColorBrush bb = new SolidColorBrush(Color.FromArgb(alpha, _accent.R, _accent.G, _accent.B));
            bb.Freeze();
            Pen bp = new Pen(bb, Math.Max(0.5, _thickness * k));
            bp.Freeze();
            double br = r + r * 0.26 * b;
            dc.DrawEllipse(null, bp, c, br, br);
        }

        DrawLogo(dc, c);
    }

    private void DrawLogo(DrawingContext dc, Point c)
    {
        if (_logo == null) return;
        // the brand sits inside its square without being stretched
        double ar = _logo.Width > 0 && _logo.Height > 0 ? _logo.Width / _logo.Height : 1.0;
        double w = _logoSide, h = _logoSide;
        if (ar > 1.0) h = w / ar; else w = h * ar;
        dc.DrawImage(_logo, new Rect(c.X - w / 2.0, c.Y - h / 2.0, w, h));
    }
}

// The pulse: a thin bar whose two lozenges grow out of the left edge, cross,
// and are drawn out of the right one. It has no scale and no beginning, which
// is the point: it says work is going on, and nobody glancing at it can take
// it for a quantity.
public class SlantPulse : FrameworkElement
{
    public static readonly DependencyProperty PhaseProperty =
        DependencyProperty.Register("Phase", typeof(double), typeof(SlantPulse),
            new FrameworkPropertyMetadata(0.0, FrameworkPropertyMetadataOptions.AffectsRender));

    public double Phase
    {
        get { return (double)GetValue(PhaseProperty); }
        set { SetValue(PhaseProperty, value); }
    }

    private readonly Pen _rail;
    private readonly Pen _lead;
    private readonly Pen _trail;
    private readonly double _w, _h;

    public SlantPulse(double width, double height, Color accent, Color track)
    {
        _w = width; _h = height;
        Width = width; Height = height;

        SolidColorBrush rb = new SolidColorBrush(track);
        rb.Opacity = 0.30;
        rb.Freeze();
        _rail = Line(rb, Math.Max(1.0, height * 0.5));

        SolidColorBrush lb = new SolidColorBrush(accent);
        lb.Opacity = 0.92;
        lb.Freeze();
        _lead = Line(lb, height);

        SolidColorBrush sb = new SolidColorBrush(accent);
        sb.Opacity = 0.30;
        sb.Freeze();
        _trail = Line(sb, height * 0.8);
    }

    private static Pen Line(Brush b, double w)
    {
        Pen p = new Pen(b, w);
        p.StartLineCap = PenLineCap.Round;
        p.EndLineCap = PenLineCap.Round;
        p.Freeze();
        return p;
    }

    private static double Clamp01(double v) { return v < 0 ? 0 : (v > 1 ? 1 : v); }

    private static double Ease(double t)
    {
        if (t <= 0) return 0;
        if (t >= 1) return 1;
        return t < 0.5 ? 4 * t * t * t : 1 - Math.Pow(-2 * t + 2, 3) / 2;
    }

    // head and tail ease along the same curve, a third of a turn apart: the
    // lozenge is short as it enters, long as it crosses, short as it leaves
    private void Shuttle(DrawingContext dc, double t, Pen pen, double y, double inset)
    {
        double head = Ease(Clamp01(t / 0.66));
        double tail = Ease(Clamp01((t - 0.34) / 0.66));
        if (head - tail < 0.006) return;
        double span = _w - 2 * inset;
        dc.DrawLine(pen, new Point(inset + span * tail, y), new Point(inset + span * head, y));
    }

    protected override Size MeasureOverride(Size available)
    {
        return new Size(_w, _h);
    }

    protected override void OnRender(DrawingContext dc)
    {
        double y = _h / 2.0;
        double inset = _h / 2.0;
        dc.DrawLine(_rail, new Point(inset, y), new Point(_w - inset, y));
        double t = Phase - Math.Floor(Phase);
        // two of them, half a turn apart, so the bar is never empty: an
        // activity mark that stops, even for a frame, reads as a hang
        Shuttle(dc, (t + 0.5) % 1.0, _trail, y, inset);
        Shuttle(dc, t, _lead, y, inset);
    }
}

// A step with no corner at either end, 3t^2 - 2t^3: the curve the Qt half's
// splash.qml calls smooth(), so the two halves hand over on the same curve
// and not on two that look alike.
public sealed class SlantSmoothEase : EasingFunctionBase
{
    public SlantSmoothEase() { EasingMode = EasingMode.EaseIn; }

    protected override double EaseInCore(double t)
    {
        if (t <= 0) return 0;
        if (t >= 1) return 1;
        return t * t * (3 - 2 * t);
    }

    protected override Freezable CreateInstanceCore() { return new SlantSmoothEase(); }
}

// The thread that draws, and the orders it takes from outside.
public sealed class SlantSplashCore
{
    private readonly HostVisual _host = new HostVisual();
    private readonly AutoResetEvent _ready = new AutoResetEvent(false);
    private readonly Dispatcher _uiDispatcher;
    private Thread _thread;
    private Dispatcher _dispatcher;
    private VisualTarget _target;

    private Grid _root;
    private StackPanel _centre;
    private SlantRing _ring;
    private SlantPulse _pulse;
    private TextBlock _percentText;
    private TextBlock _lineText;
    private Border _ground;

    private readonly Color _accent, _track, _groundColor, _textColor;
    private readonly double _size, _thickness;
    private readonly string _logoPath;
    private readonly string _fontFamily;
    private ImageSource _logoSource;
    private double _w, _h;
    private double _target01;
    private double _goal;
    private double _speed;
    private DateTime _last;
    private DispatcherTimer _motor;
    private bool _running;
    private bool _framed;
    private bool _busy;
    private string _shown = "";
    private int _shownLen = -1;
    private bool _done;

    public HostVisual Host { get { return _host; } }
    public double Progress { get { return _target01; } }

    // What the arc has actually drawn, as opposed to what was last announced.
    // The two are never the same for long, and the difference is the point: a
    // test that samples this can say whether the ring ever stands still.
    public double Drawn
    {
        get
        {
            double v = 0;
            Dispatcher d = _dispatcher;
            if (d == null) return _target01;
            try { d.Invoke(DispatcherPriority.Send, (Action)delegate () { v = _ring.Progress; }); }
            catch { return _target01; }
            return v;
        }
    }

    // ground is what is behind the ring: the window's own surface, opaque,
    // while an application loads, so the window is seen empty and not the
    // application assembling itself under a veil; or the scrim, for a wait in
    // the middle of work, where the page stays in sight.
    public SlantSplashCore(string accent, string track, string ground, string text,
                           double size, string logoPath, string fontFamily)
    {
        _uiDispatcher = Dispatcher.CurrentDispatcher;
        _accent = Parse(accent, Colors.Gold);
        _track = Parse(track, Colors.Gray);
        _groundColor = Parse(ground, Color.FromArgb(255, 13, 13, 15));
        _textColor = Parse(text, Colors.Gainsboro);
        _size = size > 0 ? size : 132;
        _thickness = Math.Max(3.0, Math.Round(_size / 34.0));
        _logoPath = logoPath;
        _fontFamily = string.IsNullOrEmpty(fontFamily) ? "Segoe UI" : fontFamily;
    }

    // The brand as vector art, handed in already frozen. A frozen Freezable is
    // the one kind of drawing that crosses threads, so the caller can read an
    // SVG with the reader it already has and this thread can use what came out
    // of it, at any size, with no pixels in between. Anything not frozen is
    // refused, instead of being thrown at another thread where it would be
    // an exception and an empty middle.
    public void SetLogoSource(ImageSource source)
    {
        if (source != null && source.IsFrozen) _logoSource = source;
    }

    private static Color Parse(string s, Color fallback)
    {
        try
        {
            if (string.IsNullOrEmpty(s)) return fallback;
            object o = ColorConverter.ConvertFromString(s);
            if (o is Color) return (Color)o;
        }
        catch { }
        return fallback;
    }

    // It starts at the size the host has now: the first frame has to be in the
    // right place already, or the ring is seen jumping to the middle.
    public void Start(double width, double height, string firstLine)
    {
        _w = width; _h = height;
        _thread = new Thread(delegate ()
        {
            _dispatcher = Dispatcher.CurrentDispatcher;
            _target = new VisualTarget(_host);
            Build(firstLine);
            _target.RootVisual = _root;
            _ready.Set();
            Dispatcher.Run();
        });
        _thread.Name = "SlantSplash";
        _thread.SetApartmentState(ApartmentState.STA);
        _thread.IsBackground = true;
        _thread.Start();
        _ready.WaitOne(4000);
    }

    private void Build(string firstLine)
    {
        ImageSource logo = _logoSource;
        if (logo == null)
        {
            try
            {
                if (!string.IsNullOrEmpty(_logoPath) && System.IO.File.Exists(_logoPath))
                {
                    BitmapImage bi = new BitmapImage();
                    bi.BeginInit();
                    bi.UriSource = new Uri(_logoPath);
                    bi.CacheOption = BitmapCacheOption.OnLoad;
                    bi.EndInit();
                    bi.Freeze();
                    logo = bi;
                }
            }
            catch { }
        }

        _root = new Grid();
        _root.HorizontalAlignment = HorizontalAlignment.Stretch;
        _root.VerticalAlignment = VerticalAlignment.Stretch;

        _ground = new Border();
        SolidColorBrush sb = new SolidColorBrush(_groundColor);
        sb.Freeze();
        _ground.Background = sb;
        _root.Children.Add(_ground);

        StackPanel centre = new StackPanel();
        centre.HorizontalAlignment = HorizontalAlignment.Center;
        centre.VerticalAlignment = VerticalAlignment.Center;
        _root.Children.Add(centre);
        _centre = centre;

        _ring = new SlantRing(_size, _thickness, _accent, _track, logo);
        _ring.HorizontalAlignment = HorizontalAlignment.Center;
        centre.Children.Add(_ring);

        FontFamily ff = new FontFamily(_fontFamily);
        SolidColorBrush ab = new SolidColorBrush(_accent);
        ab.Freeze();
        SolidColorBrush tb = new SolidColorBrush(_textColor);
        tb.Freeze();

        _percentText = new TextBlock();
        _percentText.FontFamily = ff;
        _percentText.FontSize = 13;
        _percentText.FontWeight = FontWeights.SemiBold;
        _percentText.Foreground = ab;
        _percentText.HorizontalAlignment = HorizontalAlignment.Center;
        _percentText.Margin = new Thickness(0, 17, 0, 0);
        _percentText.Text = "0%";
        centre.Children.Add(_percentText);

        _lineText = new TextBlock();
        _lineText.FontFamily = ff;
        _lineText.FontSize = 11.5;
        _lineText.Foreground = tb;
        _lineText.HorizontalAlignment = HorizontalAlignment.Center;
        _lineText.Margin = new Thickness(0, 5, 0, 0);
        _lineText.Text = firstLine == null ? "" : firstLine;
        centre.Children.Add(_lineText);

        _pulse = new SlantPulse(Math.Round(_size * 1.30), 3.0, _accent, _track);
        _pulse.HorizontalAlignment = HorizontalAlignment.Center;
        _pulse.Margin = new Thickness(0, 15, 0, 0);
        centre.Children.Add(_pulse);

        // the figure is written by the arc's own animation, frame by frame
        _ring.ProgressChanged = delegate (double v)
        {
            try
            {
                string t = ((int)Math.Floor(v * 100 + 0.5)).ToString(CultureInfo.InvariantCulture) + "%";
                if (t == _shown) return;
                _shown = t;
                _percentText.Text = t;
                // a layout pass only when the figure changes width: without one
                // the new text is arranged in the old box and clipped, with one
                // on every frame the panel is measured sixty times a second for
                // nothing
                if (t.Length != _shownLen) { _shownLen = t.Length; Layout(); }
            }
            catch { }
        };

        Layout();

        // the pulse runs for as long as the splash is up, on the thread where
        // running means sixty frames a second whatever the application does
        DoubleAnimation phase = new DoubleAnimation(0, 1, TimeSpan.FromMilliseconds(1750));
        phase.RepeatBehavior = RepeatBehavior.Forever;
        _pulse.BeginAnimation(SlantPulse.PhaseProperty, phase);

        // A caller can ask for the waiting mode before the thread exists,
        // which is the normal way round: SetBusy is called and then Start.
        // Applying it here is what makes that work; without it the flag was
        // set and the screen came up measuring anyway, showing 1% of nothing.
        if (_busy) { SetBusyNow(true); return; }

        // and the arc starts drifting at once, before anyone has announced a
        // step: the first seconds of a load are the ones with nothing to say
        Run();
    }

    // Without a PresentationSource the layout does not happen by itself: it is
    // measured and arranged by hand, which for five elements costs nothing.
    private void Layout()
    {
        if (_root == null) return;
        Size s = new Size(Math.Max(1, _w), Math.Max(1, _h));
        _root.Measure(s);
        _root.Arrange(new Rect(new Point(0, 0), s));
    }

    public void SetSize(double width, double height)
    {
        if (_dispatcher == null) return;
        _dispatcher.BeginInvoke(DispatcherPriority.Render, (Action)delegate ()
        {
            _w = width; _h = height;
            Layout();
        });
    }

    // A step is announced, and the arc is told where to get to. It is never
    // told to jump: the motor below takes it there.
    public void SetProgress(double fraction, string line)
    {
        if (double.IsNaN(fraction)) return;
        if (fraction < 0) fraction = 0;
        if (fraction > 1) fraction = 1;
        _target01 = fraction;
        if (_dispatcher == null) return;
        _dispatcher.BeginInvoke(DispatcherPriority.Normal, (Action)delegate ()
        {
            try
            {
                if (line != null) { _lineText.Text = line; Layout(); }
                // never backwards: the arc may already have crept past a step
                // that turns out to announce less than it reached
                if (fraction > _goal) _goal = fraction;
                if (fraction > 0.9995) _goal = 1.0;
                // Whoever announces a step has something to measure, so the
                // wait with nothing to measure ends here by itself. It is what
                // makes a handover work: the screen a launcher put up turns,
                // this one starts turning, and it begins to fill on the first
                // step, with no jump to be seen between the two.
                if (_busy && fraction > 0.0) { SetBusyNow(false); }
                if (!_busy) Run();
            }
            catch { }
        });
    }

    // Why the arc is not a DoubleAnimation any more.
    //
    // One animation per step means one arrival per step, and an arrival is a
    // stop: the arc leapt thirty degrees, stopped dead, leapt forty-five,
    // stopped again. Easing made it worse, because an ease-out ends at zero
    // speed by definition. Between the steps a slow "creep" animation filled
    // the silence, but it started a tenth of a second later and on another
    // curve, so what was seen was start, stop, start, stop.
    //
    // So the arc has a speed instead of a destination. Sixty times a second
    // this moves it towards the goal, and the speed itself is eased, not the
    // position: it rises and falls smoothly and never reaches zero while there
    // is work left. Three rules and nothing else:
    //
    //   * far from the goal it moves quickly, proportionally to what is left,
    //     with a floor so a small gap is still crossed at a visible pace;
    //   * at the goal it keeps drifting, very slowly, towards a third of what
    //     remains: a load with nothing to report for four seconds must not look
    //     like a load that has stopped, and a drift of one per cent a second is
    //     movement without being a promise;
    //   * at the end it closes the circle and stops, which is the one stop that
    //     means something.
    //
    // The timer lives on the drawing thread, which has nothing else to do, so
    // it beats while the application is stuck reading a folder.
    private void Run()
    {
        _last = DateTime.UtcNow;
        // One step per composed frame. CompositionTarget.Rendering fires once
        // for every frame this thread's compositor puts up, so the arc moves
        // exactly as often as the screen can show it moving: no timer interval
        // to miss a frame or land twice in one, and nothing to tune. The timer
        // stays as a fallback for a thread where that event never comes, and
        // the first frame arms it: if a frame has arrived, the fallback is
        // dropped for good.
        if (!_running)
        {
            _running = true;
            CompositionTarget.Rendering += OnFrame;
            if (_motor == null)
            {
                _motor = new DispatcherTimer(DispatcherPriority.Render, _dispatcher);
                _motor.Interval = TimeSpan.FromMilliseconds(16);
                _motor.Tick += delegate (object s, EventArgs e) { if (!_framed) Step(); };
            }
            _motor.Start();
        }
    }

    private void OnFrame(object sender, EventArgs e)
    {
        if (!_framed)
        {
            _framed = true;
            try { if (_motor != null) _motor.Stop(); } catch { }
        }
        Step();
    }

    private void Halt()
    {
        if (!_running) return;
        _running = false;
        try { CompositionTarget.Rendering -= OnFrame; } catch { }
        try { if (_motor != null) _motor.Stop(); } catch { }
    }

    private void Step()
    {
        try
        {
            DateTime now = DateTime.UtcNow;
            double dt = (now - _last).TotalSeconds;
            _last = now;
            if (dt <= 0) return;
            if (dt > 0.25) dt = 0.25;          // a frozen thread must not teleport the arc

            double pos = _ring.Progress;
            double ceiling = _goal >= 1.0 ? 1.0 : _goal + (1.0 - _goal) * 0.32;
            double want;
            if (pos < _goal - 0.0005)
            {
                // what is left, crossed in about a second and a half, but never
                // slower than eight per cent a second. The last stretch is
                // quicker: the splash is taken away shortly after the work ends,
                // and an arc still climbing when it goes looks like something
                // was skipped.
                double floor = _goal >= 1.0 ? 0.55 : 0.06;
                want = Math.Max(floor, (_goal - pos) * 0.68);
            }
            else if (pos < ceiling)
            {
                want = 0.011;                  // the drift: alive, and no promise
            }
            else
            {
                want = 0.0;
            }

            // the speed is what gets eased, so there are no corners in the
            // movement even when the goal jumps
            _speed += (want - _speed) * Math.Min(1.0, dt * 6.0);
            double next = pos + _speed * dt;
            if (next > ceiling) { next = ceiling; _speed = want; }
            if (next > 1.0) next = 1.0;
            if (next != pos) _ring.Progress = next;

            if (_goal >= 1.0 && next >= 0.9999)
            {
                Halt();
                Finish();
            }
            else if (want == 0.0 && Math.Abs(_speed) < 0.0005)
            {
                // nothing left to draw until the next step arrives
                Halt();
            }
        }
        catch { }
    }

    // The end: the pulse has nothing left to say, so it goes, and the ring
    // lets one ripple out. Both are over well before the splash is taken away.
    private void Finish()
    {
        if (_done) return;
        _done = true;
        try
        {
            DoubleAnimation fade = new DoubleAnimation(1.0, 0.0, TimeSpan.FromMilliseconds(260));
            fade.FillBehavior = FillBehavior.HoldEnd;
            _pulse.BeginAnimation(UIElement.OpacityProperty, fade);

            DoubleAnimation ripple = new DoubleAnimation(0.0, 1.0, TimeSpan.FromMilliseconds(620));
            CubicEase e = new CubicEase();
            e.EasingMode = EasingMode.EaseOut;
            ripple.EasingFunction = e;
            ripple.FillBehavior = FillBehavior.HoldEnd;
            _ring.BeginAnimation(SlantRing.BurstProperty, ripple);
        }
        catch { }
    }

    // True once the arc has drawn the whole circle. The application waits for
    // this instead of guessing a delay: the wait at the end should be as short
    // as it can be, and how long the arc needs is something only the arc knows.
    public bool Complete { get { return _goal >= 1.0 && Drawn >= 0.9995; } }

    // True once a composed frame has driven the arc at least once, which is
    // how a caller can tell the movement is coming from the compositor and not
    // from the fallback timer. A test that cannot see the difference would let
    // the good path rot away unnoticed.
    public bool Composed { get { return _framed; } }

    // Which of the two modes the screen is in. It is readable and not only
    // settable for the same reason Composed is: a waiting mode that was asked
    // for before the thread existed and then quietly dropped looked, from
    // outside, exactly like one that took.
    public bool Waiting { get { return _busy; } }

    // A wait with nothing to measure: no figure, and the ring turns instead of
    // filling. It is what an application shows while it does one thing whose
    // length nobody knows, and it is drawn by the same thread, so it keeps
    // turning while that thing happens.
    // A wait with nothing to measure: no figure, and the ring turns instead of
    // filling. It is what an application shows while it does one thing whose
    // length nobody knows, and it is drawn by the same thread, so it keeps
    // turning while that thing happens.
    public void SetBusy(bool on)
    {
        if (_dispatcher == null) { _busy = on; return; }
        _dispatcher.BeginInvoke(DispatcherPriority.Normal, (Action)delegate () { SetBusyNow(on); });
    }

    private void SetBusyNow(bool on)
    {
        {
            try
            {
                _busy = on;
                _ring.Indeterminate = on;
                // The figure goes, because in a wait with nothing to measure
                // it would be a lie. The bar stays: it says work is going on,
                // and in a wait that is the only thing there is to say.
                _percentText.Visibility = on ? Visibility.Collapsed : Visibility.Visible;
                if (on)
                {
                    Halt();
                    DoubleAnimation turn = new DoubleAnimation(0, 360, TimeSpan.FromMilliseconds(1500));
                    turn.RepeatBehavior = RepeatBehavior.Forever;
                    _ring.BeginAnimation(SlantRing.SpinProperty, turn);
                }
                else
                {
                    _ring.BeginAnimation(SlantRing.SpinProperty, null);
                    Run();
                }
                Layout();
            }
            catch { }
        }
    }

    public void SetText(string line)
    {
        if (_dispatcher == null || line == null) return;
        _dispatcher.BeginInvoke(DispatcherPriority.Normal, (Action)delegate ()
        {
            try { _lineText.Text = line; Layout(); } catch { }
        });
    }

    // The handover is done by this thread, so it is smooth whatever the
    // application is doing; when it is over it tells the caller, on the
    // caller's thread, to take the host out of the tree and the blur off the
    // page.
    //
    // It is the movement the Qt half draws (splash.qml), on the same curves
    // and at the same fractions of the same length, so an application in one
    // half and an application in the other hand over the same way. The ring
    // goes first, over the first forty-five hundredths, fading as it grows a
    // little, the way the circle it let go at the end went outwards. The
    // ground thins out behind it between a tenth and six tenths, uncovering
    // the page. And the page comes into focus through it over the whole
    // length: that part is the caller's, because the page lives on the
    // caller's thread (Hide, in SlantUI.psm1).
    public void FadeOut(int ms, Action done)
    {
        if (_dispatcher == null)
        {
            if (done != null) done();
            return;
        }
        _dispatcher.BeginInvoke(DispatcherPriority.Normal, (Action)delegate ()
        {
            try
            {
                Halt();
                double total = Math.Max(1, ms);
                ScaleTransform grow = new ScaleTransform(1.0, 1.0);
                _centre.RenderTransformOrigin = new Point(0.5, 0.5);
                _centre.RenderTransform = grow;

                DoubleAnimation ring = new DoubleAnimation(1.0, 0.0, TimeSpan.FromMilliseconds(total * 0.45));
                ring.EasingFunction = new SlantSmoothEase();
                _centre.BeginAnimation(UIElement.OpacityProperty, ring);

                CubicEase out_ = new CubicEase();
                out_.EasingMode = EasingMode.EaseOut;
                foreach (DependencyProperty pr in new DependencyProperty[] {
                             ScaleTransform.ScaleXProperty, ScaleTransform.ScaleYProperty })
                {
                    DoubleAnimation g = new DoubleAnimation(1.0, 1.08, TimeSpan.FromMilliseconds(total * 0.45));
                    g.EasingFunction = out_;
                    grow.BeginAnimation(pr, g);
                }

                DoubleAnimation ground = new DoubleAnimation(1.0, 0.0, TimeSpan.FromMilliseconds(total * 0.50));
                ground.BeginTime = TimeSpan.FromMilliseconds(total * 0.10);
                ground.EasingFunction = new SlantSmoothEase();
                _ground.BeginAnimation(UIElement.OpacityProperty, ground);

                // the clock of the whole movement: nothing to see, and it says
                // when the movement is over
                DoubleAnimation clock = new DoubleAnimation(1.0, 1.0, TimeSpan.FromMilliseconds(total));
                clock.Completed += delegate (object s, EventArgs ev)
                {
                    if (done != null && _uiDispatcher != null)
                        _uiDispatcher.BeginInvoke(DispatcherPriority.Send, done);
                    Shutdown();
                };
                _root.BeginAnimation(UIElement.OpacityProperty, clock);
            }
            catch
            {
                if (done != null && _uiDispatcher != null)
                    _uiDispatcher.BeginInvoke(DispatcherPriority.Send, done);
            }
        });
    }

    // A photograph of what this thread has on screen: the rest of the window
    // renders itself, a HostVisual does not, because its content lives
    // somewhere else. The screenshots of the window need it.
    public BitmapSource Snapshot(double scale)
    {
        if (_dispatcher == null) return null;
        BitmapSource result = null;
        double sc = scale > 0 ? scale : 1.0;
        _dispatcher.Invoke(DispatcherPriority.Render, (Action)delegate ()
        {
            try
            {
                Layout();
                RenderTargetBitmap rtb = new RenderTargetBitmap(
                    (int)Math.Round(_w * sc), (int)Math.Round(_h * sc),
                    96 * sc, 96 * sc, PixelFormats.Pbgra32);
                rtb.Render(_root);
                rtb.Freeze();
                result = rtb;
            }
            catch { }
        });
        return result;
    }

    public void Shutdown()
    {
        try
        {
            Dispatcher d = _dispatcher;
            _dispatcher = null;
            if (d != null) d.BeginInvoke(DispatcherPriority.Normal, (Action)delegate () { d.InvokeShutdown(); });
        }
        catch { }
    }
}
