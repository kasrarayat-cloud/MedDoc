"use strict";

// Polling reads a saved result. Only an explicit form action can change coding.
(() => {
  let panel = document.querySelector('[data-coding-panel]');
  if (!panel || !window.fetch) return;
  const encounter = panel.dataset.encounterId;
  const statusURL = new URL(panel.dataset.statusUrl, location.href);
  if (statusURL.origin !== location.origin) return;
  const baselines = new WeakMap();
  let timer, polling = false, posting = false, uncertain = false, staged = null, stopped = false;
  let epoch = 0, failures = 0;
  const value = form => JSON.stringify([...form.elements].filter(el => el.name && el.name !== 'csrfmiddlewaretoken' && !['submit', 'button'].includes(el.type) && (!['checkbox', 'radio'].includes(el.type) || el.checked)).map(el => [el.name, el.value]));
  const dirty = () => [...panel.querySelectorAll('[data-coding-form]')].filter(f => baselines.get(f) !== value(f));
  const error = message => {
    const el = panel.querySelector('[data-coding-error]');
    el.textContent = message; el.hidden = !message;
    if (message) el.focus();
  };
  const updateControls = () => {
    const edited = dirty().length > 0;
    panel.querySelectorAll('[data-coding-form] button[type="submit"]').forEach(button => {
      const approval = button.closest('[data-coding-form]').dataset.codingForm === 'approval';
      button.disabled = button.dataset.serverDisabled === 'true' || posting || uncertain || Boolean(staged) || (approval && edited);
    });
    panel.querySelectorAll('[data-coding-form] input, [data-coding-form] select, [data-coding-form] textarea').forEach(control => { control.disabled = posting || control.dataset.serverDisabled === 'true'; });
    panel.querySelectorAll('[data-coding-undo]').forEach(button => { button.hidden = !dirty().includes(button.closest('form')); });
    panel.querySelector('[data-coding-dirty]').hidden = !edited;
    panel.querySelector('[data-coding-update]').hidden = !staged && !uncertain;
    panel.querySelectorAll('[data-export-with-codes]').forEach(link => {
      link.setAttribute('aria-disabled', String(edited || posting || uncertain || Boolean(staged)));
    });
  };
  const bind = () => {
    panel.querySelectorAll('[data-coding-form]').forEach(form => {
      baselines.set(form, value(form));
      form.querySelectorAll('input, select, textarea').forEach(control => { control.dataset.serverDisabled = String(control.disabled); });
      form.querySelectorAll('button[type="submit"]').forEach(button => { button.dataset.serverDisabled = String(button.disabled); });
      if (['context', 'selections', 'output-decision'].includes(form.dataset.codingForm)) {
        const reset = document.createElement('button');
        reset.type = 'button'; reset.className = 'quiet'; reset.dataset.codingUndo = 'true'; reset.textContent = 'Undo unsaved changes';
        reset.addEventListener('click', () => { form.reset(); error(''); basis(); updateControls(); });
        form.append(reset);
      }
    });
    basis(); updateControls();
  };
  const basis = () => {
    const selected = panel.querySelector('[data-coding-basis]')?.value;
    const time = panel.querySelector('[data-coding-time]'), mdm = panel.querySelector('[data-coding-mdm]');
    if (time) time.hidden = selected !== 'time';
    if (mdm) mdm.hidden = selected !== 'mdm';
  };
  const apply = data => {
    if (data.encounter_id !== encounter || typeof data.html !== 'string' || typeof data.version !== 'string') throw new Error('Invalid coding response');
    const fragment = document.createElement('template'); fragment.innerHTML = data.html;
    const next = fragment.content.querySelector('[data-coding-panel]');
    if (!next || next.dataset.encounterId !== encounter || fragment.content.querySelector('script') || next.dataset.version !== data.version) throw new Error('Invalid coding panel');
    const focusID = panel.contains(document.activeElement) ? document.activeElement.id : '';
    panel.replaceWith(next); panel = next; staged = null; uncertain = false;
    bind();
    if (focusID) document.getElementById(focusID)?.focus({preventScroll:true});
  };
  const fetchJSON = async (url, options = {}) => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(url, {...options, headers:{Accept:'application/json', ...options.headers},
        credentials:'same-origin', cache:'no-store', redirect:'error', signal:controller.signal});
      if (![200, 409].includes(response.status)) throw new Error('Coding request did not complete');
      const data = await response.json();
      if (data.encounter_id !== encounter) throw new Error('Coding response does not match');
      return {response, data};
    } finally { clearTimeout(timeout); }
  };
  const schedule = () => {
    clearTimeout(timer);
    if (!stopped) timer = setTimeout(poll, failures ? Math.min(30000, 4000 * failures) : panel.dataset.pending === 'true' ? 2000 : 8000);
  };
  async function poll() {
    if (posting || polling || document.hidden || stopped) { schedule(); return; }
    polling = true;
    const ticket = epoch;
    try {
      const {data} = await fetchJSON(statusURL);
      if (ticket !== epoch || posting) return;
      failures = 0;
      panel.querySelector('[data-coding-connection]').hidden = true;
      if (data.version !== panel.dataset.version || uncertain) {
        if (dirty().length || uncertain) { staged = data; updateControls(); }
        else apply(data);
      }
    } catch (_) {
      if (ticket === epoch) {
        failures++;
        const connection = panel.querySelector('[data-coding-connection]');
        connection.textContent = 'Status connection interrupted. Your unsaved edits are kept; checking again shortly.';
        connection.hidden = false;
      }
    } finally { polling = false; schedule(); }
  }
  document.addEventListener('input', event => {
    if (panel.contains(event.target)) updateControls();
  });
  document.addEventListener('change', event => {
    if (panel.contains(event.target)) { basis(); updateControls(); }
  });
  document.addEventListener('click', event => {
    const download = event.target.closest('[data-export-with-codes]');
    if (download && panel.contains(download) && download.getAttribute('aria-disabled') === 'true') {
      event.preventDefault(); error('Save or undo your unsaved coding changes before exporting saved selections.'); return;
    }
    if (event.target.closest('[data-coding-load]') && panel.contains(event.target)) {
      if (staged) { apply(staged); error(''); }
      else { uncertain = false; updateControls(); poll(); }
    }
  });
  document.addEventListener('submit', async event => {
    const form = event.target;
    if (!panel.contains(form) || !form.matches('[data-coding-form]')) return;
    event.preventDefault();
    if (posting || uncertain || staged) return;
    if (dirty().some(other => other !== form)) {
      error('Save or undo the unsaved changes in the other form before using this action.'); return;
    }
    if (form.dataset.codingForm === 'approval' && dirty().length) {
      error('Save your code selections before approving the complete coding record.'); return;
    }
    const url = new URL(form.action, location.href);
    if (url.origin !== location.origin) return;
    const body = new FormData(form);
    // FormData(form) omits the clicked action. Preserve the explicit choice;
    // an absent submitter must never silently default to clinical acceptance.
    const submitter = event.submitter;
    if (submitter && submitter.form === form && submitter.name && !submitter.disabled) body.append(submitter.name, submitter.value);
    if (form.dataset.codingForm === 'output-decision' && !['accepted', 'rejected'].includes(body.get('outcome'))) {
      error('Choose Accept or Reject to record your decision.'); return;
    }
    posting = true; epoch++; clearTimeout(timer); error(''); updateControls();
    try {
      const {response, data} = await fetchJSON(url, {method:'POST', body});
      if (response.status === 409) {
        if (data.version !== panel.dataset.version) staged = data;
        error(data.error || 'This coding review changed. Review the saved result before continuing.');
      } else { apply(data); }
    } catch (_) {
      uncertain = true;
      error('The save response was interrupted. No action will be resent. Check the saved result before continuing; your local edits are kept.');
    } finally { posting = false; updateControls(); schedule(); }
  });
  window.addEventListener('beforeunload', event => {
    if (dirty().length || posting) { event.preventDefault(); event.returnValue = ''; }
  });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });
  window.addEventListener('pagehide', () => { stopped = true; clearTimeout(timer); });
  window.addEventListener('pageshow', event => { if (event.persisted) { stopped = false; schedule(); } });
  bind(); schedule();
})();
