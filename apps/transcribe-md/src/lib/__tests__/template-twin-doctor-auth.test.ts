import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  findUser: vi.fn(),
  pinRollout: vi.fn(),
}));

vi.mock('@/lib/nextauth', () => ({ auth: mocks.auth }));
vi.mock('@meddoc/db', () => ({
  default: { user: { findUnique: mocks.findUser } },
}));
vi.mock('@/lib/template-twin/rollout', async (importOriginal) => {
  const actual = await importOriginal<
    typeof import('@/lib/template-twin/rollout')
  >();
  return {
    ...actual,
    pinTemplateTwinRollout: mocks.pinRollout,
  };
});

import { requireDoctorSession } from '../auth';

beforeEach(() => {
  vi.clearAllMocks();
  process.env.TEMPLATE_TWIN_KILL_SWITCH = 'false';
  mocks.pinRollout.mockResolvedValue({
    practiceId: 'practice-current',
    globalGeneration: BigInt(1),
    practiceGeneration: BigInt(1),
  });
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
        practice: { templateTwinEnabled: true },
      });

      await expect(requireDoctorSession()).rejects.toMatchObject({
        code: 'FORBIDDEN',
      });
      expect(mocks.findUser).toHaveBeenCalledTimes(1);
      expect(mocks.findUser).toHaveBeenCalledWith({
        where: { id: 'user-synthetic-role' },
        select: {
          role: true,
          isActive: true,
          practiceId: true,
          practice: { select: { templateTwinEnabled: true } },
        },
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
      practice: { templateTwinEnabled: true },
    });

    await expect(requireDoctorSession()).resolves.toMatchObject({
      templateTwinRolloutToken: {
        practiceId: 'practice-current',
        globalGeneration: BigInt(1),
        practiceGeneration: BigInt(1),
      },
      user: {
        id: 'user-synthetic-role',
        role: 'DOCTOR',
        practiceId: 'practice-current',
      },
    });
    expect(mocks.pinRollout).toHaveBeenCalledWith({
      practiceId: 'practice-current',
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
      practice: { templateTwinEnabled: true },
    });

    await expect(requireDoctorSession()).rejects.toMatchObject({
      code: 'FORBIDDEN',
    });
  });

  it('fails closed when the owning practice rollout flag is disabled', async () => {
    mocks.findUser.mockResolvedValue({
      role: 'DOCTOR',
      isActive: true,
      practiceId: 'practice-current',
      practice: { templateTwinEnabled: false },
    });

    await expect(requireDoctorSession()).rejects.toMatchObject({
      code: 'FORBIDDEN',
      message: 'Template Twin is not enabled for this practice.',
    });
  });

  it('fails closed when the global kill switch is not explicitly disabled', async () => {
    delete process.env.TEMPLATE_TWIN_KILL_SWITCH;
    mocks.findUser.mockResolvedValue({
      role: 'DOCTOR',
      isActive: true,
      practiceId: 'practice-current',
      practice: { templateTwinEnabled: true },
    });

    await expect(requireDoctorSession()).rejects.toMatchObject({
      code: 'FORBIDDEN',
      message: 'Template Twin is temporarily unavailable.',
    });
  });
});
