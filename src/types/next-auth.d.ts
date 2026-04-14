// ============================================================================
// NextAuth Module Augmentation
// ----------------------------------------------------------------------------
// Adds our custom fields (id, role) to the default NextAuth Session/User/JWT
// types so they're properly typed across the codebase.
// ============================================================================

import type { DefaultSession } from 'next-auth';

export type UserRole = 'DOCTOR' | 'ADMIN' | 'STAFF' | 'SUPER_ADMIN';

declare module 'next-auth' {
  /**
   * Returned by `auth()`, `useSession()`, `getServerSession()` etc.
   */
  interface Session {
    user: {
      id: string;
      role: UserRole;
      /** Multi-tenancy: the practice this user belongs to. Every tenant-
       *  scoped query filters by this. Required — there is no "global"
       *  user until a SUPER_ADMIN role lands. */
      practiceId: string;
    } & DefaultSession['user'];
  }

  /**
   * The shape of the user returned from the `authorize()` callback
   * and stored in the JWT.
   */
  interface User {
    id: string;
    email: string;
    name?: string | null;
    role: UserRole;
    practiceId: string;
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    id: string;
    role: UserRole;
    practiceId: string;
  }
}
