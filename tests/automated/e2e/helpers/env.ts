// Shared helpers for the automated E2E suite. Kept in a thin module so
// specs don't duplicate credential-reading boilerplate.

export function requireTestCreds(label: 'app' | 'pro'): {
  email: string;
  password: string;
} | null {
  const prefix = label === 'app' ? 'TEST_APP' : 'TEST_PRO';
  const email = process.env[`${prefix}_EMAIL`];
  const password = process.env[`${prefix}_PASSWORD`];
  if (!email || !password) return null;
  return { email, password };
}

export const E2E_READ_ONLY = (process.env.E2E_READ_ONLY ?? 'true') === 'true';

export const APP_URL =
  process.env.TEST_APP_URL ?? 'https://app.quillmd.com';

export const PROCESSING_TIMEOUT_MS = Number(
  process.env.E2E_PROCESSING_TIMEOUT_MS ?? 120_000
);
