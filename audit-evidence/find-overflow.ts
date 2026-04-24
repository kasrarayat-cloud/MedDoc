import { test } from '@playwright/test';

test('find overflow culprit on /pricing', async ({ page }) => {
  await page.setViewportSize({ width: 393, height: 851 });
  await page.goto('https://quillmd.com/pricing', { waitUntil: 'networkidle' });
  const offenders = await page.evaluate(() => {
    const results: Array<{ tag: string; cls: string; right: number; left: number; text: string }> = [];
    const vw = document.documentElement.clientWidth;
    function walk(el: Element, depth: number) {
      const r = el.getBoundingClientRect();
      if (r.right > vw + 1) {
        results.push({
          tag: el.tagName.toLowerCase() + (el.id ? `#${el.id}` : ''),
          cls: (el.getAttribute('class') || '').slice(0, 80),
          right: Math.round(r.right),
          left: Math.round(r.left),
          text: (el.textContent || '').trim().slice(0, 60),
        });
      }
      for (const child of Array.from(el.children)) walk(child, depth + 1);
    }
    walk(document.body, 0);
    return { viewport: vw, offenders: results.slice(0, 15) };
  });
  console.log(JSON.stringify(offenders, null, 2));
});
