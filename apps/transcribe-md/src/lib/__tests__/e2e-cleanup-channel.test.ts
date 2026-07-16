import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  execSync: vi.fn(),
  assertNonProdDbName: vi.fn(),
}));

vi.mock('node:child_process', () => ({
  default: { execSync: mocks.execSync },
  execSync: mocks.execSync,
}));
vi.mock('@meddoc/db/guard', () => ({
  assertNonProdDbName: mocks.assertNonProdDbName,
}));

import { cleanupTestUsers } from '../../../tests/e2e/helpers/cleanup';

beforeEach(() => {
  vi.clearAllMocks();
  process.env.PSQL_BIN =
    'psql "postgresql://synthetic@localhost:5432/meddoc_qa_test"';
});

describe('cleanupTestUsers direct CI channel', () => {
  it('verifies the connected database name before running destructive SQL', () => {
    mocks.execSync
      .mockReturnValueOnce('meddoc_qa_test\n')
      .mockReturnValueOnce(Buffer.alloc(0));

    cleanupTestUsers();

    expect(mocks.execSync.mock.calls[0]?.[0]).toContain(
      'SELECT current_database()',
    );
    expect(mocks.assertNonProdDbName).toHaveBeenCalledWith('meddoc_qa_test');
    expect(mocks.execSync.mock.calls[1]?.[0]).toContain(
      '-v ON_ERROR_STOP=1 -A -t -f -',
    );
    expect(mocks.execSync.mock.calls[1]?.[1]).toMatchObject({
      input: expect.stringContaining('FOR UPDATE OF v'),
    });
  });

  it('does not execute cleanup when the database guard rejects the target', () => {
    mocks.execSync.mockReturnValueOnce('meddoc\n');
    mocks.assertNonProdDbName.mockImplementationOnce(() => {
      throw new Error('synthetic guard rejection');
    });

    expect(() => cleanupTestUsers()).toThrow('synthetic guard rejection');
    expect(mocks.execSync).toHaveBeenCalledTimes(1);
  });
});
