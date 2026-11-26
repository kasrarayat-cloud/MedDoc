'use strict';
// The pages outside the app - the sign-in page and the account page (its "Sign out everywhere", and the page a forced
// password change lands on) - tell this browser's app tabs that they were reached (integrated refutation round 1,
// session-0). Each message goes on the channel the app's tabs share (app.js SESSION_CHANNEL: a BroadcastChannel, else
// the localStorage key, written exactly as app.js shareSession writes it) and names this page's session (its
// data-session, studio.sessions.session_tag; '' on the sign-in page):
// - at load, {type: 'page'}: an app tab of another session asks the server which session it is in (app.js
//   receiveSession -> checkSession, marked a poll: no one's activity), and a 401 or another session there is an end,
//   which wipes what the tab keeps in page memory (R2-18) - after a sign-out everywhere, or another member's sign-in;
//   a tab of this page's own session hears nothing it acts on;
// - when the "Sign out everywhere" form is sent, {type: 'signed-out', reason: 'expired'}, on which the tabs of this
//   session leave at once, as on the app's own sign-out.
// It reads the page's session tag and the form, keeps nothing, and is loaded with defer (the site's policy:
// script-src 'self').
(() => {
  const CHANNEL = 'cpt-studio-session';  // app.js SESSION_CHANNEL
  const body = document.body;
  const session = body && body.dataset && typeof body.dataset.session === 'string' ? body.dataset.session : '';
  let channel = null;
  try {
    channel = typeof BroadcastChannel === 'function' ? new BroadcastChannel(CHANNEL) : null;
  } catch {
    channel = null;
  }
  const tell = message => {
    const data = Object.assign({}, message, { session, at: Date.now() });
    try {
      if (channel) {
        channel.postMessage(data);
        return;
      }
    } catch {
      // fall through to the storage events
    }
    try {
      localStorage.setItem(CHANNEL, JSON.stringify(data));
    } catch {
      // no storage here: an app tab hears of the end at its next request
    }
  };
  tell({ type: 'page' });
  const everywhere = document.getElementById('everywhereForm');
  if (everywhere) everywhere.addEventListener('submit', () => tell({ type: 'signed-out', reason: 'expired' }));
})();
