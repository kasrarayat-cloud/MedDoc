// ============================================================================
// S4b regression guard — clinical clipboard copies must be audited.
// ----------------------------------------------------------------------------
// Three of the four copy affordances wrote PHI to the OS clipboard and left no
// audit row at all. The durable failure mode is not the three we just fixed —
// it is the FOURTH one somebody adds next quarter. So this is a source-level
// scan: any component that copies clinical text must also report it.
//
// Source-level rather than behavioural on purpose (same reasoning as
// detector-enum-cast.test.ts): a mocked-clipboard unit test only covers the
// call sites that already exist, and would pass happily on the day a new
// unaudited Copy button lands.
// ============================================================================

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = join(__dirname, '..', '..');

/** Files that legitimately copy something that is NOT clinical PHI. */
const NON_PHI_ALLOWLIST = [
  // MFA backup codes are the user's OWN authentication secret, not patient
  // data. Copying them is a security event, not a PHI disclosure, and it is
  // deliberately out of EXPORT_* scope.
  'settings/security/mfa/mfa-enrollment-panel.tsx',
];

/** Files that audit via a different, already-audited server route. */
const AUDITED_ELSEWHERE = [
  // Posts to /api/visits/[id]/export/clipboard, which builds the text
  // server-side and writes EXPORT_CLIPBOARD_COPIED itself.
  'visits/[id]/sign-and-send-modal.tsx',
];

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules' || entry === '__tests__') continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.tsx?$/.test(entry)) out.push(full);
  }
  return out;
}

describe('S4b — clipboard PHI egress is audited', () => {
  const copiers = walk(SRC)
    .filter((f) => readFileSync(f, 'utf-8').includes('clipboard.writeText'))
    .map((f) => f.slice(SRC.length + 1).replace(/\\/g, '/'));

  it('finds the known clipboard call sites (canary — update if UI changes)', () => {
    // If this fails the UI moved; re-run the audit rather than editing blindly.
    expect(copiers.length).toBeGreaterThanOrEqual(4);
  });

  it('every clinical copy reports the disclosure', () => {
    const unaudited = copiers.filter((rel) => {
      if (NON_PHI_ALLOWLIST.some((a) => rel.endsWith(a))) return false;
      if (AUDITED_ELSEWHERE.some((a) => rel.endsWith(a))) return false;
      const src = readFileSync(join(SRC, rel), 'utf-8');
      // Match the CALL, not the bare identifier — an `import { reportClipboardCopy }`
      // left behind after the call was deleted would otherwise satisfy this
      // check. (Found by mutation-testing this guard: removing the call while
      // leaving the import made this assertion pass.)
      return !src.includes('reportClipboardCopy(');
    });

    expect(
      unaudited,
      'these components copy clinical text to the clipboard without recording ' +
        'the disclosure — call reportClipboardCopy() after the write resolves, ' +
        'or add the file to an allowlist above with a reason'
    ).toEqual([]);
  });

  it('reports only AFTER the clipboard write resolves', () => {
    // Auditing a disclosure that never happened is a false record. In every
    // call site the report must come after `await navigator.clipboard...`,
    // never before it.
    for (const rel of copiers) {
      const src = readFileSync(join(SRC, rel), 'utf-8');
      if (!src.includes('reportClipboardCopy')) continue;
      const write = src.indexOf('clipboard.writeText');
      const report = src.indexOf('reportClipboardCopy(');
      expect(report, `${rel}: audit call precedes the clipboard write`).toBeGreaterThan(write);
    }
  });
});

describe('S4b — bulk export routes are audited', () => {
  const ROUTES: [string, string][] = [
    ['app/api/settings/export-data/route.ts', 'EXPORT_ACCOUNT_ARCHIVE_DOWNLOADED'],
    ['app/api/patients/[id]/export/route.ts', 'EXPORT_PATIENT_ARCHIVE_DOWNLOADED'],
  ];

  it.each(ROUTES)('%s writes %s', (rel, action) => {
    const src = readFileSync(join(SRC, rel), 'utf-8');
    expect(src).toContain(`action: '${action}'`);
    // Must be awaited, not fire-and-forget: these routes return a STREAM, and
    // the handler's scope can be torn down before a floating promise resolves.
    expect(src).toMatch(/await logAudit\(\{\s*\n\s*action: 'EXPORT_/);
  });

  it('both actions keep the EXPORT_ prefix the admin detector filters on', () => {
    // dashboard-data.ts filters `action::text LIKE 'EXPORT_%'`. A bulk-export
    // action that broke this prefix would be invisible to the volume-spike
    // detector — exactly the class of blindness S4a just fixed.
    for (const [, action] of ROUTES) expect(action.startsWith('EXPORT_')).toBe(true);
  });
});
