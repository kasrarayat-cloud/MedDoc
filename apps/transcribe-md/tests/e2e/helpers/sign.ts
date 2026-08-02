// ============================================================================
// Signing, from a test — and the attestation that is now part of it.
// ----------------------------------------------------------------------------
// ⚠️ `POST /sign` REQUIRES AN ATTESTATION SINCE 2026-08-02. It was a UI-only
// gate; a second sign control shipped that did not count it, and with nothing on
// the server counting it either a signature could pass the gate with no refusal
// and no audit row. `sign-gates.ts` now marks it `serverEnforced: true` and the
// route answers 400 ATTESTATION_REQUIRED without it.
//
// That made every SIGNING TEST a caller that had to be updated, which is the
// half of the traversal a source-only grep misses: the product has exactly one
// `fetch` site (the modal), and the specs have ten more. They were found by CI,
// not by me — the default `chromium` pack is the FLAG-OFF build, where nothing
// upstream has attested, so the modal collects it and no spec was ticking it.
// Every Rounds pack passed locally because Gate 3 attests for them.
//
// These helpers exist so the requirement is STRUCTURAL rather than remembered:
// a new signing test that uses them cannot forget, and one that hand-rolls the
// click will fail loudly against the real route.
// ============================================================================

import { expect, type Page } from '@playwright/test';

/**
 * Tick the modal's attestation if it is asking for one, then submit.
 *
 * The toggle renders ONLY when nobody upstream has attested (i.e. off Rounds,
 * or any surface without a Gate 3). Under Rounds the gate flow has already
 * collected it and forwards it, so there is nothing to tick — which is why this
 * is conditional rather than an unconditional click that would fail there.
 */
export async function attestAndSubmit(page: Page): Promise<void> {
  const toggle = page.getByTestId('sign-attestation-toggle');
  if (await toggle.count()) {
    await toggle.first().click();
    await expect(
      toggle.first(),
      'the attestation toggle did not take — the sign will be refused',
    ).toHaveAttribute('aria-pressed', 'true');
  }
  const submit = page.getByRole('button', { name: /sign & deliver/i }).first();

  // ⚠️ WAIT FOR ENABLED BEFORE SUBMITTING, AND ASSERT IT.
  // `dispatchEvent` is synchronous and does NOT wait for actionability — that
  // is why it is used here (the submit sits under an overlay in some layouts,
  // where a real click waits on "element is not enabled" forever). The cost is
  // that it will happily fire at a button React has not re-enabled yet: the
  // toggle's state update had not flushed, the button was still disabled, the
  // dispatch did nothing, and the failure surfaced far away as "the dialog did
  // not close". Waiting here turns that into a statement about the button.
  await expect(
    submit,
    'the sign submit never became enabled — the attestation (or the E/M ' +
      'confirm) is still outstanding in the modal',
  ).toBeEnabled({ timeout: 10_000 });

  // ⚠️ A REAL CLICK FIRST — `dispatchEvent` IS THE FALLBACK, NOT THE DEFAULT.
  // The first version of this helper dispatched unconditionally, because that
  // is what the Rounds gate-flow specs do (their submit sits under an overlay,
  // where a real click waits on "element is not enabled" forever). Imposing it
  // on the legacy modal — whose specs were using a plain `.click()` and
  // working — meant the handler never ran: no request, no audit row, no server
  // warn, and a failure that surfaced 10s later as "waiting for event
  // download". A dispatched click that goes nowhere looks exactly like a
  // button that does nothing.
  // So: click properly where clicking works, and fall back only where the
  // overlay actually blocks it.
  try {
    await submit.click({ timeout: 5_000 });
  } catch {
    await submit.dispatchEvent('click');
  }
}

/**
 * The API-level equivalent, for specs that drive `POST /sign` directly to reach
 * SIGNED without walking the UI. Attests by default; pass `attest: false` to
 * prove the refusal.
 */
export async function signViaApi(
  page: Page,
  visitId: string,
  opts: { destinations?: unknown[]; attest?: boolean } = {},
) {
  const attest = opts.attest ?? true;
  return page.request.post(`/api/visits/${visitId}/sign`, {
    data: {
      destinations: opts.destinations ?? [],
      ...(attest ? { attestation: { acknowledged: true } } : {}),
    },
    headers: { 'Content-Type': 'application/json' },
  });
}
