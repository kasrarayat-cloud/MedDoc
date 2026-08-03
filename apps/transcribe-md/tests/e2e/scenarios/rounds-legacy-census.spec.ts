// ============================================================================
// R3 ITEM 0 — THE LEGACY-ISLAND CENSUS.
// ----------------------------------------------------------------------------
// ⚠️ THIS EXISTS TO END WHACK-A-MOLE, AND THAT IS A DIFFERENT JOB FROM FIXING
// THE EIGHT ITEMS. R1 found the app split-brain, R2 found a footer that two
// artifacts claimed was already gone, and R3's brief is eight more legacy
// islands. Each round has been a list of sightings. A list of sightings cannot
// tell you when you are finished.
//
// So this walks every authenticated route on the LIVE DOM and enumerates what
// is actually rendering legacy skin — by CLASS FAMILY (`qm-c3-*`, `qm-lin-*`)
// and by COMPUTED COLOUR against the legacy palette. The output is a table the
// ledger carries: surface → family → the R3 item that fixes it, or a stated
// justification for why it stays.
//
// ─── WHAT WOULD MAKE THIS LIE (rule 7) ──────────────────────────────────────
//  · a route that fails to load          → counted as "clean", zero islands
//  · a matcher that matches nothing      → every route reads clean
//  · a class present but never RENDERED  → inflates the census with dead nodes
//  · counting the Rounds bridge's own    → `.qm-rounds-host` legitimately
//    hosted legacy classes as islands       REDECLARES `--color-linear-*`, so a
//                                           `qm-c3-*` inside it is already
//                                           re-skinned and is NOT an island
//
// Each is guarded below: a per-route load assertion, a positive control on the
// matcher, `offsetParent`/rect checks for visibility, and bridge-awareness that
// reports hosted vs unhosted separately rather than lumping them.
// ============================================================================
import { writeFileSync, mkdirSync } from 'node:fs';

import { expect, test } from '@playwright/test';

import { signupFreshUser } from '../helpers/signup';
import { seedReviewDocVisit } from '../helpers/seedReviewDocVisit';
import { cleanupTestUsers } from '../helpers/cleanup';

test.afterEach(() => {
  cleanupTestUsers();
});

/** The legacy palette, from globals.css. Computed colours are matched against
 *  these — a class rename cannot hide a legacy colour, and a Rounds class
 *  painted with a legacy token is still an island. */
const LEGACY_COLORS: Record<string, string> = {
  'rgb(122, 166, 140)': 'legacy sage --color-linear-sage',
  'rgb(139, 180, 156)': 'legacy sage-bright',
  'rgb(13, 14, 16)': 'legacy surface-1',
  'rgb(8, 9, 10)': 'legacy bg',
  'rgb(245, 242, 235)': 'legacy cream',
  'rgb(250, 248, 243)': 'legacy cream-2',
};

test('R3.0 — the legacy-island census', async ({ page }, testInfo) => {
  const { email } = await signupFreshUser(page, 'census');
  const visit = seedReviewDocVisit(email, { idSalt: 'cen' });
  test.skip(!visit, 'psql seeding unavailable');

  // ⚠️ STATES, NOT ROUTES. The first cut of this census walked seven routes in
  // ONE state each and reported /patients and the visit stage as clean, which
  // contradicted the owner's own walkthrough. A route rendered once is a
  // SAMPLE; the whole point of a census is that it is an inventory.
  const ROUTES = [
    '/board',
    '/patients',
    `/patients/${visit!.patientId}`,
    '/visits',
    '/visits/new',
    `/visits/${visit!.visitId}`,
    `/visits/${visit!.visitId}/record`,
    '/settings',
    '/settings/note-format',
  ];

  const rows: Array<Record<string, unknown>> = [];

  for (const route of ROUTES) {
    const res = await page.goto(route);
    // NON-VACUITY #1: a route that 404s or errors would report zero islands.
    expect(res?.status(), `${route} did not load — it would read as clean`).toBeLessThan(400);
    await expect(page.locator('body')).toBeVisible();

    // ⚠️ SETTLE BEFORE ENUMERATING, AND THIS WAS MEASURED RATHER THAN ASSUMED.
    // The first widened run reported the visit stage as **0** legacy classes and
    // the next as **37** — same build, same fixture. The paper renders
    // asynchronously ("Opening your document…"), so a census that enumerates on
    // first paint counts whatever happened to be mounted. An inventory that
    // varies by timing is still a sample.
    //
    // `networkidle` plus an explicit settle: the deadline is short and a route
    // that never idles is still enumerated rather than skipped — under-reporting
    // one surface beats losing the whole run.
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
    await page.waitForTimeout(1200);

    const found = await page.evaluate((colors) => {
      const out: Array<{
        family: string;
        cls: string;
        tag: string;
        hosted: boolean;
        why: string;
        sample: string;
      }> = [];
      const seen = new Set<string>();

      const visible = (el: Element) => {
        const he = el as HTMLElement;
        if (!he.offsetParent && getComputedStyle(he).position !== 'fixed') return false;
        const r = he.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
      };

      for (const el of Array.from(document.querySelectorAll('*'))) {
        if (!visible(el)) continue;
        const he = el as HTMLElement;
        // The Rounds bridge REDECLARES the legacy custom properties on a scoped
        // class, so legacy markup inside it is already re-skinned. Reported, but
        // as `hosted` — not as an island to fix.
        const hosted = !!he.closest('.qm-rounds-host');
        const classes = (he.getAttribute('class') || '').split(/\s+/).filter(Boolean);

        for (const c of classes) {
          const fam = c.startsWith('qm-c3-') ? 'qm-c3-*' : c.startsWith('qm-lin-') ? 'qm-lin-*' : null;
          if (!fam) continue;
          const key = `cls:${c}:${hosted}`;
          if (seen.has(key)) continue;
          seen.add(key);
          out.push({
            family: fam,
            cls: c,
            tag: he.tagName.toLowerCase(),
            hosted,
            why: 'legacy class family',
            sample: (he.textContent || '').trim().slice(0, 40),
          });
        }

        // Computed-colour arm — catches a legacy colour on ANY class name.
        const cs = getComputedStyle(he);
        for (const prop of ['color', 'backgroundColor', 'borderTopColor'] as const) {
          const v = cs[prop];
          const label = (colors as Record<string, string>)[v];
          if (!label) continue;
          const key = `col:${prop}:${v}:${classes[0] || he.tagName}`;
          if (seen.has(key)) continue;
          seen.add(key);
          out.push({
            family: label,
            cls: classes[0] || `<${he.tagName.toLowerCase()}>`,
            tag: he.tagName.toLowerCase(),
            hosted,
            why: `${prop} = ${v}`,
            sample: (he.textContent || '').trim().slice(0, 40),
          });
        }
      }
      return out;
    }, LEGACY_COLORS);

    for (const f of found) rows.push({ route, ...f });
  }

  // NON-VACUITY #2 — THE POSITIVE CONTROL. A matcher that finds nothing makes
  // every route read clean. Inject a node carrying BOTH arms and prove the same
  // predicate sees it; without this a zero census and a broken census are the
  // same output.
  const control = await page.evaluate((colors) => {
    const probe = document.createElement('div');
    probe.className = 'qm-c3-census-probe';
    probe.style.cssText =
      'position:fixed;top:0;left:0;width:10px;height:10px;color:rgb(122, 166, 140)';
    probe.textContent = 'probe';
    document.body.appendChild(probe);
    const he = probe as HTMLElement;
    const classHit = (he.getAttribute('class') || '').split(/\s+/).some((c) => c.startsWith('qm-c3-'));
    const colorHit = !!(colors as Record<string, string>)[getComputedStyle(he).color];
    probe.remove();
    return { classHit, colorHit };
  }, LEGACY_COLORS);
  expect(control.classHit, 'the CLASS arm of the census matcher is blind').toBe(true);
  expect(control.colorHit, 'the COLOUR arm of the census matcher is blind').toBe(true);

  // ── ARM 2 — THE SOURCE SWEEP, AND WHY THE DOM ARM ALONE IS NOT A CENSUS ──
  // A DOM walk can only see states it can REACH. Three of R3's eight items live
  // in states this spec cannot get to on a seeded fixture:
  //
  //   · the "Writing the note…" card   — transient, only during a live creation
  //   · the post-creation error/retry  — only on a failed pipeline run
  //
  // ⚠️ AND ONE I GOT WRONG, CORRECTED HERE RATHER THAN LEFT STANDING: this list
  // also named the prescription-safety rail as unreachable, on the reasoning
  // that it needs `MOCK_RX_WARNINGS`. It does not — `seedReviewDocVisit` writes
  // `rxDrafts`, so the rail renders on the ordinary fixture and the DOM arm
  // enumerated 30+ `qm-lin-rx-*` classes from it. A boundary statement that
  // over-claims what a check cannot see is the same defect as one that
  // over-claims what it can.
  //
  // Reporting those as "clean" because the walk never rendered them is exactly
  // the defect this census exists to end. So the second arm reads the SOURCE:
  // every component under `src/app` + `src/components` that applies a legacy
  // class family, minus the ones only a flag-OFF build renders. It over-reports
  // by design — a compiled-but-unreachable component appears — and that is the
  // right direction to be wrong in for an inventory.
  const sourceIslands = await page.evaluate(() => null).then(async () => {
    const { execSync } = await import('node:child_process');
    const raw = execSync(
      `grep -rlE "qm-(c3|lin)-" src/app src/components --include=*.tsx || true`,
      { encoding: 'utf8' },
    );
    return raw.split('\n').filter(Boolean).sort();
  });

  const unhosted = rows.filter((r) => !r.hosted);
  const bySurface = new Map<string, Set<string>>();
  for (const r of unhosted) {
    const k = String(r.route);
    if (!bySurface.has(k)) bySurface.set(k, new Set());
    bySurface.get(k)!.add(String(r.cls));
  }

  const lines = [
    '# R3.0 — legacy-island census',
    '',
    `Routes walked: ${ROUTES.length}. Matcher positive-controlled (class arm + colour arm).`,
    `Rows: ${rows.length} total, ${unhosted.length} UNHOSTED (islands), ` +
      `${rows.length - unhosted.length} inside \`.qm-rounds-host\` (already bridged).`,
    '',
    '| surface | class / colour | family | tag | sample |',
    '|---|---|---|---|---|',
    ...unhosted.map(
      (r) =>
        `| \`${r.route}\` | \`${r.cls}\` | ${r.family} | ${r.tag} | ${String(r.sample).replace(/\|/g, '\\|')} |`,
    ),
    '',
    '## Per-surface island class count (unhosted)',
    '',
    ...[...bySurface.entries()].map(([k, v]) => `- \`${k}\` — ${v.size} distinct legacy classes`),
    '',
    '## ARM 2 — source sweep (states the DOM walk cannot reach)',
    '',
    'A DOM walk sees only rendered states. These components APPLY a legacy class',
    'family in source; some are flag-OFF-only and are not islands. Over-reports by',
    'design — for an inventory that is the right direction to be wrong in.',
    '',
    ...sourceIslands.map((f) => `- \`${f}\``),
    '',
    '## STATED BOUNDARY',
    '',
    '- Walked: ' + ROUTES.length + ' states on the flag-ON QA image, single filesystem.',
    '- NOT walked (needs a live pipeline run), named rather than reported clean:',
    '  the "Writing the note…" processing card, and the post-creation error/retry',
    '  surface. Both are transient states of a real creation.',
    '- The prescription-safety rail IS walked — `seedReviewDocVisit` writes',
    '  `rxDrafts`, so it renders on the ordinary fixture. An earlier draft of this',
    '  boundary claimed it needed MOCK_RX_WARNINGS and was wrong.',
    '- The class/colour arms CANNOT see "correct tokens, wrong anatomy". `/patients`',
    '  reports zero legacy classes and is still a redesign target (R3.1) — the',
    '  owner\'s verdict was "a redesign, not a recolor", which no class matcher',
    '  detects. A clean row here is not a claim that a surface is finished.',
  ];

  mkdirSync('census-out', { recursive: true });
  writeFileSync('census-out/census.md', lines.join('\n'));
  await testInfo.attach('census', { path: 'census-out/census.md' });

  console.log(`\n[CENSUS] routes=${ROUTES.length} rows=${rows.length} unhosted=${unhosted.length}`);
  for (const [k, v] of bySurface) console.log(`[CENSUS] ${k}: ${v.size} legacy classes`);
});
