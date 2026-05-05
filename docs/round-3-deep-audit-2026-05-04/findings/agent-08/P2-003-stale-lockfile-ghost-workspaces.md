---
id: A08-P2-003
title: Lockfile carries 51 extraneous packages and references a deleted workspace (apps/scribe)
severity: P2
domain: dependency-hygiene-supply-chain
status: open
---

## Issue

`package-lock.json` and `node_modules/` are out of sync with the actual workspace
manifests. Two distinct symptoms:

1. **`apps/scribe` ghost workspace**: the lockfile still has an `apps/scribe` entry with
   its own dependency tree, but the directory does not exist on disk.
2. **51 extraneous packages** in `node_modules/` — almost all are `@react-three/*`,
   `three`, and the surrounding 3D/WebGL ecosystem (`troika-*`, `meshline`, `hls.js`,
   `detect-gpu`, etc.). The current `apps/marketing/package.json` and
   `apps/transcribe-md/package.json` do **not** declare any of them. They appear in the
   stale `apps/marketing/.next/standalone/apps/marketing/package.json` (last touched
   May 3) and `apps/transcribe-md/.next/standalone/apps/transcribe-md/package.json`
   (May 2), suggesting they were declared in a prior build that has since been pruned.

## Evidence

Ghost workspace:

```bash
$ ls /opt/meddoc-pro/apps/scribe
ls: cannot access '/opt/meddoc-pro/apps/scribe': No such file or directory

$ python3 -c "import json; d=json.load(open('/opt/meddoc-pro/package-lock.json'));
              print(d['packages'].get('apps/scribe', {}).get('extraneous'),
                    list(d['packages']['apps/scribe']['dependencies'])[:6])"
True ['@meddoc/ai', '@meddoc/auth', '@meddoc/db', '@meddoc/types', '@prisma/adapter-pg', '@prisma/client']
```

Extraneous count + sample:

```bash
$ cd /opt/meddoc-pro && npm ls --workspaces --all 2>&1 | grep "extraneous" | wc -l
51

$ npm ls --workspaces --all 2>&1 | grep extraneous | head -10
├─┬ @emnapi/core@1.10.0 extraneous
├─┬ @emnapi/runtime@1.10.0 extraneous
├── @mediapipe/tasks-vision@0.10.17 extraneous
├─┬ @react-three/drei@10.7.7 extraneous
├─┬ @react-three/fiber@9.6.0 extraneous
├── @tweenjs/tween.js@23.1.3 extraneous
├─┬ @types/three@0.169.0 extraneous
├── @use-gesture/core@10.3.1 extraneous
├── camera-controls@3.1.2 extraneous
├── cross-env@7.0.3 extraneous
```

Stale standalone build manifests (the proximate cause):

```bash
$ ls -la apps/marketing/.next/standalone/apps/marketing/package.json \
         apps/transcribe-md/.next/standalone/apps/transcribe-md/package.json
-rw-rw-r-- 1 ... 861 May  3 06:06 apps/marketing/.next/standalone/...
-rw-rw-r-- 1 ... 2241 May  2 18:34 apps/transcribe-md/.next/standalone/...

$ cat apps/marketing/.next/standalone/apps/marketing/package.json | grep three
    "@react-three/drei": "^10.7.7",
    "@react-three/fiber": "^9.6.0",
    "three": "^0.169.0"
    "@types/three": "^0.169.0",
```

(Source `apps/marketing/package.json` from Apr 19 has none of these.)

## Risk

- **Reproducibility**: `npm ci` on a fresh checkout of this lockfile would attempt to
  resolve `apps/scribe` and either fail (newer npm versions are stricter) or produce a
  different `node_modules/` than the current VPS has.
- **Audit confusion**: 51 unaccounted-for packages in `node_modules/` (including a heavy
  3D/WebGL stack — `three`, `@react-three/drei`, `@mediapipe/tasks-vision`) look alarming
  to a security reviewer. "Why does a medical-transcription app ship a WebGL physics engine?"
  is the question we don't want to spend an hour answering. (Answer: it doesn't — they're
  ghosts from an earlier build.)
- **Disk + image bloat**: while the `runner` stages copy only `.next/standalone` outputs,
  the `builder` stage installs the full lockfile. The extraneous deps inflate the
  intermediate build cache (~80 MB worth). On a VPS that recently regressed from 16 → 5.6 GB
  RAM, build OOM headroom matters.
- **CVE noise**: `npm audit` on these 51 extras will report future CVEs against `three`,
  `hls.js`, etc. that we have no real exposure to. Each one is a triage cost.

## Recommended fix

Three steps, all on a fresh branch (read-only constraint of this audit means I'm not running
them):

1. **Regenerate the lockfile** cleanly:
   ```bash
   git rm -r apps/scribe || true   # already deleted, just in case
   rm -rf node_modules apps/*/node_modules packages/*/node_modules \
          apps/*/.next/standalone apps/*/.next/server apps/*/.next/cache
   rm package-lock.json
   npm install
   git add package-lock.json
   ```

2. **Verify** post-clean:
   ```bash
   npm ls --workspaces --all 2>&1 | grep -E "(extraneous|missing|invalid)" | wc -l
   # expect: 0
   python3 -c "import json; d=json.load(open('package-lock.json'));
               print('apps/scribe' in d['packages'])"
   # expect: False
   ```

3. **Add a CI check** that fails the PR if the lockfile is out of sync with manifests:
   ```yaml
   - name: Lockfile integrity
     run: |
       npm ci --dry-run
       test "$(npm ls --workspaces --all 2>&1 | grep -c extraneous)" = "0"
   ```

   Or simpler: `npx --yes lockfile-lint --path package-lock.json --validate-https
   --allowed-hosts npm`.

4. **`.gitignore` audit**: confirm `apps/*/.next/standalone/` is ignored (it should be a
   build artifact, not committed). Currently `apps/marketing/.next/standalone/.../package.json`
   has its own dependency list that conflicts with source — that's a smell either way.

## Cross-domain hooks

- Agent 09 (CI): the lockfile-integrity check belongs in the same job that runs
  `npm ci`.
- Agent 04 (build): the stale `.next/standalone` dirs suggest the build cache isn't being
  cleared between feature-branch builds; worth confirming.
- Agent 11 (operations / VPS): a fresh `npm install` after this fix will trim ~80 MB from
  the build cache.
