import QtQuick 2.15
import QtWebEngine 1.10
import QtWebChannel 1.15

/* The window's only content: the application's page, edge to edge.

   window.py loads this file into a QQuickView, registers the bridge on
   `channel` (the page reaches it through qt.webChannelTransport) and calls
   run() for tools and tests, which answer through jsResult. Nothing about
   the page itself lives here. */
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
}
