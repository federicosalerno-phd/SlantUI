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

    /* The page is told the screen is up, before it draws a frame, and while
       it is told it keeps its body out of focus and the strip under the band
       in the empty window's colour (pagemark.qml and layout.css say why).
       The page does its own blur: the window never draws the page twice. */
    Loader {
        id: mark
        active: splash.active
        source: pagemarkSource
        onLoaded: item.target = web
        onStatusChanged: if (status === Loader.Error) active = false
    }
    Binding {
        target: mark.item
        when: mark.item !== null && splash.item !== null
        property: "state_"
        value: splash.item ? splash.item.page : ""
    }

    Loader {
        id: splash
        objectName: "splash"
        source: splashSource
        active: false
        anchors.fill: parent
        anchors.topMargin: splashBandHeight
        onLoaded: item.over = true
    }
}
