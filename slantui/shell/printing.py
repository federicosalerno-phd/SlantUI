"""A page, printed to PDF, without a window.

    from slantui.shell import print_to_pdf

    def done(data, error):
        if error: ...
        else: Path("out.pdf").write_bytes(data)

    print_to_pdf("report.html", done, page="A4", margins_mm=(16, 14, 16, 14))

The page is an HTML file on disk, laid out by the same engine the window
uses, so a document an application composes looks like the application: the
library's stylesheet, its fonts, its roles in whichever palette the document
puts on its <html> (a printed page wants the light one). It is loaded from
the FILE and not handed over as a string, because a string passed to setHtml
is capped near two megabytes, and a document with a few pictures in it is
past that.

What the engine prints is the DOM. A <canvas> drawn with WebGL comes out
empty in a PDF: a view of a 3D scene has to be read out of its canvas while
it is being drawn, and go into the document as an <img>.

The callback gets the bytes and None, or None and a sentence saying what
went wrong. It is called once, from the event loop; a page that does not
load or does not print within ``timeout_ms`` is an error too, not a wait
without end.
"""
from __future__ import annotations

from pathlib import Path

from .qt import (QMarginsF, QPageLayout, QPageSize, QTimer, QUrl, QWebEnginePage,
                 USE_QT6)

# The pages alive while they print. A QWebEnginePage nobody holds is collected
# half way through, and its callback never comes.
_LIVE: list = []

_SIZES = {"A4": "A4", "A3": "A3", "Letter": "Letter"}


def _page_size(name: str):
    ids = QPageSize.PageSizeId if USE_QT6 else QPageSize
    return QPageSize(getattr(ids, _SIZES.get(name, "A4")))


def print_to_pdf(html_path, done, page: str = "A4", landscape: bool = False,
                 margins_mm=(15, 15, 15, 15), timeout_ms: int = 60000) -> None:
    """Load ``html_path`` in a page of its own and print it; ``done(data, error)``.

    ``margins_mm`` is (top, right, bottom, left), the order CSS uses.
    """
    path = Path(html_path)
    if not path.is_file():
        done(None, "there is no file at %s" % path)
        return
    web = QWebEnginePage()
    state = {"over": False}
    _LIVE.append(web)

    def finish(data, error):
        if state["over"]:
            return
        state["over"] = True
        try:
            _LIVE.remove(web)
        except ValueError:
            pass
        web.deleteLater()
        done(data, error)

    def printed(data):
        body = bytes(data) if data is not None else b""
        if not body.startswith(b"%PDF"):
            finish(None, "the engine printed nothing")
        else:
            finish(body, None)

    def loaded(ok):
        if not ok:
            finish(None, "the page did not load: %s" % path)
            return
        orient = (QPageLayout.Orientation.Landscape if landscape else QPageLayout.Orientation.Portrait) \
            if USE_QT6 else (QPageLayout.Landscape if landscape else QPageLayout.Portrait)
        unit = QPageLayout.Unit.Millimeter if USE_QT6 else QPageLayout.Millimeter
        top, right, bottom, left = (float(x) for x in margins_mm)
        layout = QPageLayout(_page_size(page), orient, QMarginsF(left, top, right, bottom), unit)
        web.printToPdf(printed, layout)

    web.loadFinished.connect(loaded)
    QTimer.singleShot(int(timeout_ms), lambda: finish(None, "the page did not print within %d s"
                                                      % (timeout_ms // 1000)))
    web.load(QUrl.fromLocalFile(str(path.resolve())))
