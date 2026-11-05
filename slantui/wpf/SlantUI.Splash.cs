using System;
using System.Collections.Generic;
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
//   * The bar under the line fills with the ring, the same fraction drawn
//     straight (SlantBar). Since 2026-11-05 a screen that measures shows one
//     way of loading and not two: there was a shuttle under it, two lozenges
//     crossing a rail, which said "still going" in a second style. The shuttle
//     is left for the wait with nothing to measure (SetBusy), where it is the
//     only thing to say.
//
// The arc keeps a pace, not a destination: it goes round in the time the load
// is expected to take (SetExpected), and the announced steps only nudge it,
// half again faster when it is behind them, half as fast when it is ahead. It
// never stops before the end and never races: a load whose steps are uneven in
// time made an arc that chased each step race to it and then stand still.

// How the brand moves while the screen is up. Nothing moves unless an
// application asks for it: a preset is a name and a handful of numbers, and
// the parts it moves are read off the drawing itself, so one preset fits a
// mark it has never seen.
//
//   * "breathe": each part moves out along its own line and back, one after
//     the other, so the mark seems to breathe in turns;
//   * "pulse": the same movement with every part in step;
//   * "none": the mark stands still, which is what it has always done.
//   * "flow": a choreography, not a breath. The parts come in from close by,
//     turning a little and growing, each a little after the one before, and
//     land softly; the hub grows in under them, and a soft glow lights up
//     behind. The whole entrance takes six tenths of a second. Then a cycle of
//     1.8 seconds: a wave goes round the mark and each part in turn lifts out
//     and grows a touch, always one or two of them on the move, and the whole
//     mark floats. Nothing on it is drawn through a layer once it has come in:
//     no light, no sheen, the glow one of a set of brushes made once, so each
//     frame costs what the shapes cost. Settle brings it all to rest before
//     the fade. It was asked for on 2026-11-05 ("static, boring, slow, it
//     stutters"): the breath was smooth, measured at one change per frame at
//     60 Hz, but it moved a few pixels in three and a half seconds, which reads
//     as standing still; and later the same day "faster, more pleasant, fluid":
//     the first flow took a second to come in and 2.6 to go round, and the
//     last part jumped a quarter of its lift in one frame where the cycle took
//     over from the entrance.
//
// The time of "flow" is an animation, not a stopwatch (FlowTime): its value is
// the frame's own time, the same for every shape drawn in that frame, while a
// stopwatch read inside OnRender is whenever OnRender happens to run, a few
// milliseconds early or late from one frame to the next, and the movement
// judders by that much. A window shown covered until it has drawn calls
// RestartFlow when it is uncovered, so the entrance is seen from its start.
//
// A part is one top-level shape of the drawing; a group holding a single
// thing is opened up until there is more than one thing inside. Its line runs
// from the centre of the movement through the part's own centroid. The centre
// is the part sitting on the middle of the mark, when there is one, and that
// part is the hub: it holds still and the others move away from it. A mark
// with no hub moves about the middle of its frame. The frame is the box the
// mark was drawn in, its viewBox when it came from an SVG.
//
// Distances are fractions of the frame's height, so a preset reads the same
// on a mark of any size: 0.0335 is eight units on a mark 239 tall. The
// distance of part k at time t is
//
//     d = height * (Offset + Amplitude * sin(2 pi t / Period - k * Stagger))
//
// which at the defaults goes from 0, the parts closed around the hub, to
// sixteen units and back in 2.4 seconds, each part a third of a turn behind
// the one before. Only a vector mark has parts: a raster stands still.
//
// Curve "smooth" passes the sine through a smoothstep before it is used: the
// same two ends and the same cycle, but the part lingers a moment at each end,
// closed and open, and travels in between. A plain sine never rests, and on a
// mark that moves a long way that reads as a twitch; with the rest it reads
// as a breath.
public sealed class SlantMotion
{
    public string Preset = "none";
    public double Period = double.NaN;      // seconds for one cycle
    public double Offset = double.NaN;      // the middle of the movement
    public double Amplitude = double.NaN;   // how far it goes either side of the middle
    public double Stagger = double.NaN;     // degrees between one part and the next
    public int[] Still;                     // parts that never move, in drawing order
    public int Centre = -1;                 // the part the lines start from; -1 finds the hub
    public int Arrive = -1;                 // ms for the parts to open when the screen comes up
    public int Settle = -1;                 // ms for them to come home before it goes
    public string Curve = "sine";           // "sine", or "smooth": a rest at either end

    // the movement as it was drawn: eight units either side of eight, on a
    // mark 238.92 units tall
    public const double Breath = 8.0 / 238.92;
}

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

    // The time of the brand's movement, in seconds within one cycle, and how
    // much of the movement is let through: 0 is every part at home, 1 the
    // whole of it. Both are animated on the drawing thread, so the mark moves
    // while the application holds its own thread down, like the ring does.
    public static readonly DependencyProperty MotionClockProperty =
        DependencyProperty.Register("MotionClock", typeof(double), typeof(SlantRing),
            new FrameworkPropertyMetadata(0.0, FrameworkPropertyMetadataOptions.AffectsRender));

    public static readonly DependencyProperty MotionAmountProperty =
        DependencyProperty.Register("MotionAmount", typeof(double), typeof(SlantRing),
            new FrameworkPropertyMetadata(1.0, FrameworkPropertyMetadataOptions.AffectsRender));

    // "flow" only: seconds since the entrance began, animated on the drawing
    // thread, so every frame reads the frame's own time
    public static readonly DependencyProperty FlowTimeProperty =
        DependencyProperty.Register("FlowTime", typeof(double), typeof(SlantRing),
            new FrameworkPropertyMetadata(0.0, FrameworkPropertyMetadataOptions.AffectsRender));

    public double FlowTime
    {
        get { return (double)GetValue(FlowTimeProperty); }
        set { SetValue(FlowTimeProperty, value); }
    }

    public double MotionClock
    {
        get { return (double)GetValue(MotionClockProperty); }
        set { SetValue(MotionClockProperty, value); }
    }

    public double MotionAmount
    {
        get { return (double)GetValue(MotionAmountProperty); }
        set { SetValue(MotionAmountProperty, value); }
    }

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

        // (Burst is kept as a property for the applications that set it, and
        // draws nothing: the thin circle the ring let go at the end is gone.)
        DrawLogo(dc, c);
    }

    private void DrawLogo(DrawingContext dc, Point c)
    {
        if (_logo == null) return;
        // the brand sits inside its square without being stretched
        double ar = _logo.Width > 0 && _logo.Height > 0 ? _logo.Width / _logo.Height : 1.0;
        double w = _logoSide, h = _logoSide;
        if (ar > 1.0) h = w / ar; else w = h * ar;
        Rect where = new Rect(c.X - w / 2.0, c.Y - h / 2.0, w, h);
        if (_parts == null || _box.Width <= 0 || _box.Height <= 0)
        {
            dc.DrawImage(_logo, where);
            return;
        }

        // The same placement DrawImage gives the whole drawing, the box of
        // the mark onto the square, and then each part on its own, moved
        // along its line. The clip the drawing carried is left behind on
        // purpose: it is the box of the mark at rest, and a part on its way
        // out would be cut by it.
        double s = where.Width / _box.Width;
        Matrix place = Matrix.Identity;
        place.Translate(-_box.X, -_box.Y);
        place.Scale(s, s);
        place.Translate(where.X, where.Y);
        dc.PushTransform(new MatrixTransform(place));
        if (_flow)
        {
            bool dim = _innerOpacity < 0.999;
            if (dim) dc.PushOpacity(_innerOpacity);
            DrawFlow(dc);
            if (dim) dc.Pop();
            dc.Pop();
            return;
        }
        bool faded = _innerOpacity < 0.999;
        if (faded) dc.PushOpacity(_innerOpacity);
        double t = MotionClock, env = MotionAmount;
        for (int i = 0; i < _parts.Length; i++)
        {
            Part p = _parts[i];
            double d = Distance(p, t, env);
            bool moved = p.Turn >= 0 && Math.Abs(d) > 1e-6;
            if (moved) dc.PushTransform(new TranslateTransform(p.Way.X * d, p.Way.Y * d));
            if (_hasInner) dc.PushTransform(_innerTransform);
            dc.DrawDrawing(p.Art);
            if (_hasInner) dc.Pop();
            if (moved) dc.Pop();
        }
        if (faded) dc.Pop();
        dc.Pop();
    }

    // --- the brand in parts ----------------------------------------------
    private sealed class Part
    {
        public Drawing Art;
        public Point Centroid;
        public Vector Way;          // a unit vector, in the mark's own units
        public int Turn = -1;       // its place among the parts that move; -1 holds still
    }

    private Part[] _parts;
    private int _moving;
    private Rect _box;
    private bool _hasInner;
    private MatrixTransform _innerTransform;
    private double _innerOpacity = 1.0;
    private double _period = 2.4, _offset, _amplitude, _stagger, _height;
    private int _settleMs;
    private bool _settling;
    private bool _smooth;
    // "flow": the hub, and the glow at every strength it is drawn at, made
    // once (a brush made in a frame is a resource the render thread builds in
    // that frame, and a radial one is a texture)
    private bool _flow;
    private int _hub = -1;
    private Brush[] _glows;

    // The entrance, in seconds from the first frame: each face starts a gap
    // after the one before and lands in FaceLand, from FaceFrom of the mark's
    // height away; the hub grows in under them. The cycle takes over when the
    // last of them is home. Then each face spends Lift of the cycle lifted, out
    // by Reach of the height and grown by Grow.
    private const double FlowFaceGap = 0.07, FlowFaceLand = 0.46, FlowFaceFrom = 0.20;
    private const double FlowHubStart = 0.16, FlowHubLand = 0.42;
    private const double FlowLift = 0.55, FlowReach = 0.07, FlowGrow = 0.05;
    private const double FlowPeriod = 1.8;

    private double FlowIntro
    {
        get
        {
            double faces = Math.Max(0, _moving - 1) * FlowFaceGap + FlowFaceLand;
            return Math.Max(faces, FlowHubStart + FlowHubLand);
        }
    }

    public int PartCount { get { return _parts == null ? 0 : _parts.Length; } }
    public int MovingCount { get { return _parts == null ? 0 : _moving; } }
    public int SettleMs { get { return _parts == null || _moving == 0 ? 0 : _settleMs; } }

    private double Distance(Part p, double t, double env)
    {
        if (p.Turn < 0 || env <= 0) return 0.0;
        double a = 2 * Math.PI * t / _period - p.Turn * _stagger;
        double w = Math.Sin(a);
        if (_smooth)
        {
            double u = (1.0 + w) / 2.0;
            u = u * u * (3.0 - 2.0 * u);
            w = 2.0 * u - 1.0;
        }
        return env * _height * (_offset + _amplitude * w);
    }

    // The line of each part, for a test to read: "x,y" for one that moves,
    // "still" for one that does not, in drawing order.
    public string Ways()
    {
        if (_parts == null) return "";
        List<string> o = new List<string>();
        foreach (Part p in _parts)
            o.Add(p.Turn < 0 ? "still"
                  : p.Way.X.ToString("0.000", CultureInfo.InvariantCulture) + "," +
                    p.Way.Y.ToString("0.000", CultureInfo.InvariantCulture));
        return string.Join(";", o.ToArray());
    }

    // Where each part is now, as a distance from home in the mark's units.
    public double[] Offsets()
    {
        if (_parts == null) return new double[0];
        double t = MotionClock, env = MotionAmount;
        double[] o = new double[_parts.Length];
        for (int i = 0; i < _parts.Length; i++) o[i] = Distance(_parts[i], t, env);
        return o;
    }

    // The centroid of a shape: the shoelace sum over its outline, flattened
    // into segments. A shape with no area, or a drawing that is not a single
    // shape, falls back to the middle of its box.
    private static Point Centroid(Drawing d)
    {
        GeometryDrawing gd = d as GeometryDrawing;
        if (gd != null && gd.Geometry != null)
        {
            try
            {
                PathGeometry flat = gd.Geometry.GetFlattenedPathGeometry();
                double a = 0, cx = 0, cy = 0;
                foreach (PathFigure f in flat.Figures)
                {
                    List<Point> pts = new List<Point>();
                    pts.Add(f.StartPoint);
                    foreach (PathSegment seg in f.Segments)
                    {
                        PolyLineSegment pl = seg as PolyLineSegment;
                        if (pl != null) { foreach (Point q in pl.Points) pts.Add(q); continue; }
                        LineSegment ls = seg as LineSegment;
                        if (ls != null) pts.Add(ls.Point);
                    }
                    for (int i = 0; i < pts.Count; i++)
                    {
                        Point p0 = pts[i], p1 = pts[(i + 1) % pts.Count];
                        double cross = p0.X * p1.Y - p1.X * p0.Y;
                        a += cross;
                        cx += (p0.X + p1.X) * cross;
                        cy += (p0.Y + p1.Y) * cross;
                    }
                }
                if (Math.Abs(a) > 1e-9)
                {
                    Point p = new Point(cx / (3 * a), cy / (3 * a));
                    // whether the flattened copy has the shape's transform
                    // folded into its points or kept aside is WPF's business;
                    // what it kept aside is applied here, so both ways agree
                    if (flat.Transform != null && !flat.Transform.Value.IsIdentity)
                        p = flat.Transform.Value.Transform(p);
                    return p;
                }
            }
            catch { }
        }
        Rect b = d.Bounds;
        if (b.IsEmpty) return new Point(0, 0);
        return new Point(b.X + b.Width / 2.0, b.Y + b.Height / 2.0);
    }

    // Read the parts off the drawing and start the movement. Called on the
    // drawing thread; the drawing is frozen, so reading it from here is fine.
    public void SetMotion(SlantMotion m)
    {
        _parts = null;
        _moving = 0;
        BeginAnimation(MotionClockProperty, null);
        BeginAnimation(MotionAmountProperty, null);
        if (m == null) return;
        string preset = (m.Preset ?? "none").Trim().ToLowerInvariant();
        if (preset != "breathe" && preset != "pulse" && preset != "flow") return;
        _flow = preset == "flow";
        DrawingImage di = _logo as DrawingImage;
        if (di == null || di.Drawing == null) return;

        Drawing root = di.Drawing;
        _box = root.Bounds;
        if (_box.IsEmpty || _box.Width <= 0 || _box.Height <= 0) return;

        // The frame of the mark, which is where its middle is and what its
        // height is measured on: the clip the drawing carries when it has one,
        // because that is the box the mark was drawn in (an SVG's viewBox).
        // The bounds of a clipped group are the clip cut down to what is
        // inside it, and a mark that does not fill its box would have its
        // middle somewhere it was never drawn.
        Rect frame = _box;
        DrawingGroup rg = root as DrawingGroup;
        if (rg != null && rg.ClipGeometry != null)
        {
            Rect cb = rg.ClipGeometry.Bounds;
            if (!cb.IsEmpty && cb.Width > 0 && cb.Height > 0)
            {
                if (rg.Transform != null) cb.Transform(rg.Transform.Value);
                frame = cb;
            }
        }

        // open the groups that hold one thing each, carrying what they would
        // have applied to it: a transform and an opacity
        Matrix inner = Matrix.Identity;
        double opacity = 1.0;
        Drawing level = root;
        List<Drawing> arts = new List<Drawing>();
        while (true)
        {
            DrawingGroup g = level as DrawingGroup;
            if (g == null) { arts.Add(level); break; }
            if (g.Transform != null) inner = Matrix.Multiply(g.Transform.Value, inner);
            opacity *= g.Opacity;
            if (g.Children.Count == 1) { level = g.Children[0]; continue; }
            foreach (Drawing ch in g.Children) arts.Add(ch);
            break;
        }
        if (arts.Count == 0) return;

        Part[] parts = new Part[arts.Count];
        for (int i = 0; i < arts.Count; i++)
        {
            Part p = new Part();
            p.Art = arts[i];
            p.Centroid = inner.Transform(Centroid(arts[i]));
            parts[i] = p;
        }

        // the centre: the part asked for, or the hub, the part whose centroid
        // sits on the middle of the frame within four hundredths of its size
        Point mid = new Point(frame.X + frame.Width / 2.0, frame.Y + frame.Height / 2.0);
        double near = 0.04 * Math.Max(frame.Width, frame.Height);
        int hub = -1;
        if (m.Centre >= 0 && m.Centre < parts.Length) hub = m.Centre;
        else
        {
            double best = double.MaxValue;
            for (int i = 0; i < parts.Length; i++)
            {
                double dd = (parts[i].Centroid - mid).Length;
                if (dd < best) { best = dd; hub = i; }
            }
            if (best > near) hub = -1;
        }
        Point centre = hub >= 0 ? parts[hub].Centroid : mid;

        HashSet<int> still = new HashSet<int>();
        if (hub >= 0) still.Add(hub);
        if (m.Still != null) foreach (int k in m.Still) still.Add(k);
        int turn = 0;
        for (int i = 0; i < parts.Length; i++)
        {
            Vector v = parts[i].Centroid - centre;
            // a part on the centre itself has no line to move along
            if (still.Contains(i) || v.Length < near) continue;
            v.Normalize();
            parts[i].Way = v;
            parts[i].Turn = turn++;
        }
        if (turn == 0) return;

        _parts = parts;
        _moving = turn;
        _height = frame.Height;
        _hasInner = !inner.IsIdentity;
        _innerTransform = new MatrixTransform(inner);
        _innerTransform.Freeze();
        _innerOpacity = opacity;
        _period = !double.IsNaN(m.Period) && m.Period > 0.05 ? m.Period : 2.4;
        _offset = !double.IsNaN(m.Offset) ? m.Offset : SlantMotion.Breath;
        _amplitude = !double.IsNaN(m.Amplitude) ? m.Amplitude : SlantMotion.Breath;
        double stagger = !double.IsNaN(m.Stagger) ? m.Stagger
                         : (preset == "pulse" ? 0.0 : 360.0 / turn);
        _stagger = stagger * Math.PI / 180.0;
        _settleMs = m.Settle >= 0 ? m.Settle : 260;
        _settling = false;
        _smooth = string.Equals((m.Curve ?? "").Trim(), "smooth", StringComparison.OrdinalIgnoreCase);

        DoubleAnimation clock = new DoubleAnimation(0.0, _period, TimeSpan.FromSeconds(_period));
        clock.RepeatBehavior = RepeatBehavior.Forever;
        BeginAnimation(MotionClockProperty, clock);

        if (_flow)
        {
            _hub = hub;
            if (double.IsNaN(m.Period) || m.Period <= 0.05) _period = FlowPeriod;
            // 65 strengths: the glow changes by a sixty-fourth at most from
            // one brush to the next, which no eye picks out
            _glows = new Brush[65];
            for (int j = 0; j < _glows.Length; j++)
            {
                RadialGradientBrush g = new RadialGradientBrush();
                g.GradientStops.Add(new GradientStop(Color.FromArgb(150, _accent.R, _accent.G, _accent.B), 0.0));
                g.GradientStops.Add(new GradientStop(Color.FromArgb(48, _accent.R, _accent.G, _accent.B), 0.45));
                g.GradientStops.Add(new GradientStop(Color.FromArgb(0, _accent.R, _accent.G, _accent.B), 1.0));
                g.Opacity = j / (double)(_glows.Length - 1);
                g.Freeze();
                _glows[j] = g;
            }
            // MotionClock goes on turning one cycle at a time, for whoever
            // reads it; the drawing reads FlowTime, which also asks for a
            // frame on every frame of the compositor
            DoubleAnimation tick = new DoubleAnimation(0.0, _period, TimeSpan.FromSeconds(_period));
            tick.RepeatBehavior = RepeatBehavior.Forever;
            BeginAnimation(MotionClockProperty, tick);
            BeginAnimation(MotionAmountProperty, null);
            MotionAmount = 1.0;
            RestartFlow();
            return;
        }

        // The parts open from home when the screen comes up, so the first
        // frame shows the mark whole, as it is everywhere else, and the
        // movement grows out of it instead of starting in the middle.
        int arrive = m.Arrive >= 0 ? m.Arrive : 420;
        if (arrive > 0)
        {
            DoubleAnimation open = new DoubleAnimation(0.0, 1.0, TimeSpan.FromMilliseconds(arrive));
            open.EasingFunction = new SlantSmoothEase();
            open.FillBehavior = FillBehavior.Stop;
            MotionAmount = 1.0;
            BeginAnimation(MotionAmountProperty, open);
        }
        else MotionAmount = 1.0;
    }

    // --- "flow" -------------------------------------------------------------
    private static double Clamp01(double x) { return x < 0 ? 0 : (x > 1 ? 1 : x); }
    private static double SmoothStep(double x) { x = Clamp01(x); return x * x * (3 - 2 * x); }
    private static double Frac(double x) { return x - Math.Floor(x); }
    // past the end and back: the landing of something that arrives with speed
    private static double OutBack(double k, double s)
    {
        k = Clamp01(k) - 1;
        return 1 + (s + 1) * k * k * k + s * k * k;
    }
    private static double OutCubic(double k) { k = 1 - Clamp01(k); return 1 - k * k * k; }
    // a raised cosine over the first 'width' of the cycle, zero for the rest:
    // it leaves rest and comes back to it with no corner at either end
    private static double Bump(double ph, double width)
    {
        if (ph < 0 || ph >= width) return 0;
        return 0.5 - 0.5 * Math.Cos(2 * Math.PI * ph / width);
    }

    // Where part i is, at time 'now' (seconds from the start of the entrance)
    // with the cycle turned up by 'env': a distance along its line, a scale,
    // a turn in degrees about its centroid and an opacity.
    private void FlowPose(Part p, int i, double now, double env,
                          out double d, out double s, out double rot, out double op)
    {
        d = 0; s = 1; rot = 0; op = 1;
        double loop = now - FlowIntro;
        if (p.Turn >= 0)
        {
            double k = Clamp01((now - p.Turn * FlowFaceGap) / FlowFaceLand);
            // a soft landing: a hint of overshoot, a small turn, from close by
            double e = OutBack(k, 1.2);
            d = (1 - e) * FlowFaceFrom * _height;
            s = 0.7 + 0.3 * e;
            rot = (1 - e) * (p.Turn % 2 == 0 ? -10 : 10);
            op = SmoothStep(k * 3.0);
            // The wave. Each face's first lift starts a turn after the one
            // before it, from rest, so the cycle takes over from the entrance
            // without moving anything: a phase wrapped from the first frame
            // put the last face a quarter of the way up in a single frame.
            double ph = loop / _period - p.Turn / (double)Math.Max(1, _moving);
            if (ph > 0)
            {
                double b = Bump(Frac(ph), FlowLift) * env;
                d += FlowReach * _height * b;
                s *= 1 + FlowGrow * b;
            }
        }
        else if (i == _hub)
        {
            // it grows out of nothing, so it needs no fade, and no layer
            double k = Clamp01((now - FlowHubStart) / FlowHubLand);
            s = Math.Max(0.0, OutBack(k, 1.4));
            if (loop > 0) s *= 1 + 0.05 * env * Bump(Frac(loop / _period), 0.30);
        }
    }

    private void DrawFlow(DrawingContext dc)
    {
        double now = FlowTime;
        double env = MotionAmount;
        double H = _height;
        Point mc = _hub >= 0 ? _parts[_hub].Centroid : new Point(_box.X + _box.Width / 2.0, _box.Y + _box.Height / 2.0);

        // the glow behind: it comes up with the entrance and breathes with
        // the cycle, and goes down with the rest when the screen settles
        double glow = SmoothStep(now / 0.5) * (0.55 + 0.20 * Math.Sin(2 * Math.PI * now / _period)) * (0.35 + 0.65 * env);
        if (_glows != null)
        {
            int g = (int)Math.Round(Clamp01(glow) * (_glows.Length - 1));
            if (g > 0) dc.DrawEllipse(_glows[g], null, mc, 0.66 * H, 0.66 * H);
        }

        // the whole mark floats, a little, once every two cycles
        double fy = 0.010 * H * Math.Sin(Math.PI * now / _period) * env;
        dc.PushTransform(new TranslateTransform(0, fy));

        // the parts: the faces first, the hub last, so it sits on top as in
        // the drawing, each with its own pose. The only layer is the fade of
        // a face in the first sixth of a second of its entrance.
        for (int i = 0; i < _parts.Length; i++)
        {
            Part p = _parts[i];
            double d, s, rot, op;
            FlowPose(p, i, now, env, out d, out s, out rot, out op);
            if (op <= 0.003 || s <= 0.003) continue;
            Matrix m = Matrix.Identity;
            m.Translate(-p.Centroid.X, -p.Centroid.Y);
            m.Scale(s, s);
            m.Rotate(rot);
            m.Translate(p.Centroid.X + p.Way.X * d, p.Centroid.Y + p.Way.Y * d);
            dc.PushTransform(new MatrixTransform(m));
            bool fadeIn = op < 0.999;
            if (fadeIn) dc.PushOpacity(op);
            if (_hasInner) dc.PushTransform(_innerTransform);
            dc.DrawDrawing(p.Art);
            if (_hasInner) dc.Pop();
            if (fadeIn) dc.Pop();
            dc.Pop();
        }
        dc.Pop();
    }

    // The entrance from its start, now. A window shown covered until it has
    // drawn (DWMWA_CLOAK) is uncovered a few hundred milliseconds after the
    // motion was set, and those milliseconds of the entrance went by under the
    // cover: the mark came up already half way in. Whoever uncovers the window
    // calls this at that moment (SlantSplashCore.MotionFromNow).
    public void RestartFlow()
    {
        if (!_flow || _parts == null) return;
        DoubleAnimation t = new DoubleAnimation(0.0, 86400.0, TimeSpan.FromSeconds(86400.0));
        BeginAnimation(FlowTimeProperty, t);
    }

    // For a test: the largest change of each part's pose from one sample to
    // the next, from 'from' to 'to' seconds into the movement, sampled every
    // 'step' seconds, with the cycle fully on. Distance in fractions of the mark's
    // height, scale, turn in degrees, opacity; and the time of the largest
    // distance step. A jump anywhere shows up as one step far larger than
    // its neighbours.
    public double[] FlowSteps(double from, double to, double step)
    {
        double[] r = new double[5];
        if (!_flow || _parts == null || step <= 0 || _height <= 0) return r;
        int n = _parts.Length;
        double[] pd = new double[n], ps = new double[n], pr = new double[n], po = new double[n];
        for (int i = 0; i < n; i++) FlowPose(_parts[i], i, from, 1.0, out pd[i], out ps[i], out pr[i], out po[i]);
        for (double t = from + step; t <= to + 1e-9; t += step)
        {
            for (int i = 0; i < n; i++)
            {
                double d, s, rot, op;
                FlowPose(_parts[i], i, t, 1.0, out d, out s, out rot, out op);
                double dd = Math.Abs(d - pd[i]) / _height;
                if (dd > r[0]) { r[0] = dd; r[4] = t; }
                r[1] = Math.Max(r[1], Math.Abs(s - ps[i]));
                r[2] = Math.Max(r[2], Math.Abs(rot - pr[i]));
                r[3] = Math.Max(r[3], Math.Abs(op - po[i]));
                pd[i] = d; ps[i] = s; pr[i] = rot; po[i] = op;
            }
        }
        return r;
    }

    // The parts come home, from wherever they are, on a curve that leaves
    // quickly and settles. It returns how long that takes, so the caller can
    // start the fade after it: a mark that fades while still apart looks
    // like it was dropped. Zero when there is nothing to bring home.
    public int Settle()
    {
        if (_parts == null || _moving == 0 || _settling) return 0;
        _settling = true;
        if (_settleMs <= 0)
        {
            BeginAnimation(MotionAmountProperty, null);
            MotionAmount = 0.0;
            return 0;
        }
        DoubleAnimation home = new DoubleAnimation(0.0, TimeSpan.FromMilliseconds(_settleMs));
        CubicEase e = new CubicEase();
        e.EasingMode = EasingMode.EaseOut;
        home.EasingFunction = e;
        home.FillBehavior = FillBehavior.HoldEnd;
        BeginAnimation(MotionAmountProperty, home);
        return _settleMs;
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

// The bar under the line, in the measuring mode: the same fraction as the
// ring, drawn straight. It is set from the ring's own ProgressChanged, on the
// same thread and in the same frame, so the two can never say different
// numbers. A screen that turned a ring for a while and then filled one, with a
// shuttle running underneath, had two ways of saying "loading" and two styles
// for them (2026-11-05: "it makes no sense to have two kinds of loading").
public class SlantBar : FrameworkElement
{
    public static readonly DependencyProperty ProgressProperty =
        DependencyProperty.Register("Progress", typeof(double), typeof(SlantBar),
            new FrameworkPropertyMetadata(0.0, FrameworkPropertyMetadataOptions.AffectsRender));

    public double Progress
    {
        get { return (double)GetValue(ProgressProperty); }
        set { SetValue(ProgressProperty, value); }
    }

    private readonly Pen _rail;
    private readonly Pen _fill;
    private readonly double _w, _h;

    public SlantBar(double width, double height, Color accent, Color track)
    {
        _w = width; _h = height;
        Width = width; Height = height;
        SolidColorBrush rb = new SolidColorBrush(track);
        rb.Opacity = 0.30;
        rb.Freeze();
        _rail = Line(rb, Math.Max(1.0, height * 0.5));
        SolidColorBrush fb = new SolidColorBrush(accent);
        fb.Opacity = 0.92;
        fb.Freeze();
        _fill = Line(fb, height);
    }

    private static Pen Line(Brush b, double w)
    {
        Pen p = new Pen(b, w);
        p.StartLineCap = PenLineCap.Round;
        p.EndLineCap = PenLineCap.Round;
        p.Freeze();
        return p;
    }

    protected override Size MeasureOverride(Size available)
    {
        return new Size(_w, _h);
    }

    protected override void OnRender(DrawingContext dc)
    {
        double y = _h / 2.0;
        double inset = _h / 2.0;
        double span = _w - 2 * inset;
        dc.DrawLine(_rail, new Point(inset, y), new Point(_w - inset, y));
        double p = Progress;
        if (p > 1.0) p = 1.0;
        if (p > 0.002) dc.DrawLine(_fill, new Point(inset, y), new Point(inset + span * p, y));
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
    private SlantBar _bar;
    // How long the whole fill is expected to take, in seconds: the pace the
    // arc keeps when nothing tells it otherwise (SetExpected)
    private double _expected = 8.0;
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
    private SlantMotion _motion;

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

    // The ring and the bar, read in one go on the drawing thread: they are
    // the same number drawn twice, and a test can say so.
    public double[] DrawnPair
    {
        get
        {
            double a = -1, b = -1;
            Dispatcher d = _dispatcher;
            if (d == null || _ring == null || _bar == null) return new double[] { a, b };
            try { d.Invoke(DispatcherPriority.Send, (Action)delegate () { a = _ring.Progress; b = _bar.Progress; }); }
            catch { }
            return new double[] { a, b };
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

    // How the brand moves (SlantMotion, above). Asked for before the thread
    // exists it is applied when the ring is built; asked for later it is sent
    // over. Either way the parts are read on the drawing thread.
    public void SetMotion(SlantMotion motion)
    {
        _motion = motion;
        Dispatcher d = _dispatcher;
        if (d == null) return;
        d.BeginInvoke(DispatcherPriority.Normal, (Action)delegate ()
        {
            try { _ring.SetMotion(motion); } catch { }
        });
    }

    // A value read on the drawing thread, for a caller on another one. The
    // ring's properties belong to that thread and cannot be read from here.
    private T OnRing<T>(Func<SlantRing, T> read, T fallback)
    {
        Dispatcher d = _dispatcher;
        if (d == null || _ring == null) return fallback;
        T v = fallback;
        try { d.Invoke(DispatcherPriority.Send, (Action)delegate () { v = read(_ring); }); }
        catch { return fallback; }
        return v;
    }

    // How many parts the brand was read into, and how many of them move:
    // zero for a raster, for a mark of one piece, and with no motion asked for.
    public int MarkParts { get { return OnRing(r => r.PartCount, 0); } }
    // The centre of the ring in the screen's own coordinates (the host's),
    // for a test that wants to see it stay put from one mode to the other.
    public Point RingCentre
    {
        get
        {
            return OnRing(r =>
            {
                if (_root == null || r.ActualWidth <= 0) return new Point(double.NaN, double.NaN);
                return r.TranslatePoint(new Point(r.ActualWidth / 2.0, r.ActualHeight / 2.0), _root);
            }, new Point(double.NaN, double.NaN));
        }
    }
    public int MarkMoving { get { return OnRing(r => r.MovingCount, 0); } }
    public string MarkWays { get { return OnRing(r => r.Ways(), ""); } }
    public double MotionClock { get { return OnRing(r => r.MotionClock, 0.0); } }
    public double MotionAmount { get { return OnRing(r => r.MotionAmount, 0.0); } }
    public double[] MarkOffsets() { return OnRing(r => r.Offsets(), new double[0]); }
    public double FlowTime { get { return OnRing(r => r.FlowTime, 0.0); } }
    public double[] MarkFlowSteps(double from, double to, double step) { return OnRing(r => r.FlowSteps(from, to, step), new double[0]); }

    // The brand's entrance from its start, now ("flow"): for a window shown
    // covered while it drew, called at the moment it is uncovered. Queued
    // behind SetMotion, at the same priority, so it can never run first.
    public void MotionFromNow()
    {
        Dispatcher d = _dispatcher;
        if (d == null) return;
        d.BeginInvoke(DispatcherPriority.Normal, (Action)delegate ()
        {
            try { if (_ring != null) _ring.RestartFlow(); } catch { }
        });
    }

    // Bring the parts home and say how long it takes. Hide calls this first
    // and starts the fade when it is over.
    public int Settle() { return OnRing(r => r.Settle(), 0); }

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
        // Ahead of the application's own threads: while it loads, they all want
        // the processor at once, and the one that has to be on time for every
        // frame is this one (measured on 2026-11-05: one step in seven missed a
        // frame while the application filled its page at normal priority).
        _thread.Priority = ThreadPriority.Highest;
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
        if (_motion != null) { try { _ring.SetMotion(_motion); } catch { } }

        FontFamily ff = new FontFamily(_fontFamily);
        SolidColorBrush ab = new SolidColorBrush(_accent);
        ab.Freeze();
        SolidColorBrush tb = new SolidColorBrush(_textColor);
        tb.Freeze();

        _percentText = new TextBlock();
        _percentText.FontFamily = ff;
        // a bigger ring brings bigger words, but less than in proportion: the
        // ring is the picture and the words are its caption
        double grow = Math.Sqrt(Math.Max(1.0, _size / 132.0));
        _percentText.FontSize = Math.Round(13 * grow * 2) / 2;
        _percentText.FontWeight = FontWeights.SemiBold;
        _percentText.Foreground = ab;
        _percentText.HorizontalAlignment = HorizontalAlignment.Center;
        _percentText.Margin = new Thickness(0, Math.Round(17 * grow), 0, 0);
        _percentText.Text = "0%";
        centre.Children.Add(_percentText);

        _lineText = new TextBlock();
        _lineText.FontFamily = ff;
        _lineText.FontSize = Math.Round(11.5 * grow * 2) / 2;
        _lineText.Foreground = tb;
        _lineText.HorizontalAlignment = HorizontalAlignment.Center;
        _lineText.Margin = new Thickness(0, Math.Round(5 * grow), 0, 0);
        _lineText.Text = firstLine == null ? "" : firstLine;
        centre.Children.Add(_lineText);

        // the bar and the shuttle share one slot: the bar while the ring
        // measures, the shuttle in a wait with nothing to measure. Swapping
        // them moves nothing, because the slot keeps its size
        Grid slot = new Grid();
        slot.HorizontalAlignment = HorizontalAlignment.Center;
        slot.Margin = new Thickness(0, Math.Round(15 * grow), 0, 0);
        _bar = new SlantBar(Math.Round(_size * 1.30), 3.0, _accent, _track);
        _pulse = new SlantPulse(Math.Round(_size * 1.30), 3.0, _accent, _track);
        _pulse.Visibility = Visibility.Hidden;
        slot.Children.Add(_bar);
        slot.Children.Add(_pulse);
        centre.Children.Add(slot);

        // the figure and the bar are written by the arc's own movement, frame
        // by frame
        _ring.ProgressChanged = delegate (double v)
        {
            try
            {
                _bar.Progress = v;
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

            // The pace is the time, not the steps (2026-11-05: "fill a little
            // at a time, continuously, not stuck at some points and running at
            // others"). Chasing each announced step made the arc race to it and
            // then crawl or stop: the steps of a load are not evenly spread in
            // time. So the arc goes round at the pace of the expected length of
            // the load (SetExpected, which an application can take from its
            // last start), and the steps only nudge it: behind what has been
            // announced it goes up to half as fast again, ahead of it down to
            // half, and the speed is eased, so a nudge is never seen as a jolt.
            // It never stops before the end: short of it, it slows into a soft
            // wall at 98.5 per cent, and only the last step closes the circle.
            double pos = _ring.Progress;
            double basePace = 1.0 / Math.Max(1.5, _expected);
            double want;
            double wall = _goal >= 1.0 ? 1.0 : 0.985;
            if (_goal >= 1.0)
            {
                // the end is announced: what is left goes in about half a second,
                // never slower than the pace it had
                want = Math.Max(basePace, (1.0 - pos) / 0.5);
            }
            else
            {
                double lead = pos - _goal;
                double k = 1.0 - lead * 4.0;
                if (k < 0.5) k = 0.5;
                if (k > 1.5) k = 1.5;
                want = basePace * k;
                double room = wall - pos;
                if (room < 0.15) want *= Math.Max(0.05, room / 0.15);
            }

            // the speed is what gets eased, so there are no corners in the
            // movement even when the pace changes
            _speed += (want - _speed) * Math.Min(1.0, dt * 2.5);
            double next = pos + _speed * dt;
            if (next > wall) next = wall;
            if (next > 1.0) next = 1.0;
            if (next != pos) _ring.Progress = next;

            if (_goal >= 1.0 && next >= 0.9999)
            {
                Halt();
                Finish();
            }
        }
        catch { }
    }

    // The end: the circle and the bar are full, and that is the whole of it.
    // The thin circle the ring used to let go outwards here is gone
    // (2026-11-05, "take away that thin circle that widens"): a full ring
    // already says it, and the fade that follows is movement enough.
    private void Finish()
    {
        if (_done) return;
        _done = true;
    }

    // How long the whole fill is expected to take. An application that knows
    // how long it took last time says so, and the arc keeps that pace; a step
    // announced early or late nudges it, never more than half again or half.
    public void SetExpected(double ms)
    {
        if (double.IsNaN(ms) || ms <= 0) return;
        double s = Math.Max(1.5, Math.Min(120.0, ms / 1000.0));
        Dispatcher d = _dispatcher;
        if (d == null) { _expected = s; return; }
        d.BeginInvoke(DispatcherPriority.Normal, (Action)delegate () { _expected = s; });
    }
    public double Expected { get { return _expected; } }

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
                //
                // Hidden and not Collapsed: the figure keeps its place. The
                // ring, the figure, the line and the bar are one block centred
                // in the window, and a figure taken out of the block made it
                // shorter, so the ring sat lower while it turned and jumped up
                // when the first step turned it into a measure (seen on
                // 2026-11-05). The ring must never move.
                _percentText.Visibility = on ? Visibility.Hidden : Visibility.Visible;
                // the shuttle says "still going" in a wait with no measure;
                // measuring, the bar fills with the ring. One slot for both
                _pulse.Visibility = on ? Visibility.Visible : Visibility.Hidden;
                _bar.Visibility = on ? Visibility.Hidden : Visibility.Visible;
                if (on)
                {
                    Halt();
                    DoubleAnimation turn = new DoubleAnimation(0, 360, TimeSpan.FromMilliseconds(1500));
                    turn.RepeatBehavior = RepeatBehavior.Forever;
                    _ring.BeginAnimation(SlantRing.SpinProperty, turn);
                    DoubleAnimation phase = new DoubleAnimation(0, 1, TimeSpan.FromMilliseconds(1750));
                    phase.RepeatBehavior = RepeatBehavior.Forever;
                    _pulse.BeginAnimation(SlantPulse.PhaseProperty, phase);
                }
                else
                {
                    _ring.BeginAnimation(SlantRing.SpinProperty, null);
                    _pulse.BeginAnimation(SlantPulse.PhaseProperty, null);
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
