"""The Win32 frame behind the frameless window, and the DWM attributes.

Everything here takes a window handle as a plain integer and does nothing at
all off Windows, so the window class stays readable and the Windows specific
part can be checked on its own.

Qt's frameless window is a bare WS_POPUP, and Windows only animates minimise,
restore, maximise and close for windows that carry a real frame (WS_CAPTION
and WS_THICKFRAME): without one the window snapped in and out of the taskbar
instead of sliding. The fix is the one Chromium and VS Code use. Keep Qt's
frameless hint, so Qt reports zero frame margins; give the HWND the frame
styles anyway; and answer WM_NCCALCSIZE with "the client area is the whole
window", which removes the caption and the borders again while the styles,
and with them the animations, the DWM shadow and Aero Snap, stay.

The frame styles have one consequence the window has to live around. When
Windows zooms a window that carries them, it places it with the frame past
the edge of the screen, eleven pixels on every side at 150 %, and it keeps
it there: MINMAXINFO is asked and then ignored, SetWindowPos on the zoomed
window is accepted and undone, and dropping WS_THICKFRAME first changes
nothing. For a window whose client is the whole window that is eleven
pixels of page cut off on every side. Up to Qt 6.11.1 nobody saw it,
because Qt maximised a frameless window by moving it onto the work area
itself and never zoomed it; 6.11.2 (QTBUG-145092) zooms it like any other
window. So the window never zooms itself (see window.py), and the two
system commands that would, Win+Up and the taskbar menu, arrive here as
WM_SYSCOMMAND and are handed to the window's own maximise instead. That is
``syscommand``. Measured on 2026-09-18 with both Qt versions side by side.

Windows' own state transitions are a second matter. They scale a snapshot of
the last frame over a fixed curve and, for a window like this one, showed up
as a jump. The window animates its geometry itself instead, and switches the
DWM transition off only around the state change, so nothing animates twice.
That switch is ``set_transitions``.
"""
from __future__ import annotations

import sys

__all__ = [
    "WM_NCCALCSIZE", "WM_NCACTIVATE", "WM_SYSCOMMAND", "SC_MINIMIZE", "SC_MAXIMIZE",
    "SC_RESTORE", "WS_FRAME", "GWL_STYLE", "SWP_FRAMECHANGED",
    "DWMWA_WINDOW_CORNER_PREFERENCE", "DWMWCP_ROUND", "DWMWA_BORDER_COLOR",
    "DWMWA_COLOR_NONE", "DWMWA_TRANSITIONS_FORCEDISABLED",
    "IS_WINDOWS", "dress", "set_transitions", "answer", "syscommand",
]

IS_WINDOWS = sys.platform == "win32"

WM_NCCALCSIZE = 0x0083
WM_NCACTIVATE = 0x0086
WM_SYSCOMMAND = 0x0112
SC_MINIMIZE = 0xF020
SC_MAXIMIZE = 0xF030
SC_RESTORE = 0xF120
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_SYSMENU = 0x00080000
WS_FRAME = WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU
GWL_STYLE = -16
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020 | SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE
DWMWA_TRANSITIONS_FORCEDISABLED = 3
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2
DWMWA_BORDER_COLOR = 34
DWMWA_COLOR_NONE = -2          # 0xFFFFFFFE: no border at all (Windows 11)

_libs: dict[str, object] = {}


def _lib(name: str):
    """A private handle on a system library. ``ctypes.windll`` hands out one
    shared object per library, so argument types set on its functions leak
    into every other module that uses them; a ``WinDLL`` of our own does
    not."""
    import ctypes

    if name not in _libs:
        _libs[name] = ctypes.WinDLL(name)
    return _libs[name]


def _dwm_set(hwnd: int, attribute: int, value: int) -> None:
    import ctypes
    from ctypes import wintypes

    dwm = _lib("dwmapi")
    dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p,
                                          wintypes.DWORD]
    v = ctypes.c_int(value)
    dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), attribute, ctypes.byref(v), 4)


def dress(hwnd: int) -> None:
    """Give the HWND a real frame (see the note at the top), round the corners
    and remove Windows 11's one pixel border.

    The corners: a framed window gets them for free, a frameless one has to
    ask, or it is the only square window on the desktop. The border: Windows
    11 draws a light hairline around every window, and this design draws no
    outlines anywhere, so the DWM is told to draw none. Older Windows refuse
    the two attributes; nothing else depends on them.

    The caller's ``nativeEvent`` must already be answering WM_NCCALCSIZE when
    the frame change here sends it, or the caption would appear for a frame.
    """
    if not IS_WINDOWS:
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32 = _lib("user32")
        h = wintypes.HWND(hwnd)
        get_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
        set_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
        get_long.restype = ctypes.c_ssize_t
        get_long.argtypes = [wintypes.HWND, ctypes.c_int]
        set_long.restype = ctypes.c_ssize_t
        set_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, ctypes.c_uint]

        set_long(h, GWL_STYLE, get_long(h, GWL_STYLE) | WS_FRAME)
        user32.SetWindowPos(h, None, 0, 0, 0, 0, SWP_FRAMECHANGED)

        _dwm_set(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)
        _dwm_set(hwnd, DWMWA_BORDER_COLOR, DWMWA_COLOR_NONE)
    except Exception:
        pass


def set_transitions(hwnd: int, enabled: bool) -> None:
    """Switch the DWM's own minimise, restore and maximise animation on or off
    for this window."""
    if not IS_WINDOWS:
        return
    try:
        _dwm_set(hwnd, DWMWA_TRANSITIONS_FORCEDISABLED, 0 if enabled else 1)
    except Exception:
        pass


def answer(message: int) -> tuple[bool, int] | None:
    """The two messages that make a framed HWND look frameless.

    ``message`` is the address of the ``MSG`` Qt hands to ``nativeEvent``.
    Returns what ``nativeEvent`` should return for the two messages that
    matter, ``None`` for every other one.

    WM_NCCALCSIZE with wParam set: answering 0 without touching the rectangle
    makes the client area the whole window, so no caption and no border are
    ever laid out. WM_NCACTIVATE: passed to DefWindowProc with lParam -1,
    which is the documented way to say "do not repaint the caption", the one
    place a 1 px caption line could still show when focus changes.
    """
    if not IS_WINDOWS:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        msg = wintypes.MSG.from_address(message)
        if msg.message == WM_NCCALCSIZE:
            return (True, 0) if msg.wParam else None
        if msg.message == WM_NCACTIVATE:
            proc = _lib("user32").DefWindowProcW
            proc.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            proc.restype = ctypes.c_ssize_t
            return True, int(proc(msg.hWnd, WM_NCACTIVATE, msg.wParam, -1))
    except Exception:
        pass
    return None


def syscommand(message: int) -> int | None:
    """The system command a WM_SYSCOMMAND carries (SC_MINIMIZE, SC_MAXIMIZE,
    SC_RESTORE, ...), or ``None`` when the message is something else. The
    low four bits are the system's own and are masked off, as the
    documentation says to."""
    if not IS_WINDOWS:
        return None
    try:
        from ctypes import wintypes

        msg = wintypes.MSG.from_address(message)
        if msg.message == WM_SYSCOMMAND:
            return int(msg.wParam) & 0xFFF0
    except Exception:
        pass
    return None
