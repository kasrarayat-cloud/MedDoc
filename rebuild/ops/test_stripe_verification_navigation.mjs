import assert from 'node:assert/strict';
import http from 'node:http';
import {once} from 'node:events';
import {test} from 'node:test';
import {chromium} from '@playwright/test';
import {observeCheckoutReturn, validateVerificationArguments} from './stripe_verification_navigation.mjs';

const release = 'a'.repeat(40);

test('optional attempt labels preserve strict CLI validation', () => {
  for (const args of [
    ['--release', release, '--dry-run'],
    ['--execute', '--release', release, '--attempt', '20260920-a1'],
    ['--attempt', 'dry-readiness-1', '--release', release, '--dry-run'],
  ]) assert.doesNotThrow(() => validateVerificationArguments(args));
  for (const args of [
    ['--release', release, '--execute', '--dry-run'],
    ['--release', release, '--execute', '--execute'],
    ['--release', release, '--release', release, '--execute'],
    ['--release', release, '--attempt', 'first', '--attempt', 'second', '--execute'],
    ['--release', release, '--execute', '--attempt'],
    ['--release', release, '--execute', '--unknown'],
    ['--release', release.slice(0, 12), '--execute'],
    ['--release', release],
    ...['', '../escape', '/absolute', 'UPPER', 'a/b', 'a b', '-option', 'a'.repeat(49)]
      .map(label => ['--release', release, '--execute', '--attempt', label]),
  ]) assert.throws(() => validateVerificationArguments(args), assert.AssertionError);
});

test('real browser navigation qualifies only the exact main-document return chain', async t => {
  let authenticated = false;
  const app = http.createServer((request, response) => {
    const url = new URL(request.url, 'http://localhost');
    if (url.pathname === '/billing/' && !authenticated) {
      response.writeHead(302, {Location: '/login/?next=/billing/'}); response.end(); return;
    }
    response.writeHead(200, {'Content-Type': 'text/html'});
    response.end('<!doctype html><title>Synthetic application</title><p>Private fixture</p>');
  });
  app.listen(0, '127.0.0.1'); await once(app, 'listening');
  const origin = `http://localhost:${app.address().port}`;
  const checkout = http.createServer((request, response) => {
    response.writeHead(200, {'Content-Type': 'text/html'});
    response.end(`<!doctype html><title>Synthetic return fixture</title><a href="${origin}/billing/?payment=processing">Return</a>`);
  });
  checkout.listen(0, '127.0.0.1'); await once(checkout, 'listening');
  const checkoutOrigin = `http://127.0.0.1:${checkout.address().port}`;
  let browser;
  try {
    browser = await chromium.launch({headless: true});
    const run = async action => {
      const page = await browser.newPage();
      try {await page.goto(checkoutOrigin); await action(page);} finally {await page.close();}
    };
    await t.test('actual 302 login chain passes while the former URL wait fails', async () => run(async page => {
      const oldWait = page.waitForURL(`${origin}/billing/?payment=processing`, {timeout: 500})
        .then(() => true, () => false);
      const result = await observeCheckoutReturn(page, origin, () => page.getByRole('link', {name: 'Return'}).click(), 5000);
      assert.equal(await oldWait, false);
      assert.equal(result.request_chain_observed, true);
      assert.deepEqual(result.landing, {origin, path: '/login/', query: 'next=/billing/'});
    }));
    await t.test('authenticated return commits the exact billing URL', async () => run(async page => {
      authenticated = true;
      try {
        const result = await observeCheckoutReturn(page, origin, () => page.getByRole('link', {name: 'Return'}).click(), 5000);
        assert.deepEqual(result.landing, {origin, path: '/billing/', query: 'payment=processing'});
      } finally {authenticated = false;}
    }));
    await t.test('direct login navigation supplies no success-request evidence', async () => run(async page => {
      await assert.rejects(observeCheckoutReturn(page, origin, () => page.goto(`${origin}/login/?next=/billing/`), 350), {name: 'TimeoutError'});
    }));
    await t.test('another origin cannot stand in for the configured return', async () => run(async page => {
      await assert.rejects(observeCheckoutReturn(page, origin, () => page.goto(`${checkoutOrigin}/billing/?payment=processing`), 350), {name: 'TimeoutError'});
    }));
    await t.test('wrong or extra success parameters do not qualify a login redirect', async () => {
      for (const query of ['payment=failed', 'payment=processing&extra=1']) await run(async page => {
        await assert.rejects(observeCheckoutReturn(page, origin, () => page.goto(`${origin}/billing/?${query}`), 350), {name: 'TimeoutError'});
      });
    });
    await t.test('a fetch followed by login is not a main-document success chain', async () => run(async page => {
      await assert.rejects(observeCheckoutReturn(page, origin, async () => {
        await page.evaluate(url => fetch(url, {mode: 'no-cors'}), `${origin}/billing/?payment=processing`);
        await page.goto(`${origin}/login/?next=/billing/`);
      }, 350), {name: 'TimeoutError'});
    }));
    await t.test('an iframe return cannot qualify the main page', async () => run(async page => {
      await assert.rejects(observeCheckoutReturn(page, origin, async () => {
        await page.evaluate(url => {const frame = document.createElement('iframe'); frame.src = url; document.body.append(frame);}, `${origin}/billing/?payment=processing`);
      }, 350), {name: 'TimeoutError'});
    }));
  } finally {
    await browser?.close();
    await Promise.all([new Promise(resolve => app.close(resolve)), new Promise(resolve => checkout.close(resolve))]);
  }
});
