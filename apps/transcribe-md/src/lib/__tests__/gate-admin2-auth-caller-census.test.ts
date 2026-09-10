// ============================================================================
// ADMIN-2 (#196) — EVERY DIRECT `auth()` CALLER IS CLASSIFIED, AND EVERY HOST
// READ GOES THROUGH ONE READER. A CENSUS, DERIVED — NOT A LIST.
// ----------------------------------------------------------------------------
// The host reconcile lives in `getSession()` (lib/auth.ts) and in `authorize()`
// (lib/nextauth.ts). A file that calls `auth()` directly — NextAuth's own
// session reader — BYPASSES the reconcile. The recon counted 19 such files;
// a hand-kept list of 19 is correct until the twentieth is written by somebody
// who never opens this file (#289's lesson, and rdoc-gate-hosts' before it).
//
// So the universe is READ FROM THE FILESYSTEM:
//   · every file importing the `auth` binding from lib/nextauth (under any
//     alias), with the number of times it references that binding;
//   · every file minting its OWN `auth` via `NextAuth(...)`.
// Each must be classified "reconciled" (and the reconcile call is then
// CHECKED in the file, not asserted) or "exempt: <reason>". A new caller, a
// new reference inside an exempt file, or a vanished caller all RED, by name.
//
// ⚠️ SHAPES THAT CANNOT BE COUNTED FAIL CLOSED. A namespace import, a dynamic
// `import()`, a `require()` or a re-export of lib/nextauth hides which binding
// is used and how often; the gate refuses them outright rather than guessing.
//
// The second census: every read of the request's host — `.get('host')`,
// `x-forwarded-host`, `forwarded`, `headers.host`, `nextUrl.host`, … — outside
// lib/practice-host.ts reds. That file reads `Host` only; see its header for
// why X-Forwarded-Host is client-controlled on this ingress.
//
// Limits, stated so they are not read as more: the comment stripper handles
// strings and template literals but not regex literals, and unquoted JSX text
// containing `//` would hide the rest of its line. Either could only produce a
// false count, which reds.
// ============================================================================
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const SRC = resolve(__dirname, '..', '..');
const NEXTAUTH_ID = join(SRC, 'lib', 'nextauth');

// ── the scanner ──────────────────────────────────────────────────────────────

/** Remove comments; optionally blank string/template TEXT (keeping `${}` code). */
export function stripComments(src: string, blankStrings = false): string {
  let out = '';
  let i = 0;
  const n = src.length;
  // 'tpl' = inside template text, 'expr' = inside `${`, 'brace' = a `{` in code
  const stack: Array<'tpl' | 'expr' | 'brace'> = [];
  while (i < n) {
    const c = src[i]!;
    const d = src[i + 1];
    if (stack[stack.length - 1] === 'tpl') {
      if (c === '\\') {
        out += blankStrings ? '  ' : c + (d ?? '');
        i += 2;
        continue;
      }
      if (c === '`') {
        stack.pop();
        out += c;
        i += 1;
        continue;
      }
      if (c === '$' && d === '{') {
        stack.push('expr');
        out += '${';
        i += 2;
        continue;
      }
      out += blankStrings && c !== '\n' ? ' ' : c;
      i += 1;
      continue;
    }
    if (c === '/' && d === '/') {
      while (i < n && src[i] !== '\n') i += 1;
      continue;
    }
    if (c === '/' && d === '*') {
      const end = src.indexOf('*/', i + 2);
      i = end < 0 ? n : end + 2;
      out += ' ';
      continue;
    }
    if (c === "'" || c === '"') {
      out += c;
      i += 1;
      while (i < n && src[i] !== c && src[i] !== '\n') {
        if (src[i] === '\\') {
          out += blankStrings ? '  ' : src[i]! + (src[i + 1] ?? '');
          i += 2;
          continue;
        }
        out += blankStrings ? ' ' : src[i]!;
        i += 1;
      }
      if (i < n) {
        out += src[i]!;
        i += 1;
      }
      continue;
    }
    if (c === '`') {
      stack.push('tpl');
      out += c;
      i += 1;
      continue;
    }
    if (c === '{' && stack.length > 0) stack.push('brace');
    if (c === '}' && stack.length > 0) stack.pop();
    out += c;
    i += 1;
  }
  return out;
}

const IDENT = '[A-Za-z_$][\\w$]*';
const STATIC_IMPORT_RE = new RegExp(
  `\\bimport\\s+(?:type\\s+)?((?:${IDENT}\\s*,\\s*)?(?:\\{[^}]*\\}|\\*\\s*as\\s+${IDENT})|${IDENT})\\s*from\\s*(['"])([^'"]+)\\2`,
  'g',
);
const REEXPORT_RE = new RegExp(`\\bexport\\s+(?:type\\s+)?(?:\\*(?:\\s*as\\s+${IDENT})?|\\{[^}]*\\})\\s*from\\s*(['"])([^'"]+)\\1`, 'g');
const DYNAMIC_RE = /\bimport\s*\(\s*(['"`])([^'"`]+)\1\s*\)/g;
const REQUIRE_RE = /\brequire\s*\(\s*(['"`])([^'"`]+)\1\s*\)/g;

function resolvesTo(fromFile: string, spec: string, targetId: string): boolean {
  let abs: string;
  if (spec.startsWith('@/')) abs = join(SRC, spec.slice(2));
  else if (spec.startsWith('.')) abs = resolve(dirname(fromFile), spec);
  else return false;
  abs = abs.replace(/\.(?:[cm]?[jt]sx?)$/, '').replace(/[\\/]index$/, '');
  return abs === targetId;
}

export type Scan = {
  /** local names bound to lib/nextauth's `auth` */
  authLocals: string[];
  /** local names bound to next-auth's default export (NextAuth) */
  mintLocals: string[];
  /** references to any of those names outside the import clause */
  refs: number;
  /** a shape the gate cannot count */
  opaque: string[];
};

export function scanSource(file: string, src: string): Scan {
  const code = stripComments(src);
  const authLocals: string[] = [];
  const mintLocals: string[] = [];
  const opaque: string[] = [];
  let withoutImports = code;

  for (const m of code.matchAll(STATIC_IMPORT_RE)) {
    const clause = m[1]!;
    const spec = m[3]!;
    const isNextauth = resolvesTo(file, spec, NEXTAUTH_ID);
    const isNextAuthPkg = spec === 'next-auth';
    if (!isNextauth && !isNextAuthPkg) continue;
    withoutImports = withoutImports.replace(m[0], ' ');
    const ns = clause.match(new RegExp(`\\*\\s*as\\s+(${IDENT})`));
    const def = clause.match(new RegExp(`^(${IDENT})\\s*(?:,|$)`));
    const named = clause.match(/\{([^}]*)\}/);
    if (isNextauth) {
      if (ns) opaque.push(`namespace import of lib/nextauth (${ns[1]})`);
      if (def && def[1] !== 'type') opaque.push(`default import of lib/nextauth (${def[1]})`);
      for (const part of (named?.[1] ?? '').split(',')) {
        const p = part.trim().replace(/^type\s+/, '');
        const a = p.match(new RegExp(`^auth(?:\\s+as\\s+(${IDENT}))?$`));
        if (a) authLocals.push(a[1] ?? 'auth');
      }
    } else {
      if (def) mintLocals.push(def[1]!);
      if (ns) opaque.push(`namespace import of next-auth (${ns[1]})`);
    }
  }
  for (const m of code.matchAll(REEXPORT_RE)) {
    if (resolvesTo(file, m[2]!, NEXTAUTH_ID)) opaque.push(`re-export of lib/nextauth`);
  }
  for (const re of [DYNAMIC_RE, REQUIRE_RE]) {
    for (const m of code.matchAll(re)) {
      if (resolvesTo(file, m[2]!, NEXTAUTH_ID)) opaque.push(`dynamic import/require of lib/nextauth`);
      if (m[2] === 'next-auth') opaque.push(`dynamic import/require of next-auth`);
    }
  }

  const body = stripComments(withoutImports, true);
  let refs = 0;
  for (const local of [...authLocals, ...mintLocals]) {
    const re = new RegExp(`(?<![\\w$.])${local.replace(/\$/g, '\\$')}(?![\\w$])`, 'g');
    refs += (body.match(re) ?? []).length;
  }
  return { authLocals, mintLocals, refs, opaque };
}

function sourceFiles(dir = SRC, out: string[] = []): string[] {
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    if (e === 'node_modules' || e === '__tests__' || e === '__fixtures__') continue;
    if (statSync(p).isDirectory()) sourceFiles(p, out);
    else if (/\.[cm]?[jt]sx?$/.test(e) && !/\.(?:test|spec)\.[cm]?[jt]sx?$/.test(e) && !e.endsWith('.d.ts')) out.push(p);
  }
  return out;
}

// ── the classification ──────────────────────────────────────────────────────

type Entry = {
  refs: number;
  verdict: 'reconciled' | 'exempt';
  reason: string;
  /** for 'reconciled': the call that IS the reconcile, checked in the file */
  marker?: string;
};

const OWN_ACCOUNT =
  "reads and writes only the caller's OWN users row (keyed on session.user.id); no practice data is selected by, or shown for, the host";
const REDIRECT_ONLY =
  'branches on the PRESENCE of a session only, to send a signed-in user elsewhere; renders no account or practice data';

const CENSUS: Record<string, Entry> = {
  // ── reconciled ──
  'lib/auth.ts': {
    refs: 2,
    verdict: 'reconciled',
    marker: 'assertHostAdmitsPractice(',
    reason:
      "getSession() IS the reconcile — assertHostAdmitsPractice() after the DB re-read; the second reference is getCurrentSessionId(), which returns only the caller's own sessionId claim and admits nothing",
  },
  'lib/nextauth.ts': {
    refs: 1,
    verdict: 'reconciled',
    marker: 'loginHostRefusal(',
    reason: 'THE definition of auth(); its authorize() carries the sign-in half of the reconcile (loginHostRefusal)',
  },
  // ── exempt ──
  'proxy.ts': {
    refs: 1,
    verdict: 'exempt',
    reason:
      'edge cookie gate (matcher: /dashboard, /visits, /settings) — no database on the edge, admits nothing by itself; every matched page makes its own server-side read',
  },
  'actions/session.ts': {
    refs: 1,
    verdict: 'exempt',
    reason:
      'sign-out attribution only (who is signing out, for the audit row); refusing a sign-out on any host would strand a live session',
  },
  'app/admin/layout.tsx': {
    refs: 1,
    verdict: 'exempt',
    reason:
      'platform-wide BY DESIGN — SUPER_ADMIN re-read from the database, not practice-scoped; admin. is a neutral host (ingress leg: the wildcard Caddy block should keep /admin off practice hosts)',
  },
  'app/admin/page.tsx': {
    refs: 1,
    verdict: 'exempt',
    reason: "reads the signed-in admin's email for display; the SUPER_ADMIN layout gates the route",
  },
  'app/admin/users/page.tsx': {
    refs: 1,
    verdict: 'exempt',
    reason: "reads the signed-in admin's id/email for display; the SUPER_ADMIN layout gates the route",
  },
  'app/api/mfa/disable/route.ts': { refs: 1, verdict: 'exempt', reason: OWN_ACCOUNT },
  'app/api/mfa/enroll/route.ts': { refs: 1, verdict: 'exempt', reason: OWN_ACCOUNT },
  'app/api/mfa/verify-enrollment/route.ts': { refs: 1, verdict: 'exempt', reason: OWN_ACCOUNT },
  'app/api/settings/change-email/route.ts': { refs: 1, verdict: 'exempt', reason: OWN_ACCOUNT },
  'app/api/settings/change-password/route.ts': { refs: 1, verdict: 'exempt', reason: OWN_ACCOUNT },
  'app/api/settings/delete-account/route.ts': {
    refs: 1,
    verdict: 'exempt',
    reason: `${OWN_ACCOUNT} — and, when the caller is its last member, their OWN practice (keyed on the users row, never on the host)`,
  },
  'app/settings/security/mfa/page.tsx': { refs: 1, verdict: 'exempt', reason: OWN_ACCOUNT },
  'app/settings/page.tsx': {
    refs: 1,
    verdict: 'exempt',
    reason:
      "the caller's own settings and their OWN practice's members, keyed on the users row re-read from the database, never on the host. ⚠️ The weakest exemption: on a foreign practice host (reachable only with a cookie minted there, i.e. a member who has since moved) it renders the caller's own practice under the wrong address",
  },
  'components/ui/app-frame.tsx': {
    refs: 1,
    verdict: 'exempt',
    reason: "the caller's own display name for the nav; every page it wraps makes its own session read",
  },
  'app/layout.tsx': { refs: 1, verdict: 'exempt', reason: 'Boolean(signed in) for UI chrome only (command palette shortcuts)' },
  'app/page.tsx': { refs: 1, verdict: 'exempt', reason: REDIRECT_ONLY },
  'app/login/page.tsx': { refs: 1, verdict: 'exempt', reason: REDIRECT_ONLY },
  'app/signup/page.tsx': { refs: 1, verdict: 'exempt', reason: REDIRECT_ONLY },
  'app/forgot-password/page.tsx': { refs: 1, verdict: 'exempt', reason: REDIRECT_ONLY },
  'app/reset-password/page.tsx': { refs: 1, verdict: 'exempt', reason: REDIRECT_ONLY },
  'lib/admin-api-gate.ts': {
    refs: 1,
    verdict: 'exempt',
    reason:
      'SUPER_ADMIN platform API gate — products and isActive re-read from the database, 12h freshness; platform-wide by design, not practice-scoped',
  },
  'lib/audit.ts': {
    refs: 1,
    verdict: 'exempt',
    reason: 'attribution only — fills userId/practiceId on an audit row when the caller passed neither; admits nothing',
  },
};

// ── the arms ────────────────────────────────────────────────────────────────

function deriveCensus(): { found: Map<string, Scan>; opaque: string[] } {
  const found = new Map<string, Scan>();
  const opaque: string[] = [];
  for (const abs of sourceFiles()) {
    const src = readFileSync(abs, 'utf8');
    if (!/nextauth|next-auth/.test(src)) continue;
    const s = scanSource(abs, src);
    const rel = relative(SRC, abs).split('\\').join('/');
    for (const o of s.opaque) opaque.push(`${rel}: ${o}`);
    if (s.authLocals.length || s.mintLocals.length) found.set(rel, s);
  }
  return { found, opaque };
}

describe('the scanner cannot pass vacuously — planted sources', () => {
  const at = (p: string) => join(SRC, p);

  it('an ALIASED import is found and its references counted', () => {
    const s = scanSource(
      at('app/x/page.tsx'),
      "import { auth as whoAmI, signIn } from '../../lib/nextauth';\nexport default async function P(){ const s = await whoAmI(); return s; }\n",
    );
    expect(s.authLocals).toEqual(['whoAmI']);
    expect(s.refs).toBe(1);
  });

  it('a reference passed by value (not called) still counts', () => {
    const s = scanSource(at('lib/x.ts'), "import { auth } from '@/lib/nextauth';\nexport const f = () => Promise.resolve().then(auth);\n");
    expect(s.refs).toBe(1);
  });

  it('a commented-out import and an auth() inside a string or comment are NOT callers', () => {
    const s = scanSource(
      at('lib/x.ts'),
      "// import { auth } from '@/lib/nextauth';\n/* auth() */ const m = 'auth()';\nimport { signIn } from '@/lib/nextauth';\n",
    );
    expect(s.authLocals).toEqual([]);
    expect(s.refs).toBe(0);
  });

  it.each([
    ["import * as na from '@/lib/nextauth'; na.auth();", 'namespace'],
    ["export { auth } from '@/lib/nextauth';", 're-export'],
    ["const m = await import('@/lib/nextauth');", 'dynamic'],
    ["const m = require('../lib/nextauth');", 'dynamic import/require'],
  ])('⚠️ an uncountable shape is OPAQUE and fails closed: %s', (src, kind) => {
    const s = scanSource(at('app/y.ts'), src);
    expect(s.opaque.join('|')).toContain(kind);
  });

  it('a NextAuth(...) mint is found', () => {
    const s = scanSource(at('z.ts'), "import NextAuth from 'next-auth';\nconst { auth } = NextAuth({});\n");
    expect(s.mintLocals).toEqual(['NextAuth']);
    expect(s.refs).toBe(1);
  });
});

describe('ADMIN-2 — the direct auth() caller census', () => {
  const { found, opaque } = deriveCensus();

  it('positive control: the census finds callers we KNOW exist', () => {
    expect(found.has('lib/auth.ts'), 'getSession itself was not found — the scanner is blind').toBe(true);
    expect(found.has('lib/audit.ts')).toBe(true);
    expect(found.has('proxy.ts'), 'the edge NextAuth mint was not found').toBe(true);
    expect(found.size).toBeGreaterThan(15);
  });

  it('⚠️ no uncountable import shape of lib/nextauth or next-auth exists', () => {
    expect(opaque, 'import `auth` BY NAME so it can be counted and classified').toEqual([]);
  });

  it('⚠️ every direct caller is classified — a new one REDS by name', () => {
    const unclassified = [...found.keys()].filter((f) => !(f in CENSUS)).sort();
    expect(
      unclassified,
      "classify it in CENSUS: 'reconciled' (and name the reconcile call) or 'exempt' with the reason it may bypass getSession()'s host reconcile",
    ).toEqual([]);
  });

  it('every classification still names a live caller (no stale rows)', () => {
    const stale = Object.keys(CENSUS).filter((f) => !found.has(f)).sort();
    expect(stale, 'a classified caller no longer imports auth — delete its row').toEqual([]);
  });

  it('⚠️ reference counts match — a NEW auth() inside an exempt file reds too', () => {
    const drift = [...found.entries()]
      .filter(([f, s]) => CENSUS[f] && CENSUS[f]!.refs !== s.refs)
      .map(([f, s]) => `${f}: classified ${CENSUS[f]!.refs}, measured ${s.refs}`);
    expect(drift, 're-read the file and re-classify the new reference before changing the number').toEqual([]);
  });

  it("⚠️ 'reconciled' is CHECKED, not asserted — the reconcile call is in the file", () => {
    for (const [f, e] of Object.entries(CENSUS)) {
      expect(e.reason.length, `${f}: a reason is somebody's words or nothing`).toBeGreaterThan(20);
      if (e.verdict !== 'reconciled') continue;
      expect(e.marker, `${f}: a reconciled row must name its reconcile call`).toBeTruthy();
      const code = stripComments(readFileSync(join(SRC, f), 'utf8'));
      expect(code.includes(e.marker!), `${f} is classified reconciled but never calls ${e.marker}`).toBe(true);
    }
  });
});

describe('ADMIN-2 — every host read goes through lib/practice-host.ts', () => {
  const HOST_READ: RegExp[] = [
    /\.get\(\s*(['"`])(?:host|x-forwarded-host|forwarded|x-original-host|x-forwarded-server|x-host|:authority)\1\s*\)/i,
    /\[\s*(['"`])(?:host|x-forwarded-host|forwarded|x-original-host)\1\s*\]/i,
    /\.headers\.host\b/,
    /\bnextUrl\.(?:host|hostname|origin|href)\b/,
    /\b[A-Za-z_$]*[uU]rl\.(?:host|hostname|origin)\b/,
  ];
  const THE_READER = 'lib/practice-host.ts';

  const readers = (src: string) => {
    const code = stripComments(src);
    return HOST_READ.filter((re) => re.test(code)).length;
  };

  it('planted: the shapes the old readers used are caught, a comment is not', () => {
    expect(readers("const host = (h.get('x-forwarded-host') ?? h.get('host') ?? '');")).toBeGreaterThan(0);
    expect(readers('const host = h.get("Host");')).toBeGreaterThan(0);
    expect(readers('const o = req.nextUrl.origin;')).toBeGreaterThan(0);
    expect(readers("// h.get('host')")).toBe(0);
  });

  it('positive control: the one reader IS found by this scan', () => {
    expect(readers(readFileSync(join(SRC, THE_READER), 'utf8'))).toBeGreaterThan(0);
  });

  it('⚠️ no other file in src reads the request host', () => {
    const offenders = sourceFiles()
      .map((abs) => relative(SRC, abs).split('\\').join('/'))
      .filter((rel) => rel !== THE_READER)
      .filter((rel) => readers(readFileSync(join(SRC, rel), 'utf8')) > 0)
      .sort();
    expect(offenders, 'read the host through requestHost() in lib/practice-host.ts — Host only, never X-Forwarded-Host').toEqual([]);
  });
});
