// ============================================================================
// Auth helpers — login / logout + in-test TOTP (Phase 2 Batch 2).
// ============================================================================

import { createHmac } from 'node:crypto';

import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';

import { TEST_PASSWORD } from './test-utils';

import { expectAtHome } from './home';

/** Log in through the /login form and assert we reach /dashboard. For an
 *  MFA-enabled account, pass `totp` — the form re-renders with the 6-digit
 *  field after the first submit and we complete the second factor. */
export async function loginUser(
  page: Page,
  email: string,
  password: string = TEST_PASSWORD,
  opts: { totp?: string } = {},
): Promise<void> {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: /^sign in$/i }).click();

  if (opts.totp) {
    const totpField = page.locator('#totpToken');
    await expect(totpField).toBeVisible({ timeout: 10_000 });
    // Password is uncontrolled, but re-fill defensively so the second submit
    // always carries it alongside the second factor.
    await page.getByLabel('Password', { exact: true }).fill(password);
    await totpField.fill(opts.totp);
    await page.getByRole('button', { name: /^sign in$/i }).click();
  }

  await expectAtHome(page);
}

/** Sign out via the user menu; returns only once the session cookie is actually
 *  cleared, so callers get a genuinely logged-out context.
 *
 *  The NextAuth sign-out Set-Cookie clears the session a beat AFTER the menu's
 *  client-side redirect to /login. We wait on the browser COOKIE state rather
 *  than re-navigating to a protected route to probe it: a navigation carrying
 *  the not-yet-cleared cookie re-validates the (still-present) session and rolls
 *  a fresh cookie, so a tight goto-retry loop can re-mint faster than the clear
 *  settles and never converges. Polling cookies touches nothing server-side. */
export async function logoutViaMenu(page: Page): Promise<void> {
  // ⚠️ THESE TWO SELECTORS WERE UNCHANGED ON 2026-08-04 AND THAT IS THE POINT.
  //
  // Between the Rounds flip (2026-08-02) and 2026-08-04 this helper could not
  // pass against a flag-ON build: the Rounds bar rendered the clinician's name
  // as a plain <span>, so there was no account menu and no sign-out anywhere
  // outside Settings. It sat inside the 21 failures the default pack shows
  // flag-ON, and a test that has been red long enough stops being read.
  //
  // The ruling was to restore the affordance, NOT to re-point the selector at
  // whatever happened to exist. `components/rounds/account-menu.tsx` was
  // therefore built to satisfy exactly these two queries — a real <button>
  // labelled "Account menu for <name>" (not a <summary>, whose role=button
  // mapping is an implicit-AAM bet) opening role=menu with role=menuitem
  // children. `gate-rounds-account-menu` pins both, so this helper is a
  // legitimate consumer of the product rather than a thing patched around it.
  //
  // If this line ever needs editing again, ask first whether the product lost
  // a control.
  await page.getByRole('button', { name: /account menu/i }).click();
  await page.getByRole('menuitem', { name: /sign out/i }).click();
  await expect(page).toHaveURL(/\/login$/, { timeout: 15_000 });
  await expect
    .poll(
      async () =>
        (await page.context().cookies()).some((c) =>
          /session-token/i.test(c.name),
        ),
      { timeout: 10_000 },
    )
    .toBe(false);
}

// --- TOTP (RFC 6238) -------------------------------------------------------
// The app verifies with otplib defaults: SHA-1, 6 digits, 30s step, base32
// secret, ±1 step tolerance. We compute the CURRENT step's code; the server's
// tolerance absorbs the sub-second skew between generate and verify.

function base32Decode(input: string): Buffer {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const ch of input.toUpperCase().replace(/=+$/, '')) {
    const idx = alphabet.indexOf(ch);
    if (idx === -1) continue;
    bits += idx.toString(2).padStart(5, '0');
  }
  const bytes: number[] = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) {
    bytes.push(parseInt(bits.slice(i, i + 8), 2));
  }
  return Buffer.from(bytes);
}

/** Generate the current 6-digit TOTP for a base32 secret. */
export function generateTotp(secret: string): string {
  const step = Math.floor(Date.now() / 1000 / 30);
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(step));
  const hmac = createHmac('sha1', base32Decode(secret)).update(counter).digest();
  const offset = hmac[hmac.length - 1] & 0x0f;
  const bin =
    ((hmac[offset] & 0x7f) << 24) |
    ((hmac[offset + 1] & 0xff) << 16) |
    ((hmac[offset + 2] & 0xff) << 8) |
    (hmac[offset + 3] & 0xff);
  return (bin % 1_000_000).toString().padStart(6, '0');
}

/** Extract the base32 secret from an otpauth:// enrollment URI. */
export function totpSecretFromUri(uri: string): string {
  const m = uri.match(/[?&]secret=([^&]+)/i);
  if (!m) throw new Error(`[totpSecretFromUri] no secret in URI: ${uri}`);
  return decodeURIComponent(m[1]);
}
