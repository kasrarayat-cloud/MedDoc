// ============================================================================
// Seed ONE READY visit whose template is a CERTIFIED twin.
// ----------------------------------------------------------------------------
// Phase 2 only draws for a visit that can actually be filled onto the doctor's
// own form, which means: a certified compiled twin, a note, and entities. The
// generic seeds produce none of that, and a test that silently skips because
// its fixture was absent proves nothing.
//
// It ALSO seeds one suggested claim, because the claim is what proves the point
// of the phase: accept it, and the document visibly fills.
//
// Same psql channel + fail-closed db-guard as the other seeds — never prod.
// ============================================================================

import { execSync } from 'node:child_process';

import { assertNonProdDbName } from '@meddoc/db/guard';

import { QA_COMPOSE as COMPOSE, QA_DB as SEED_DB } from './qa-compose';

function psql(sql: string): string {
  // -f - - over stdin, never -c "…": the shell in the -c form evaluates '$',
  // backticks and $(…) inside the SQL. A bcrypt hash is full of '$', and that
  // form silently truncated one to 46 characters of nonsense, which then
  // presented as "invalid email or password" for a credential we had just
  // written ourselves. The rest of this suite already uses stdin (helpers/
  // admin.ts, helpers/rxSafety.ts); this is that same channel.
  const bin = process.env.PSQL_BIN;
  if (bin) {
    // The guard runs on BOTH branches. A seed that writes to a users row has no
    // business trusting an env var to have pointed somewhere safe.
    assertNonProdDbName(SEED_DB);
    return execSync(`${bin} -A -t -f -`, {
      input: sql,
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'pipe'],
    }).trim();
  }
  assertNonProdDbName(SEED_DB);
  return execSync(`${COMPOSE} exec -T postgres psql -U meddoc -d ${SEED_DB} -A -t -f -`, {
    input: sql,
    encoding: 'utf8',
    stdio: ['pipe', 'pipe', 'pipe'],
  }).trim();
}


/**
 * A SYNTHETIC venous-duplex note shaped like the form it fills — headings the
 * page-anchoring resolves against, and a measurements table the bridge reads.
 *
 * Carried here rather than read from a template's pinned proof: an earlier
 * version depended on `pinnedSyntheticNote`, which exists only on templates
 * that happen to have been certified with pinning. That made the fixture
 * something the test could not create, only hope for.
 *
 * No patient data. The names are anatomy, the numbers are made up.
 */
const SEED_NOTE = [
  '## TECHNIQUE',
  'A duplex Doppler color flow ultrasound study was performed in the upright position',
  'with and without manual augmentation of flow and Valsalva maneuver.',
  '',
  '## FINDINGS',
  'Right Leg:',
  'The great saphenous vein from the saphenofemoral junction to the knee was found to have reflux.',
  '',
  'Left Leg:',
  'The great saphenous vein from the saphenofemoral junction to the knee was found to have reflux.',
  '',
  '| Vein | Diameter (mm) | Reflux time (s) |',
  '| --- | --- | --- |',
  '| Right GSV at the SFJ | 7.0 | 2.4 |',
  '| Right GSV at the Proximal Thigh | 6.4 | 2.1 |',
  '| Right GSV at the Knee | 5.1 | 1.6 |',
  '| Left GSV at the SFJ | 8.0 | 3.1 |',
  '| Left GSV at the Proximal Thigh | 6.9 | 2.8 |',
  '| Left GSV at the Knee | 5.6 | 1.2 |',
  '',
  '## IMPRESSION',
  'Right great saphenous vein is reflux positive.',
  'Right deep venous system without evidence of obstruction or insufficiency.',
  'No saphenous reflux in right lower extremity.',
  'Left great saphenous vein is reflux positive.',
  'Left deep venous system without evidence of obstruction or insufficiency.',
  'Clinical correlation with the above findings is required.',
].join('\n');

const STYLED_NOTE = [
  '## TECHNIQUE',
  '_[All AI-drafted content for this section was set aside for your review — see the suggestions below and adopt before signing.]_',
  '',
  '## FINDINGS',
  'DIAMETER AND REFLUX TIME — Right Leg',
  '| Segment | DIAMETER (mm) | REFLUX TIME (seconds) |',
  '| --- | --- | --- |',
  '| GSV at the SFJ | 6.2 | 3.4 |',
  '| GSV at the Knee | 3.4 | 1.8 |',
  '| SSV at the Proximal Calf | [not documented] | [not documented] |',
  '',
  '## IMPRESSION',
  'Right great saphenous vein is reflux positive.',
].join('\n');

const STYLED_CLAIMS = [
  {
    section: 'FINDINGS',
    text: '| GSV at the Knee | 3.4 | 1.8 |',
    reason: 'not supported by the dictation',
    anchor: 'no anchor',
  },
];

export const VISIT_DOC_VISIT_ID = 'qa_visitdoc_twin';

/** The same visit with NO template — a doctor who taught us a note FORMAT but
 *  never uploaded a FORM, which is most of them. It must review identically. */
export const STYLED_VISIT_ID = 'qa_styled_us';

export interface SeededVisitDoc {
  visitId: string;
  /** The template's owner. The walk signs in as them — see seedVisitDocLogin. */
  doctorEmail: string;
}

/**
 * Points a READY visit at whichever CERTIFIED twin template this stack has, and
 * gives it a note plus one suggested claim. Returns null when the stack has no
 * certified twin at all — the caller must FAIL, not skip.
 */
/**
 * Seeds the visit UNDER THE TEMPLATE'S EXISTING OWNER.
 *
 * An earlier version reassigned the certified template to a freshly signed-up
 * user so the walk could log in as someone whose password it knew. Cleanup then
 * deleted that user and CASCADED THE TEMPLATE AWAY — the shared fixture this
 * whole phase depends on, destroyed by its own test. A seed may create rows; it
 * may not re-own the ones it found.
 */
export function seedVisitDocVisit(): SeededVisitDoc | null {
  const tpl = psql(
    `select nt.id, nt.version, nt."doctorId", u.email
       from note_templates nt
       join template_twin_compiled_versions cv on cv."noteTemplateId" = nt.id
       join users u on u.id = nt."doctorId"
      where cv."certificationStatus" = 'CERTIFIED'
      order by nt."updatedAt" desc limit 1`,
  );
  if (!tpl) return null;
  const [templateId, version, ownerId, ownerEmail] = tpl.split('|');
  // A donor row to clone. Enumerating this table's NOT NULL columns by hand is
  // how a seed drifts from production — copy a real visit and override only
  // what this phase actually needs.
  const donor = psql(
    `select id from transcribe_visits where "deletedAt" is null order by "createdAt" desc limit 1`,
  );
  if (!donor) return null;

  // Headings the form actually contains, so page-anchoring has something real
  // to resolve; and ONE demoted claim, because accepting it is what proves the
  // document fills.
  const note = `'${SEED_NOTE.replace(/'/g, "''")}'`;
  // THREE claims, not one. The bulk-adoption gate only engages above a single
  // suggestion (accepting one is a direct instruction, not a batch), so a
  // one-claim fixture cannot exercise it — and a test that cannot reach the
  // rule it is named after is worse than no test.
  //
  // EVERY field, or nothing: extractSuggestedClaims voids the whole array on a
  // single malformed entry (so rendered indices can never drift from the DB
  // array the adopt action validates against). A claim missing `anchor` does
  // not render as a broken card — it renders as no lane at all.
  const claimList = [
    {
      section: 'FINDINGS',
      text: 'Right GSV Below Knee measured 4.2 mm with reflux of 0.9 seconds.',
      reason: 'not supported by the dictation',
      anchor: 'no anchor',
    },
    {
      section: 'FINDINGS',
      text: 'Left SSV at the proximal calf measured 3.1 mm without reflux.',
      reason: 'not supported by the dictation',
      anchor: 'no anchor',
    },
    {
      section: 'IMPRESSION',
      text: 'No evidence of deep venous thrombosis in either lower extremity.',
      reason: 'not supported by the dictation',
      anchor: 'no anchor',
    },
  ];
  const claims = `'${JSON.stringify(claimList).replace(/'/g, "''")}'::jsonb`;

  psql(`
    create temp table _seed as select * from transcribe_visits where id = '${donor}';
    update _seed set
      id = '${VISIT_DOC_VISIT_ID}',
      status = 'READY',
      "signedAt" = null,
      "userId" = '${ownerId}',
      "noteTemplateId" = '${templateId}',
      "noteTemplateVersion" = ${version},
      "soapFinal" = ${note},
      "transcriptText" = 'Bilateral venous duplex study of the lower extremities.',
      "soapVersion" = 1,
      "needsReview" = true,
      "reviewReason" = 'Some statements were not supported by the dictation.',
      "suggestedClaims" = ${claims};
    delete from transcribe_visits where id = '${VISIT_DOC_VISIT_ID}';
    insert into transcribe_visits select * from _seed;
    delete from template_twin_fill_manifests where "visitId" = '${VISIT_DOC_VISIT_ID}';
  `);

  // The chat's reading attestations live in Redis, keyed by visit + doctor —
  // both of which this fixture REUSES. Left in place, a later test inherits an
  // earlier one's permission to bulk-adopt, and the gate looks satisfied when
  // nothing was read in that session.
  try {
    execSync(
      `${COMPOSE} exec -T redis redis-cli --scan --pattern 'chatattest:v1:${VISIT_DOC_VISIT_ID}:*'`,
      { encoding: 'utf8' },
    )
      .split('\n')
      .map((k) => k.trim())
      .filter(Boolean)
      .forEach((k) => {
        execSync(`${COMPOSE} exec -T redis redis-cli del ${k}`, { stdio: 'ignore' });
      });
  } catch {
    // No Redis, no attestation — the gate fails closed, which is correct.
  }

  // A styled twin of the same visit: no template binding, an ultrasound
  // measurements table with undocumented cells, the set-aside placeholder, and
  // a suggestion quoted as a raw table row — every artifact the old card-wall
  // surfaced, in one fixture.
  psql(`
    create temp table _styled as select * from transcribe_visits where id = '${VISIT_DOC_VISIT_ID}';
    update _styled set
      id = '${STYLED_VISIT_ID}',
      "noteTemplateId" = null,
      "noteTemplateVersion" = null,
      status = 'READY',
      "signedAt" = null,
      specialty = 'ultrasound',
      "emStale" = false,
      "emScoredCode" = null,
      -- Dollar-quoted, so the newlines survive: a standard SQL literal does
      -- not interpret escape sequences, and the note arrived as one long line
      -- with no table for the prose renderer to read a header from.
      "soapFinal" = $note$${STYLED_NOTE}$note$,
      "suggestedClaims" = $claims$${JSON.stringify(STYLED_CLAIMS)}$claims$::jsonb;
    delete from transcribe_visits where id = '${STYLED_VISIT_ID}';
    insert into transcribe_visits select * from _styled;
  `);

  return { visitId: VISIT_DOC_VISIT_ID, doctorEmail: ownerEmail };
}

/** How many fill manifests exist for the seeded visit. The preview must never
 *  change this — see previewVisitDocumentAction. */
export function visitDocManifestCount(): number {
  return Number(
    psql(
      `select count(*) from template_twin_fill_manifests where "visitId" = '${VISIT_DOC_VISIT_ID}'`,
    ) || '0',
  );
}

/** Password this helper sets on the template's owner so a walk can sign in as
 *  them. QA-only: the isolated stack's accounts are synthetic by construction
 *  (see @meddoc/db/guard), and the alternative — re-owning the template to a
 *  disposable user — is what destroyed the fixture once already. */
export const VISIT_DOC_PASSWORD = 'QaDocPage!2026';

/** What the owner's credentials were before we touched them. */
export interface OwnerCredentials {
  email: string;
  passwordHash: string;
  mfaEnabled: boolean;
}

/**
 * Makes the template's owner signable-in — and hands back what it overwrote.
 *
 * This account is SHARED: it owns the only certified twin in the stack, and
 * other specs sign in as it and rely on its `mfaEnabled` (the admin-authz gate
 * keys on that). An earlier version left it permanently re-credentialed with
 * MFA off, which is the same class of mistake as re-owning the template — a
 * seed borrowing a fixture and not putting it back. Callers MUST restore in an
 * afterAll; `restoreOwnerCredentials` does it.
 *
 * Returns null when bcrypt is unavailable, so the caller FAILS rather than
 * quietly walking as the wrong user.
 */
export function prepareVisitDocLogin(email: string): OwnerCredentials | null {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const bcrypt = require('bcryptjs') as { hashSync(s: string, r: number): string };
  const hash = bcrypt.hashSync(VISIT_DOC_PASSWORD, 10);
  if (!hash || hash.length < 50) return null;

  const before = psql(
    `select "passwordHash", "mfaEnabled" from users where email = '${email.replace(/'/g, "''")}'`,
  );
  if (!before) return null;
  const [passwordHash, mfa] = before.split('|');

  psql(
    `update users set "passwordHash" = '${hash}', "mfaEnabled" = false,
        "emailVerified" = coalesce("emailVerified", now())
      where email = '${email.replace(/'/g, "''")}'`,
  );
  return { email, passwordHash, mfaEnabled: mfa === 't' };
}

/** Puts the shared account back exactly as it was found. */
export function restoreOwnerCredentials(prev: OwnerCredentials | null): void {
  if (!prev) return;
  psql(
    `update users set "passwordHash" = '${prev.passwordHash}',
        "mfaEnabled" = ${prev.mfaEnabled}
      where email = '${prev.email.replace(/'/g, "''")}'`,
  );
}
