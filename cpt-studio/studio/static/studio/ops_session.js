'use strict';
// The console's automatic sign-out (release 1, B5; RELEASE-1-SPEC 4, B5, item 4), loaded by ops_base.html on every
// signed-in console page. The same timer and warning as the doctors' page (static/studio/app.js): the activity ping
// (POST /session/activity) at most once a minute while there is input, its answer the server's own remaining time (the
// session policy in studio/sessions.py is what ends the session), one timer shared by this browser's console tabs
// (BroadcastChannel, else localStorage events, every access in try/catch), a warning before the end with a button that
// sends the ping, and at the end the page is emptied and its sign-out form submitted to /logout/?reason=idle. Without
// script, the <noscript> refresh of ops_base.html moves the page to the sign-in after the operators' limit.
(function consoleSession() {
  const PING = '/session/activity';
  const CHANNEL = 'cpt-studio-console-session';
  const EVERY_MS = 60000;
  const INPUTS = ['pointerdown', 'keydown', 'wheel', 'scroll', 'touchstart'];

  // the timer's next step at `now` (ms): 'out' at or after the deadline, 'warn' inside the warning's lead, else 'wait'
  function step(deadline, warningMs, now) {
    if (!Number.isFinite(deadline) || deadline <= 0) return { step: 'wait', in: null, left: null };
    if (now >= deadline) return { step: 'out', in: 0, left: 0 };
    if (now >= deadline - warningMs) return { step: 'warn', in: deadline - now, left: deadline - now };
    return { step: 'wait', in: deadline - warningMs - now, left: deadline - now };
  }

  function warningText(ms) {
    const minutes = Math.max(1, Math.ceil(ms / 60000));
    return `You will be signed out in ${minutes} ${minutes === 1 ? 'minute' : 'minutes'}`;
  }

  function reasonOf(data) {
    return data && data.error === 'signed_out' && data.reason === 'idle' ? 'idle' : 'expired';
  }

  if (typeof module === 'object' && module.exports) module.exports = { step, warningText, reasonOf, PING, CHANNEL, EVERY_MS };
  if (typeof document === 'undefined') return;

  const form = document.querySelector('form[action="/logout/"]');
  if (!form) return;  // not a signed-in console page
  const watch = { deadline: 0, warningMs: 120000, lastPing: 0, pinging: false, timer: 0, channel: null, gone: false, dialog: null };

  function csrf() {
    const field = form.querySelector('input[name="csrfmiddlewaretoken"]');
    return field ? field.value : '';
  }

  function share(message) {
    const data = Object.assign({}, message, { at: Date.now() });
    try {
      if (watch.channel) {
        watch.channel.postMessage(data);
        return;
      }
    } catch (error) {
      // fall through to the storage events
    }
    try {
      window.localStorage.setItem(CHANNEL, JSON.stringify(data));
    } catch (error) {
      // no storage here: this tab keeps its own timer
    }
  }

  function clearScreen() {
    const main = document.getElementById('main');
    if (main) main.replaceChildren();
    for (const dialog of document.querySelectorAll('dialog')) {
      if (dialog.open) dialog.close();
    }
  }

  function leave(reason) {
    if (watch.gone) return;
    watch.gone = true;
    clearTimeout(watch.timer);
    clearScreen();
    window.location.assign(`/login/?reason=${reason === 'idle' ? 'idle' : 'expired'}`);
  }

  function signOut() {
    if (watch.gone) return;
    watch.gone = true;
    clearTimeout(watch.timer);
    share({ type: 'signed-out', reason: 'idle' });
    clearScreen();
    form.setAttribute('action', '/logout/?reason=idle');
    form.submit();
  }

  function warning() {
    if (watch.dialog) return watch.dialog;
    const dialog = document.createElement('dialog');
    dialog.className = 'card';
    dialog.setAttribute('aria-labelledby', 'idleTitle');
    const title = document.createElement('h2');
    title.id = 'idleTitle';
    const text = document.createElement('p');
    text.textContent = 'The console signs you out after a while without activity, and clears the screen. A form not yet sent is lost then.';
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'Stay signed in';
    button.addEventListener('click', () => ping());
    dialog.append(title, text, button);
    document.body.append(dialog);
    watch.dialog = dialog;
    return dialog;
  }

  function schedule() {
    clearTimeout(watch.timer);
    if (watch.gone) return;
    const next = step(watch.deadline, watch.warningMs, Date.now());
    if (next.step === 'out') {
      signOut();
      return;
    }
    if (next.step === 'warn') {
      const dialog = warning();
      dialog.querySelector('#idleTitle').textContent = warningText(next.left);
      if (!dialog.open) dialog.showModal();
    } else if (watch.dialog && watch.dialog.open) {
      watch.dialog.close();
    }
    if (next.in === null) return;
    watch.timer = setTimeout(schedule, next.step === 'warn' ? Math.min(1000, next.in) : Math.max(1000, next.in));
  }

  // only a later deadline moves the timer: the session's last activity only moves forward
  function adopt(deadline, warningMs, tell) {
    if (Number.isFinite(warningMs) && warningMs > 0) watch.warningMs = warningMs;
    if (!Number.isFinite(deadline) || deadline <= watch.deadline) return;
    watch.deadline = deadline;
    if (tell) share({ type: 'deadline', deadline, warningMs: watch.warningMs });
    schedule();
  }

  function receive(message) {
    if (!message || typeof message !== 'object') return;
    if (message.type === 'deadline') adopt(Number(message.deadline), Number(message.warningMs), false);
    else if (message.type === 'signed-out') leave(message.reason);
  }

  async function ping() {
    if (watch.pinging || watch.gone) return;
    watch.pinging = true;
    watch.lastPing = Date.now();
    try {
      const body = new FormData();
      body.append('csrfmiddlewaretoken', csrf());
      const response = await fetch(PING, { method: 'POST', body, credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } });
      const data = await response.json().catch(() => null);
      if (response.status === 401) {
        leave(reasonOf(data));
        return;
      }
      if (!response.ok || !data) return;
      const left = Number(data.idle_seconds);
      const lead = Number(data.warning_seconds);
      if (Number.isFinite(left) && left >= 0) adopt(Date.now() + left * 1000, Number.isFinite(lead) ? lead * 1000 : NaN, true);
    } catch (error) {
      // offline: the timer stands
    } finally {
      watch.pinging = false;
    }
  }

  try {
    watch.channel = typeof BroadcastChannel === 'function' ? new BroadcastChannel(CHANNEL) : null;
    if (watch.channel) watch.channel.onmessage = event => receive(event.data);
  } catch (error) {
    watch.channel = null;
  }
  try {
    window.addEventListener('storage', event => {
      if (event.key !== CHANNEL || !event.newValue) return;
      try {
        receive(JSON.parse(event.newValue));
      } catch (error) {
        // not a message of this console
      }
    });
  } catch (error) {
    // no storage events here
  }
  for (const type of INPUTS) {
    document.addEventListener(type, () => {
      if (!watch.gone && !watch.pinging && Date.now() - watch.lastPing >= EVERY_MS) ping();
    }, { capture: true, passive: true });
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden) schedule(); });
  form.addEventListener('submit', () => {
    if (!watch.gone) share({ type: 'signed-out', reason: 'expired' });
    watch.gone = true;
  });
  ping();
}());
