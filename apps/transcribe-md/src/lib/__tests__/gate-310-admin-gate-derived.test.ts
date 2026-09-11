// @vitest-environment node
// ============================================================================
// RULING #310 — THE /admin GATE LIST IS DERIVED FROM THE FILESYSTEM.
// ----------------------------------------------------------------------------
// The behavioural arms (gate-310-admin-pages-behavioural / -data-behavioural)
// drive what exists today. This file is the one that reds on what somebody
// adds TOMORROW: it walks ALL of src/app on disk (not git — an untracked page
// counts), keeps every file whose folder SERVES an /admin URL, and parses each
// with the TypeScript compiler, then requires:
//
//   1. every page.* — its default export AND any other exported function
//      (generateMetadata, …) is async and its FIRST statement is
//      `await requireAdminPage()`, imported from app/admin/_lib/admin-gate;
//   2. the layout — the same;
//   3. every module in a `_lib` dir, AND every SERVER module elsewhere in the
//      universe — every exported async function's FIRST statement is
//      `await assertSuperAdminCaller()`, imported from the gate; a module that
//      imports ANYTHING at runtime (a value import, a re-export, a dynamic
//      import()/require()) may export NO synchronous function and nothing
//      whose callability cannot be read off the AST (a `cache(...)`, a
//      re-export, an object/array/class holding a callable);
//   4. the gate module exports ITS OWN SURFACE and nothing else;
//   5. nothing else in the universe imports the DB / queue / redis directly
//      (statically OR dynamically), carries 'use server' (a server action is a
//      directly-POSTable door), or is a Next special file (route, template,
//      loading, …) nobody has classified.
//
// "First statement", not "somewhere": the defect was a gate that existed and
// did not run first. The checker is proved able to say NO by the planted
// sources at the bottom — a guard that cannot fail is not a guard.
//
// ⚠️ HARDENED AFTER THE FOUR-LENS PASS ON daaa379d. Twelve findings, all
// confirmed, all in this guard or its docs, none in the shipped gates. Seven
// were holes in this census, and each is closed below under a `FIX n` label
// with the finding's own planted source as an arm:
//   FIX 1  object literals / arrays / classes were waved through as "inert";
//   FIX 2  a shadowing binding was looked for at top level only;
//   FIX 3  a `_lib` module with neither 'server-only' nor a listed DB import
//          was never checked, and a server module outside `_lib` never was;
//   FIX 4  `import()` / `require()` of a data package was invisible;
//   FIX 5  the universe was the FOLDER app/admin, not the URL /admin, so a
//          route group, @slot or intercepting route escaped it;
//   FIX 6  'use client' was a text prefix, not a directive;
//   FIX 7  admin-gate.ts was exempt as a whole file.
// ============================================================================
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, isAbsolute, join, relative, resolve, sep } from 'node:path';
import { normalizeAppPath } from 'next/dist/shared/lib/router/utils/app-paths';
import {
  extractInterceptionRouteInformation,
  isInterceptionRouteAppPath,
} from 'next/dist/shared/lib/router/utils/interception-routes';
import ts from 'typescript';
import { describe, expect, it } from 'vitest';

const SRC = join(__dirname, '..', '..');
const APP_DIR = join(SRC, 'app');
const ADMIN = join(APP_DIR, 'admin');
const GATE_MODULE = join(ADMIN, '_lib', 'admin-gate.ts');

const NEXT_SPECIAL = new Set([
  'route', 'template', 'loading', 'error', 'not-found', 'default', 'global-error',
  'forbidden', 'unauthorized', 'opengraph-image', 'twitter-image', 'icon',
  'apple-icon', 'sitemap', 'manifest', 'robots',
]);
const DATA_IMPORTS = ['@meddoc/db', '@/lib/queue', '@/lib/redis', '@prisma/client'];
/** FIX 4 — an import()/require() whose specifier is not a literal could load anything. */
const NONLITERAL = '<non-literal specifier>';
const isDataSpecifier = (i: string) =>
  i === NONLITERAL || DATA_IMPORTS.some((d) => i === d || i.startsWith(`${d}/`));

/**
 * FIX 7 — the gate module's own value surface, read off admin-gate.ts on
 * 2026-09-11. It is exempt from the helper rule because readAdminVerdict reads
 * the CALLER's own row, ungated by design; nothing else may park there.
 */
const GATE_SURFACE = new Set([
  'readAdminVerdict',
  'requireAdminPage',
  'assertSuperAdminCaller',
  'SUPER_ADMIN_MFA_REDIRECT',
  'AdminAccessDeniedError',
]);

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

/**
 * FIX 5 — is this file inside the /admin URL space? Asked of Next's OWN
 * normaliser: route groups `(x)` and `@slots` fold away, and an intercepting
 * folder `(..)admin` counts for the route it intercepts. A folder Next itself
 * cannot resolve fails CLOSED (it is checked).
 */
export function inAdminUniverse(file: string): boolean {
  const relDir = relative(APP_DIR, dirname(file));
  if (relDir === '..' || relDir.startsWith(`..${sep}`) || isAbsolute(relDir)) return false;
  const appPath = relDir === '' ? '/' : `/${relDir.split(sep).join('/')}`;
  const urls = [normalizeAppPath(appPath)];
  if (isInterceptionRouteAppPath(appPath)) {
    try {
      urls.push(extractInterceptionRouteInformation(appPath).interceptedRoute);
    } catch {
      return true;
    }
  }
  return urls.some((u) => u === '/admin' || u.startsWith('/admin/'));
}

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
  // FIX 1 — a container is inert only if everything in it is: a method, an
  // accessor, a shorthand, a spread or a function-valued property is not.
  if (ts.isArrayLiteralExpression(n)) return n.elements.every((e) => isInertLiteral(e));
  if (ts.isObjectLiteralExpression(n)) {
    return n.properties.every((p) => ts.isPropertyAssignment(p) && isInertLiteral(p.initializer));
  }
  return (
    ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n) || ts.isNumericLiteral(n) ||
    n.kind === ts.SyntaxKind.TrueKeyword || n.kind === ts.SyntaxKind.FalseKeyword
  );
}
const hasMod = (n: ts.Node, k: ts.SyntaxKind) =>
  (ts.canHaveModifiers(n) ? ts.getModifiers(n) ?? [] : []).some((m) => m.kind === k);

/** Every exported function-like, plus the exports whose callability the AST cannot vouch for. */
function exportsOf(sf: ts.SourceFile): { fns: ExportedFn[]; unverifiable: string[] } {
  const locals = new Map<string, FnLike>();
  const localVars = new Map<string, ts.Expression | undefined>();
  for (const st of sf.statements) {
    if (ts.isFunctionDeclaration(st) && st.name) locals.set(st.name.text, st);
    if (ts.isVariableStatement(st)) {
      for (const d of st.declarationList.declarations) {
        if (!ts.isIdentifier(d.name)) continue;
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
    } else if (ts.isClassDeclaration(st) && hasMod(st, ts.SyntaxKind.ExportKeyword)) {
      // FIX 1 — a class holds callables the first-statement rule cannot see.
      unverifiable.push(`class ${hasMod(st, ts.SyntaxKind.DefaultKeyword) ? 'default' : st.name?.text ?? 'default'}`);
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
  return { fns, unverifiable };
}

/** FIX 7 — every name a module exports as a VALUE (a re-export from elsewhere is named by its text). */
function valueExportNames(sf: ts.SourceFile): string[] {
  const out: string[] = [];
  for (const st of sf.statements) {
    const exported = hasMod(st, ts.SyntaxKind.ExportKeyword);
    if (exported && (ts.isFunctionDeclaration(st) || ts.isClassDeclaration(st) ||
        ts.isEnumDeclaration(st) || ts.isModuleDeclaration(st))) {
      out.push(hasMod(st, ts.SyntaxKind.DefaultKeyword) || !st.name ? 'default' : st.name.getText(sf));
    } else if (exported && ts.isVariableStatement(st)) {
      for (const d of st.declarationList.declarations) out.push(d.name.getText(sf));
    } else if (exported && ts.isImportEqualsDeclaration(st)) {
      out.push(st.name.text);
    } else if (ts.isExportAssignment(st)) {
      out.push('default');
    } else if (ts.isExportDeclaration(st) && !st.isTypeOnly) {
      if (st.moduleSpecifier || !st.exportClause) { out.push(`re-export ${st.getText(sf)}`); continue; }
      if (ts.isNamedExports(st.exportClause)) {
        for (const s of st.exportClause.elements) if (!s.isTypeOnly) out.push(s.name.text);
      }
    }
  }
  return out;
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

/** The identifier a node BINDS, for every construct that introduces a value binding. */
function bindingNameOf(n: ts.Node): ts.Identifier | undefined {
  if (
    ts.isParameter(n) || ts.isVariableDeclaration(n) || ts.isBindingElement(n) ||
    ts.isFunctionDeclaration(n) || ts.isFunctionExpression(n) ||
    ts.isClassDeclaration(n) || ts.isClassExpression(n) ||
    ts.isEnumDeclaration(n) || ts.isModuleDeclaration(n) ||
    ts.isImportEqualsDeclaration(n) || ts.isNamespaceImport(n) ||
    ts.isImportClause(n) || ts.isImportSpecifier(n)
  ) {
    const nm = (n as { name?: ts.Node }).name;
    return nm && ts.isIdentifier(nm) ? nm : undefined;
  }
  return undefined;
}
function isTheGateImport(file: string, n: ts.Node, gateName: string): boolean {
  if (!ts.isImportSpecifier(n)) return false;
  const decl = n.parent.parent.parent;
  if (!ts.isImportDeclaration(decl) || !ts.isStringLiteral(decl.moduleSpecifier)) return false;
  const target = resolveSpecifier(file, decl.moduleSpecifier.text);
  return !!target && stem(target) === stem(GATE_MODULE) && (n.propertyName ?? n.name).text === gateName;
}
/**
 * FIX 2 — every binding of a gate name ANYWHERE in the file other than the
 * gate import itself: a parameter or its default, a destructured parameter,
 * a hoisted inner function, a block-scoped or catch binding, a class, a
 * second import. `firstStatementIsGate` matches identifier TEXT, so any such
 * binding would turn `await assertSuperAdminCaller()` into a call to it.
 */
function shadowsOf(file: string, sf: ts.SourceFile, bound: Set<string>, gateName: string): string[] {
  const hits: string[] = [];
  const visit = (n: ts.Node): void => {
    const name = bindingNameOf(n);
    if (name && bound.has(name.text) && !isTheGateImport(file, n, gateName)) {
      hits.push(`${name.text}' at line ${sf.getLineAndCharacterOfPosition(name.getStart(sf)).line + 1}`);
    }
    ts.forEachChild(n, visit);
  };
  visit(sf);
  return hits;
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

/** Every module this file reaches at runtime: static imports, value re-exports, import(), require(). */
function importsOf(sf: ts.SourceFile): string[] {
  const out: string[] = [];
  for (const s of sf.statements) {
    if (ts.isImportDeclaration(s) && ts.isStringLiteral(s.moduleSpecifier) && !s.importClause?.isTypeOnly) {
      out.push(s.moduleSpecifier.text);
    }
    if (ts.isExportDeclaration(s) && !s.isTypeOnly && s.moduleSpecifier && ts.isStringLiteral(s.moduleSpecifier)) {
      out.push(s.moduleSpecifier.text);
    }
  }
  // FIX 4 — dynamic import(), require() and `import x = require()` anywhere in
  // the file (the old layout read the DB through `await import('@meddoc/db')`);
  // a non-literal specifier fails closed.
  const visit = (n: ts.Node): void => {
    if (ts.isImportEqualsDeclaration(n) && !n.isTypeOnly && ts.isExternalModuleReference(n.moduleReference)) {
      const e = n.moduleReference.expression;
      out.push(ts.isStringLiteralLike(e) ? e.text : NONLITERAL);
    } else if (
      ts.isCallExpression(n) &&
      (n.expression.kind === ts.SyntaxKind.ImportKeyword ||
        (ts.isIdentifier(n.expression) && n.expression.text === 'require'))
    ) {
      const a = n.arguments[0];
      out.push(a && ts.isStringLiteralLike(a) ? a.text : NONLITERAL);
    }
    ts.forEachChild(n, visit);
  };
  visit(sf);
  return out;
}
function hasUseServer(sf: ts.SourceFile, text: string): boolean {
  return /['"]use server['"]/.test(text) &&
    (sf.statements.some((s) => ts.isExpressionStatement(s) && ts.isStringLiteral(s.expression) && s.expression.text === 'use server') ||
     /['"]use server['"]\s*;?/.test(text));
}
/**
 * FIX 6 — a REAL directive: part of the prologue (the leading run of
 * string-literal expression statements). `'use client'.length;` is an
 * expression, not a directive, and the module it opens is a server module.
 * The raw text is compared, so an escaped spelling fails closed.
 */
function hasDirective(sf: ts.SourceFile, d: string): boolean {
  for (const s of sf.statements) {
    if (!ts.isExpressionStatement(s) || !ts.isStringLiteral(s.expression)) break;
    if (s.expression.getText(sf).slice(1, -1) === d) return true;
  }
  return false;
}

/** Rule 3 — for every `_lib` module, and (FIX 3) every server module outside `_lib`. */
function dataModuleRules(file: string, sf: ts.SourceFile, rel: string): string[] {
  const v: string[] = [];
  const imports = importsOf(sf);
  // FIX 3 — reaching ANY module at runtime counts, not just the four listed
  // packages or 'server-only': a re-export or a sync wrapper around an
  // ungated reader in src/lib is the same leak. A module with no runtime
  // imports at all (admin-format.ts: one `import type`) is pure.
  const touchesData = imports.length > 0;
  const bound = gateBindings(file, sf, 'assertSuperAdminCaller');
  for (const s of shadowsOf(file, sf, bound, 'assertSuperAdminCaller')) {
    v.push(`${rel}: a declaration of '${s} shadows the gate — the call would not reach admin-gate`);
  }
  const { fns, unverifiable } = exportsOf(sf);
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

/** Returns the violations for one file. Pure, so the planted controls below can drive it. */
export function checkFile(file: string, text: string): string[] {
  // FIX 5 — the universe is the URL Next serves, not the folder name.
  if (!inAdminUniverse(file)) return [];
  const rel = relative(APP_DIR, file);
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true,
    file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const base = stem(file.split('/').pop()!);
  const inLib = rel.split(sep).includes('_lib');
  const v: string[] = [];

  if (hasUseServer(sf, text)) v.push(`${rel}: carries 'use server' — a server action is a directly-POSTable door; gate and classify it`);

  if (base === 'page' || base === 'layout') {
    const bound = gateBindings(file, sf, 'requireAdminPage');
    const { fns, unverifiable } = exportsOf(sf);
    if (bound.size === 0) v.push(`${rel}: requireAdminPage is not imported from app/admin/_lib/admin-gate`);
    for (const s of shadowsOf(file, sf, bound, 'requireAdminPage')) {
      v.push(`${rel}: a declaration of '${s} shadows the gate — the call would not reach admin-gate`);
    }
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

  if (inLib && stem(file) === stem(GATE_MODULE)) {
    // FIX 7 — exempt from the helper rule for its OWN surface only.
    for (const n of valueExportNames(sf)) {
      if (!GATE_SURFACE.has(n)) v.push(`${rel}: the gate module exports '${n}' — only the gate's own surface may live here; move it to a gated _lib module`);
    }
    return v;
  }

  if (inLib) return [...v, ...dataModuleRules(file, sf, rel)];

  // any other file in the universe
  if (hasDirective(sf, 'use client')) return v; // a client module: bundled for the browser, holds no server data
  const direct = importsOf(sf).filter(isDataSpecifier);
  if (direct.length) v.push(`${rel}: imports ${direct.join(', ')} outside a gated _lib module`);
  // FIX 3 — a SERVER module outside `_lib` is held to the same data-module
  // rules: gate it, move it into `_lib`, or make it 'use client'.
  v.push(...dataModuleRules(file, sf, rel));
  return v;
}

const FILES = walk(APP_DIR);
const ADMIN_FILES = FILES.filter(inAdminUniverse);

describe('ruling #310 — derived /admin gate list', () => {
  it('the walk is not vacuous (positive control on the universe)', () => {
    const pages = ADMIN_FILES.filter((f) => stem(f.split('/').pop()!) === 'page');
    expect(pages.length).toBeGreaterThanOrEqual(6);
    let gatedHelpers = 0;
    for (const f of ADMIN_FILES.filter((x) => relative(APP_DIR, x).split(sep).includes('_lib'))) {
      if (stem(f) === stem(GATE_MODULE)) continue;
      const sf = ts.createSourceFile(f, readFileSync(f, 'utf8'), ts.ScriptTarget.Latest, true);
      gatedHelpers += exportsOf(sf).fns.filter((x) => isAsync(x.node)).length;
    }
    expect(gatedHelpers).toBeGreaterThanOrEqual(15);
    expect(ADMIN_FILES).toContain(join(ADMIN, 'layout.tsx'));
    expect(ADMIN_FILES).toContain(GATE_MODULE);
  });

  it('FIX 5 — the walk covers all of src/app, and the URL scope does work in BOTH directions', () => {
    // every file under the app/admin folder is inside the /admin URL space …
    expect(walk(ADMIN).filter((f) => !ADMIN_FILES.includes(f))).toEqual([]);
    // … the walk really left that folder (it reached /api/admin/*) …
    const apiAdmin = FILES.filter((f) => relative(APP_DIR, f).startsWith(`api${sep}admin${sep}`));
    expect(apiAdmin.length, 'the walk never left app/admin — a vacuous src/app').toBeGreaterThanOrEqual(10);
    // … and /api/admin/* serves /api/admin, not /admin, so it is outside.
    expect(apiAdmin.filter(inAdminUniverse)).toEqual([]);
  });

  it('every page, the layout and every data function gates FIRST; nothing else reaches data', () => {
    const violations = ADMIN_FILES.flatMap((f) => checkFile(f, readFileSync(f, 'utf8')));
    expect(violations).toEqual([]);
  });

  it('FIX 7 — the gate module exports exactly its known surface today', () => {
    const sf = ts.createSourceFile(GATE_MODULE, readFileSync(GATE_MODULE, 'utf8'), ts.ScriptTarget.Latest, true);
    expect(valueExportNames(sf).sort()).toEqual([...GATE_SURFACE].sort());
  });
});

describe('ruling #310 — the checker can say NO (planted sources)', () => {
  const page = join(ADMIN, 'planted', 'page.tsx');
  const lib = join(ADMIN, 'planted', '_lib', 'planted-data.ts');
  const comp = join(ADMIN, 'planted', '_components', 'Panel.tsx');
  const GATE_IMPORT_PAGE = "import { requireAdminPage } from '../_lib/admin-gate';\n";
  const GATE_IMPORT_LIB = "import 'server-only';\nimport { assertSuperAdminCaller } from '@/app/admin/_lib/admin-gate';\n";
  const DB = "import 'server-only';\nimport prisma from '@meddoc/db';\n";
  const GATE_TEXT = readFileSync(GATE_MODULE, 'utf8');

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
    ['a TOP-LEVEL declaration shadowing the gate', GATE_IMPORT_LIB + 'const assertSuperAdminCaller = async () => {};\nexport async function leak() { await assertSuperAdminCaller(); return read(); }'],
  ])('reds on %s', (_label, src) => {
    expect(checkFile(lib, src).length).toBeGreaterThan(0);
  });

  it.each([
    ['a route handler under /admin', join(ADMIN, 'planted', 'route.ts'), 'export async function GET() { return new Response(); }'],
    ['a server action under /admin', join(ADMIN, 'planted', 'actions.ts'), "'use server';\nexport async function act() {}"],
    ['a server component reaching the DB directly', comp, "import prisma from '@meddoc/db';\nexport default async function Panel() { return null; }"],
  ])('reds on %s', (_label, file, src) => {
    expect(checkFile(file, src).length).toBeGreaterThan(0);
  });

  // ── FIX 1 — rsc:bypass finding 1: objects, arrays and classes hold callables ──
  it.each([
    ['an object literal with a method (the finding)', DB + 'export const adminQueries = { async findings() { return (prisma as any).hipaaFinding.findMany(); } };'],
    ['an object literal with an async arrow property (the finding)', DB + 'export const adminQueries = { findings: async () => (prisma as any).hipaaFinding.findMany() };'],
    ['an exported class with a static method (the finding)', DB + 'export class AdminQueries { static async findings() { return (prisma as any).hipaaFinding.findMany(); } }'],
    ['an object literal under `satisfies`', DB + 'export const q = { async f() { return prisma.x.findMany(); } } satisfies Record<string, unknown>;'],
    ['an array of async arrows', DB + 'export const qs = [async () => prisma.x.findMany()];'],
    ['a local object exported by name', DB + 'const q = { async f() { return prisma.x.findMany(); } };\nexport { q };'],
    ['an `export default class`', DB + 'export default class { async f() { return prisma.x.findMany(); } }'],
  ])('FIX 1 — reds on %s', (_label, src) => {
    expect(checkFile(lib, src).length).toBeGreaterThan(0);
  });

  // ── FIX 2 — rsc:bypass finding 2a / rsc:falsegreen B4: shadowing anywhere ──
  it.each([
    ['a parameter default named like the gate (the finding)', lib, GATE_IMPORT_LIB + "import prisma from '@meddoc/db';\nexport async function findings(assertSuperAdminCaller = async () => {}) { await assertSuperAdminCaller(); return (prisma as any).hipaaFinding.findMany(); }"],
    ['a hoisted inner function named like the gate (B4 / B4c)', lib, GATE_IMPORT_LIB + "import prisma from '@meddoc/db';\nexport async function findings() { await assertSuperAdminCaller(); return prisma.hipaaFinding.findMany(); async function assertSuperAdminCaller() {} }"],
    ['a destructured parameter named like the gate', lib, GATE_IMPORT_LIB + 'export async function findings({ assertSuperAdminCaller = async () => {} } = {}) { await assertSuperAdminCaller(); return read(); }'],
    ['a block-scoped binding of the gate name', lib, GATE_IMPORT_LIB + 'export async function findings() { await assertSuperAdminCaller(); if (flag) { const assertSuperAdminCaller = () => {}; void assertSuperAdminCaller; } return read(); }'],
    ['a catch binding of the gate name', lib, GATE_IMPORT_LIB + 'export async function findings() { await assertSuperAdminCaller(); try { return read(); } catch (assertSuperAdminCaller) { return null; } }'],
    ['a page whose parameter shadows requireAdminPage', page, GATE_IMPORT_PAGE + 'export default async function P(requireAdminPage = async () => ({})) { await requireAdminPage(); return getData(); }'],
  ])('FIX 2 — reds on %s', (_label, file, src) => {
    expect(checkFile(file, src).length).toBeGreaterThan(0);
  });

  // ── FIX 3 — rsc:falsegreen B2 + rsc:bypass finding 2b: no server-only, no listed import ──
  it.each([
    ['a re-export pair with NO server-only line (B2, the finding)', lib, "export { GET as fetchHipaaRaw } from '@/app/api/admin/hipaa/route';\nexport { isAdminSessionStale as leak2 } from '@/lib/admin-session-freshness';"],
    ['a re-exported import with NO server-only line', lib, "import { isAdminSessionStale } from '@/lib/admin-session-freshness';\nexport { isAdminSessionStale as leak };"],
    ['a sync wrapper with NO server-only line', lib, "import { isAdminSessionStale } from '@/lib/admin-session-freshness';\nexport function leak(id: string) { return isAdminSessionStale(id); }"],
    ['an `export *` with NO server-only line', lib, "export * from '@/lib/admin-session-freshness';"],
    ['a cache()-wrapped reader with NO server-only line', lib, "import { cache } from 'react';\nimport { isAdminSessionStale } from '@/lib/admin-session-freshness';\nexport const leak = cache(isAdminSessionStale);"],
    ['a server-only module OUTSIDE _lib (the finding: _server/q.ts)', join(ADMIN, 'planted', '_server', 'q.ts'), "import 'server-only';\nimport { getAllFindings } from '@/lib/some-ungated';\nexport async function q() { return getAllFindings(); }"],
    ['a server component OUTSIDE _lib via a non-listed import', comp, "import { getAllFindings } from '@/lib/some-ungated';\nexport default async function Panel() { const rows = await getAllFindings(); return rows; }"],
  ])('FIX 3 — reds on %s', (_label, file, src) => {
    expect(checkFile(file, src).length).toBeGreaterThan(0);
  });

  // ── FIX 4 — rsc:falsegreen B3: import() / require() of a data package ──
  it.each([
    ['a sync _lib export over `import(\'@meddoc/db\')` (B3, the finding)', join(ADMIN, 'audit', '_lib', 'audit-data.ts'), "export function getFindings(){ return import('@meddoc/db').then(m => m.default.hipaaFinding.findMany()); }"],
    ['a server component awaiting `import(\'@meddoc/db\')` (B3b, the finding)', join(ADMIN, '_components', 'FindingsPanel.tsx'), "export default async function FindingsPanel(){ const prisma = (await import('@meddoc/db')).default; const rows = await prisma.hipaaFinding.findMany(); return <pre>{JSON.stringify(rows)}</pre>; }"],
    ['a `require(\'@meddoc/db\')` in a component', comp, "const prisma = require('@meddoc/db').default;\nexport default function Panel() { return prisma; }"],
    ['an `import x = require(\'@meddoc/db\')`', comp, "import prisma = require('@meddoc/db');\nexport default function Panel() { return prisma; }"],
    ['a NON-LITERAL import() specifier fails closed', lib, 'export function load(m: string) { return import(m); }'],
  ])('FIX 4 — reds on %s', (_label, file, src) => {
    expect(checkFile(file, src).length).toBeGreaterThan(0);
  });

  // ── FIX 5 — rsc:falsegreen B1 / B1b: the /admin URL outside the app/admin folder ──
  const UNGATED_PAGE = "import prisma from '@meddoc/db'; export const dynamic='force-dynamic'; export default async function OpsAudit(){ const rows = await prisma.hipaaFinding.findMany(); return <pre>{JSON.stringify(rows)}</pre>; }";
  it.each([
    ['a route-group page serving /admin/audit (B1, the finding)', join(APP_DIR, '(ops)', 'admin', 'audit', 'page.tsx'), UNGATED_PAGE],
    ['an intercepting page for /admin/hipaa (B1b, the finding)', join(APP_DIR, 'dashboard', '(..)admin', 'hipaa', 'page.tsx'), UNGATED_PAGE],
    ['a root-intercepting page for /admin', join(APP_DIR, '(.)admin', 'page.tsx'), UNGATED_PAGE],
    ['an @slot page serving /admin/x', join(APP_DIR, '@ops', 'admin', 'x', 'page.tsx'), UNGATED_PAGE],
    ['a route handler in a group serving /admin/export', join(APP_DIR, '(ops)', 'admin', 'export', 'route.ts'), 'export async function GET() { return new Response(); }'],
    ['an ungated _lib helper in a group under /admin', join(APP_DIR, '(ops)', 'admin', '_lib', 'leak.ts'), DB + 'export async function leak() { return prisma.x.findMany(); }'],
  ])('FIX 5 — reds on %s', (_label, file, src) => {
    expect(checkFile(file, src).length).toBeGreaterThan(0);
  });

  // ── FIX 6 — rsc:falsegreen B8: 'use client' as text, not a directive ──
  it.each([
    ["`'use client'.length;` (B8, the finding)", "'use client'.length;\nimport prisma from '@meddoc/db';\nexport default async function Panel(){ return <pre>{JSON.stringify(await prisma.hipaaFinding.findMany())}</pre>; }"],
    ["`\"use client\" + '';`", "\"use client\" + '';\nimport prisma from '@meddoc/db';\nexport default function Panel() { return prisma; }"],
    ["`'use client'` then `(0)` (ASI makes it a call)", "'use client'\n(0);\nimport prisma from '@meddoc/db';\nexport default function Panel() { return prisma; }"],
  ])('FIX 6 — reds on %s', (_label, src) => {
    expect(checkFile(comp, src).length).toBeGreaterThan(0);
  });

  // ── FIX 7 — rsc:falsegreen B5: a data export parked in the gate module ──
  it.each([
    ['an ungated async export (B5, the finding)', '\nexport async function listFindingsForBanner() { return prisma.hipaaFinding.findMany(); }\n'],
    ['a synchronous export', '\nexport function leakSync() { return prisma.hipaaFinding.findMany(); }\n'],
    ['a cache()-wrapped export', '\nexport const leakCached = cache(async () => prisma.hipaaFinding.findMany());\n'],
    ['a re-export from a data module', "\nexport { getAllFindings } from '../hipaa/_lib/hipaa-data';\n"],
    ['an `export *`', "\nexport * from '../hipaa/_lib/hipaa-data';\n"],
    ['a default export', '\nexport default async function leak() { return prisma.hipaaFinding.findMany(); }\n'],
  ])('FIX 7 — reds on the REAL gate module plus %s', (_label, extra) => {
    expect(checkFile(GATE_MODULE, GATE_TEXT + extra).length).toBeGreaterThan(0);
  });

  it('and passes the correctly-gated shapes (so a red above is about the defect, not the shape)', () => {
    expect(checkFile(page, GATE_IMPORT_PAGE + 'export default async function P() { const s = await requireAdminPage(); return s; }')).toEqual([]);
    expect(checkFile(lib, GATE_IMPORT_LIB + 'export async function ok() { await assertSuperAdminCaller(); return 1; }')).toEqual([]);
    // FIX 1 — a container of literals is still inert, even in a data module
    expect(checkFile(lib, DB + "export const LABELS = { a: 'x', n: [1, 2], deep: { on: true } } as const;")).toEqual([]);
    // FIX 3 — a pure module (no runtime import) may export sync helpers and literals
    expect(checkFile(lib, "import type { HipaaFinding } from '../_types';\nexport function fmt(n: number) { return String(n); }\nexport const LABEL = { a: 1 };")).toEqual([]);
    // FIX 3 — a gated server module outside _lib passes
    expect(checkFile(join(ADMIN, 'planted', '_server', 'q.ts'), GATE_IMPORT_LIB + "import { getAllFindings } from '@/lib/some-ungated';\nexport async function q() { await assertSuperAdminCaller(); return getAllFindings(); }")).toEqual([]);
    // FIX 4 — a real client module making an unrelated dynamic import
    expect(checkFile(comp, "'use client';\nconst Chart = import('./Chart');\nexport default function Panel() { return Chart; }")).toEqual([]);
    // FIX 5 — a correctly-gated page in a route group passes, and a page whose
    // URL is NOT /admin is outside this census (other gates own it)
    expect(checkFile(join(APP_DIR, '(ops)', 'admin', 'audit', 'page.tsx'), "import { requireAdminPage } from '@/app/admin/_lib/admin-gate';\nexport default async function P() { await requireAdminPage(); return 1; }")).toEqual([]);
    expect(checkFile(join(APP_DIR, 'dashboard', 'page.tsx'), UNGATED_PAGE)).toEqual([]);
    expect(checkFile(join(APP_DIR, 'api', 'admin', 'x', 'route.ts'), 'export async function GET() { return new Response(); }')).toEqual([]);
    // FIX 6 — a real directive exempts, in either quote style and after a comment
    for (const head of ["'use client';", '"use client";', "// a comment\n'use client';"]) {
      expect(checkFile(comp, head + "\nimport prisma from '@meddoc/db';\nexport default function Panel() { return prisma; }")).toEqual([]);
    }
    // FIX 7 — the real gate module passes as it stands
    expect(checkFile(GATE_MODULE, GATE_TEXT)).toEqual([]);
  });
});
