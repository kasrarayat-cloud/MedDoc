import type { Page } from '@playwright/test';

// Log into app.quillmd.com via the credentials form. Returns after the
// router has landed on /dashboard so the caller doesn't have to race
// the redirect.
export async function loginApp(
  page: Page,
  email: string,
  password: string
): Promise<void> {
  await page.goto('/login');
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL(/\/dashboard/, { timeout: 15_000 });
}

export async function logoutApp(page: Page): Promise<void> {
  // User menu in the TopNav → Sign out. If the menu markup changes,
  // update this selector — the smoke suite's auth-flow.sh is the
  // HTTP-level fallback.
  const menu = page.getByRole('button', { name: /account menu|user menu/i });
  if (await menu.isVisible().catch(() => false)) {
    await menu.click();
    await page.getByRole('menuitem', { name: /sign out/i }).click();
    await page.waitForURL(/\/login/, { timeout: 10_000 });
  } else {
    // Fallback: hit the signout endpoint directly with the session cookie.
    await page.request.post('/api/auth/signout');
    await page.goto('/login');
  }
}
