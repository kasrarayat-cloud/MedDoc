'use client';

// ============================================================================
// AdminSidebar — full-navigation left rail for the System Admin command center
// ----------------------------------------------------------------------------
// 240px on desktop (sticky), slide-in drawer on mobile. Orange/teal terminal
// aesthetic to distinguish the admin surface from the clinician dashboard.
// ============================================================================

import React, { useState, useTransition } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { signOut } from 'next-auth/react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Users,
  Shield,
  Activity,
  Terminal,
  LogOut,
  Loader2,
  ArrowLeft,
  Menu,
  X,
} from 'lucide-react';

type NavItem = {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  /** If true, only mark active on exact pathname match (avoids /system-admin
   *  lighting up for every /system-admin/* subpage). */
  exact?: boolean;
};

const NAV_ITEMS: NavItem[] = [
  { label: 'Users', href: '/system-admin', icon: Users, exact: true },
  { label: 'Security Logs', href: '/system-admin/audit', icon: Shield },
  { label: 'Scribe Audit', href: '/system-admin/scribe-audit', icon: Terminal },
  { label: 'Metrics', href: '/system-admin/metrics', icon: Activity },
];

const SURFACE_BG =
  'linear-gradient(180deg, rgba(10, 14, 23, 0.98) 0%, rgba(2, 6, 23, 0.99) 100%)';

export default function AdminSidebar({ userName }: { userName?: string }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isPending, startTransition] = useTransition();

  const isActive = (item: NavItem) =>
    item.exact ? pathname === item.href : pathname.startsWith(item.href);

  const handleLogout = () => {
    startTransition(async () => {
      await signOut({ callbackUrl: '/login', redirect: true });
    });
  };

  const displayName = userName?.trim() || 'Admin';
  const initial = displayName.slice(0, 1).toUpperCase();

  const content = (isMobile: boolean) => (
    <div className="flex flex-col h-full">
      {/* Brand */}
      <div className="flex items-center gap-3 px-5 py-6 border-b border-white/5">
        <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500/20 to-orange-600/10 border border-orange-500/30 shrink-0">
          <Terminal className="w-5 h-5 text-orange-400" />
        </div>
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-orange-400/80">
            MedDoc
          </p>
          <p className="text-base font-bold text-white leading-tight">ADMIN</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const active = isActive(item);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => isMobile && setMobileOpen(false)}
              className="block"
            >
              <div
                className={`relative flex items-center gap-3 px-3 py-2.5 rounded-xl transition-colors duration-200 group ${
                  active ? 'text-white' : 'text-slate-400 hover:text-white'
                }`}
              >
                {active && (
                  <motion.div
                    layoutId={isMobile ? 'admin-active-mobile' : 'admin-active'}
                    className="absolute inset-0 rounded-xl bg-gradient-to-r from-orange-500/15 to-teal-500/10 border border-orange-500/25"
                    transition={{ type: 'spring', stiffness: 350, damping: 30 }}
                  />
                )}
                {active && (
                  <motion.div
                    layoutId={isMobile ? 'admin-ind-mobile' : 'admin-ind'}
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 rounded-r-full bg-gradient-to-b from-orange-400 to-teal-400"
                  />
                )}

                <div
                  className={`relative z-10 flex items-center justify-center w-9 h-9 rounded-lg shrink-0 transition-colors duration-200 ${
                    active
                      ? 'bg-orange-500/15 text-orange-300'
                      : 'text-slate-400 group-hover:bg-white/5 group-hover:text-white'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                </div>

                <span className="relative z-10 text-sm font-medium whitespace-nowrap">
                  {item.label}
                </span>
              </div>
            </Link>
          );
        })}

        {/* Divider */}
        <div className="my-4 h-px bg-white/5" />

        {/* Escape hatch back to the clinician view.
            Uses a plain <a> (not next/link) intentionally: the admin and
            clinician surfaces are two separate layouts, and a soft RSC
            navigation between them can leave stale tree/cache bits behind.
            A full-page load re-runs middleware, the root layout, and the
            target layout cleanly — worth the extra ~200ms. */}
        <a
          href="/dashboard"
          onClick={() => isMobile && setMobileOpen(false)}
          className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-slate-500 hover:text-white hover:bg-white/5 transition-colors group"
        >
          <div className="flex items-center justify-center w-9 h-9 rounded-lg shrink-0">
            <ArrowLeft className="w-4 h-4" />
          </div>
          <span className="text-sm font-medium">Clinician view</span>
        </a>
      </nav>

      {/* User profile + sign out */}
      <div className="px-3 py-4 border-t border-white/5">
        <div className="flex items-center gap-3 px-2">
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-orange-500 to-teal-400 flex items-center justify-center shrink-0 text-white font-semibold text-sm shadow-lg shadow-orange-500/20">
            {initial}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-white truncate">
              {displayName}
            </p>
            <p className="text-[11px] font-mono text-orange-400/70 truncate">
              Administrator
            </p>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            disabled={isPending}
            aria-label="Sign out"
            title="Sign out"
            className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer"
          >
            {isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <LogOut className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Mobile menu trigger */}
      <button
        onClick={() => setMobileOpen(true)}
        className="fixed top-4 left-4 z-40 p-2 rounded-xl bg-slate-900/90 text-white backdrop-blur-sm border border-white/10 lg:hidden cursor-pointer"
        aria-label="Open navigation"
      >
        <Menu className="w-5 h-5" />
      </button>

      {/* Mobile drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMobileOpen(false)}
              className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm lg:hidden"
            />
            <motion.aside
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'spring', stiffness: 300, damping: 30 }}
              className="fixed inset-y-0 left-0 z-50 w-[260px] lg:hidden"
              style={{
                background: SURFACE_BG,
                borderRight: '1px solid rgba(255,255,255,0.08)',
                backdropFilter: 'blur(10px)',
              }}
            >
              <button
                onClick={() => setMobileOpen(false)}
                className="absolute top-4 right-4 p-2 text-slate-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors cursor-pointer"
                aria-label="Close navigation"
              >
                <X className="w-5 h-5" />
              </button>
              {content(true)}
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Desktop sidebar */}
      <aside
        className="hidden lg:flex lg:flex-col lg:shrink-0 sticky top-0 h-screen overflow-hidden"
        style={{
          width: '240px',
          minWidth: '240px',
          background: SURFACE_BG,
          borderRight: '1px solid rgba(255,255,255,0.08)',
          backdropFilter: 'blur(10px)',
        }}
      >
        {content(false)}
        <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-orange-500/5 to-transparent pointer-events-none" />
      </aside>
    </>
  );
}
