/**
 * GATE — PRODUCTION POSTGRES IS NOT PUBLISHED TO THE HOST. Ruling #281.
 * ----------------------------------------------------------------------------
 * ⚠️ WHY. `docker-compose.yml` used to carry
 * `- "127.0.0.1:5432:5432"   # only accessible from localhost`. The comment was
 * TRUE and it was not a CONTROL: every process on the box is "localhost". A
 * diagnostic probe written against the QA database reached PRODUCTION through
 * it and was stopped by WRONG CREDENTIALS — luck standing in for a guard, on
 * the database holding every patient record.
 *
 * ⚠️ AND THE PORT BOUGHT NOTHING, WHICH IS WHY THIS IS A DELETION AND NOT A
 * TRADE. Audited before removal: every host-side consumer already goes through
 * `docker exec`. The one script that binds a host port — `restore-drill.sh` —
 * publishes its OWN throwaway container on 5433.
 *
 * ⚠️ THIS FILE READS COMPOSE, WHICH IS A CONFIG ASSERTION AND NOT A BEHAVIOUR
 * ONE. #251 retires text scanning as proof of BEHAVIOUR; the shape of a
 * declarative config file is the thing itself, and the runtime check that the
 * port is actually closed belongs to the deploy's §2.5 rows, where it is
 * measured against the running host.
 */
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

/** ⚠️ THE SAME SHAPE `gate-workflows-parse` USES, AND FOR ITS REASON.
 *  `js-yaml` reaches this tree only TRANSITIVELY (eslint → @eslint/eslintrc),
 *  so it is not a promise anyone made to this file. Importing it directly makes
 *  the guard die on an unrelated lockfile change; a try/catch that RETURNS makes
 *  the guard VANISH, which is the defect this file exists to prevent, in the
 *  file itself. So it is resolved here and a miss is a loud failure. */
const req = createRequire(__filename);
function loadYaml(): (src: string) => unknown {
  try {
    return (req('js-yaml') as { load: (s: string) => unknown }).load;
  } catch {
    throw new Error(
      'the YAML parser is not installed, so this guard cannot check anything. ' +
        'js-yaml reaches this tree transitively via eslint; if that changed, ' +
        'add it as an explicit devDependency rather than deleting this test.',
    );
  }
}
const parse = loadYaml();

const REPO = resolve(__dirname, '../../../../..');
const COMPOSE = join(REPO, 'docker-compose.yml');

type Svc = { ports?: string[] };
const services = (): Record<string, Svc> =>
  (parse(readFileSync(COMPOSE, 'utf8')) as { services: Record<string, Svc> }).services;

describe('#281 — production Postgres is not reachable from the host', () => {
  it('POSITIVE CONTROL — compose parses and names the services this gate is about', () => {
    // Without this, a compose file that failed to parse into `{}` would satisfy
    // every assertion below by having no postgres service at all.
    const s = services();
    expect(Object.keys(s).length, 'compose parsed to nothing').toBeGreaterThan(5);
    for (const name of ['postgres', 'redis', 'minio']) {
      expect(s, `compose no longer defines '${name}'`).toHaveProperty(name);
    }
  });

  it('⚠️ postgres publishes NO host port', () => {
    const pg = services().postgres;
    expect(
      pg.ports ?? [],
      'production Postgres is published to the host again. Every process on this ' +
        'box is "localhost"; a probe written for QA reached PRODUCTION through ' +
        'this mapping and was stopped only by wrong credentials. Reach it with ' +
        '`docker exec -i meddoc-pro-postgres-1 psql -U meddoc -d meddoc`.',
    ).toEqual([]);
  });

  it('⚠️ and no service publishes 5432 by any route', () => {
    // The mapping could come back under another service, or on a different host
    // port pointing at postgres. The claim is about the DATABASE being
    // reachable, not about one line.
    const offenders: string[] = [];
    for (const [name, svc] of Object.entries(services())) {
      for (const p of svc.ports ?? []) {
        if (/(^|:)5432(:|$)/.test(String(p))) offenders.push(`${name}: ${p}`);
      }
    }
    expect(offenders, `a service publishes 5432: ${offenders.join(', ')}`).toEqual([]);
  });

  it('⚠️ MINIO AND REDIS STILL PUBLISH — recorded, not silently accepted', () => {
    // #281 orders the same audit for these two AFTER Postgres. Pinning the
    // current state means the follow-up is a visible change rather than a
    // question nobody re-asks — and an unanswered question decays into
    // "probably fine" through repetition alone.
    const s = services();
    expect(s.redis.ports ?? []).toEqual(['127.0.0.1:6379:6379']);
    expect(s.minio.ports ?? []).toEqual(['127.0.0.1:9000:9000', '127.0.0.1:9001:9001']);
  });
});
