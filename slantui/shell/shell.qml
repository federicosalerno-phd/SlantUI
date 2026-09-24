import QtQuick 2.15
import QtWebEngine 1.10
import QtWebChannel 1.15

/* The window's only content: the application's page, edge to edge, and the
   loading screen over it.

   window.py loads this file into a QQuickView, registers the bridge on
   `channel` (the page reaches it through qt.webChannelTransport) and calls
   run() for tools and tests, which answer through jsResult. Nothing about
   the page itself lives here.

   The loading screen is splash.qml, loaded on demand and laid over the body:
   under the band, which stays sharp, so the window can still be moved and
   closed while it loads. It is the same file a screen of its own draws, so
   an application that puts one up before its window exists and this one are
   one screen, not two.

   The window's top left corner is round about the page's mark, and this file
   is what makes the window able to show it. The window itself is clear, the
   backdrop below is drawn with the corner cut out, the web view is clear too,
   and once a page with a title bar has loaded it is told so: data-corner on
   its <html>, which is what the stylesheet and titlebar.js cut their own
   corner on. The radius is read back off that page, so a page that redefines
   --tbar-h gets a backdrop cut to its own band. */
Item {
    id: root

    signal jsResult(int token, var value)

    // Set by window.py: maximised, the corner is on the screen's and square.
    property bool maximized: false
    // The radius of the corner. The library's own until the page has said.
    property real corner: uiCorner

    function run(script, token) {
        web.runJavaScript(script, function (result) { root.jsResult(token, result) })
    }

    /* What the window shows where the page has not painted: while it loads,
       and in the strip a live resize uncovers before the page catches up.
       Three rectangles, because a Rectangle rounds all four corners or none:
       the first is rounded everywhere, and the other two square off the
       three corners that are not this one. */
    Item {
        id: backdrop
        anchors.fill: parent
        readonly property real r: root.maximized ? 0 : root.corner
        Rectangle { anchors.fill: parent; color: uiBackground; radius: backdrop.r }
        Rectangle {
            x: backdrop.r; width: parent.width - backdrop.r; height: parent.height
            color: uiBackground
        }
        Rectangle {
            y: backdrop.r; width: parent.width; height: parent.height - backdrop.r
            color: uiBackground
        }
    }

    WebChannel { id: channel; objectName: "channel" }

    WebEngineView {
        id: web
        objectName: "web"
        anchors.fill: parent
        focus: true
        backgroundColor: "transparent"
        url: uiUrl
        webChannel: channel
        settings.javascriptEnabled: true
        settings.localContentCanAccessRemoteUrls: true
        settings.localContentCanAccessFileUrls: true
        // The page draws its own controls and never navigates: Chromium's
        // context menu (Back, Reload, ...) would only offer ways to lose the session.
        onContextMenuRequested: function (request) { request.accepted = true }
        // A page with a title bar is told the window can cut its corner, and
        // says back how round: half its band. A page without one keeps a
        // square window, since there is no mark for a corner to be round about.
        onLoadingChanged: function (info) {
            if (info.status !== WebEngineView.LoadSucceededStatus) return
            web.runJavaScript(
                "(function () {" +
                "  var bar = document.querySelector('.app>.titlebar');" +
                "  if (!bar) return 0;" +
                "  document.documentElement.setAttribute('data-corner', '');" +
                "  return bar.getBoundingClientRect().height / 2;" +
                "})()",
                function (r) { root.corner = r > 0 ? r : 0 })
        }
    }

    /* The page goes out of focus under the screen, the way it does on the WPF
       side: the veil alone over a drawn page reads as a page that went dim,
       and the blur is what says the application is busy with something else.
       It costs nothing until the screen is up, since the layer is only turned
       on with it, and it is skipped where the effect is missing (Qt 5), where
       the veil carries the screen by itself. */
    Loader {
        id: haze
        anchors.fill: web
        active: splash.active && splashBlur > 0
        source: hazeSource
        onLoaded: { item.target = web; item.radius_ = splashBlur }
        onStatusChanged: if (status === Loader.Error) active = false
    }

    Loader {
        id: splash
        objectName: "splash"
        source: splashSource
        active: false
        anchors.fill: parent
        anchors.topMargin: splashBandHeight
        onLoaded: item.veil = true
    }
}
