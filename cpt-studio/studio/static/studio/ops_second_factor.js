'use strict';
// The console's security-key ceremonies (release 1, B2), loaded by the second-factor, setup and keys pages: no inline
// script (script-src 'self'). A form marked data-ceremony="get" (the sign-in's second step, the step-up) or "create" (setup,
// a new key) asks its data-options address for the options - a POST carrying the form's own CSRF field (and
// action=options) - runs navigator.credentials with base64url converted to bytes and back, puts the answer as JSON in the
// form's "credential" field and submits the form. The server checks the challenge, the relying party, the origin, the
// key and its counter; this script only carries bytes.
(function secondFactor() {
  function toBytes(text) {
    const padded = String(text).replace(/-/g, '+').replace(/_/g, '/');
    const binary = atob(padded + '='.repeat((4 - (padded.length % 4)) % 4));
    return Uint8Array.from(binary, character => character.charCodeAt(0));
  }

  function toText(buffer) {
    let binary = '';
    for (const byte of new Uint8Array(buffer)) binary += String.fromCharCode(byte);
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  // the options as navigator.credentials.get takes them
  function requestOptions(json) {
    return Object.assign({}, json, {
      challenge: toBytes(json.challenge),
      allowCredentials: (json.allowCredentials || []).map(item => Object.assign({}, item, { id: toBytes(item.id) })),
    });
  }

  // the options as navigator.credentials.create takes them
  function creationOptions(json) {
    return Object.assign({}, json, {
      challenge: toBytes(json.challenge),
      user: Object.assign({}, json.user, { id: toBytes(json.user.id) }),
      excludeCredentials: (json.excludeCredentials || []).map(item => Object.assign({}, item, { id: toBytes(item.id) })),
    });
  }

  // the answer as the server reads it (py_webauthn's JSON: base64url for every byte string)
  function answer(credential) {
    const response = credential.response;
    const out = { id: credential.id, rawId: toText(credential.rawId), type: credential.type,
      authenticatorAttachment: credential.authenticatorAttachment || null, response: { clientDataJSON: toText(response.clientDataJSON) } };
    if (response.attestationObject) {
      out.response.attestationObject = toText(response.attestationObject);
      out.response.transports = typeof response.getTransports === 'function' ? response.getTransports() : [];
    } else {
      out.response.authenticatorData = toText(response.authenticatorData);
      out.response.signature = toText(response.signature);
      out.response.userHandle = response.userHandle ? toText(response.userHandle) : null;
    }
    return out;
  }

  const SENTENCES = {
    NotAllowedError: 'The key was not used, or the request timed out. Try again.',
    InvalidStateError: 'This key is already set up for this account. Use another key.',
    SecurityError: 'This browser refused the request for this site. Open the console at its own address and try again.',
  };

  if (typeof module === 'object' && module.exports) module.exports = { toBytes, toText, requestOptions, creationOptions, answer, SENTENCES };
  if (typeof document === 'undefined') return;

  function status(form, message) {
    const element = form.parentElement.querySelector('[data-status]');
    if (element) element.textContent = message;
  }

  async function run(form) {
    const button = form.querySelector('button[type="submit"]');
    if (!window.PublicKeyCredential || !navigator.credentials) {
      status(form, 'This browser cannot use a security key. Use a current browser, or a recovery code.');
      return;
    }
    if (button) button.disabled = true;
    try {
      status(form, 'Asking for the options…');
      const body = new FormData();
      const field = form.querySelector('input[name="csrfmiddlewaretoken"]');
      body.append('csrfmiddlewaretoken', field ? field.value : '');
      body.append('action', 'options');
      const reply = await fetch(form.dataset.options, { method: 'POST', body, credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } });
      const options = await reply.json().catch(() => null);
      if (reply.status === 403 && options && options.error === 'step_up' && options.location) {
        window.location.assign(options.location);
        return;
      }
      if (!reply.ok || !options) {
        status(form, (options && options.error) || 'The options could not be read. Reload the page and try again.');
        return;
      }
      status(form, 'Touch your security key, or confirm on this device.');
      const credential = form.dataset.ceremony === 'create'
        ? await navigator.credentials.create({ publicKey: creationOptions(options) })
        : await navigator.credentials.get({ publicKey: requestOptions(options) });
      form.querySelector('input[name="credential"]').value = JSON.stringify(answer(credential));
      form.dataset.ready = '1';
      status(form, 'Checking…');
      form.submit();
    } catch (error) {
      status(form, SENTENCES[error && error.name] || 'The key could not be used. Try again.');
    } finally {
      if (button && form.dataset.ready !== '1') button.disabled = false;
    }
  }

  document.addEventListener('submit', event => {
    const form = event.target && event.target.closest ? event.target.closest('form[data-ceremony]') : null;
    if (!form || form.dataset.ready === '1') return;
    event.preventDefault();
    run(form);
  });
}());
