'use strict';
// The console's automatic sign-out (release 1, B5; RELEASE-1-SPEC 4, B5, item 4), loaded by ops_base.html on every
// signed-in console page. The same timer and warning as the doctors' page (static/studio/app.js):
// - armed the moment the page loads, from the seconds ops_base.html puts on the body (data-idle-seconds,
//   data-cap-seconds, data-warning-seconds: studio.sessions.page_config), whatever becomes of the first ping
//   (refutation r2, finding 13); the deadline is the earlier of the idle end and the session's cap (finding 16);
// - the activity ping (POST /session/activity) at most once a minute while there is input - one that failed is tried
//   again on input after RETRY_MS, the deadline standing meanwhile - its answer the server's own remaining time (the
//   session policy in studio/sessions.py is what ends the session);
// - one timer shared by this browser's console tabs of the same session (BroadcastChannel, else localStorage events,
//   every access in try/catch): every message names its session (data-session), a message of another session makes
//   the tab ask the server which session it is in (the ping marked a poll: no activity), a tab whose session is no
//   longer the browser's leaves, and a 401 is told to every tab of the session (finding 14);
// - a warning before the end: before the idle end with a button that sends the ping, before the cap with a sentence
//   to send what is typed (the cap cannot be moved); when it closes the focus goes back where it was;
// - at the end the page is emptied and its sign-out form submitted to /logout/?reason=idle, or ?reason=expired at the
//   cap. Without script, the <noscript> refresh of ops_base.html moves the page to the sign-in after the session's end.
(function consoleSession() {
  const PING = '/session/activity';
  const CHANNEL = 'cpt-studio-console-session';
  const POLL_HEADER = 'X-CPT-Poll';
  const EVERY_MS = 60000;
  const RETRY_MS = 15000;
  const DEFAULT_IDLE_SECONDS = 600;  // the operators' limit, for a page the server gave no seconds (it always gives them)
  const INPUTS = ['pointerdown', 'keydown', 'wheel', 'scroll', 'touchstart'];
  const IDLE_TEXT = 'The console signs you out after a while without activity, and clears the screen. A form not yet sent is lost then.';
  const CAP_TEXT = 'This session has reached its time limit. The console clears the screen and signs you out when it ends. Send or copy anything you are typing now: you will need to sign in again.';

  // the timer's next step at `now` (ms): 'out' at or after the deadline, 'warn' inside the warning's lead, else 'wait'
  function step(deadline, warningMs, now) {
    if (!Number.isFinite(deadline) || deadline <= 0) return { step: 'wait', in: null, left: null };
    if (now >= deadline) return { step: 'out', in: 0, left: 0 };
    if (now >= deadline - warningMs) return { step: 'warn', in: deadline - now, left: deadline - now };
    return { step: 'wait', in: deadline - warningMs - now, left: deadline - now };
  }

  function minutesText(prefix, ms) {
    const minutes = Math.max(1, Math.ceil(ms / 60000));
    return `${prefix} ${minutes} ${minutes === 1 ? 'minute' : 'minutes'}`;
  }

  function warningText(ms) {
    return minutesText('You will be signed out in', ms);
  }

  function capWarningText(ms) {
    return minutesText('Your session ends in', ms);
  }

  function reasonOf(data) {
    return data && data.error === 'signed_out' && data.reason === 'idle' ? 'idle' : 'expired';
  }

  function seconds(value) {
    const number = Number(value);
    return Number.isFinite(number) && number >= 0 ? number : null;
  }

  // the seconds the server put on the page, each null when absent or no number, and the session's tag ('' when absent)
  function pageSession(dataset) {
    const data = dataset || {};
    const number = value => (typeof value === 'string' && value.trim() !== '' ? seconds(value) : null);
    return { idle: number(data.idleSeconds), cap: number(data.capSeconds), warning: number(data.warningSeconds),
      session: typeof data.session === 'string' ? data.session : '' };
  }

  if (typeof module === 'object' && module.exports) {
    module.exports = { step, warningText, capWarningText, reasonOf, pageSession, PING, CHANNEL, EVERY_MS, RETRY_MS,
      DEFAULT_IDLE_SECONDS, IDLE_TEXT, CAP_TEXT };
  }
  if (typeof document === 'undefined') return;

  const form = document.querySelector('form[action="/logout/"]');
  if (!form) return;  // not a signed-in console page
  const config = pageSession(document.body && document.body.dataset);
  const watch = { deadline: 0, idleEnd: 0, capEnd: 0, warningMs: 120000, lastPing: 0, pinging: false, checking: false,
    timer: 0, channel: null, gone: false, dialog: null, session: config.session, capClosed: 0, returnFocus: null };

  function csrf() {
    const field = form.querySelector('input[name="csrfmiddlewaretoken"]');
    return field ? field.value : '';
  }

  // every message names this tab's session
  function share(message) {
    const data = Object.assign({}, message, { session: watch.session, at: Date.now() });
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

  // the server answered this tab 401: every tab of the session is told, then this one leaves
  function ended(reason) {
    if (!watch.gone) share({ type: 'signed-out', reason });
    leave(reason);
  }

  function signOut(reason) {
    if (watch.gone) return;
    watch.gone = true;
    clearTimeout(watch.timer);
    share({ type: 'signed-out', reason });
    clearScreen();
    form.setAttribute('action', `/logout/?reason=${reason === 'expired' ? 'expired' : 'idle'}`);
    form.submit();
  }

  // whether the session's cap comes before its idle end
  function capFirst() {
    return Boolean(watch.capEnd) && watch.capEnd <= watch.idleEnd;
  }

  function warning() {
    if (watch.dialog) return watch.dialog;
    const dialog = document.createElement('dialog');
    dialog.className = 'card';
    dialog.setAttribute('aria-labelledby', 'idleTitle');
    dialog.setAttribute('aria-describedby', 'idleText');
    const title = document.createElement('h2');
    title.id = 'idleTitle';
    const text = document.createElement('p');
    text.id = 'idleText';
    const stay = document.createElement('button');
    stay.type = 'button';
    stay.id = 'idleStay';
    stay.textContent = 'Stay signed in';
    stay.addEventListener('click', () => ping(false));
    const close = document.createElement('button');
    close.type = 'button';
    close.id = 'idleClose';
    close.className = 'secondary';
    close.textContent = 'Close';
    close.addEventListener('click', () => {
      watch.capClosed = watch.capEnd;  // read: closed until the end, which no ping moves
      hide();
    });
    dialog.append(title, text, stay, close);
    document.body.append(dialog);
    watch.dialog = dialog;
    return dialog;
  }

  function show(left) {
    const dialog = warning();
    const cap = capFirst();
    dialog.querySelector('#idleTitle').textContent = cap ? capWarningText(left) : warningText(left);
    dialog.querySelector('#idleText').textContent = cap ? CAP_TEXT : IDLE_TEXT;
    dialog.querySelector('#idleStay').hidden = cap;
    dialog.querySelector('#idleClose').hidden = !cap;
    if (dialog.open) return;
    const active = document.activeElement;
    watch.returnFocus = active && active !== document.body ? active : null;
    dialog.showModal();
  }

  // the warning closes, and the focus goes back where it was
  function hide() {
    if (!watch.dialog || !watch.dialog.open) return;
    watch.dialog.close();
    const back = watch.returnFocus;
    watch.returnFocus = null;
    if (!back || back.isConnected === false || typeof back.focus !== 'function') return;
    try {
      back.focus({ preventScroll: true });
    } catch (error) {
      // gone meanwhile
    }
  }

  function schedule() {
    clearTimeout(watch.timer);
    if (watch.gone) return;
    const next = step(watch.deadline, watch.warningMs, Date.now());
    if (next.step === 'out') {
      signOut(capFirst() ? 'expired' : 'idle');
      return;
    }
    if (next.step === 'warn' && !(capFirst() && watch.capClosed === watch.capEnd)) show(next.left);
    else hide();
    if (next.in === null) return;
    watch.timer = setTimeout(schedule, next.step === 'warn' ? Math.min(1000, next.in) : Math.max(1000, next.in));
  }

  // the idle end only moves later and the cap only comes closer; the deadline is the earlier of the two
  function adopt(deadline, warningMs, tell, cap) {
    if (Number.isFinite(warningMs) && warningMs > 0) watch.warningMs = warningMs;
    let moved = false;
    if (Number.isFinite(deadline) && deadline > watch.idleEnd) {
      watch.idleEnd = deadline;
      moved = true;
    }
    if (Number.isFinite(cap) && cap > 0 && (!watch.capEnd || cap < watch.capEnd)) {
      watch.capEnd = cap;
      moved = true;
    }
    if (!moved) return;
    watch.deadline = watch.capEnd ? Math.min(watch.idleEnd, watch.capEnd) : watch.idleEnd;
    if (tell) share({ type: 'deadline', deadline: watch.idleEnd, cap: watch.capEnd, warningMs: watch.warningMs });
    schedule();
  }

  // a tab's news: acted on when it is of this tab's session; any other makes this tab ask the server, never adopt it
  function receive(message) {
    if (!message || typeof message !== 'object' || watch.gone) return;
    if (message.session !== watch.session) {
      ping(true);
      return;
    }
    if (message.type === 'deadline') adopt(Number(message.deadline), Number(message.warningMs), false, Number(message.cap));
    else if (message.type === 'signed-out') leave(message.reason);
  }

  // the answer of a ping: a tab of another session than the browser's leaves; else the server's time moves the timer
  function apply(data, tell) {
    const tag = typeof data.session === 'string' ? data.session : '';
    if (tag && watch.session && tag !== watch.session) {
      leave('expired');
      return;
    }
    const left = seconds(data.idle_seconds);
    const cap = seconds(data.cap_seconds);
    const lead = seconds(data.warning_seconds);
    const now = Date.now();
    if (left !== null) adopt(now + left * 1000, lead === null ? NaN : lead * 1000, tell, cap === null ? NaN : now + cap * 1000);
  }

  // the ping: the person's activity, or (``poll``) only the question which session this tab is in
  async function ping(poll) {
    if (watch.gone || (poll ? watch.checking : watch.pinging)) return;
    if (poll) watch.checking = true;
    else {
      watch.pinging = true;
      watch.lastPing = Date.now();
    }
    try {
      const body = new FormData();
      body.append('csrfmiddlewaretoken', csrf());
      const headers = { Accept: 'application/json' };
      if (poll) headers[POLL_HEADER] = '1';
      const response = await fetch(PING, { method: 'POST', body, credentials: 'same-origin', cache: 'no-store', headers });
      const data = await response.json().catch(() => null);
      if (response.status === 401) {
        ended(reasonOf(data));
        return;
      }
      if (!response.ok || !data) throw new Error('no answer');
      apply(data, !poll);
    } catch (error) {
      // offline, or the edge's own answer: the deadline stands, and the next input after RETRY_MS tries again
      if (!poll) watch.lastPing = Date.now() - EVERY_MS + RETRY_MS;
    } finally {
      if (poll) watch.checking = false;
      else watch.pinging = false;
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
      if (!watch.gone && !watch.pinging && Date.now() - watch.lastPing >= EVERY_MS) ping(false);
    }, { capture: true, passive: true });
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden) schedule(); });
  form.addEventListener('submit', () => {
    if (!watch.gone) share({ type: 'signed-out', reason: 'expired' });
    watch.gone = true;
  });
  const now = Date.now();  // armed at load from the page's own seconds, before any ping answers
  adopt(now + (config.idle === null ? DEFAULT_IDLE_SECONDS : config.idle) * 1000,
    config.warning === null ? NaN : config.warning * 1000, false, config.cap === null ? NaN : now + config.cap * 1000);
  ping(false);
}());
