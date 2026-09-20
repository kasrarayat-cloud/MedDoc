import assert from 'node:assert/strict';

export function validateVerificationArguments(args) {
  const options = new Map();
  for (let i = 0; i < args.length; i++) {
    const name = args[i];
    assert(['--release', '--attempt', '--execute', '--dry-run'].includes(name), 'Unknown verification argument.');
    assert(!options.has(name), 'Repeated verification argument.');
    if (name === '--release' || name === '--attempt') {
      assert(typeof args[i + 1] === 'string' && !args[i + 1].startsWith('--'), 'Missing verification argument value.');
      options.set(name, args[++i]);
    } else options.set(name, true);
  }
  assert(/^[a-f0-9]{40}$/.test(options.get('--release') || ''), 'A full release SHA is required.');
  assert(options.has('--execute') !== options.has('--dry-run'), 'Choose exactly one execution mode.');
  if (options.has('--attempt')) assert(/^[a-z0-9][a-z0-9-]{0,47}$/.test(options.get('--attempt')), 'Invalid attempt label.');
}

function exactQuery(url, name, value) {
  return [...url.searchParams].length === 1 && url.searchParams.get(name) === value && !url.hash;
}

// An HTTP redirect's intermediate URL never commits as page.url(). Observe the
// actual main-document request chain, including the authenticated-app boundary.
// No Stripe URL, card value, cookie or credential is returned or logged here.
export async function observeCheckoutReturn(page, appOrigin, submit, timeout = 90000) {
  const origin = new URL(appOrigin);
  assert(origin.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(origin.hostname)
    && origin.origin === appOrigin, 'Expected a bare private application origin.');
  const success = value => {
    const url = new URL(value);
    return url.origin === appOrigin && url.pathname === '/billing/' && exactQuery(url, 'payment', 'processing');
  };
  const landing = value => {
    const url = new URL(value);
    return url.origin === appOrigin && (success(value)
      || (url.pathname === '/login/' && exactQuery(url, 'next', '/billing/')));
  };
  const responsePromise = page.waitForResponse(response => {
    if (response.status() !== 200 || !landing(response.url())) return false;
    for (let request = response.request(); request; request = request.redirectedFrom()) {
      if (request.method() === 'GET' && request.isNavigationRequest()
        && request.frame() === page.mainFrame() && success(request.url())) return true;
    }
    return false;
  }, {timeout});
  const [response] = await Promise.all([responsePromise, Promise.resolve().then(submit)]);
  await page.waitForURL(response.url(), {timeout, waitUntil: 'domcontentloaded'});
  const final = new URL(page.url());
  assert(landing(final.href), 'Unexpected checkout return destination.');
  return {
    origin: appOrigin, path: '/billing/', query: 'payment=processing',
    request_chain_observed: true,
    landing: {origin: appOrigin, path: final.pathname,
      query: final.pathname === '/login/' ? 'next=/billing/' : 'payment=processing'},
    note: 'The success navigation was observed before any login redirect; balances are read on the canonical origin using its existing session.',
  };
}
