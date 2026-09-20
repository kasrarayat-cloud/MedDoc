import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {test} from 'node:test';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');

test('actual mutation wrapper cannot infer absence of effects from child exit status', async t => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'quillmd-wrapper-exit-'));
  const env = {PATH: process.env.PATH, HOME: process.env.HOME, LANG: 'C.UTF-8', RULED_ACT_POLL: '1', RULED_ACT_MAX_SECS: '15'};
  const command = (name, args) => spawnSync(name, args, {cwd: temp, env, encoding: 'utf8', timeout: 25000});
  const git = args => {
    const result = command('git', ['-c', 'core.hooksPath=/dev/null', '-c', 'user.name=Synthetic Test', '-c', 'user.email=wrapper@synthetic.quillmd.invalid', ...args]);
    assert.equal(result.status, 0, result.stderr);
  };
  try {
    await fs.mkdir(path.join(temp, 'scripts/lib'), {recursive: true});
    for (const name of ['scripts/run-ruled-mutation.sh', 'scripts/lib/declaration.sh', 'scripts/lib/run-watched.sh']) {
      await fs.copyFile(path.join(root, name), path.join(temp, name));
    }
    await fs.writeFile(path.join(temp, 'declaration.md'), '# Synthetic declaration\nOnly write this isolated temporary canary.\n');
    git(['init', '--quiet']); git(['add', 'declaration.md']); git(['commit', '--quiet', '-m', 'Synthetic declaration before local child']);
    const run = code => command('bash', ['scripts/run-ruled-mutation.sh', '--declaration', 'declaration.md', '--',
      'bash', '-c', 'printf written > "$1"; exit "$2"', 'synthetic-child', `canary-${code}`, String(code)]);
    await t.test('exit 2 after a real write requires inspection, never automatic rerun', async () => {
      const result = run(2);
      assert.equal(result.status, 2);
      assert.equal(await fs.readFile(path.join(temp, 'canary-2'), 'utf8'), 'written');
      assert.match(result.stdout, /EXIT 2/);
      assert.match(result.stdout, /Inspect the child.*evidence/);
      assert.match(result.stdout, /Do not automatically re-run/);
      assert.doesNotMatch(result.stdout, /REFUSED before acting|Nothing was opened|nothing was written|no partial state/);
    });
    await t.test('successful child remains exit zero', async () => {
      const result = run(0);
      assert.equal(result.status, 0); assert.equal(await fs.readFile(path.join(temp, 'canary-0'), 'utf8'), 'written');
      assert.doesNotMatch(result.stdout, /NON-ZERO EXIT|EXIT 2/);
    });
    await t.test('other failure still carries the partial-effects warning', async () => {
      const result = run(7);
      assert.equal(result.status, 7); assert.equal(await fs.readFile(path.join(temp, 'canary-7'), 'utf8'), 'written');
      assert.match(result.stdout, /NON-ZERO EXIT/); assert.match(result.stdout, /Do not re-run until you know what landed/);
    });
    await t.test('timeout status preserves the existing watchdog warning', async () => {
      const result = run(124);
      assert.equal(result.status, 124); assert.equal(await fs.readFile(path.join(temp, 'canary-124'), 'utf8'), 'written');
      assert.match(result.stdout, /WATCHDOG TIMEOUT/); assert.match(result.stdout, /NOT a verdict on the act/);
    });
    await t.test('modified declaration still refuses before opening the child', async () => {
      await fs.appendFile(path.join(temp, 'declaration.md'), 'Uncommitted modification.\n');
      const result = run(3);
      assert.equal(result.status, 1); assert.match(result.stdout, /committed but MODIFIED/);
      await assert.rejects(fs.stat(path.join(temp, 'canary-3')), {code: 'ENOENT'});
    });
  } finally {await fs.rm(temp, {recursive: true, force: true});}
});
