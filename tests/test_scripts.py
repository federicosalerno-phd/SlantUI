"""The browser side scripts, run in a bare V8 against a small fake DOM.

The text level checks at the top always run. The rest need py_mini_racer,
which ships V8 as a wheel and is in the dev extra; without it they skip.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from slantui.js import SCRIPTS, bundle, path
from slantui.tokens import DEFAULT, PALETTES, color
from slantui.tokens.roles import ROLE_NAMES

ROOT = Path(__file__).resolve().parent.parent
FAKEDOM = (ROOT / "tests" / "fakedom.js").read_text(encoding="utf-8")


def _src(name: str) -> str:
    return path(name).read_text(encoding="utf-8")


# ── text level ──────────────────────────────────────────────────────────────
def test_every_script_exists():
    for name in SCRIPTS:
        assert path(name).is_file(), name


def test_bundle_is_in_load_order():
    b = bundle()
    starts = [b.index(_src(n)) for n in SCRIPTS]
    assert starts == sorted(starts)


@pytest.mark.parametrize("name", SCRIPTS)
def test_a_classic_script_not_a_module(name):
    """file:// gives a page no module loading, so nothing may import."""
    assert not re.search(r"^\s*(import|export)\b", _src(name), re.M), name


@pytest.mark.parametrize("name", SCRIPTS)
def test_no_colour_literal(name):
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", _src(name)), name


def test_theme_roles_match_the_python():
    m = re.search(r"const THEME_ROLES = \[(.*?)\];", _src("theme.js"), re.S)
    assert m
    assert tuple(re.findall(r"'([a-z0-9-]+)'", m.group(1))) == ROLE_NAMES


def test_the_credit_text_is_the_licence_text():
    lic = (ROOT / "LICENSE").read_text(encoding="utf-8")
    m = re.search(r"It\s+reads:\s*\n\s*\n[ \t]+(.+?)[ \t]*\n", lic)
    assert m, "LICENSE no longer says what the credit line reads"
    assert f"const CREDIT_TEXT = '{m.group(1)}';" in _src("titlebar.js")


def test_the_title_bar_finds_nothing_by_id():
    """The shell is classes, so a page keeps its ids."""
    assert "getElementById" not in _src("titlebar.js")


# ── executed ────────────────────────────────────────────────────────────────
racer = pytest.importorskip("py_mini_racer")


@pytest.fixture
def js():
    ctx = racer.MiniRacer()
    ctx.eval(FAKEDOM)
    return ctx


def J(ctx, expr: str):
    """Evaluate and bring the value over as JSON, whatever its type."""
    return json.loads(ctx.eval(f"JSON.stringify({expr})"))


def _bytes(h: str) -> tuple[int, int, int]:
    r, g, b, _ = color.parse(h)
    return round(r * 255), round(g * 255), round(b * 255)


# ── theme.js ────────────────────────────────────────────────────────────────
THEME_PAGE = """
  const DARK = %s;
  const LIGHT = %s;
  DARK['--c-gt'] = '#57B26A';
  getComputedStyle = function () {
    return { getPropertyValue: function (n) {
      const p = document.documentElement.getAttribute('data-palette');
      return (p === 'slate-light' ? LIGHT : DARK)[n] || '';
    } };
  };
"""


def test_theme_reads_the_roles_and_follows_the_palette_switch(js):
    dark = {f"--{k}": v for k, v in DEFAULT.values.items()}
    light = {f"--{k}": v for k, v in PALETTES["slate-light"].values.items()}
    js.eval(THEME_PAGE % (json.dumps(dark), json.dumps(light)))
    js.eval(_src("theme.js"))

    assert J(js, "Theme.read()") == DEFAULT.values
    assert J(js, "Theme.palette()") == ""
    assert J(js, "Theme.get('nobody-read-this')") == ""

    js.eval("Theme.setPalette('slate-light')")
    assert J(js, "Theme.palette()") == "slate-light"
    assert J(js, "Theme.get('accent')") == PALETTES["slate-light"]["accent"]
    assert J(js, "Theme.values") == PALETTES["slate-light"].values

    js.eval("Theme.setPalette('')")
    assert J(js, "document.documentElement.getAttribute('data-palette')") is None
    assert J(js, "Theme.get('accent')") == DEFAULT["accent"]

    # an application's own tokens go through the same call and survive a switch
    assert J(js, "Theme.read(['c-gt'])['c-gt']") == "#57B26A"
    js.eval("Theme.setPalette('slate-light')")
    assert J(js, "Theme.get('c-gt')") == ""
    assert J(js, "Theme.get('text-1')") == PALETTES["slate-light"]["text-1"]


@pytest.mark.parametrize("h", ["#F5C542", "#0D0D0F", "#fff", "#101013F2", "#00000099", "#abc"])
def test_theme_maths_agrees_with_color_py(js, h):
    js.eval(_src("theme.js"))
    r, g, b = _bytes(h)
    a = color.alpha_of(h)
    got = J(js, f"Theme.rgb('{h}')")
    assert got[:3] == [r, g, b]
    assert got[3] == pytest.approx(a, abs=1e-9)
    assert J(js, f"Theme.rgba('{h}', 0.5)") == f"rgba({r},{g},{b},0.5)"
    assert J(js, f"Theme.hex3d('{h}')") == (r << 16) | (g << 8) | b


def test_theme_mix_is_a_straight_line(js):
    js.eval(_src("theme.js"))
    assert J(js, "Theme.mix('#000000', '#FFFFFF', 0)") == "rgb(0,0,0)"
    assert J(js, "Theme.mix('#000000', '#FFFFFF', 1)") == "rgb(255,255,255)"
    assert J(js, "Theme.mix('#000000', '#FFFFFF', 0.5)") == "rgb(128,128,128)"
    assert J(js, "Theme.mix('#F5C542', '#0D0D0F', 0.25)") == "rgb(187,151,53)"
    assert J(js, "Theme.rgb('#abcd')") == [170, 187, 204, pytest.approx(221 / 255)]


# ── bridge.js ───────────────────────────────────────────────────────────────
REMOTE = """
  const SEEN = [];
  const GOT = [];
  const SIG = { handlers: [], connect: function (fn) { this.handlers.push(fn); } };
  const REMOTE = {
    ping: function (done) { SEEN.push(['ping']); done('pong'); },
    setScale: function (v, done) { SEEN.push(['setScale', v]); done(v * 2); },
    info: function (done) { done('{"a": 1}'); },
    broken: function (done) { done('{not json'); },
    render: function (a, b, c, done) { SEEN.push(['render', a, b, c]); done('ok'); },
    editSet: function (a, b, c, done) { SEEN.push(['editSet', a, b, c]); done('{"n": ' + a + '}'); },
    shout: function (a, b) { SEEN.push(['shout', a]); b(); },
    windowMaximized: SIG,
  };
"""


def test_bridge_queues_until_the_channel_is_up_then_connects_at_once(js):
    js.eval(_src("bridge.js"))
    js.eval(REMOTE)
    js.eval("""
      Bridge.on('windowMaximized', function (m) { GOT.push(['max', m]); });
      be('ping', undefined, function (r) { GOT.push(r); });
      be('setScale', 21, function (r) { GOT.push(r); });
      Bridge.init();
    """)
    # no qt on the page yet: it polls, and nothing has been sent
    assert J(js, "TIMERS.length") == 1
    assert J(js, "SEEN") == []
    assert J(js, "Bridge.ready") is False

    js.eval("""
      var qt = { webChannelTransport: {} };
      function QWebChannel(transport, cb) { cb({ objects: { backend: REMOTE } }); }
      TIMERS[0].fn();
    """)
    assert J(js, "Bridge.ready") is True
    assert J(js, "SEEN") == [["ping"], ["setScale", 21]]
    assert J(js, "GOT") == ["pong", 42]
    assert J(js, "SIG.handlers.length") == 1

    # a subscription made after the channel is up is connected at once
    js.eval("Bridge.on('windowMaximized', function (m) { GOT.push(['again', m]); })")
    assert J(js, "SIG.handlers.length") == 2
    js.eval("SIG.handlers[0](true); SIG.handlers[1](true)")
    assert J(js, "GOT")[-2:] == [["max", True], ["again", True]]

    # calls now go straight through
    js.eval("be('ping')")
    assert J(js, "SEEN")[-1] == ["ping"]

    # beJson parses, and hands over null for what does not parse
    js.eval("beJson('info', undefined, function (v) { GOT.push(v); })")
    assert J(js, "GOT")[-1] == {"a": 1}
    js.eval("beJson('broken', undefined, function (v) { GOT.push(v); })")
    assert J(js, "GOT")[-1] is None

    # a missing slot or signal is said, not thrown
    js.eval("be('nothing'); Bridge.on('nosuch', function () {})")
    log = [" ".join(map(str, entry)) for entry in J(js, "LOG")]
    assert any("no slot nothing" in entry for entry in log)
    assert any("no signal nosuch" in entry for entry in log)


def test_bridge_hands_the_object_over_when_the_channel_comes_up(js):
    """For a page that keeps its own reference instead of calling be()."""
    js.eval(_src("bridge.js"))
    js.eval(REMOTE)
    js.eval("var MINE = null; Bridge.whenReady(function (o) { MINE = o; }); Bridge.init();")
    assert J(js, "MINE") is None
    js.eval("""
      var qt = { webChannelTransport: {} };
      function QWebChannel(transport, cb) { cb({ objects: { backend: REMOTE } }); }
      TIMERS[0].fn();
    """)
    assert J(js, "MINE === REMOTE") is True

    # asked for after the channel is up, it runs at once
    js.eval("var LATE = null; Bridge.whenReady(function (o) { LATE = o; });")
    assert J(js, "LATE === REMOTE") is True


def test_bridge_passes_as_many_arguments_as_the_slot_takes(js):
    """A slot can take three arguments, or six. The rule is the one
    JavaScript already has: a trailing function is the callback."""
    js.eval(_src("bridge.js"))
    js.eval(REMOTE)
    js.eval("""
      var qt = { webChannelTransport: {} };
      function QWebChannel(transport, cb) { cb({ objects: { backend: REMOTE } }); }
      Bridge.init();
    """)

    js.eval("be('render', 'C:/cases/01', '3', 'draft')")
    assert J(js, "SEEN")[-1] == ["render", "C:/cases/01", "3", "draft"]

    js.eval("be('render', 'C:/cases/01', '3', 'final', function (r) { GOT.push(r); })")
    assert J(js, "GOT")[-1] == "ok"

    # and beJson does the same, with the answer parsed
    js.eval("beJson('editSet', 2, 7, 'abc', function (v) { GOT.push(v); })")
    assert J(js, "SEEN")[-1] == ["editSet", 2, 7, "abc"]
    assert J(js, "GOT")[-1] == {"n": 2}

    # a slot with no callback still gets one, because QWebChannel wants the
    # last argument to be a function whatever the caller wanted
    js.eval("be('shout', 'hey')")
    assert J(js, "SEEN")[-1] == ["shout", "hey"]


def test_bridge_queued_calls_keep_all_their_arguments(js):
    js.eval(_src("bridge.js"))
    js.eval(REMOTE)
    js.eval("be('render', 'a', 'b', 'c'); Bridge.init();")
    assert J(js, "SEEN") == []
    js.eval("""
      var qt = { webChannelTransport: {} };
      function QWebChannel(transport, cb) { cb({ objects: { backend: REMOTE } }); }
      TIMERS[0].fn();
    """)
    assert J(js, "SEEN") == [["render", "a", "b", "c"]]


def test_bridge_takes_another_object_name(js):
    js.eval(_src("bridge.js"))
    js.eval(REMOTE)
    js.eval("""
      var qt = { webChannelTransport: {} };
      function QWebChannel(transport, cb) { cb({ objects: { app: REMOTE } }); }
      be('ping');
      Bridge.init('app');
    """)
    assert J(js, "Bridge.objectName") == "app"
    assert J(js, "Bridge.ready") is True
    assert J(js, "SEEN") == [["ping"]]


def test_bridge_says_when_the_object_is_not_there(js):
    js.eval(_src("bridge.js"))
    js.eval(REMOTE)
    js.eval("""
      var qt = { webChannelTransport: {} };
      function QWebChannel(transport, cb) { cb({ objects: { app: REMOTE } }); }
      Bridge.init();
    """)
    assert J(js, "Bridge.ready") is False
    assert any("no object called backend" in " ".join(map(str, e)) for e in J(js, "LOG"))


# ── titlebar.js ─────────────────────────────────────────────────────────────
TITLEBAR_PAGE = """
  CSS_VARS = { '--tbar-thin': '28px', '--tbar-slant': '38px', '--tbar-join': '8px' };
  const app = document.body.appendChild(new El('div', 'app'));
  const bar = app.appendChild(new El('div', 'titlebar'));
  bar.clientWidth = 800; bar.clientHeight = 44;
  const band = bar.appendChild(new El('div', 'tbar-band'));
  const brand = bar.appendChild(new El('div', 'tbar-brand'));
  brand.rect.width = 120;
  bar.appendChild(new El('div', 'tbar-drag'));
  const btns = bar.appendChild(new El('div', 'tbar-btns'));
  const bMin = btns.appendChild(new El('div', 'wbtn wbtn-min'));
  const bMax = btns.appendChild(new El('div', 'wbtn wbtn-max'));
  const bClose = btns.appendChild(new El('div', 'wbtn wbtn-close'));
  ['n', 's', 'e', 'w', 'nw', 'ne', 'sw', 'se'].forEach(function (e) {
    const rz = document.body.appendChild(new El('div', 'rz rz-' + e));
    rz.dataset.edge = e;
  });
  // stand ins for bridge.js, which has its own test. be() is variadic there,
  // so it is variadic here: a trailing function is the callback.
  const Bridge = { subs: [], on: function (s, fn) { this.subs.push(s); } };
  function be(m) {
    const rest = Array.prototype.slice.call(arguments, 1);
    let cb = null;
    if (typeof rest[rest.length - 1] === 'function') cb = rest.pop();
    CALLS.push([m].concat(rest.length ? rest : [null]));
    if (m === 'winIsMaximized' && cb) cb(false);
  }
"""


def test_the_band_is_cut_to_the_metrics(js):
    js.eval(TITLEBAR_PAGE)
    js.eval(_src("titlebar.js"))
    js.eval("shapeTitleBar()")
    clip = J(js, "band.style.clipPath")
    # the three window corners, then the thin end flush with the right edge
    assert clip.startswith('path("M0.00,0.00 L800.00,0.00 L800.00,28.00 L')
    assert clip.endswith('Z")')
    # two rounded joints: the top of the taper at brand width + slant, the
    # bottom at brand width. Each is entered 8px early and left 8px late.
    assert "L166.00,28.00 Q158.00,28.00 150.63,31.10" in clip
    assert "L127.37,40.90 Q120.00,44.00 112.00,44.00" in clip
    assert clip.count("Q") == 2

    # on the Qt 5 engine, the same six points as a polygon, joints unrounded
    js.eval("SUPPORTS_PATH = false; shapeTitleBar()")
    assert J(js, "band.style.clipPath") == \
        "polygon(0px 0px,800px 0px,800px 28px,158px 28px,120px 44px,0px 44px)"

    # a wider name moves the taper
    js.eval("SUPPORTS_PATH = true; brand.rect.width = 200; shapeTitleBar()")
    assert "Q238.00,28.00" in J(js, "band.style.clipPath")


def test_rounded_poly_path_leaves_sharp_corners_alone(js):
    js.eval(_src("titlebar.js"))
    assert J(js, "roundedPolyPath([{x:0,y:0},{x:10,y:0},{x:10,y:10}])") == \
        "M0.00,0.00 L10.00,0.00 L10.00,10.00 Z"
    # a radius larger than half the shorter side is trimmed to it
    d = J(js, "roundedPolyPath([{x:0,y:0},{x:10,y:0,r:50},{x:10,y:10}])")
    assert d == "M0.00,0.00 L5.00,0.00 Q10.00,0.00 10.00,5.00 L10.00,10.00 Z"


def test_the_title_bar_writes_the_credit_and_wires_the_window(js):
    js.eval(TITLEBAR_PAGE)
    js.eval(_src("titlebar.js"))
    js.eval("initTitlebar()")

    # the credit line is there, with the licence's text, before the buttons
    assert J(js, "bar.querySelector('.tbar-credit').textContent") == "Layout by Federico Salerno"
    assert J(js, "bar.children.map(function (c) { return c.className; })") == \
        ["tbar-band", "tbar-brand", "tbar-drag", "tbar-credit", "tbar-btns"]

    # it asked Qt for the state and subscribed to changes of it
    assert J(js, "Bridge.subs") == ["windowMaximized"]
    assert J(js, "CALLS") == [["winIsMaximized", None]]
    assert J(js, "bMax.title") == "Maximise"

    # a press on the bar moves the window; on a button, or with another
    # button of the mouse, it does not
    js.eval("CALLS.length = 0; fire(bar, 'mousedown', { button: 0 })")
    assert J(js, "CALLS") == [["winDrag", None]]
    js.eval("CALLS.length = 0; fire(bMin, 'mousedown', { button: 0 })")
    assert J(js, "CALLS") == []
    js.eval("fire(bar, 'mousedown', { button: 2 })")
    assert J(js, "CALLS") == []

    js.eval("bMin.onclick(); bMax.onclick(); bClose.onclick()")
    assert J(js, "CALLS") == [["winMinimize", None], ["winMaximizeToggle", None], ["winClose", None]]

    js.eval("CALLS.length = 0; fire(bar, 'dblclick', {})")
    assert J(js, "CALLS") == [["winMaximizeToggle", None]]
    js.eval("CALLS.length = 0; fire(bClose, 'dblclick', {})")
    assert J(js, "CALLS") == []

    js.eval("fire(document.body.querySelector('.rz-se'), 'mousedown', { button: 0 })")
    assert J(js, "CALLS") == [["winResize", "se"]]

    # the state Qt reports swaps the glyph and the class the strips hide on
    js.eval("onWindowMaximized(true)")
    assert J(js, "document.body.classList.contains('maximized')") is True
    assert J(js, "bMax.title") == "Restore"
    assert "M4.6" in J(js, "bMax.innerHTML")
    js.eval("onWindowMaximized(false)")
    assert J(js, "document.body.classList.contains('maximized')") is False
    assert J(js, "bMax.title") == "Maximise"


def test_a_credit_the_page_wrote_is_replaced_not_doubled(js):
    js.eval(TITLEBAR_PAGE)
    js.eval("const mine = new El('span', 'tbar-credit'); mine.textContent = 'nope'; bar.insertBefore(mine, btns);")
    js.eval(_src("titlebar.js"))
    js.eval("initTitlebar()")
    assert J(js, "bar.querySelectorAll('.tbar-credit').length") == 1
    assert J(js, "mine.textContent") == "Layout by Federico Salerno"


# ── widgets.js ──────────────────────────────────────────────────────────────
COMBO_PAGE = """
  const combo = document.body.appendChild(new El('div', 'combo'));
  combo.setAttribute('data-options', 'Alpha|Beta|Gamma');
  combo.rect = { left: 10, top: 100, width: 200, height: 28, right: 210, bottom: 128 };
  const label = combo.appendChild(new El('span', 'combo-v'));
  const CHANGES = [];
  combo.addEventListener('change', function () { CHANGES.push(combo.value); });
  function popup() { return document.body.querySelector('.combopop'); }
  function options() {
    return document.body.querySelectorAll('.combo-opt').map(function (o) { return o.className; });
  }
"""


def test_the_dropdown_answers_like_a_select(js):
    js.eval(COMBO_PAGE)
    js.eval(_src("widgets.js"))
    js.eval("initSelects()")

    # the first option when the page set none, and the label follows
    assert J(js, "combo.value") == "Alpha"
    assert J(js, "label.textContent") == "Alpha"

    # arrows move and fire change; the ends clamp
    js.eval("fire(combo, 'keydown', { key: 'ArrowDown' })")
    assert J(js, "combo.value") == "Beta"
    assert J(js, "CHANGES") == ["Beta"]
    js.eval("fire(combo, 'keydown', { key: 'ArrowUp' }); fire(combo, 'keydown', { key: 'ArrowUp' })")
    assert J(js, "combo.value") == "Alpha"
    assert J(js, "CHANGES") == ["Beta", "Alpha"]

    # setting .value from code fires nothing, like a <select>
    js.eval("combo.value = 'Gamma'")
    assert J(js, "label.textContent") == "Gamma"
    assert J(js, "CHANGES") == ["Beta", "Alpha"]

    # open: a popup on the body, under the trigger, the current row marked
    js.eval("fire(combo, 'click', {})")
    assert J(js, "combo.classList.contains('open')") is True
    assert J(js, "options()") == ["combo-opt", "combo-opt", "combo-opt combo-on"]
    assert J(js, "popup().style.top") == "132px"
    assert J(js, "popup().style.left") == "10px"
    assert J(js, "popup().style.width") == "200px"

    # a click on a row picks it and closes
    js.eval("document.body.querySelectorAll('.combo-opt')[1].onclick()")
    assert J(js, "combo.value") == "Beta"
    assert J(js, "CHANGES")[-1] == "Beta"
    assert J(js, "popup()") is None
    assert J(js, "combo.classList.contains('open')") is False

    # Escape closes, and so does a press anywhere else
    js.eval("fire(combo, 'click', {}); fire(combo, 'keydown', { key: 'Escape' })")
    assert J(js, "popup()") is None


def test_the_dropdown_keeps_a_value_apart_from_its_label(js):
    """A <select> has carried that split since it was invented, and
    A list built from data needs it: the row reads "Report of March, 412
    slices" and the value is the index."""
    js.eval(COMBO_PAGE)
    js.eval(_src("widgets.js"))
    js.eval("combo.setAttribute('data-values', 'a|b|c')")
    js.eval("initSelects()")

    assert J(js, "combo.value") == "a"
    assert J(js, "label.textContent") == "Alpha"

    js.eval("combo.value = 'c'")
    assert J(js, "label.textContent") == "Gamma"

    # the popup shows the labels and hands back the values
    js.eval("fire(combo, 'click', {})")
    assert J(js, "document.body.querySelectorAll('.combo-opt').map("
                 "function (o) { return o.textContent; })") == ["Alpha", "Beta", "Gamma"]
    js.eval("document.body.querySelectorAll('.combo-opt')[1].onclick()")
    assert J(js, "combo.value") == "b"
    assert J(js, "label.textContent") == "Beta"

    # and the arrows move over the values, not the labels
    js.eval("fire(combo, 'keydown', { key: 'ArrowDown' })")
    assert J(js, "combo.value") == "c"


def test_a_dropdown_filled_from_code(js):
    js.eval(COMBO_PAGE)
    js.eval(_src("widgets.js"))
    js.eval("initSelects()")

    js.eval("setOptions(combo, ['CT head, 412 slices', 'CT neck, 88 slices'], ['0', '1'])")
    assert J(js, "combo.value") == "0"
    assert J(js, "label.textContent") == "CT head, 412 slices"

    # refilling with the same value still in the list keeps the selection
    js.eval("combo.value = '1'")
    js.eval("setOptions(combo, ['CT head, 412 slices', 'CT neck, 88 slices', "
            "'CT chest, 900 slices'], ['0', '1', '2'])")
    assert J(js, "combo.value") == "1"

    # and drops to the first when it is gone
    js.eval("setOptions(combo, ['nothing found'], ['x'])")
    assert J(js, "combo.value") == "x"

    # no values given means the label is the value
    js.eval("setOptions(combo, ['One', 'Two'])")
    assert J(js, "combo.value") == "One"
    assert J(js, "combo.getAttribute('data-values')") is None


def test_a_dropdown_option_may_not_carry_the_separator(js):
    """Writing it would come back as two rows, and the page would show a
    list nobody asked for."""
    js.eval(COMBO_PAGE)
    js.eval(_src("widgets.js"))
    js.eval("initSelects()")
    js.eval("var caught = ''; try { setOptions(combo, ['a|b']); } "
            "catch (e) { caught = e.message; }")
    assert "vertical bar" in J(js, "caught")
    js.eval("fire(combo, 'click', {}); fire(document.body, 'mousedown', {})")
    assert J(js, "popup()") is None


def test_the_dropdown_opens_above_when_there_is_no_room_below(js):
    js.eval(COMBO_PAGE)
    js.eval(_src("widgets.js"))
    js.eval("initSelects()")
    # the popup measures itself once appended; the fake DOM answers with the
    # height the test set on the prototype for this case
    js.eval("Object.defineProperty(El.prototype, 'offsetHeight', { get: function () { return 90; }, configurable: true });")
    js.eval("combo.rect = { left: 10, top: 590, width: 200, height: 28, right: 210, bottom: 618 };"
            "fire(combo, 'click', {})")
    assert J(js, "popup().style.top") == "496px"


def test_the_stepper_keeps_the_decimals_of_the_step(js):
    js.eval(_src("widgets.js"))
    js.eval("""
      const f = new El('input');
      f.step = '0.1'; f.value = '50'; f.min = '0'; f.max = '60';
      const INPUTS = [];
      f.addEventListener('input', function () { INPUTS.push(f.value); });
    """)
    js.eval("numStep(f, 1)")
    assert J(js, "f.value") == "50.1"
    js.eval("f.value = ''; numStep(f, 1)")
    assert J(js, "f.value") == "0.1"
    js.eval("f.value = ''; numStep(f, -1)")
    assert J(js, "f.value") == "0.0"
    js.eval("f.value = '59.95'; numStep(f, 1)")
    assert J(js, "f.value") == "60.0"
    js.eval("f.step = ''; f.min = ''; f.value = '1'; numStep(f, -1); numStep(f, -1)")
    assert J(js, "f.value") == "0"
    assert J(js, "INPUTS.length") == 6
    # by id as well as by element
    js.eval("f.attrs.id = 'calLen'; f.step = '5'; document.body.appendChild(f); numStep('calLen', 1)")
    assert J(js, "f.value") == "5"


def test_fit_one_line_shrinks_then_drops_the_middle(js):
    js.eval(_src("widgets.js"))
    js.eval("const box = new El('div', 'fit'); box.clientWidth = 120;")

    js.eval("fitOneLine(box, 'short.png', 13.5, 10)")
    assert J(js, "box.style.fontSize") == "13.5px"
    assert J(js, "box.textContent") == "short.png"
    assert J(js, "box.title") == "short.png"

    long = "a_very_long_photograph_name_2026_09_18_case_17.jpeg"
    js.eval(f"fitOneLine(box, '{long}', 13.5, 10)")
    assert J(js, "box.style.fontSize") == "10px"
    assert J(js, "box.title") == long
    shown = J(js, "box.textContent")
    assert shown == "a_very_long" + chr(0x2026) + "_17.jpeg"
    assert J(js, "box.scrollWidth") <= 120

    # a box that is not laid out yet is left alone
    js.eval("const tiny = new El('div'); tiny.clientWidth = 0; fitOneLine(tiny, 'x', 13, 10)")
    assert J(js, "tiny.style.fontSize") == ""
    assert J(js, "tiny.textContent") == "x"

    # nothing to show clears the box
    js.eval("fitOneLine(box, null, 13.5, 10)")
    assert J(js, "box.textContent") == ""
    assert J(js, "box.title") == ""
