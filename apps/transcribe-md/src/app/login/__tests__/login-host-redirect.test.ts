// ============================================================================
// ADMIN-2 — the signed-in /login redirect reads the Host header ONLY.
// ----------------------------------------------------------------------------
// It used to read `x-forwarded-host ?? host`. On this ingress nginx never sets
// X-Forwarded-Host and the trusted Caddy hop keeps a client-sent one, so a
// client could choose the branch. For an honest request the two are equal —
// these arms pin both halves: the forged header no longer steers, and the real
// admin host still does.
// ============================================================================
import { beforeEach, describe, expect, it, vi } from 'vitest';

const authFn = vi.fn();
const headerBag = new Map<string, string>();
const redirectFn = vi.fn((to: string) => {
  throw new Error(`REDIRECT:${to}`);
});

vi.mock('@/lib/nextauth', () => ({ auth: () => authFn() }));
vi.mock('next/headers', () => ({ headers: async () => headerBag }));
vi.mock('next/navigation', () => ({ redirect: (to: string) => redirectFn(to) }));
vi.mock('@/lib/recovery-href', () => ({ recoveryHref: () => '/board' }));
vi.mock('@/components/ui/auth-shell', () => ({ AuthShell: () => null }));
vi.mock('../login-form', () => ({ LoginForm: () => null }));
vi.mock('../verify-toast', () => ({ VerifyToast: () => null }));
vi.mock('@meddoc/db', () => ({ __esModule: true, default: {} }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

async function landing(): Promise<string> {
  const { default: LoginPage } = await import('../page');
  try {
    await LoginPage();
  } catch (e) {
    const m = String((e as Error).message).match(/^REDIRECT:(.*)$/);
    if (m) return m[1]!;
    throw e;
  }
  throw new Error('LoginPage did not redirect a signed-in user');
}

beforeEach(() => {
  vi.clearAllMocks();
  headerBag.clear();
  authFn.mockResolvedValue({ user: { id: 'usr_1' } });
});

describe('/login — signed-in redirect is steered by Host only', () => {
  it('⚠️ a forged X-Forwarded-Host: admin.* on the app host does NOT send the user to /admin', async () => {
    headerBag.set('host', 'app.quillmd.com');
    headerBag.set('x-forwarded-host', 'admin.quillmd.com');
    expect(await landing()).toBe('/board');
  });

  it('control: the real admin host still lands on /admin', async () => {
    headerBag.set('host', 'admin.quillmd.com');
    expect(await landing()).toBe('/admin');
  });

  it('control: the app host lands on the clinician home', async () => {
    headerBag.set('host', 'app.quillmd.com:443');
    expect(await landing()).toBe('/board');
  });
});
