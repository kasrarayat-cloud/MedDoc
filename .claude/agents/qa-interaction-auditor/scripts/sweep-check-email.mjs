#!/usr/bin/env node
// ============================================================================
// sweep-check-email.mjs — /check-email (preview-only tier, v3.3).
// ----------------------------------------------------------------------------
// Public route — agent walks anonymous. Post-signup confirmation page;
// not a real form (no <form> element), just informational copy + an
// envelope SVG + a single "Resend verification link" button + a back-
// to-sign-in link. Clicking Resend fires POST /api/auth/resend-
// verification — that's a real email + a tick on the verification rate
// limit. Walker confirms shape: button present (with the right label)
// + outbound link enumeration. **Never clicks Resend.**
//
// We pass `?email=...` so the resend button is enabled (component
// gates `canSend` on email being non-empty). Without it the button
// renders disabled, which is also a valid render — but the spec calls
// for asserting the button is present, so the e-mail-prefilled URL
// matches what real users land on after signup.
// ============================================================================

import { emit, launchBrowser, newAppContext, smokeLoad } from './lib/walker-base.mjs';

const URL = '/check-email?email=qa-auditor%40quillmd.test';
const NAME = 'check-email';

const browser = await launchBrowser();
try {
  const ctx = await newAppContext(browser);
  const page = await ctx.newPage();
  emit({ event: 'walker-start', name: NAME, url: URL });
  const result = await smokeLoad(page, URL);

  // Preview-only assertions. Note: this page has NO <form> element —
  // the resend control is a plain `<button type="button">` (not
  // type="submit"). Don't assert form presence; assert button presence
  // by visible label.
  const shape = await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll('button'));
    const resendBtn = buttons.find((b) =>
      /resend/i.test((b.textContent ?? '').trim())
    );
    return {
      hasForm: !!document.querySelector('form'),
      buttonCount: buttons.length,
      hasResendButton: !!resendBtn,
      resendButtonText: (resendBtn?.textContent ?? '').trim() || null,
      resendButtonType: resendBtn?.getAttribute('type') ?? null,
      resendButtonDisabled:
        (resendBtn instanceof HTMLButtonElement && resendBtn.disabled) ||
        resendBtn?.getAttribute('aria-disabled') === 'true',
      outboundLinks: Array.from(document.querySelectorAll('a[href]'))
        .map((a) => ({
          href: a.getAttribute('href'),
          text: (a.textContent ?? '').trim().slice(0, 40),
        }))
        .filter(
          (l) => l.href && (l.href.startsWith('/') || l.href.startsWith('http'))
        ),
    };
  });

  emit({
    event: 'click-skipped',
    label: shape.resendButtonText ?? 'Resend verification link',
    reason:
      'walker is read-only — Resend POSTs /api/auth/resend-verification, fires a real email + ticks the verification rate-limit bucket',
  });

  emit({
    event: 'walker-result',
    name: NAME,
    url: URL,
    ok: !result.loadErr && shape.hasResendButton,
    ...result,
    shape,
  });
  emit({ event: 'walker-end', name: NAME });
  await ctx.close();
} finally {
  await browser.close();
}
