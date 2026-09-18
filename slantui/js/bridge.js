/* ============================================================================
   bridge.js: the only file that talks to Qt.

   The Python side registers one object on a QWebChannel. Everything the page
   asks of Python goes through be(); everything Python pushes back is a
   signal a module subscribed to with Bridge.on().

     be('winDrag');                              nothing to say, nothing back
     be('runJob', 2400);                         one argument
     be('render', folder, page, 'draft');        as many as the slot takes
     be('appInfo', function (s) { ... });        nothing in, an answer back
     be('saveStl', name, text, function (r) {}); both

   The rule is the one JavaScript already has: a trailing function is the
   callback and everything before it is the slot's arguments.

   Calls made before the channel is up are queued and sent when it comes up.
   Subscriptions made before it is up are connected when it comes up, and a
   subscription made after that is connected at once. So no module has to
   care about start up order.

   The object's name on the channel is "backend" unless the page says
   otherwise before init(): Bridge.init('app'), or Bridge.objectName = 'app'.

   Leaves on the window: Bridge, be, beJson.

   Bridge.whenReady(fn) is for a page that wants the remote object
   itself instead of going through be().
   ========================================================================== */

const Bridge = {
  objectName: 'backend',
  obj: null,        // the remote object, once the channel is up
  ready: false,
  _queue: [],       // calls made before the channel came up
  _subs: {},        // signal name -> [handler]
  _waiting: [],     // whenReady callbacks, for a page holding its own obj

  /* Run something once the channel is up, with the remote object.

     An application that calls Python only through be() never needs this:
     the calls queue. An application that keeps its own reference to the
     remote object does, and a page with a hundred call sites naming it has
     no cheap way to queue them. Handed the object, and run at once when the
     channel is already up. */
  whenReady: function (fn) {
    if (this.ready) { fn(this.obj); return; }
    this._waiting.push(fn);
  },

  /* Subscribe to a signal on the remote object. Safe at any time. */
  on: function (signal, fn) {
    if (!this._subs[signal]) this._subs[signal] = [];
    this._subs[signal].push(fn);
    if (this.ready) this._connectOne(signal, fn);
  },

  /* Connect the transport, then flush whatever queued up meanwhile. Polls
     until Qt has put the transport on the page. */
  init: function (objectName) {
    if (objectName) this.objectName = objectName;
    if (typeof qt === 'undefined' || !qt.webChannelTransport) {
      setTimeout(function () { Bridge.init(); }, 80);
      return;
    }
    new QWebChannel(qt.webChannelTransport, function (channel) {
      Bridge.obj = channel.objects[Bridge.objectName];
      if (!Bridge.obj) {
        console.error('bridge: the channel has no object called', Bridge.objectName);
        return;
      }
      Bridge.ready = true;
      Bridge._connect();
      Bridge._flush();
      while (Bridge._waiting.length) Bridge._waiting.shift()(Bridge.obj);
    });
  },

  _connectOne: function (signal, fn) {
    const emitter = this.obj[signal];
    if (!emitter || !emitter.connect) {
      console.warn('bridge: no signal', signal);
      return false;
    }
    emitter.connect(fn);
    return true;
  },

  _connect: function () {
    for (const signal in this._subs) {
      const fns = this._subs[signal];
      for (let i = 0; i < fns.length; i++) {
        if (!this._connectOne(signal, fns[i])) break;
      }
    }
  },

  _flush: function () {
    while (this._queue.length) {
      const c = this._queue.shift();
      this._invoke(c.m, c.args, c.cb);
    }
  },

  /* QWebChannel gives every slot a function taking the slot's own arguments
     and then a callback. `args` is already the list, so this is one apply. */
  _invoke: function (m, args, cb) {
    const fn = this.obj[m];
    if (!fn) { console.error('bridge: no slot', m); return; }
    fn.apply(this.obj, args.concat([cb || function () {}]));
  },
};

/* Split a call's tail into the slot's arguments and the callback. */
function _beSplit(rest) {
  const args = Array.prototype.slice.call(rest);
  let cb = null;
  if (typeof args[args.length - 1] === 'function') cb = args.pop();
  /* An explicit undefined at the end is a caller writing be(m, undefined, cb)
     for a slot that takes nothing. It is not an argument. */
  while (args.length && args[args.length - 1] === undefined) args.pop();
  return { args: args, cb: cb };
}

/* Call a slot on the remote object. Pass the slot's arguments, then a
   callback if you want its return value; the value arrives already decoded
   by QWebChannel, so a JSON string is still a string. */
function be(method) {
  const c = _beSplit(Array.prototype.slice.call(arguments, 1));
  if (Bridge.ready) Bridge._invoke(method, c.args, c.cb);
  else Bridge._queue.push({ m: method, args: c.args, cb: c.cb });
}

/* The same, for a slot that answers with a JSON string. The callback gets
   the parsed value, or null when the string did not parse. */
function beJson(method) {
  const c = _beSplit(Array.prototype.slice.call(arguments, 1));
  const args = c.args.concat([function (raw) {
    let parsed = null;
    try { parsed = JSON.parse(raw); } catch (e) { console.error('bridge: bad JSON from', method, raw); }
    if (c.cb) c.cb(parsed);
  }]);
  be.apply(null, [method].concat(args));
}
