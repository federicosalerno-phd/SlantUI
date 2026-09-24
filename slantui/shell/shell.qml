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
   one screen, not two. */
Item {
    id: root

    signal jsResult(int token, var value)

    function run(script, token) {
        web.runJavaScript(script, function (result) { root.jsResult(token, result) })
    }

    WebChannel { id: channel; objectName: "channel" }

    WebEngineView {
        id: web
        objectName: "web"
        anchors.fill: parent
        focus: true
        backgroundColor: uiBackground
        url: uiUrl
        webChannel: channel
        settings.javascriptEnabled: true
        settings.localContentCanAccessRemoteUrls: true
        settings.localContentCanAccessFileUrls: true
        // The page draws its own controls and never navigates: Chromium's
        // context menu (Back, Reload, ...) would only offer ways to lose the session.
        onContextMenuRequested: function (request) { request.accepted = true }
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
