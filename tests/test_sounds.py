"""sounds.js, run in a bare V8 against the fake DOM and a fake audio engine.

The engine here records what the script asks of it instead of making a sound,
which is enough to hold the script to what it promises: every voice is ready
before the first press, a voice starts the moment it is asked for, a press on
a control that says it makes a sound makes it, nothing plays before the page
has said whether sounds are on, the switch and the key do what they say, and
a burst stays a few sounds. The samples themselves are checked here too: that
the script reads them as they were written, and that each one starts and ends
on zero.
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import pytest

from slantui.js import SCRIPTS, path

ROOT = Path(__file__).resolve().parent.parent
FAKEDOM = (ROOT / "tests" / "fakedom.js").read_text(encoding="utf-8")
SRC = path("sounds.js").read_text(encoding="utf-8")
VOICES = ("forward", "back", "shutter", "on", "off", "confirm", "error")


def _data() -> dict[str, bytes]:
    block = re.search(r"const SOUND_DATA = \{(.*?)\n\};", SRC, re.S)
    assert block, "sounds.js carries no SOUND_DATA"
    return {k: base64.b64decode(v) for k, v in re.findall(r"^  (\w+): '([A-Za-z0-9+/=]*)',$", block.group(1), re.M)}


def _samples(raw: bytes) -> list[int]:
    return [int.from_bytes(raw[i:i + 2], "little", signed=True) for i in range(0, len(raw), 2)]


def test_the_sounds_load_after_the_signs_they_draw_the_switch_with():
    assert "sounds.js" in SCRIPTS
    assert SCRIPTS.index("sounds.js") > SCRIPTS.index("icons.js")


def test_every_voice_has_its_samples_and_says_where_they_come_from():
    data = _data()
    assert sorted(data) == sorted(VOICES)
    assert "CC0" in SRC and "kenney.nl" in SRC


def test_every_voice_is_short_starts_and_ends_on_zero_and_stays_low():
    for name, raw in _data().items():
        x = _samples(raw)
        ms = len(x) / 48000 * 1000
        assert 20 <= ms <= 200, (name, ms)
        assert x[0] == 0 and x[-1] == 0, name
        assert max(abs(v) for v in x) < 32768 * 0.5, name          # under -6 dBFS


racer = pytest.importorskip("py_mini_racer")

# An audio engine that keeps a list of what it was asked. Its clock is NOW,
# in ms, which the test moves by hand.
FAKE_AUDIO = """
  var NOW = 1000;
  var performance = { now: function () { return NOW; } };
  var NODES = [], BUFFERS = [], STARTS = [];
  function Param(v) { this.value = v; this.events = []; }
  Param.prototype.setTargetAtTime = function (v, t, k) { this.events.push(['target', v, t, k]); };
  function Node(kind) { this.kind = kind; this.outs = []; NODES.push(this); }
  Node.prototype.connect = function (n) { this.outs.push(n); return n; };
  Node.prototype.disconnect = function () { this.outs = []; };
  var FAKE_STATE = 'running';
  function FakeAudio(opts) {
    this.opts = opts; this.currentTime = 5; this.sampleRate = 48000; this.state = FAKE_STATE;
    this.baseLatency = 0.01; this.outputLatency = 0.012;
    this.destination = new Node('destination');
    FakeAudio.made++;
  }
  FakeAudio.made = 0;
  FakeAudio.prototype.createGain = function () { var n = new Node('gain'); n.gain = new Param(1); return n; };
  FakeAudio.prototype.createBufferSource = function () {
    var n = new Node('source');
    n.start = function () { STARTS.push(Array.prototype.slice.call(arguments)); n.started = true; };
    n.stop = function (t) { n.stopAt = t; };
    return n;
  };
  FakeAudio.prototype.createConstantSource = function () {
    var n = new Node('constant'); n.offset = new Param(1);
    n.start = function () { n.started = true; }; n.stop = function () { n.stopped = true; };
    return n;
  };
  FakeAudio.prototype.createBuffer = function (ch, len, rate) {
    var d = new Float32Array(len); var b = { ch: ch, len: len, rate: rate, getChannelData: function () { return d; } };
    BUFFERS.push(b); return b;
  };
  FakeAudio.prototype.resume = function () {
    this.state = 'running'; return { then: function (ok) { ok(); } };
  };
  var AudioContext = FakeAudio;
  var KEPT = {};
  var localStorage = {
    getItem: function (k) { return k in KEPT ? KEPT[k] : null; },
    setItem: function (k, v) { KEPT[k] = String(v); },
  };
  function band() {
    var bar = new El('div', 'titlebar'), btns = new El('div', 'tbar-btns');
    ['wbtn wbtn-min', 'wbtn wbtn-max', 'wbtn wbtn-close'].forEach(function (c) { btns.appendChild(new El('div', c)); });
    bar.appendChild(btns);
    document.body.appendChild(bar);
    return btns;
  }
  function played() { return _snd.cur ? _snd.cur.name : null; }
"""


@pytest.fixture
def js():
    ctx = racer.MiniRacer()
    ctx.eval(FAKEDOM)
    ctx.eval(FAKE_AUDIO)
    ctx.eval(path("icons.js").read_text(encoding="utf-8"))
    ctx.eval(SRC)
    return ctx


def J(ctx, expr: str):
    return json.loads(ctx.eval(f"JSON.stringify({expr})"))


def test_the_script_reads_the_samples_as_they_were_written(js):
    raw = _data()["confirm"]
    want = [v / 32768 for v in _samples(raw)]
    got = J(js, "Array.prototype.slice.call(_sndSamples('confirm'))")
    assert len(got) == len(want)
    assert max(abs(a - b) for a, b in zip(got, want)) < 1e-6


def test_nothing_plays_before_the_page_says_whether_sounds_are_on(js):
    assert J(js, "playSound('confirm')") is False
    assert J(js, "FakeAudio.made") == 0


def test_every_voice_is_ready_before_the_first_press(js):
    js.eval("initSounds({ on: true, band: false })")
    assert J(js, "FakeAudio.made") == 1
    assert J(js, "_snd.ctx.opts.latencyHint") == "interactive"
    assert sorted(J(js, "Object.keys(_snd.buffers)")) == sorted(VOICES)
    assert J(js, "BUFFERS.every(function (b) { return b.ch === 1 && b.rate === 48000 && b.len > 0; })") is True
    made = J(js, "BUFFERS.length")
    js.eval("playSound('forward'); NOW += 1000; playSound('confirm')")
    assert J(js, "BUFFERS.length") == made                     # nothing made at the press


def test_a_voice_starts_now(js):
    js.eval("initSounds({ on: true, band: false })")
    assert J(js, "playSound('shutter')") is True
    assert J(js, "STARTS") == [[]]                              # start(): as soon as it can, never later
    assert J(js, "soundLatency().total") == pytest.approx(22.0)


def test_the_same_voice_again_inside_its_gap_is_dropped(js):
    js.eval("initSounds({ on: true, band: false })")
    assert J(js, "playSound('forward')") is True
    js.eval("NOW += 20")
    assert J(js, "playSound('forward')") is False
    js.eval("NOW += 60")
    assert J(js, "playSound('forward')") is True


def test_a_voice_that_says_less_gives_way(js):
    js.eval("initSounds({ on: true, band: false })")
    assert J(js, "playSound('error')") is True
    js.eval("NOW += 20")
    assert J(js, "playSound('back')") is False         # less, too close: dropped
    js.eval("NOW += 200")
    assert J(js, "playSound('back')") is True
    js.eval("var first = _snd.cur.out; NOW += 20")
    assert J(js, "playSound('confirm')") is True       # more: plays, and the first fades and stops
    assert any(e[0] == "target" and e[1] == 0 for e in J(js, "first.gain.gain.events"))
    assert J(js, "first.src.stopAt") is not None


def test_a_burst_stays_a_few_sounds(js):
    js.eval("initSounds({ on: true, band: false })")
    played = J(js, """(function () {
      var n = 0, names = ['forward', 'back', 'on', 'off', 'shutter', 'forward', 'back', 'on'];
      names.forEach(function (v) { NOW += 100; if (playSound(v)) n++; });
      return n; })()""")
    assert played == J(js, "SOUND_BURST")


def test_a_press_on_a_control_makes_its_sound_at_once(js):
    js.eval("initSounds({ on: true, band: false });"
            "var b = new El('button'); b.setAttribute('data-sound', 'forward');"
            "var inside = new El('span'); b.appendChild(inside); document.body.appendChild(b);")
    fire = lambda props: J(js, f"(function () {{ _snd.cur = null; _snd.last = {{}}; _snd.recent = [];"  # noqa: E731
                                 f" fire(inside, {props!r}.split(' ')[0], {props!r}.split(' ')[1] ? "
                                 f"JSON.parse({props!r}.split(' ').slice(1).join(' ')) : null); return played(); }})()")
    assert fire('pointerdown {"button":0}') == "forward"
    assert fire('pointerdown {"button":2}') is None         # the other button is a menu, not a press
    assert fire('keydown {"key":"Enter"}') == "forward"
    assert fire('keydown {"key":"Enter","defaultPrevented":true}') is None    # a key somebody already used
    js.eval("b.disabled = true")
    assert fire('pointerdown {"button":0}') is None         # a control that is off says nothing


def test_off_is_quiet_and_says_so_once(js):
    js.eval("var said = []; initSounds({ on: true, band: false, keep: function (on) { said.push(on); } })")
    assert J(js, "setSoundsOn(false)") is False
    assert J(js, "played()") == "off"                       # the last sound before the quiet
    assert J(js, "said") == [False]
    js.eval("NOW += 1000")
    assert J(js, "playSound('confirm')") is False
    assert J(js, "soundsOn()") is False


def test_the_choice_is_kept_in_the_page_when_the_application_keeps_nothing(js):
    js.eval("initSounds({ band: false })")
    assert J(js, "soundsOn()") is True                      # on, the first time
    js.eval("setSoundsOn(false)")
    assert J(js, "KEPT['slantui.sounds']") == "0"
    js.eval("_snd.ready = false; initSounds({ band: false })")
    assert J(js, "soundsOn()") is False


def test_the_switch_goes_first_among_the_window_buttons_and_flips_on_the_press(js):
    js.eval("var btns = band(); initSounds({ on: true, hints: { on: 'Sounds on', off: 'Sounds off' } })")
    first = J(js, "[btns.children[0].className, btns.children[0].getAttribute('aria-pressed'),"
                  " btns.children[0].title, btns.children.length]")
    assert first == ["wbtn wbtn-sound", "true", "Sounds on", 4]
    assert 'data-segno="sound-on"' in J(js, "btns.children[0].innerHTML")
    js.eval("btns.children[0].onpointerdown({ button: 0 })")
    assert J(js, "[soundsOn(), btns.children[0].title, btns.children[0].getAttribute('aria-pressed')]") == \
        [False, "Sounds off", "false"]
    assert 'data-segno="sound-off"' in J(js, "btns.children[0].innerHTML")
    js.eval("initSounds({ on: false })")
    assert J(js, "btns.children.length") == 4               # asked again: still one switch


def test_ctrl_m_flips_it_from_anywhere_and_lights_the_switch(js):
    js.eval("var btns = band(); initSounds({ on: true })")
    assert J(js, "btns.children[0].title") == "Ctrl+M"      # with no words given, the key at least
    ev = J(js, "(function () { var e = fire(document.body, 'keydown', { key: 'm', ctrlKey: true });"
               " return [e.defaultPrevented, soundsOn(), btns.children[0].classList.contains('on')]; })()")
    assert ev == [True, False, True]
    # a plain m, or Ctrl+Shift+M, is somebody else's
    js.eval("fire(document.body, 'keydown', { key: 'm' });"
            " fire(document.body, 'keydown', { key: 'M', ctrlKey: true, shiftKey: true })")
    assert J(js, "soundsOn()") is False
    # on a layout whose letter there is not a latin m, the place of the key still counts
    js.eval("NOW += 1000; fire(document.body, 'keydown', { key: '\\u044c', code: 'KeyM', ctrlKey: true })")
    assert J(js, "soundsOn()") is True


def test_a_device_not_yet_running_plays_when_it_starts_and_not_late(js):
    js.eval("FAKE_STATE = 'suspended'; initSounds({ on: true, band: false })")
    assert J(js, "_snd.ctx.state") == "running"             # woken at once where the engine allows it
    js.eval("_snd.ctx.state = 'suspended'; STARTS.length = 0")
    assert J(js, "playSound('confirm')") is True
    assert J(js, "STARTS.length") == 1                      # resumed, then played


def test_the_device_is_kept_open_while_sounds_are_on_and_let_go_when_off(js):
    # a context that plays only silence may have its device closed, and the next voice waits for it to open again
    js.eval("initSounds({ on: true, band: false })")
    awake = "NODES.filter(function (n) { return n.kind === 'constant'; })"
    assert J(js, awake + ".length") == 1
    assert J(js, awake + "[0].started && " + awake + "[0].outs[0] === _snd.ctx.destination") is True
    assert 0 < J(js, awake + "[0].offset.value") < 1e-5             # far under hearing, never a tone
    js.eval("setSoundsOn(false)")
    assert J(js, awake + "[0].stopped") is True and J(js, "_snd.awake") is None
    js.eval("NOW += 1000; setSoundsOn(true)")
    assert J(js, awake + ".length") == 2 and J(js, "!!_snd.awake") is True
