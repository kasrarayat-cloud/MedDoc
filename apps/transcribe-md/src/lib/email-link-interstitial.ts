// ============================================================================
// Email-link interstitial — anti-CSRF + anti-Referer-leak posture for
// click-to-verify / click-to-confirm GET handlers.
// ----------------------------------------------------------------------------
// Security audit P1-K (2026-05-13): the historical pattern was
//
//   GET /api/auth/verify-email?token=… → mutate DB + redirect
//
// A high-entropy single-use token mitigates most of the risk, but the
// token leaks via the `Referer` header if the user clicks the email
// link while another tab is also navigated to a hostile origin
// (browser will sometimes forward the Referer cross-tab). A leaked
// token, until it expires or is used, can be replayed by the
// attacker.
//
// The fix is the standard "interstitial POST" pattern used by GitHub,
// Stripe, etc.: the GET handler renders a tiny HTML page that POSTs
// the token to the same endpoint. The POST handler does the actual
// mutation. Browsers don't forward Referer on POST submissions to
// same-origin endpoints (the page itself becomes the referrer), so
// the token never lands in a third-party context.
//
// The page auto-submits via `setTimeout` so link-prefetchers (which
// often run JS but never POST) and humans see the same UX. A
// `<noscript>` fallback button keeps the flow working for JS-off
// clients — rare on email-link traffic, but worth supporting.
// ============================================================================

const PAGE_STYLES = `
  body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif; background: #fafafa; color: #111; }
  .wrap { max-width: 440px; margin: 96px auto; padding: 28px 32px; background: #fff; border: 1px solid #eaeaea; border-radius: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
  h1 { font-size: 17px; font-weight: 600; margin: 0 0 6px; letter-spacing: -0.01em; }
  p { font-size: 14px; color: #555; margin: 0 0 18px; }
  button { font: inherit; font-size: 14px; padding: 9px 18px; border: 1px solid #d0d7de; background: #f6f8fa; border-radius: 6px; cursor: pointer; }
  button:hover { background: #eef1f4; }
  .pulse { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #2ea043; margin-right: 8px; animation: pulse 1.2s ease-in-out infinite; vertical-align: middle; }
  @keyframes pulse { 0%,100% { opacity: 0.35 } 50% { opacity: 1 } }
`;

/** Build the interstitial HTML. `actionPath` should be the absolute
 *  path to the POST handler (e.g., `/api/auth/verify-email`). The
 *  page auto-submits the token after ~200ms; renders a noscript
 *  fallback button. */
export function emailLinkInterstitialHtml(args: {
  actionPath: string;
  token: string;
  headline: string;
  detail: string;
}): string {
  // Defensive escaping: the token is base64url-ish from the auth-
  // tokens helper (no HTML metacharacters expected), but escape
  // anyway so a future encoding change can't introduce an XSS
  // surface. Same for the headline/detail — they're internal strings
  // today but the function signature accepts arbitrary input.
  const esc = (s: string) =>
    s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="robots" content="noindex, nofollow" />
  <title>${esc(args.headline)}</title>
  <style>${PAGE_STYLES}</style>
</head>
<body>
  <div class="wrap">
    <h1><span class="pulse" aria-hidden="true"></span>${esc(args.headline)}</h1>
    <p>${esc(args.detail)}</p>
    <form id="f" action="${esc(args.actionPath)}" method="POST">
      <input type="hidden" name="token" value="${esc(args.token)}" />
      <noscript>
        <button type="submit">Continue</button>
        <p style="font-size:12px;color:#777;margin-top:12px;">JavaScript is disabled — click Continue to finish.</p>
      </noscript>
    </form>
    <script>
      setTimeout(function () {
        var f = document.getElementById('f');
        if (f) f.submit();
      }, 200);
    </script>
  </div>
</body>
</html>`;
}
