// ============================================================================
// AN INGRESS UPSTREAM THAT NAMES A DELETED SERVICE FAILS *SILENTLY* — UNTIL THE
// LAYER IN FRONT OF IT IS REMOVED, WHICH IS EXACTLY WHEN SOMEBODY NEEDS IT
// ----------------------------------------------------------------------------
// Ruling #307 removed the `meddoc-pro` service from `docker-compose.yml`. The
// `Caddyfile` kept `reverse_proxy meddoc-pro:3000` inside its `pro.quillmd.com`
// block. Nothing went red, and nothing could have:
//
//   · HOST nginx terminates `pro.quillmd.com` with an unconditional `return 410`
//     in a block with no `proxy_pass`, so Caddy is NEVER CONSULTED for that
//     hostname (measured: public = `HTTP/2 410, server: nginx/1.24.0`; Caddy
//     direct on 127.0.0.1:8443 with that SNI = `HTTP/2 502, server: Caddy`);
//   · so the dangling upstream is invisible to every HTTP check in the tree,
//     including `scripts/check-cotenants.sh`, whose row for this host is green
//     either way.
//
// ⚠️ THE ORDERING IS WHAT TURNS INVISIBLE INTO HARMFUL. `DEPLOYMENT_RUNBOOK.md`
// §3.5's restore procedure deletes the nginx 410 block and reloads nginx BEFORE
// it touches the container. The instant that reload lands, Caddy is what
// answers — and a dead upstream answers 502, which `check-cotenants.sh:42`
// names as THE FINDING for this host: *"a 502 wearing its place"*.
//
// The repair makes the two layers AGREE rather than one masking the other: the
// `pro.quillmd.com` block now answers 410 itself. Removing either control alone
// no longer produces a 502.
//
// ⚠️ AND THE GENERAL FORM IS THE POINT, NOT THIS HOST. A compose service and
// its ingress route live in two files that are edited by different commits for
// different reasons, and nothing joined them. Every ACTIVE `reverse_proxy`
// naming a compose-network host must name a service that exists.
// ============================================================================
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const REPO = join(process.cwd(), '..', '..');
const CADDYFILE = join(REPO, 'Caddyfile');
const COMPOSE = join(REPO, 'docker-compose.yml');
const COTENANTS = join(REPO, 'scripts', 'check-cotenants.sh');

const req = createRequire(__filename);
function services(): Set<string> {
  let load: (s: string) => unknown;
  try {
    load = (req('js-yaml') as { load: (s: string) => unknown }).load;
  } catch {
    throw new Error(
      'the YAML parser is not installed, so this guard cannot check anything. ' +
        'js-yaml reaches this tree transitively via eslint; add it as an ' +
        'explicit devDependency rather than deleting this test.',
    );
  }
  const doc = load(readFileSync(COMPOSE, 'utf8')) as { services?: Record<string, unknown> };
  return new Set(Object.keys(doc?.services ?? {}));
}

/** The `host|code|why` rows of the co-tenant expectation table. */
export function cotenantExpectations(sh: string): Map<string, string> {
  const out = new Map<string, string>();
  const block = /EXPECTED=\(\n([\s\S]*?)\n\)/.exec(sh);
  if (!block) return out;
  for (const line of block[1].split('\n')) {
    const m = /^\s*"([^"|]+)\|([0-9]{3})\|/.exec(line);
    if (m) out.set(m[1], m[2]);
  }
  return out;
}

/** The status a site block answers when nothing else matched, or null when the
 *  block has no unmatched `respond` (it proxies, so something else decides). */
export function unmatchedRespondStatus(block: string): string | null {
  for (const l of block.split('\n')) {
    if (l.trimStart().startsWith('#')) continue;
    const m = /^\s*respond\s+(.*)$/.exec(l);
    if (!m) continue;
    const args = m[1].trim();
    if (args.startsWith('@')) continue; // matched — not the fallback
    const code = /(?:^|\s)([1-5][0-9]{2})\s*$/.exec(args);
    if (code) return code[1];
  }
  return null;
}

export type Upstream = { line: number; target: string };

/** Every `reverse_proxy` target Caddy will actually load. Commented-out
 *  rollback references are configuration ARCHAEOLOGY, not routes. */
export function activeUpstreams(caddySrc: string): Upstream[] {
  const out: Upstream[] = [];
  caddySrc.split('\n').forEach((l, i) => {
    if (l.trimStart().startsWith('#')) return;
    const m = /^\s*reverse_proxy\s+(\S+)/.exec(l);
    if (m) out.push({ line: i + 1, target: m[1] });
  });
  return out;
}

/** Targets that are not compose service names and never needed to be. */
function isNonComposeTarget(target: string): boolean {
  const host = target.replace(/^[a-z]+:\/\//, '').split(':')[0];
  return (
    host === 'localhost' ||
    host === 'host.docker.internal' ||
    /^\d{1,3}(\.\d{1,3}){3}$/.test(host) ||
    /^\{/.test(host) ||
    /^\[/.test(host)
  );
}

export function danglingUpstreams(caddySrc: string, defined: Set<string>): string[] {
  return activeUpstreams(caddySrc)
    .filter((u) => !isNonComposeTarget(u.target))
    .filter((u) => {
      const host = u.target.replace(/^[a-z]+:\/\//, '').split(':')[0];
      return /^[a-z][a-z0-9._-]*$/.test(host) && !defined.has(host);
    })
    .map((u) => `Caddyfile:${u.line}  reverse_proxy ${u.target}`);
}

/** The body of a named site block, brace-counted from its opening line. */
export function siteBlock(caddySrc: string, host: string): string | null {
  const lines = caddySrc.split('\n');
  const start = lines.findIndex(
    (l) => !l.trimStart().startsWith('#') && new RegExp(`^${host.replace(/\./g, '\\.')}\\s*\\{`).test(l.trim()),
  );
  if (start === -1) return null;
  let depth = 0;
  const body: string[] = [];
  for (let i = start; i < lines.length; i += 1) {
    const l = lines[i];
    body.push(l);
    if (!l.trimStart().startsWith('#')) {
      depth += (l.match(/\{/g) ?? []).length - (l.match(/\}/g) ?? []).length;
    }
    if (i > start && depth === 0) break;
  }
  return body.join('\n');
}

describe('#307 — every active ingress upstream names a service that exists', () => {
  it('has no reverse_proxy pointing at a compose service that is not defined', () => {
    const src = readFileSync(CADDYFILE, 'utf8');
    expect(
      danglingUpstreams(src, services()),
      'A Caddy route proxies to a compose service that docker-compose.yml does ' +
        'not define. Today that reads 502 the moment anything in front of it is ' +
        'removed — and for pro.quillmd.com the documented restore procedure ' +
        'removes exactly that. Terminate the route or restore the service.',
    ).toEqual([]);
  });

  it('the retired pro.quillmd.com host is TERMINATED in the ingress, not merely unreachable', () => {
    const block = siteBlock(readFileSync(CADDYFILE, 'utf8'), 'pro.quillmd.com');
    expect(block, 'the pro.quillmd.com site block has gone missing').not.toBeNull();
    const live = (block as string)
      .split('\n')
      .filter((l) => !l.trimStart().startsWith('#'))
      .join('\n');
    expect(/reverse_proxy/.test(live)).toBe(false);
    expect(/\brespond\b[^\n]*\b410\b/.test(live)).toBe(true);
  });

  // ── CONTROLS ──────────────────────────────────────────────────────────────

  it('POSITIVE CONTROL — the extractor reads the routes that DO exist', () => {
    const active = activeUpstreams(readFileSync(CADDYFILE, 'utf8')).map((u) => u.target);
    expect(active.length).toBeGreaterThan(0);
    expect(active).toContain('transcribe-md:3011');
    expect(active).toContain('marketing:3010');
    // and the classifier is not simply calling everything non-compose:
    expect(isNonComposeTarget('transcribe-md:3011')).toBe(false);
    expect(isNonComposeTarget('127.0.0.1:9000')).toBe(true);
  });

  it('DISCRIMINATION CONTROL — a commented rollback reference is NOT what makes this green', () => {
    // ⚠️ THE REAL FILE STILL CARRIES `reverse_proxy meddoc-pro:3000` — inside the
    // inactive "MODE A — rollback reference" block. If the arm above were green
    // because the extractor sees nothing, this pair would not hold: the string is
    // present in the file and absent from the active set.
    const src = readFileSync(CADDYFILE, 'utf8');
    expect(src).toContain('reverse_proxy meddoc-pro:3000');
    expect(activeUpstreams(src).map((u) => u.target)).not.toContain('meddoc-pro:3000');
  });

  it('the co-tenant expectation table and the ingress agree on every host the ingress answers itself', () => {
    // ⚠️ THIS IS THE DRIFT THAT PRODUCED THE MISATTRIBUTION IN THE FIRST PLACE.
    // `check-cotenants.sh` declares an expected status per host; the `Caddyfile`
    // decides what the stack answers for that host. Nothing joined them, so the
    // table could say 410 while the ingress said 502 — and it did, for months,
    // invisibly, because host nginx sat in front and answered first.
    const table = cotenantExpectations(readFileSync(COTENANTS, 'utf8'));
    const caddy = readFileSync(CADDYFILE, 'utf8');
    const disagreements: string[] = [];
    let joined = 0;
    for (const [host, want] of table) {
      const block = siteBlock(caddy, host);
      if (!block) continue;
      const fallback = unmatchedRespondStatus(block);
      if (fallback === null) continue; // the block proxies; nginx/app decides
      joined += 1;
      if (fallback !== want) disagreements.push(`${host}: table says ${want}, Caddyfile answers ${fallback}`);
    }
    expect(
      joined,
      'no host is answered by BOTH the expectation table and a Caddy `respond`. ' +
        'Either the parser broke or the ingress stopped terminating anything — ' +
        'and a zero here makes the comparison below vacuous.',
    ).toBeGreaterThanOrEqual(2);
    expect(disagreements).toEqual([]);
  });

  it('DISCRIMINATION CONTROL — the expectation/ingress join catches a planted disagreement', () => {
    const block = ['x.example.com {', '    respond "gone" 410', '}'].join('\n');
    expect(unmatchedRespondStatus(block)).toBe('410');
    // a MATCHED respond is not the fallback answer
    expect(unmatchedRespondStatus(['y.example.com {', '    respond @internal 404', '}'].join('\n'))).toBeNull();
    // a proxying block has no fallback of its own
    expect(unmatchedRespondStatus(['z.example.com {', '    reverse_proxy a:1', '}'].join('\n'))).toBeNull();
    // and the table parser reads real rows, not the header prose around them
    const table = cotenantExpectations(readFileSync(COTENANTS, 'utf8'));
    expect(table.get('pro.quillmd.com')).toBe('410');
    expect(table.get('app.quillmd.com')).toBe('307');
    expect(table.size).toBeGreaterThanOrEqual(4);
  });

  it('DISCRIMINATION CONTROL — a planted live dangling upstream is caught; a commented one is not', () => {
    const planted = [
      'ghost.example.com {',
      '    reverse_proxy ghost-service:3000',
      '}',
      '# inactive rollback reference:',
      '#     reverse_proxy other-ghost:9999 {',
      'ok.example.com {',
      '    reverse_proxy transcribe-md:3011',
      '    reverse_proxy 127.0.0.1:9000',
      '}',
    ].join('\n');
    const defined = services();
    expect(activeUpstreams(planted).map((u) => u.target)).toEqual([
      'ghost-service:3000',
      'transcribe-md:3011',
      '127.0.0.1:9000',
    ]);
    expect(danglingUpstreams(planted, defined)).toEqual([
      'Caddyfile:2  reverse_proxy ghost-service:3000',
    ]);
  });
});
