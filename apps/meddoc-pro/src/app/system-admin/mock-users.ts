// ============================================================================
// Mock user store for dev mode (no DB) — survives hot-reload via globalThis
// ============================================================================

import type { AdminUserView } from './page';

const g = globalThis as unknown as { _mockAdminUsers?: AdminUserView[] };

if (!g._mockAdminUsers) {
  g._mockAdminUsers = [
    {
      id: 'admin_kasra_01',
      email: 'kasra@meddoc.pro',
      name: 'Kasra',
      role: 'ADMIN',
      isActive: true,
      lastLogin: new Date().toISOString(),
      createdAt: '2024-06-01T00:00:00Z',
      failedLoginCount: 0,
      lastSessionIp: '127.0.0.1',
      lastSessionAt: new Date().toISOString(),
      lastSessionAgent: 'Chrome',
      sessionCount: 3,
    },
    {
      id: 'mock_user_doctor_01',
      email: 'doctor@meddoc.local',
      name: 'Dr. Bakhtiar Moussazadeh',
      role: 'DOCTOR',
      isActive: true,
      lastLogin: new Date().toISOString(),
      createdAt: '2024-01-01T00:00:00Z',
      failedLoginCount: 0,
      lastSessionIp: '::1',
      lastSessionAt: new Date().toISOString(),
      lastSessionAgent: 'MedDoc Dev',
      sessionCount: 1,
    },
  ];
}

export const mockAdminUsers = g._mockAdminUsers;

export function addMockUser(user: AdminUserView): void {
  g._mockAdminUsers!.unshift(user);
}

export function updateMockUser(userId: string, data: Partial<AdminUserView>): boolean {
  const idx = g._mockAdminUsers!.findIndex((u) => u.id === userId);
  if (idx === -1) return false;
  g._mockAdminUsers![idx] = { ...g._mockAdminUsers![idx], ...data };
  return true;
}

export function deleteMockUser(userId: string): boolean {
  const idx = g._mockAdminUsers!.findIndex((u) => u.id === userId);
  if (idx === -1) return false;
  g._mockAdminUsers!.splice(idx, 1);
  return true;
}
