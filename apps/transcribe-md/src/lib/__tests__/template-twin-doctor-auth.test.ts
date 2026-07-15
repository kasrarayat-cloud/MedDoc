import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  findUser: vi.fn(),
}));

vi.mock('@/lib/nextauth', () => ({ auth: mocks.auth }));
vi.mock('@meddoc/db', () => ({
  default: { user: { findUnique: mocks.findUser } },
}));

import { requireDoctorSession } from '../auth';

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.mockResolvedValue({
    user: {
      id: 'user-synthetic-role',
      email: 'role-user@synthetic.test',
      name: 'Synthetic Role User',
      role: 'DOCTOR',
      practiceId: 'practice-stale-jwt',
    },
  });
});

describe('Template Twin fresh physician authorization', () => {
  it.each(['STAFF', 'ADMIN'] as const)(
    'rejects a stale DOCTOR JWT when the current database role is %s',
    async (role) => {
      mocks.findUser.mockResolvedValue({
        role,
        isActive: true,
        practiceId: 'practice-current',
      });

      await expect(requireDoctorSession()).rejects.toMatchObject({
        code: 'FORBIDDEN',
      });
      expect(mocks.findUser).toHaveBeenCalledTimes(1);
      expect(mocks.findUser).toHaveBeenCalledWith({
        where: { id: 'user-synthetic-role' },
        select: { role: true, isActive: true, practiceId: true },
      });
    },
  );

  it('uses the fresh physician role and tenant instead of stale JWT claims', async () => {
    mocks.auth.mockResolvedValue({
      user: {
        id: 'user-synthetic-role',
        email: 'role-user@synthetic.test',
        name: 'Synthetic Role User',
        role: 'STAFF',
        practiceId: 'practice-stale-jwt',
      },
    });
    mocks.findUser.mockResolvedValue({
      role: 'DOCTOR',
      isActive: true,
      practiceId: 'practice-current',
    });

    await expect(requireDoctorSession()).resolves.toMatchObject({
      user: {
        id: 'user-synthetic-role',
        role: 'DOCTOR',
        practiceId: 'practice-current',
      },
    });
  });

  it('fails closed when fresh database role evidence is unavailable', async () => {
    mocks.findUser.mockRejectedValue(new Error('Synthetic database outage'));

    await expect(requireDoctorSession()).rejects.toMatchObject({
      code: 'FORBIDDEN',
    });
  });

  it('rejects an inactive physician', async () => {
    mocks.findUser.mockResolvedValue({
      role: 'DOCTOR',
      isActive: false,
      practiceId: 'practice-current',
    });

    await expect(requireDoctorSession()).rejects.toMatchObject({
      code: 'FORBIDDEN',
    });
  });
});
