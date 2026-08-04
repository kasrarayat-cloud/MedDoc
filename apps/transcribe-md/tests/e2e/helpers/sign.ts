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
/**
 * Open the sign flow and get to the modal, on WHICHEVER SKIN IS BUILT.
 *
 * ⚠️ THIS EXISTS BECAUSE FIVE SPECS EACH HAND-ROLLED THE SIGN WALK, AND ALL
 * FIVE BROKE THE SAME WAY WHEN THE SKIN SHIPPED.
 *
 * Flag-OFF the opener is one button labelled "Sign & Send". Under Rounds there
 * is no such button: the stage rail carries `rounds-review-sign` ("Review &
 * sign"), which opens the gate flow, and the modal's trigger is the gate
 * signbar's "Sign & Download" (`review-sign-bar.tsx:118`). Two different walks
 * to the same modal.
 *
 * F-ret.1 found five specs (#1, #9, #12, #13, #14) failing on
 * `getByRole('button', { name: /sign & send/i })`. Fixing them five times over
 * would rebuild exactly the hand-kept list AGENTS.md records as "wrong
 * eventually" — so the walk lives here, once.
 *
 * ⚠️ DELIBERATELY BRANCHES ON THE DOM, NOT ON A FLAG. `NEXT_PUBLIC_SKIN_ROUNDS`
 * is inlined at docker-build time and is NOT in the Playwright runner's
 * environment, so a test-side `isSkinRounds()` reads `undefined` and would
 * confidently walk the wrong path on the flag-ON image. Same reasoning as
 * `helpers/home.ts`, and the same trap.
 *
 * ⚠️ AND IT MUST NOT USE `getByRole('dialog')`. Under Rounds the gate flow
 * carries `role="dialog"` (`gate-flow.tsx:228`) AND so does the Radix modal —
 * two open at once, so the role query goes strict-mode ambiguous and an
 * "is the dialog gone?" assertion can resolve against the wrong node. Callers
 * should assert on `review-doc-signbar` / `rounds-gate-attest` instead.
 */
export async function openSignFlow(page: Page): Promise<void> {
  const roundsRail = page.getByTestId('rounds-review-sign');

  if (await roundsRail.count()) {
    // ── Rounds: rail → gate flow → the signbar's trigger ──────────────────
    await expect(
      roundsRail.first(),
      'the Rounds review-and-sign rail button is present but never enabled',
    ).toBeEnabled({ timeout: 10_000 });
    await roundsRail.first().click();

    // The gate flow is the thing that collects the attestation. Assert we
    // actually reached it, or a later "the modal did not open" is reported
    // miles from its cause.
    const attest = page.getByTestId('rounds-gate-attest');
    await expect(
      attest.first(),
      'clicked Review & sign but the gate flow never presented the attestation',
    ).toBeVisible({ timeout: 10_000 });
    await attest.first().click();

    const bar = page.getByTestId('review-doc-signbar');
    await expect(
      bar.first(),
      'the gate signbar never appeared — the gates are still blocking',
    ).toBeVisible({ timeout: 10_000 });
    await bar.first().getByRole('button', { name: /sign & download/i }).click();
    return;
  }

  // ── Legacy: one button, straight to the modal ────────────────────────────
  const legacy = page.getByRole('button', { name: /sign & send/i });
  await expect(
    legacy.first(),
    'neither the Rounds rail (rounds-review-sign) nor the legacy "Sign & Send" ' +
      'button is present — this is not a signable visit surface',
  ).toBeVisible({ timeout: 10_000 });
  await legacy.first().click();
}

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
