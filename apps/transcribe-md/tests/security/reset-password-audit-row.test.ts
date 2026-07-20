// ============================================================================
// Reset-password transactional PASSWORD_CHANGED audit
// ----------------------------------------------------------------------------
// The immutable audit receipt is part of the same Prisma transaction as the
// credential mutation, token consumption, and session revocation. Awaiting it
// before the callback returns means an audit insert failure rejects and rolls
// back the whole transaction rather than leaving an unaudited password change.
// ============================================================================

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const SRC = readFileSync(
  resolve(
    __dirname,
    '..',
    '..',
    'src',
    'app',
    'api',
    'auth',
    'reset-password',
    'route.ts'
  ),
  'utf8'
);

const transactionStart = SRC.indexOf('result = await prisma.$transaction');
const transactionEnd = SRC.indexOf('\n    } catch (error)', transactionStart);
const transaction = SRC.slice(transactionStart, transactionEnd);

describe('reset-password transactional audit contract', () => {
  it('imports the transaction-scoped auth mutation helper', () => {
    expect(SRC).toMatch(
      /import\s+\{\s*appendAuthMutationAuditInTransaction\s*\}\s+from\s+['"]@\/lib\/audit['"]/
    );
  });

  it('awaits the receipt inside the mutation transaction before returning', () => {
    const auditAt = transaction.indexOf(
      'await appendAuthMutationAuditInTransaction(tx'
    );
    const callbackReturnAt = transaction.indexOf(
      'return { userId: locked.user.id }'
    );

    expect(transactionStart).toBeGreaterThanOrEqual(0);
    expect(transactionEnd).toBeGreaterThan(transactionStart);
    expect(auditAt).toBeGreaterThan(
      transaction.indexOf('await tx.user.update')
    );
    expect(auditAt).toBeGreaterThan(
      transaction.indexOf('await consumeLockedAuthToken')
    );
    expect(callbackReturnAt).toBeGreaterThan(auditAt);
  });

  it('binds the receipt to the exact locked user, practice, and reset-token provenance', () => {
    expect(transaction).toMatch(
      /appendAuthMutationAuditInTransaction\(tx,\s*\{[\s\S]*?action:\s*['"]PASSWORD_CHANGED['"][\s\S]*?userId:\s*locked\.user\.id[\s\S]*?userEmail:\s*locked\.user\.email[\s\S]*?practiceId:\s*locked\.user\.practiceId[\s\S]*?metadata:\s*\{\s*via:\s*['"]reset_token['"]\s*\}/
    );
    expect(SRC.slice(transactionEnd)).not.toContain(
      'appendAuthMutationAuditInTransaction'
    );
    expect(SRC).not.toMatch(/\blogAudit\s*\(/);
  });
});
