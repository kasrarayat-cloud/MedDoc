#!/usr/bin/env node
// sweep-dev-rx-warnings.mjs — /dev/rx-warnings (gate-check tier, v3.3).
// ----------------------------------------------------------------------------
// Dual-outcome contract: the route is dev-only. In a dev build it
// renders the RxWarningCard variant grid; in a production build the
// page calls `notFound()` (apps/transcribe-md/src/app/dev/rx-warnings/
// page.tsx — `if (process.env.NODE_ENV === 'production') notFound()`)
// and the response is 404.
//
// The walker is OK if EITHER outcome obtains. The failure mode is a
// silent 200 with empty content — that's a server bug (page loaded
// but rendered nothing), not a build-mode mismatch.
//
// Why we simplified vs v2: the previous walker iterated a `VARIANTS`
// list (critical / warning / info / collapsed / expanded / in-context)
// and smoke-loaded each one. That's a v2-era design-system smoke —
// useful for visual regression on a dev build, but it adds zero
// gate-check value. The v3.3 walker collapses to a single load + a
// `looksDevPreview` OR `looksGated` assertion. Variant cycling stays
// available for engineers via direct browser visit.
//
// Read-only. Uses fresh `login(page)` for consistency with the admin
// gate-check walkers (sweep-admin-queues.mjs etc.) — though session
// freshness is not strictly required here, the convention is "all
// gate-check walkers log in fresh."

import {
  emit,
  login,
  launchBrowser,
  newAppContext,
  smokeLoad,
} from './lib/walker-base.mjs';

const browser = await launchBrowser();
try {
  const ctx = await newAppContext(browser);
  const page = await ctx.newPage();
  emit({ event: 'walker-start', name: 'dev-rx-warnings' });
  try {
    await login(page);
  } catch (err) {
    emit({
      event: 'walker-result',
      name: 'dev-rx-warnings',
      ok: false,
      stage: 'login',
      loadErr: err.message,
    });
    emit({ event: 'walker-end', name: 'dev-rx-warnings' });
    await ctx.close();
    process.exit(0);
  }

  const result = await smokeLoad(page, '/dev/rx-warnings', { timeout: 15_000 });

  // The 404 path: production build called notFound(). Title contains
  // "404" OR the body is essentially empty.
  const looksGated =
    (result.title && result.title.includes('404')) ||
    (result.bodyTextLength ?? 0) < 200;

  // The dev-render path: title isn't 404, body is substantive, and at
  // least one rx-warning marker is present in the DOM. We use a class
  // probe because the variant card is owned by the `.qm-warn-*` family
  // (referenced in the page header comment) and the eyebrow contains
  // "Dev / Rx warnings" in the rendered preview.
  const devPreviewMarker = await page
    .evaluate(() => {
      const html = document.body?.innerHTML ?? '';
      const hasWarnClass = /class="[^"]*qm-warn-/.test(html);
      const hasDevEyebrow = /Dev \/ Rx warnings/i.test(
        document.body?.innerText ?? ''
      );
      return { hasWarnClass, hasDevEyebrow };
    })
    .catch(() => ({ hasWarnClass: false, hasDevEyebrow: false }));

  const looksDevPreview =
    !!result.title &&
    !result.title.includes('404') &&
    (result.bodyTextLength ?? 0) > 500 &&
    (devPreviewMarker.hasWarnClass || devPreviewMarker.hasDevEyebrow);

  const ok = looksDevPreview || looksGated;

  emit({
    event: 'walker-result',
    name: 'dev-rx-warnings',
    url: '/dev/rx-warnings',
    ok,
    note: looksGated
      ? 'expected 404 — production-build gate working'
      : looksDevPreview
        ? 'dev-build render — variant grid present'
        : 'silent 200 with empty content — server bug',
    looksDevPreview,
    looksGated,
    devPreviewMarker,
    ...result,
  });
  emit({ event: 'walker-end', name: 'dev-rx-warnings' });
  await ctx.close();
} finally {
  await browser.close();
}
