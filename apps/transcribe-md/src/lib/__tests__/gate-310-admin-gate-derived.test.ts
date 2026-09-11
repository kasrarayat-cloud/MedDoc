// @vitest-environment node
// ============================================================================
// RULING #310 — THE /admin GATE LIST IS DERIVED FROM THE FILESYSTEM.
// ----------------------------------------------------------------------------
// The behavioural arms (gate-310-admin-pages-behavioural / -data-behavioural)
// drive what exists today. This file is the one that reds on what somebody
// adds TOMORROW: it walks app/admin on disk (not git — an untracked page
// counts) and parses every file with the TypeScript compiler, then requires:
//
//   1. every page.* — its default export AND any other exported function
//      (generateMetadata, …) is async and its FIRST statement is
//      `await requireAdminPage()`, imported from app/admin/_lib/admin-gate;
//   2. the layout — the same;
//   3. every module in a `_lib` dir (except admin-gate itself) — every
//      exported async function's FIRST statement is
//      `await assertSuperAdminCaller()`, imported from the gate; a module that
//      touches the DB may export NO synchronous function and nothing whose
//      callability cannot be read off the AST (a `cache(...)`, a re-export);
//   4. nothing else under app/admin imports the DB / queue / redis directly,
//      carries 'use server' (a server action is a directly-POSTable door),
//      or is a Next special file (route, template, loading, …) nobody has
//      classified.
//
// "First statement", not "somewhere": the defect was a gate that existed and
// did not run first. The checker is proved able to say NO by the planted
// sources at the bottom — a guard that cannot fail is not a guard.
// ============================================================================
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import ts from 'typescript';
import { describe, expect, it } from 'vitest';

const SRC = join(__dirname, '..', '..');
const ADMIN = join(SRC, 'app', 'admin');
const GATE_MODULE = join(ADMIN, '_lib', 'admin-gate.ts');

const NEXT_SPECIAL = new Set([
  'route', 'template', 'loading', 'error', 'not-found', 'default', 'global-error',
  'forbidden', 'unauthorized', 'opengraph-image', 'twitter-image', 'icon',
  'apple-icon', 'sitemap', 'manifest', 'robots',
]);
const DATA_IMPORTS = ['@meddoc/db', '@/lib/queue', '@/lib/redis', '@prisma/client'];

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) {
      if (name === '__tests__' || name === 'node_modules') continue;
      out.push(...walk(p));
    } else if (/\.(tsx?|jsx?|mjs|cjs)$/.test(name)) out.push(p);
  }
  return out.sort();
}

const stem = (p: string) => p.replace(/\.(tsx?|jsx?|mjs|cjs)$/, '');

function resolveSpecifier(fromFile: string, spec: string): string | null {
  if (spec.startsWith('@/')) return join(SRC, spec.slice(2));
  if (spec.startsWith('.')) return resolve(dirname(fromFile), spec);
  return null;
}

type FnLike = ts.FunctionDeclaration | ts.FunctionExpression | ts.ArrowFunction;
interface ExportedFn { name: string; node: FnLike }

function isFnLike(n: ts.Node | undefined): n is FnLike {
  return !!n && (ts.isFunctionDeclaration(n) || ts.isFunctionExpression(n) || ts.isArrowFunction(n));
}
function isInertLiteral(n: ts.Expression | undefined): boolean {
  if (!n) return false;
  if (ts.isAsExpression(n) || ts.isSatisfiesExpression(n) || ts.isParenthesizedExpression(n)) {
    return isInertLiteral(n.expression);
  }
  return (
    ts.isObjectLiteralExpression(n) || ts.isArrayLiteralExpression(n) ||
    ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n) || ts.isNumericLiteral(n) ||
    n.kind === ts.SyntaxKind.TrueKeyword || n.kind === ts.SyntaxKind.FalseKeyword
  );
}
const hasMod = (n: ts.Node, k: ts.SyntaxKind) =>
  (ts.canHaveModifiers(n) ? ts.getModifiers(n) ?? [] : []).some((m) => m.kind === k);

/** Every exported function-like, plus the exports whose callability the AST cannot vouch for. */
function exportsOf(sf: ts.SourceFile): { fns: ExportedFn[]; unverifiable: string[]; localGateDecl: Set<string> } {
  const locals = new Map<string, FnLike>();
  const localVars = new Map<string, ts.Expression | undefined>();
  const localGateDecl = new Set<string>();
  for (const st of sf.statements) {
    if (ts.isFunctionDeclaration(st) && st.name) { locals.set(st.name.text, st); localGateDecl.add(st.name.text); }
    if (ts.isVariableStatement(st)) {
      for (const d of st.declarationList.declarations) {
        if (!ts.isIdentifier(d.name)) continue;
        localGateDecl.add(d.name.text);
        if (isFnLike(d.initializer)) locals.set(d.name.text, d.initializer);
        else localVars.set(d.name.text, d.initializer);
      }
    }
  }
  const fns: ExportedFn[] = [];
  const unverifiable: string[] = [];
  for (const st of sf.statements) {
    if (ts.isFunctionDeclaration(st) && hasMod(st, ts.SyntaxKind.ExportKeyword)) {
      fns.push({ name: hasMod(st, ts.SyntaxKind.DefaultKeyword) ? 'default' : st.name?.text ?? 'default', node: st });
    } else if (ts.isVariableStatement(st) && hasMod(st, ts.SyntaxKind.ExportKeyword)) {
      for (const d of st.declarationList.declarations) {
        const name = ts.isIdentifier(d.name) ? d.name.text : d.name.getText(sf);
        if (isFnLike(d.initializer)) fns.push({ name, node: d.initializer });
        else if (!isInertLiteral(d.initializer)) unverifiable.push(name);
      }
    } else if (ts.isExportAssignment(st)) {
      const e = st.expression;
      if (isFnLike(e)) fns.push({ name: 'default', node: e });
      else if (ts.isIdentifier(e) && locals.has(e.text)) fns.push({ name: 'default', node: locals.get(e.text)! });
      else unverifiable.push('default');
    } else if (ts.isExportDeclaration(st) && !st.isTypeOnly) {
      if (st.moduleSpecifier || !st.exportClause) { unverifiable.push(`re-export ${st.getText(sf)}`); continue; }
      if (ts.isNamedExports(st.exportClause)) {
        for (const s of st.exportClause.elements) {
          if (s.isTypeOnly) continue;
          const local = (s.propertyName ?? s.name).text;
          const exported = s.name.text;
          if (locals.has(local)) fns.push({ name: exported, node: locals.get(local)! });
          else if (localVars.has(local) && isInertLiteral(localVars.get(local))) continue;
          else if (localVars.has(local) || !isImportedName(sf, local)) unverifiable.push(exported);
          else unverifiable.push(`${exported} (re-exported import)`);
        }
      }
    }
  }
  return { fns, unverifiable, localGateDecl };
}

function isImportedName(sf: ts.SourceFile, name: string): boolean {
  return sf.statements.some(
    (st) => ts.isImportDeclaration(st) && !!st.importClause?.namedBindings &&
      ts.isNamedImports(st.importClause.namedBindings) &&
      st.importClause.namedBindings.elements.some((e) => e.name.text === name),
  );
}

/** Local identifiers bound to `gateName` imported from the gate module. */
function gateBindings(file: string, sf: ts.SourceFile, gateName: string): Set<string> {
  const out = new Set<string>();
  for (const st of sf.statements) {
    if (!ts.isImportDeclaration(st) || !ts.isStringLiteral(st.moduleSpecifier)) continue;
    const target = resolveSpecifier(file, st.moduleSpecifier.text);
    if (!target || stem(target) !== stem(GATE_MODULE)) continue;
    const nb = st.importClause?.namedBindings;
    if (st.importClause?.isTypeOnly || !nb || !ts.isNamedImports(nb)) continue;
    for (const e of nb.elements) {
      if (!e.isTypeOnly && (e.propertyName ?? e.name).text === gateName) out.add(e.name.text);
    }
  }
  return out;
}

function firstStatementIsGate(fn: FnLike, bound: Set<string>): boolean {
  if (!fn.body || !ts.isBlock(fn.body)) return false;
  const st = fn.body.statements[0];
  if (!st) return false;
  let expr: ts.Expression | undefined;
  if (ts.isExpressionStatement(st)) expr = st.expression;
  else if (ts.isVariableStatement(st) && st.declarationList.declarations.length === 1) {
    expr = st.declarationList.declarations[0].initializer;
  }
  if (!expr || !ts.isAwaitExpression(expr)) return false;
  const call = expr.expression;
  return (
    ts.isCallExpression(call) && ts.isIdentifier(call.expression) &&
    bound.has(call.expression.text) && call.arguments.length === 0
  );
}
const isAsync = (fn: FnLike) => hasMod(fn, ts.SyntaxKind.AsyncKeyword);

function importsOf(sf: ts.SourceFile): string[] {
  return sf.statements
    .filter((s): s is ts.ImportDeclaration => ts.isImportDeclaration(s) && ts.isStringLiteral(s.moduleSpecifier))
    .filter((s) => !s.importClause?.isTypeOnly)
    .map((s) => (s.moduleSpecifier as ts.StringLiteral).text);
}
function hasUseServer(sf: ts.SourceFile, text: string): boolean {
  return /['"]use server['"]/.test(text) &&
    (sf.statements.some((s) => ts.isExpressionStatement(s) && ts.isStringLiteral(s.expression) && s.expression.text === 'use server') ||
     /['"]use server['"]\s*;?/.test(text));
}

/** Returns the violations for one file. Pure, so the planted controls below can drive it. */
export function checkFile(file: string, text: string): string[] {
  const rel = relative(ADMIN, file);
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true,
    file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const base = stem(file.split('/').pop()!);
  const inLib = rel.split('/').includes('_lib');
  const v: string[] = [];

  if (hasUseServer(sf, text)) v.push(`${rel}: carries 'use server' — a server action is a directly-POSTable door; gate and classify it`);

  if (base === 'page' || base === 'layout') {
    const bound = gateBindings(file, sf, 'requireAdminPage');
    const { fns, unverifiable, localGateDecl } = exportsOf(sf);
    if (bound.size === 0) v.push(`${rel}: requireAdminPage is not imported from app/admin/_lib/admin-gate`);
    for (const b of bound) if (localGateDecl.has(b)) v.push(`${rel}: a local declaration shadows the gate '${b}'`);
    if (!fns.some((f) => f.name === 'default')) v.push(`${rel}: no default export function the checker can read`);
    for (const f of fns) {
      if (!isAsync(f.node)) v.push(`${rel}: export '${f.name}' is not async, so it cannot await the gate first`);
      else if (!firstStatementIsGate(f.node, bound)) v.push(`${rel}: export '${f.name}' — first statement is not \`await requireAdminPage()\``);
    }
    for (const u of unverifiable) v.push(`${rel}: export '${u}' cannot be verified from the AST`);
    return v;
  }

  if (NEXT_SPECIAL.has(base) && !inLib) {
    v.push(`${rel}: unclassified Next special file '${base}' under /admin — it is a render/handler entry the gate list does not cover`);
    return v;
  }

  if (inLib) {
    if (stem(file) === stem(GATE_MODULE)) return v; // the gate itself
    const imports = importsOf(sf);
    const touchesData = imports.some((i) => DATA_IMPORTS.includes(i)) || imports.includes('server-only');
    const bound = gateBindings(file, sf, 'assertSuperAdminCaller');
    const { fns, unverifiable, localGateDecl } = exportsOf(sf);
    for (const b of bound) if (localGateDecl.has(b)) v.push(`${rel}: a local declaration shadows the gate '${b}'`);
    for (const f of fns) {
      if (isAsync(f.node)) {
        if (!firstStatementIsGate(f.node, bound)) {
          v.push(`${rel}: export '${f.name}' — first statement is not \`await assertSuperAdminCaller()\``);
        }
      } else if (touchesData) {
        v.push(`${rel}: export '${f.name}' is synchronous in a module that reaches data — make it async and gate it`);
      }
    }
    if (touchesData) for (const u of unverifiable) v.push(`${rel}: export '${u}' cannot be verified from the AST`);
    return v;
  }

  // any other file under /admin
  const direct = importsOf(sf).filter((i) => DATA_IMPORTS.includes(i));
  if (direct.length && !text.startsWith("'use client'") && !text.startsWith('"use client"')) {
    v.push(`${rel}: imports ${direct.join(', ')} outside a gated _lib module`);
  }
  return v;
}

const FILES = walk(ADMIN);

describe('ruling #310 — derived /admin gate list', () => {
  it('the walk is not vacuous (positive control on the universe)', () => {
    const pages = FILES.filter((f) => stem(f.split('/').pop()!) === 'page');
    expect(pages.length).toBeGreaterThanOrEqual(6);
    let gatedHelpers = 0;
    for (const f of FILES.filter((x) => relative(ADMIN, x).split('/').includes('_lib'))) {
      if (stem(f) === stem(GATE_MODULE)) continue;
      const sf = ts.createSourceFile(f, readFileSync(f, 'utf8'), ts.ScriptTarget.Latest, true);
      gatedHelpers += exportsOf(sf).fns.filter((x) => isAsync(x.node)).length;
    }
    expect(gatedHelpers).toBeGreaterThanOrEqual(15);
    expect(FILES).toContain(join(ADMIN, 'layout.tsx'));
  });

  it('every page, the layout and every data function gates FIRST; nothing else reaches data', () => {
    const violations = FILES.flatMap((f) => checkFile(f, readFileSync(f, 'utf8')));
    expect(violations).toEqual([]);
  });
});

describe('ruling #310 — the checker can say NO (planted sources)', () => {
  const page = join(ADMIN, 'planted', 'page.tsx');
  const lib = join(ADMIN, 'planted', '_lib', 'planted-data.ts');
  const GATE_IMPORT_PAGE = "import { requireAdminPage } from '../_lib/admin-gate';\n";
  const GATE_IMPORT_LIB = "import 'server-only';\nimport { assertSuperAdminCaller } from '@/app/admin/_lib/admin-gate';\n";

  it.each([
    ['a page with no gate', 'export default async function P() { const d = await getData(); return d; }'],
    ['a page whose gate runs AFTER its data', GATE_IMPORT_PAGE + 'export default async function P() { const d = await getData(); await requireAdminPage(); return d; }'],
    ['a page whose gate is not awaited', GATE_IMPORT_PAGE + 'export default async function P() { requireAdminPage(); return await getData(); }'],
    ['a page calling a LOOK-ALIKE gate', "import { requireAdminPage } from './fake';\nexport default async function P() { await requireAdminPage(); return 1; }"],
    ['a page with an ungated generateMetadata', GATE_IMPORT_PAGE + 'export default async function P() { await requireAdminPage(); }\nexport async function generateMetadata() { return await getData(); }'],
    ['a synchronous page', GATE_IMPORT_PAGE + 'export default function P() { return null; }'],
  ])('reds on %s', (_label, src) => {
    expect(checkFile(page, src).length).toBeGreaterThan(0);
  });

  it.each([
    ['an ungated async helper', "import 'server-only';\nimport prisma from '@meddoc/db';\nexport async function leak() { return prisma.x.findMany(); }"],
    ['a helper whose gate runs AFTER its read', GATE_IMPORT_LIB + 'export async function leak() { const r = await read(); await assertSuperAdminCaller(); return r; }'],
    ['an async ARROW helper, ungated', "import 'server-only';\nexport const leak = async () => read();"],
    ['a cache()-wrapped export', "import 'server-only';\nexport const leak = cache(async () => read());"],
    ['a synchronous helper in a data module', "import prisma from '@meddoc/db';\nexport function leak() { return prisma.x.findMany(); }"],
    ['a re-export from elsewhere', "import 'server-only';\nexport { leak } from './elsewhere';"],
  ])('reds on %s', (_label, src) => {
    expect(checkFile(lib, src).length).toBeGreaterThan(0);
  });

  it.each([
    ['a route handler under /admin', join(ADMIN, 'planted', 'route.ts'), 'export async function GET() { return new Response(); }'],
    ['a server action under /admin', join(ADMIN, 'planted', 'actions.ts'), "'use server';\nexport async function act() {}"],
    ['a server component reaching the DB directly', join(ADMIN, 'planted', '_components', 'Panel.tsx'), "import prisma from '@meddoc/db';\nexport default async function Panel() { return null; }"],
  ])('reds on %s', (_label, file, src) => {
    expect(checkFile(file, src).length).toBeGreaterThan(0);
  });

  it('and passes the correctly-gated shapes (so a red above is about the defect, not the shape)', () => {
    expect(checkFile(page, GATE_IMPORT_PAGE + 'export default async function P() { const s = await requireAdminPage(); return s; }')).toEqual([]);
    expect(checkFile(lib, GATE_IMPORT_LIB + 'export async function ok() { await assertSuperAdminCaller(); return 1; }')).toEqual([]);
  });
});
