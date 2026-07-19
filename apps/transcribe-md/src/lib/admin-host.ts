const PRODUCTION_ADMIN_HOST = 'admin.quillmd.com';

type HostEnvironment = Partial<
  Pick<NodeJS.ProcessEnv, 'ADMIN_PUBLIC_HOST' | 'NODE_ENV'>
>;

function normalizeHost(value: string | null | undefined): string | null {
  const raw = value?.trim().toLowerCase().replace(/\.$/u, '');
  if (!raw || raw.includes('/') || raw.includes('\\') || raw.includes('@')) {
    return null;
  }

  if (raw.startsWith('[')) {
    const closingBracket = raw.indexOf(']');
    if (closingBracket < 0) return null;
    const suffix = raw.slice(closingBracket + 1);
    if (suffix && !/^:\d+$/u.test(suffix)) return null;
    return raw.slice(0, closingBracket + 1);
  }

  const colon = raw.lastIndexOf(':');
  if (colon >= 0) {
    const port = raw.slice(colon + 1);
    if (!/^\d+$/u.test(port)) return null;
    return raw.slice(0, colon);
  }
  return raw;
}

export function configuredAdminHost(
  environment: HostEnvironment = process.env,
): string | null {
  const configured = normalizeHost(environment.ADMIN_PUBLIC_HOST);
  if (environment.ADMIN_PUBLIC_HOST !== undefined) return configured;
  return environment.NODE_ENV === 'production' ? PRODUCTION_ADMIN_HOST : null;
}

/**
 * Administrative routes are served by the same Next.js process as the
 * physician application. The edge proxy is the first host boundary; this is
 * the application-layer boundary for direct-container and proxy-misroute
 * defense. Development/test environments opt in by setting ADMIN_PUBLIC_HOST.
 */
export function isAdminRequestHost(
  headers: Pick<Headers, 'get'>,
  environment: HostEnvironment = process.env,
): boolean {
  const expected = configuredAdminHost(environment);
  if (environment.ADMIN_PUBLIC_HOST !== undefined && !expected) return false;
  if (!expected) return environment.NODE_ENV !== 'production';

  // Caddy overwrites Host with the accepted virtual host. Do not prefer a
  // caller-controlled X-Forwarded-Host value here.
  return normalizeHost(headers.get('host')) === expected;
}
