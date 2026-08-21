import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

/**
 * F5-h RESIDUAL — THE GATE AND THE WRITE JUDGE ONE SNAPSHOT.
 *
 * The aimed re-run caught this in the fix itself, which is the reason the gate
 * is worth having: W1 read `cptCodes` fresh inside the transaction (correct —
 * it stopped a concurrent override being erased) and in the same expression
 * began freezing a level that no attestation on the record named.
 *
 * `POST /em-score/override` deliberately does not move `soapVersion`, so it is
 * invisible to the note-CAS; and the confirm gate runs hundreds of lines before
 * the write, against the ENTRY capture. Between them a doctor can move the
 * level. Before W1 that override was erased — data loss, but the signed record
 * stayed internally honest. After W1 the record could assert an acknowledged
 * 99213→99214 while freezing 99215.
 *
 *   AN ABSENT FIELD IS CONTENT THE DOCTOR DID NOT SEE.
 *   A WRONG FIELD SAYS THE OPPOSITE OF THE RECORD BEING SIGNED.
 *
 * These are SOURCE assertions over one route file, and that is a real limit —
 * they cannot prove the interleave at runtime. They are written this way
 * because the alternative is a two-connection Serializable harness against a
 * live database, which this repo's canon forbids running anywhere a real record
 * could be touched. What they CAN do is fail the moment the structure that
 * makes the divergence impossible is edited away — which is the shape the
 * partial-fix rule asks for.
 */
const ROUTE = join(__dirname, '..', 'route.ts');
const src = readFileSync(ROUTE, 'utf8');

describe('the E/M gate and the E/M write share one snapshot', () => {
  it('re-reads the GATE\'S datum inside the transaction, not just cptCodes', () => {
    // The defect was precisely that `emPendingChange` was SELECTED and never
    // consumed. Presence of the select proves nothing; consumption does.
    expect(src).toContain('unacknowledgedEmChange(fresh?.emPendingChange)');
  });

  it('REFUSES when the fresh change diverges from what the gate judged', () => {
    expect(src).toContain('throw new EmChangedWhileSigning(');
    expect(src).toMatch(/freshPending\.from !== gateJudged\.from/);
    expect(src).toMatch(/freshPending\.to !== gateJudged\.to/);
    // `at` discriminates two changes that happen to share from/to — a doctor
    // moving 99213→99214, reverting, and moving again is not the same event.
    expect(src).toMatch(/freshPending\.at !== gateJudged\.at/);
    // gate saw NOTHING and one appeared -> also a divergence. This is the arm
    // that catches the common case, and a `gateJudged === null` omission would
    // make the whole check vacuous for it.
    expect(src).toMatch(/gateJudged === null \|\|/);
  });

  it('writes the FRESH pending record, never the captured one', () => {
    // The half-landed shape: refuse on divergence but still spread the stale
    // capture. That version passes the refusal arm above and still stamps an
    // acknowledgement onto a record the database no longer holds.
    expect(src).toContain('...(freshPending');
    expect(src).toContain('...freshPending,');
    expect(src).not.toMatch(/\.\.\.\(pendingEm\s*\n\s*\?\s*\{\s*\n\s*emPendingChange/);
  });

  it('is SERIALIZABLE — the re-read and the CAS are one snapshot', () => {
    // READ COMMITTED leaves the original erasure race with a smaller window,
    // which is not a closed one. The create path already uses this level.
    expect(src).toContain('Prisma.TransactionIsolationLevel.Serializable');
  });

  it('keeps the model call OUTSIDE the transaction', () => {
    const tx = src.slice(src.indexOf('const signWrite'), src.indexOf('let updated:'));
    // Holding a row lock across a model call is how a formatting concern
    // becomes a database incident.
    expect(tx).not.toContain('computeDisplayedEmCode');
    expect(tx).not.toContain('computeEmScore');
  });

  it('does NOT retry the refusal as a styled signature', () => {
    // Falling into the manifest-vanished retry would re-run the identical
    // transaction, diverge identically, and throw outside the try — a 500 on
    // the one route whose job is to say precisely why a signature did not
    // happen.
    expect(src).toContain('if (err instanceof EmChangedWhileSigning)');
    const i = src.indexOf('if (err instanceof EmChangedWhileSigning)');
    const j = src.indexOf('frozen manifest unavailable at signature');
    expect(i).toBeGreaterThan(0);
    expect(j).toBeGreaterThan(i); // the rethrow precedes the styled fallback
  });

  it('refuses with a code the client ALREADY renders', () => {
    // The sibling finding in the same pass was that `supersededBy` is a wire
    // field nothing reads. A fresh code here would repeat it: the doctor would
    // get a generic error toast for a one-click coding confirmation.
    expect(src).toContain("code: 'EM_CHANGE_UNACKNOWLEDGED'");
    expect(src).toContain('pendingEmChange: { from: err.emFrom, to: err.emTo }');
  });

  it('audits under an action that exists in ALL THREE layers', () => {
    // The three-edit trap: TS union, Prisma enum, and its own migration. This
    // route reuses a value that already cleared all three rather than minting
    // a fourth that would throw at runtime and be swallowed.
    expect(src).toContain("action: 'EM_SIGN_BLOCKED_UNACKNOWLEDGED_CHANGE'");
    const audit = readFileSync(
      join(__dirname, '..', '..', '..', '..', '..', '..', 'lib', 'audit.ts'),
      'utf8'
    );
    expect(audit).toContain("'EM_SIGN_BLOCKED_UNACKNOWLEDGED_CHANGE'");
    const schema = readFileSync(
      join(__dirname, '..', '..', '..', '..', '..', '..', '..', '..', '..',
           'packages', 'db', 'prisma', 'schema.prisma'),
      'utf8'
    );
    expect(schema).toContain('EM_SIGN_BLOCKED_UNACKNOWLEDGED_CHANGE');
  });

  it('does not invent a second clinician when a session supersedes itself', () => {
    // Nothing serialises two sign requests from one session, so a double
    // submit loses the CAS to itself. "Dr X signed this first", where Dr X is
    // the caller, is a fabricated actor in a clinical audit trail.
    expect(src).toContain('refreshed.signedBy === userId');
    expect(src).toContain('this account (a second signature request)');
  });
});
