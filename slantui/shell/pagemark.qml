import QtQuick
import QtWebEngine

/* What the page is told while the loading screen is over it.

   The screen covers the body, and the body is all it covers: the band is the
   page's, and so is the strip under the band's thin half, which titlebar.js
   paints with whatever is under the bar. While the window is empty, what is
   under the bar is the page nobody is shown yet, so the strip came out in the
   colour of a step rail over an empty window: a line across the top that
   belonged to nothing. The page has to know the screen is up to paint it the
   empty window's colour instead, and it has to know before it paints anything.

   So it is told at the creation of its document, before any of its own
   scripts run and before its first frame, with an attribute on its root:

     data-splash="up"        the window is empty, the strip is too
     data-splash="leaving"   the page is arriving, and the strip goes over to
                             its own colour on the same long curve
     (none)                  the screen is gone

   The attribute is the library's, read by the library's own titlebar.js and
   layout.css. A page can read it too, and has no need to.

   Its own file for the same reason as haze.qml: the script API it uses is Qt
   6's, and loaded from here a toolkit without it leaves the Loader in error
   and the window carries on, with the strip as it was. */
Item {
    id: mark
    visible: false

    property var target: null
    property string state_: ""           // "up", "leaving", or "" for gone

    readonly property string name_: "slantui-splash"

    // Run at the creation of the document, when the root element does not
    // exist yet: it is put on the root the moment the parser makes it.
    readonly property string early_:
        "(function () {" +
        "  function put() {" +
        "    var h = document.documentElement;" +
        "    if (!h) return false;" +
        "    if (!h.hasAttribute('data-splash')) h.setAttribute('data-splash', 'up');" +
        "    return true;" +
        "  }" +
        "  if (!put()) new MutationObserver(function (list, watch) {" +
        "    if (put()) watch.disconnect();" +
        "  }).observe(document, { childList: true });" +
        "})();"

    function forget() {
        if (!target) return
        var old = target.userScripts.find(name_)
        for (var i = 0; i < old.length; i++) target.userScripts.remove(old[i])
    }

    function tell(state) {
        if (!target) return
        forget()
        if (state === "up") {
            var s = WebEngine.script()
            s.name = name_
            s.sourceCode = early_
            s.injectionPoint = WebEngineScript.DocumentCreation
            s.worldId = WebEngineScript.MainWorld
            target.userScripts.insert(s)
        }
        // and the document that is already there, if one is: the script above
        // only reaches the ones created from now on
        target.runJavaScript(state
            ? "document.documentElement && document.documentElement.setAttribute('data-splash', '" + state + "')"
            : "document.documentElement && document.documentElement.removeAttribute('data-splash')")
    }

    onTargetChanged: tell(state_)
    onState_Changed: tell(state_)
    Component.onDestruction: tell("")
}
