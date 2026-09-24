import QtQuick 2.15

/* The loading screen, drawn the way the WPF half of the library draws it: the
   brand in the middle of a ring, a figure, a line saying what is happening,
   and a thin bar under it.

   One file, two places. Over the body of a window this library dressed it is
   the window itself, empty: the band sharp above it, so the window can still
   be moved and closed while it loads, and under the band nothing but the
   window's own surface. The page is not shown through it. A page seen while
   it is being put together is an application assembling itself in front of
   the person waiting for it, and what they should see is the window, and then
   the application in it. On its own it is a small window with the same screen
   on it, for the seconds before there is an application to dress. Both are
   this file, which is what makes the two hand over without a jump.

   A wait in the middle of work is the other case, and `veil` is for it: there
   the page is the person's work and stays in sight, out of focus under a
   scrim, because hiding it would look like it had been lost.

   The handover is one movement, `leave`, from nothing to one. The ring goes
   first, fading as it grows a little, the way the circle it let go at the end
   went outwards; the empty window thins out behind it; and through it the page
   comes into focus, arriving sharp exactly as the movement ends. The first
   two are curves over that one number, here; the third is the page's own,
   told to start in the same frame and written in layout.css over the same
   length, because the page is the one that blurs itself. How long the
   movement lasts is splash.py's, which takes it from --t-reveal.

   The ring is a canvas and not a shape, for one reason: the arc is not a flat
   colour. It runs from a lighter accent to the accent, along a gradient
   mapped to the box and not to the arc, so that it does not swing round as
   the arc grows, and a stroke gradient is something a canvas has and a Shape
   does not. The head of the arc and the halo around it are on the same
   canvas, since they are part of the same drawing.

   Everything here is driven from splash.py: this file draws a state and holds
   no rule about how that state moves. The colours arrive as the accent's and
   the track's own components, out of the palette, so no value in this file is
   a colour. */
Item {
    id: root

    property real progress: 0          // 0 .. 1, the arc's fill
    property bool busy: false          // a wait with nothing to measure
    property real spin: 0              // turns, while waiting
    property real phase: 0             // the bar's travel, 0 .. 1
    property real burst: 0             // the ring's one flourish, at the end
    property string line: ""           // what is happening, in words
    property url logo: ""
    property bool over: false          // over an application's body, not on its own
    property bool veil: false          // and the page left in sight, under a scrim
    property real leave: 0             // the handover, 0 .. 1

    // a step from a to b with no corner at either end
    function smooth(a, b, x) {
        var t = Math.max(0, Math.min(1, (x - a) / (b - a)))
        return t * t * (3 - 2 * t)
    }
    readonly property real ringGone: smooth(0.0, 0.45, leave)
    readonly property real ringGrow: 1 - Math.pow(1 - Math.min(1, leave / 0.45), 3)
    readonly property real groundGone: smooth(0.10, 0.60, leave)
    // What the page is told (pagemark.qml): the page blurs its own body under
    // the screen and comes into focus on the same curve, and paints the strip
    // under the band in the empty window's colour while the window is empty.
    readonly property string page: !over ? ""
        : veil ? (leave > 0 ? "lifting" : "veil")
        : (leave > 0 ? "leaving" : "up")

    readonly property real ring: ringSize
    readonly property real thick: ringThickness
    // The air AROUND the ring, which two things need and neither used to get.
    // The arc's head is a radial glow of 2.3 thicknesses centred ON the stroke,
    // so it reaches nearly two thicknesses past the ring; the closing circle
    // starts at the ring and grows by 26% of the radius before it fades. Both
    // were cut off, because the canvas was exactly the size of the ring and the
    // ring fills it. It showed at the top and to the right, where the head is
    // while it spins, and it looked like a crop box, which is what it was.
    readonly property real halo: Math.max(thick * 1.9, ring * 0.16)

    // What is behind the ring: the window's own surface, which is what an
    // empty window is, or the scrim over a page left in sight. On its own the
    // screen is a small window with round corners, and this is its fill.
    Rectangle {
        anchors.fill: parent
        color: root.over && root.veil ? scrimColour : surfaceColour
        radius: root.over ? 0 : cornerRadius
        opacity: 1 - root.groundGone
    }

    // The accent, lifted towards white. The arc is lighter where it starts
    // than where it ends, and the head lighter still: that is what makes a
    // ring read as one moving thing and not as a bent line.
    function lift(c, k) { return c + (1 - c) * k }
    function accent(a) { return Qt.rgba(accentR, accentG, accentB, a) }
    function lifted(k, a) {
        return Qt.rgba(lift(accentR, k), lift(accentG, k), lift(accentB, k), a)
    }
    function track(a) { return Qt.rgba(trackR, trackG, trackB, a) }

    onProgressChanged: ringCanvas.requestPaint()
    onSpinChanged: if (busy) ringCanvas.requestPaint()
    onBusyChanged: ringCanvas.requestPaint()
    onBurstChanged: ringCanvas.requestPaint()

    Column {
        anchors.centerIn: parent
        spacing: 0
        opacity: 1 - root.ringGone
        scale: 1 + 0.08 * root.ringGrow
        transformOrigin: Item.Center

        Item {
            width: root.ring
            height: root.ring
            anchors.horizontalCenter: parent.horizontalCenter

            Canvas {
                id: ringCanvas
                // Bigger than the ring and centred on it, so what leaves
                // the ring has somewhere to go. With anchors.fill the sheet
                // ended where the stroke ends, and everything past it was cut.
                anchors.centerIn: parent
                width: parent.width + 2 * root.halo
                height: parent.height + 2 * root.halo
                antialiasing: true

                // an arc from twelve o'clock, clockwise, sweep as a fraction
                // of a turn
                function drawArc(ctx, cx, cy, r, t, stroke, from, sweep) {
                    var a0 = (from - 0.25) * 2 * Math.PI
                    var a1 = (from + Math.min(sweep, 0.9999) - 0.25) * 2 * Math.PI
                    ctx.beginPath()
                    ctx.arc(cx, cy, r, a0, a1, false)
                    ctx.lineWidth = t
                    ctx.lineCap = "round"
                    ctx.strokeStyle = stroke
                    ctx.stroke()
                }

                // The head is where the eye goes. It is what makes a growing
                // arc read as something moving, and not as a shape that
                // happens to be longer than it was a moment ago.
                function drawHead(ctx, cx, cy, r, t, at) {
                    var a = (at - 0.25) * 2 * Math.PI
                    var hx = cx + r * Math.cos(a), hy = cy + r * Math.sin(a)
                    var g = ctx.createRadialGradient(hx, hy, 0, hx, hy, t * 2.3)
                    g.addColorStop(0, root.accent(0.30))
                    g.addColorStop(0.55, root.accent(0.09))
                    g.addColorStop(1, root.accent(0))
                    ctx.beginPath()
                    ctx.arc(hx, hy, t * 2.3, 0, 2 * Math.PI)
                    ctx.fillStyle = g
                    ctx.fill()
                    ctx.beginPath()
                    ctx.arc(hx, hy, t * 0.46, 0, 2 * Math.PI)
                    ctx.fillStyle = root.lifted(0.30, 1)
                    ctx.fill()
                }

                onPaint: {
                    var ctx = getContext("2d")
                    // the sheet is larger than the ring: the ring is what is
                    // left once the air around it is taken off
                    var s = width - 2 * root.halo, t = root.thick
                    var r = (s - t) / 2, cx = width / 2, cy = height / 2
                    ctx.reset()

                    // the track: thinner than the arc, since the measure is
                    // what should carry the weight and a track of equal
                    // stroke competes with it
                    ctx.beginPath()
                    ctx.arc(cx, cy, r, 0, 2 * Math.PI)
                    ctx.lineWidth = Math.max(1, t * 0.55)
                    ctx.strokeStyle = root.track(0.38)
                    ctx.stroke()

                    var grad = ctx.createLinearGradient(cx - s * 0.40, cy - s * 0.50,
                                                        cx + s * 0.40, cy + s * 0.50)
                    grad.addColorStop(0, root.lifted(0.38, 1))
                    grad.addColorStop(0.65, root.accent(1))

                    if (root.busy) {
                        // a fifth of the circle, turning, its head lit like
                        // the arc's: the same drawing language, saying "no
                        // idea how long" instead of "this far"
                        drawArc(ctx, cx, cy, r, t, grad, root.spin, 0.2)
                        drawHead(ctx, cx, cy, r, t, root.spin + 0.2)
                    } else if (root.progress > 0.0025) {
                        var p = Math.min(1, root.progress)
                        drawArc(ctx, cx, cy, r, t, grad, 0, p)
                        drawHead(ctx, cx, cy, r, t, p)
                    }

                    // The one flourish on the whole screen, and it lasts half
                    // a second: at the end the ring lets a thin circle go
                    // outwards and fade.
                    if (root.burst > 0.001 && root.burst < 0.999) {
                        var k = 1 - root.burst
                        ctx.beginPath()
                        ctx.arc(cx, cy, r + r * 0.26 * root.burst, 0, 2 * Math.PI)
                        ctx.lineWidth = Math.max(0.5, t * k)
                        ctx.strokeStyle = root.accent(0.59 * k * k)
                        ctx.stroke()
                    }
                }
            }

            Image {
                source: root.logo
                visible: String(root.logo).length > 0
                width: Math.round(root.ring * 0.52)
                height: Math.round(root.ring * 0.52)
                anchors.centerIn: parent
                fillMode: Image.PreserveAspectFit    // the brand is not stretched
                smooth: true
                mipmap: true
            }
        }

        Item { width: 1; height: figureGap }

        Text {
            text: Math.floor(root.progress * 100 + 0.5) + "%"
            visible: !root.busy
            color: accentColour
            font.family: fontFamily
            font.pixelSize: figureSize
            font.weight: Font.DemiBold
            anchors.horizontalCenter: parent.horizontalCenter
        }

        Item { width: 1; height: root.busy ? 0 : lineGap }

        Text {
            text: root.line
            color: textColour
            font.family: fontFamily
            font.pixelSize: lineSize
            anchors.horizontalCenter: parent.horizontalCenter
        }

        Item { width: 1; height: barGap }

        /* The bar: two lozenges that grow out of the left edge, cross, and are
           drawn out of the right one. It has no scale and no beginning, which
           is the point: it says work is going on, and nobody glancing at it
           can take it for a quantity. Two of them, half a turn apart, so the
           bar is never empty: an activity mark that stops, even for a frame,
           reads as a hang. */
        Item {
            id: bar
            width: root.ring * 1.3
            height: barHeight
            anchors.horizontalCenter: parent.horizontalCenter

            readonly property real inset: height / 2
            readonly property real span: width - 2 * inset

            function ease(t) {
                if (t <= 0) return 0
                if (t >= 1) return 1
                return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
            }
            // head and tail ease along the same curve, a third of a turn
            // apart: the lozenge is short as it enters, long as it crosses,
            // short as it leaves
            function head(t) { return ease(Math.max(0, Math.min(1, t / 0.66))) }
            function tail(t) { return ease(Math.max(0, Math.min(1, (t - 0.34) / 0.66))) }

            Rectangle {                         // the rail
                x: bar.inset
                width: bar.span
                height: Math.max(1, bar.height * 0.5)
                radius: height / 2
                anchors.verticalCenter: parent.verticalCenter
                color: root.track(0.30)
            }

            Repeater {
                model: [{ "at": 0.5, "ink": 0.30, "thin": 0.8 },   // the trailing one
                        { "at": 0.0, "ink": 0.92, "thin": 1.0 }]   // the leading one
                Rectangle {
                    readonly property real t: (root.phase + modelData.at) % 1.0
                    readonly property real from_: bar.tail(t)
                    readonly property real to_: bar.head(t)
                    visible: to_ - from_ > 0.006
                    x: bar.inset + bar.span * from_
                    width: bar.span * (to_ - from_)
                    height: bar.height * modelData.thin
                    radius: height / 2
                    anchors.verticalCenter: parent.verticalCenter
                    color: root.accent(modelData.ink)
                }
            }
        }
    }
}
