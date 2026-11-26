'use strict';
// Release 2 (RELEASE-2-SPEC R2-20; lane S, refutation rounds 1 and 2): every code point JavaScript's toLowerCase
// changes - the page's half of the search's lower-casing, which tests/test_lists.py compares with PostgreSQL's
// pg_c_utf8 over every code point. With no argument, node's own table: {"unicode": node's Unicode version, "icu": its
// ICU version, "lowered": {code point: [the code points it lower-cases to]}}. With --browsers (D-R2-42), the same table
// in each Chromium present on this host - the walk's own (ops/walk.cjs PLAYWRIGHT, launched as the walk launches it)
// and the newest build installed in Playwright's browser folder, when it is another build - each opened on a blank page
// with every request refused, then closed: {"engines": [{"name", "version", "lowered"}], "absent": [{"name", "why"}]}.
// An engine is absent only where Playwright or its build is not installed; any other failure exits 1. Writes to stdout
// only; reads nothing but Playwright's own files.
const fs = require('fs');
const os = require('os');
const path = require('path');

// Run by node and, serialised by page.evaluate, in each browser's page: it may use nothing from outside itself.
function lowerTable() {
  const lowered = {};
  for (let point = 1; point <= 0x10ffff; point += 1) {
    if (point >= 0xd800 && point <= 0xdfff) continue; // a lone surrogate is no letter
    const letter = String.fromCodePoint(point);
    const lower = letter.toLowerCase();
    if (lower !== letter) lowered[point] = Array.from(lower, piece => piece.codePointAt(0));
  }
  return lowered;
}

// Playwright's browser folder, found as Playwright finds it on Linux: PLAYWRIGHT_BROWSERS_PATH, else the user's cache.
// Its "0" keeps the browsers inside the Playwright package, where the walk's own build is the one there: null.
function browserFolder() {
  const named = process.env.PLAYWRIGHT_BROWSERS_PATH;
  if (named === '0') return null;
  if (named) return path.resolve(named);
  return path.join(process.env.XDG_CACHE_HOME || path.join(os.homedir(), '.cache'), 'ms-playwright');
}

// The newest Chromium build installed in `folder` whose installation completed: {revision, executable}, or null. Of
// one revision, its headless shell is taken before its full browser (the walk's headless launch takes the shell too).
const CHROMIUM_LAYOUTS = [
  [/^chromium_headless_shell-(\d+)$/, ['chrome-headless-shell-linux64', 'chrome-headless-shell'], 1],
  [/^chromium-(\d+)$/, ['chrome-linux64', 'chrome'], 0],
];
function newestChromium(folder) {
  let newest = null;
  for (const entry of fs.readdirSync(folder)) {
    for (const [pattern, parts, preferred] of CHROMIUM_LAYOUTS) {
      const match = pattern.exec(entry);
      if (!match) continue;
      const executable = path.join(folder, entry, ...parts);
      if (!fs.existsSync(path.join(folder, entry, 'INSTALLATION_COMPLETE')) || !fs.existsSync(executable)) continue;
      const revision = Number(match[1]);
      if (!newest || revision > newest.revision || (revision === newest.revision && preferred > newest.preferred)) {
        newest = { revision, executable, preferred };
      }
    }
  }
  return newest;
}

async function browserTable(chromium, options) {
  const browser = await chromium.launch({ headless: true, ...options });
  try {
    const page = await browser.newPage();
    await page.route('**/*', route => route.abort());
    return { version: browser.version(), lowered: await page.evaluate(lowerTable) };
  } finally {
    await browser.close();
  }
}

// Playwright's own sentence for a build that is not installed: the one launch failure read as absent.
const NOT_INSTALLED = "Executable doesn't exist";
const WALKS = "the walk's Chromium";
const NEWEST = 'the newest Chromium installed';

async function browserTables() {
  const { PLAYWRIGHT } = require(path.join(__dirname, '..', '..', 'ops', 'walk.cjs'));
  const engines = [];
  const absent = [];
  if (!fs.existsSync(path.join(PLAYWRIGHT, 'package.json'))) {
    absent.push({ name: WALKS, why: `no Playwright at ${PLAYWRIGHT}` });
    absent.push({ name: NEWEST, why: `no Playwright at ${PLAYWRIGHT} to open it` });
    return { engines, absent };
  }
  const { chromium } = require(PLAYWRIGHT);
  try {
    const table = await browserTable(chromium, {});
    engines.push({ name: `Chromium ${table.version} (the walk's)`, ...table });
  } catch (error) {
    const message = String((error && error.message) || error);
    if (!message.includes(NOT_INSTALLED)) throw error;
    absent.push({ name: WALKS, why: `not installed: ${message.split('\n')[0]}` });
  }
  const folder = browserFolder();
  const newest = folder && fs.existsSync(folder) ? newestChromium(folder) : null;
  if (!newest) {
    absent.push({ name: NEWEST, why: folder ? `no Chromium build installed in ${folder}`
      : "PLAYWRIGHT_BROWSERS_PATH is 0: the walk's own build is the one installed" });
    return { engines, absent };
  }
  const table = await browserTable(chromium, { executablePath: newest.executable });
  const same = engines.find(engine => engine.version === table.version);
  if (same) same.name = `Chromium ${table.version} (the walk's, and the newest installed)`;
  else engines.push({ name: `Chromium ${table.version} (the newest installed, build ${newest.revision})`, ...table });
  return { engines, absent };
}

if (process.argv[2] === '--browsers') {
  browserTables().then(found => process.stdout.write(JSON.stringify(found)), error => {
    process.stderr.write(`lower_table: ${(error && error.stack) || error}\n`);
    process.exitCode = 1;
  });
} else if (process.argv.length > 2) {
  process.stderr.write('usage: node tests/frontend/lower_table.cjs [--browsers]\n');
  process.exitCode = 2;
} else {
  process.stdout.write(JSON.stringify({ unicode: process.versions.unicode, icu: process.versions.icu,
    lowered: lowerTable() }));
}
