import QtQuick 2.15
import QtQuick.Effects

/* The page out of focus, behind the loading screen.

   It is its own file because the effect it needs arrives with Qt 6: loaded
   from here, a toolkit without it leaves the Loader in error and the screen
   carries on with the veil alone, while an import at the top of shell.qml
   would have taken the whole window down with it. */
MultiEffect {
    property Item target: null
    source: target
    blurEnabled: true
    blur: 1.0
    blurMax: Math.max(2, Math.round(radius_))
    property real radius_: 14
}
