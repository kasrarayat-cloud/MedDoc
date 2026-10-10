(() => {
  'use strict';
  const root = document.querySelector('[data-definition-preparation]');
  if (!root) return;
  const running = new Set(['queued', 'inventory', 'proposer', 'checker']);
  const label = root.querySelector('[data-definition-status]');
  const progress = root.querySelector('[data-definition-progress]');
  let busy = false;
  let completed = !running.has(root.dataset.state);
  const labels = {queued: 'Waiting for the preparation worker', inventory: 'Checking the complete blank original',
    proposer: 'AI proposer is defining answer meanings', checker: 'Independent AI checker is checking definitions'};
  const poll = async () => {
    if (completed || busy || document.hidden) return;
    busy = true;
    try {
      const response = await fetch(root.dataset.statusUrl, {credentials: 'same-origin', redirect: 'error', cache: 'no-store'});
      if (!response.ok) throw new Error('status unavailable');
      const result = await response.json();
      if (running.has(result.state)) {
        label.textContent = labels[result.state];
      } else {
        completed = true;
        // Pending preparation has no editable form; retain any unexpected dirty page.
        if (root.querySelector('[data-definition-corrections]')) {
          label.textContent = 'Preparation finished. Your edits are retained; reopen the page after saving.';
        } else window.location.reload();
      }
    } catch (_) {
      progress.textContent = 'Connection interrupted. Checking resumes automatically; the retained request is not repeated.';
    } finally { busy = false; }
  };
  if (!completed) {
    window.setInterval(poll, 2000);
    window.addEventListener('online', poll);
    document.addEventListener('visibilitychange', poll);
    poll();
  }
  // Avoid approving old retained values while a clinician has unsaved corrections.
  const corrections = root.querySelector('[data-definition-corrections]');
  const approval = root.querySelector('[data-definition-approval]');
  if (corrections && approval) {
    const baseline = new URLSearchParams(new FormData(corrections)).toString();
    const changed = () => new URLSearchParams(new FormData(corrections)).toString() !== baseline;
    approval.addEventListener('submit', event => {
      if (changed()) {
        event.preventDefault(); event.stopImmediatePropagation();
        progress.textContent = 'Save your edited definitions before approving the new version.';
        corrections.scrollIntoView({block: 'start'});
      }
    }, true);
  }
})();
