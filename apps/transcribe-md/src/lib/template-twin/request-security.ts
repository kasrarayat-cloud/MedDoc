/** Same-origin check for cookie-authenticated JSON/multipart mutation routes. */
export function isSameOriginTemplateTwinMutation(request: Request): boolean {
  const fetchSite = request.headers.get('sec-fetch-site');
  if (fetchSite === 'cross-site') return false;

  const claimed = request.headers.get('origin') ?? request.headers.get('referer');
  if (!claimed) return false;

  try {
    const claimedUrl = new URL(claimed);
    const requestUrl = new URL(request.url);
    const host =
      request.headers.get('x-forwarded-host')?.split(',')[0]?.trim() ||
      request.headers.get('host') ||
      requestUrl.host;
    const protocol =
      request.headers.get('x-forwarded-proto')?.split(',')[0]?.trim() ||
      requestUrl.protocol.replace(':', '');
    return claimedUrl.host === host && claimedUrl.protocol === `${protocol}:`;
  } catch {
    return false;
  }
}
