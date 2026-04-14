'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Home,
  Users,
  FileEdit,
  History,
  Settings,
  Stethoscope,
  ChevronLeft,
  Menu,
  X,
  CalendarDays,
  Shield,
  Terminal,
} from 'lucide-react';
import LogoutButton from '@/components/LogoutButton';

const navItems = [
  { label: 'Dashboard', href: '/dashboard', icon: Home },
  { label: 'Patients', href: '/dashboard/patients', icon: Users },
  { label: 'Schedule', href: '/dashboard/schedule', icon: CalendarDays },
  { label: 'Doc Editor', href: '/dashboard/doc-editor', icon: FileEdit },
  { label: 'Document History', href: '/dashboard/history', icon: History },
  { label: 'Audit Logs', href: '/dashboard/audit', icon: Shield },
  { label: 'Settings', href: '/dashboard/settings', icon: Settings },
];

const sidebarVariants = {
  open: {
    width: 280,
    transition: { type: 'spring' as const, stiffness: 300, damping: 30 },
  },
  collapsed: {
    width: 72,
    transition: { type: 'spring' as const, stiffness: 300, damping: 30 },
  },
};

const labelVariants = {
  open: { opacity: 1, x: 0, display: 'block' },
  collapsed: { opacity: 0, x: -10, display: 'none' },
};

const mobileOverlayVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
};

const mobilePanelVariants = {
  hidden: { x: '-100%' },
  visible: {
    x: 0,
    transition: { type: 'spring' as const, stiffness: 300, damping: 30 },
  },
};

const ROLE_SUBTITLE: Record<string, string> = {
  DOCTOR: 'Clinician',
  ADMIN: 'Administrator',
  SUPER_ADMIN: 'Platform Admin',
  STAFF: 'Staff',
};

export default function Sidebar({
  userRole = null,
  userName = null,
  userEmail = null,
}: {
  /** Passed by the server layout. When 'ADMIN', we render a Back to Admin
   *  bridge so admins can return to /system-admin without hunting for it. */
  userRole?: string | null;
  /** Display name (User.name from NextAuth). May be null for users who
   *  only have an email on file. */
  userName?: string | null;
  /** Fallback when userName is missing. */
  userEmail?: string | null;
}) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const isAdmin = userRole === 'ADMIN' || userRole === 'SUPER_ADMIN';

  // Display name fallback chain: name → email local-part → "User".
  // Avoids an empty/blank header if a user was created without a name.
  const displayName =
    userName?.trim() ||
    userEmail?.split('@')[0] ||
    'User';
  const initial = displayName.slice(0, 1).toUpperCase();
  const subtitle =
    (userRole && ROLE_SUBTITLE[userRole]) || 'Member';

  const isActive = (href: string) => {
    if (href === '/dashboard') return pathname === '/dashboard';
    return pathname.startsWith(href);
  };

  const sidebarContent = (isMobile: boolean) => (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-6 border-b border-white/10">
        <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-teal-400 shadow-lg shadow-blue-500/20 shrink-0">
          <Stethoscope className="w-5 h-5 text-white" />
        </div>
        <AnimatePresence>
          {(!collapsed || isMobile) && (
            <motion.span
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              className="text-lg font-bold text-white whitespace-nowrap"
            >
              MedDoc Pro
            </motion.span>
          )}
        </AnimatePresence>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const active = isActive(item.href);
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => isMobile && setMobileOpen(false)}
              className="block"
            >
              <motion.div
                whileHover={{ x: 4 }}
                whileTap={{ scale: 0.98 }}
                className={`
                  relative flex items-center gap-3 px-3 py-2.5 rounded-xl
                  transition-colors duration-200 group
                  ${
                    active
                      ? 'text-white'
                      : 'text-slate-400 hover:text-white'
                  }
                `}
              >
                {/* Active background */}
                {active && (
                  <motion.div
                    layoutId={isMobile ? 'active-nav-mobile' : 'active-nav'}
                    className="absolute inset-0 rounded-xl bg-gradient-to-r from-blue-600/30 to-teal-500/20 border border-blue-500/20"
                    transition={{
                      type: 'spring',
                      stiffness: 350,
                      damping: 30,
                    }}
                  />
                )}

                {/* Active indicator bar */}
                {active && (
                  <motion.div
                    layoutId={
                      isMobile ? 'active-indicator-mobile' : 'active-indicator'
                    }
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 rounded-r-full bg-gradient-to-b from-blue-400 to-teal-400"
                  />
                )}

                <div
                  className={`
                    relative z-10 flex items-center justify-center w-9 h-9 rounded-lg shrink-0
                    transition-colors duration-200
                    ${
                      active
                        ? 'bg-blue-500/20 text-blue-400'
                        : 'text-slate-400 group-hover:bg-white/5 group-hover:text-white'
                    }
                  `}
                >
                  <Icon className="w-5 h-5" />
                </div>

                <AnimatePresence>
                  {(!collapsed || isMobile) && (
                    <motion.span
                      variants={labelVariants}
                      initial="collapsed"
                      animate="open"
                      exit="collapsed"
                      className="relative z-10 text-sm font-medium whitespace-nowrap"
                    >
                      {item.label}
                    </motion.span>
                  )}
                </AnimatePresence>
              </motion.div>
            </Link>
          );
        })}

        {/* Back to Admin — only for ADMINs. Plain <a> (not next/link) for a
            full-page load: admin and clinician surfaces are separate layouts
            and a soft RSC nav between them can leave stale tree bits behind.
            Mirror of the "Clinician view" escape hatch in AdminSidebar. */}
        {isAdmin && (
          <>
            <div className="my-4 h-px bg-white/5" />
            <a
              href="/system-admin"
              onClick={() => isMobile && setMobileOpen(false)}
              className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-orange-300/80 hover:text-orange-200 hover:bg-orange-500/10 border border-transparent hover:border-orange-500/20 transition-colors group"
            >
              <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-orange-500/10 border border-orange-500/20 shrink-0">
                <Terminal className="w-4 h-4 text-orange-400" />
              </div>
              <AnimatePresence>
                {(!collapsed || isMobile) && (
                  <motion.span
                    variants={labelVariants}
                    initial="collapsed"
                    animate="open"
                    exit="collapsed"
                    className="text-sm font-medium whitespace-nowrap"
                  >
                    Back to Admin
                  </motion.span>
                )}
              </AnimatePresence>
            </a>
          </>
        )}
      </nav>

      {/* User section */}
      <div className="px-3 py-4 border-t border-white/10">
        <div
          className={`flex items-center gap-3 px-3 py-2 ${
            collapsed && !isMobile ? 'justify-center' : ''
          }`}
        >
          <div
            className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-teal-400 flex items-center justify-center shrink-0 text-white font-semibold text-sm shadow-lg shadow-blue-500/20"
            aria-label={`${displayName} avatar`}
          >
            {initial}
          </div>
          <AnimatePresence>
            {(!collapsed || isMobile) && (
              <motion.div
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                className="flex-1 min-w-0"
              >
                <p className="text-sm font-medium text-white truncate">
                  {displayName}
                </p>
                <p className="text-xs text-slate-400 truncate">{subtitle}</p>
              </motion.div>
            )}
          </AnimatePresence>
          <AnimatePresence>
            {(!collapsed || isMobile) && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <LogoutButton iconOnly ariaLabel="Logout" />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Mobile menu button */}
      <button
        onClick={() => setMobileOpen(true)}
        className="fixed top-4 left-4 z-50 p-2 rounded-xl bg-slate-900/90 text-white backdrop-blur-sm border border-white/10 lg:hidden cursor-pointer"
        aria-label="Open menu"
      >
        <Menu className="w-5 h-5" />
      </button>

      {/* Mobile sidebar overlay */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              variants={mobileOverlayVariants}
              initial="hidden"
              animate="visible"
              exit="hidden"
              onClick={() => setMobileOpen(false)}
              className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm lg:hidden"
            />
            <motion.aside
              variants={mobilePanelVariants}
              initial="hidden"
              animate="visible"
              exit="hidden"
              className="fixed inset-y-0 left-0 z-50 w-[280px] lg:hidden"
              style={{
                background:
                  'linear-gradient(180deg, rgba(15, 23, 42, 0.97) 0%, rgba(2, 6, 23, 0.99) 100%)',
                borderRight: '1px solid rgba(255,255,255,0.08)',
              }}
            >
              <button
                onClick={() => setMobileOpen(false)}
                className="absolute top-4 right-4 p-2 text-slate-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors cursor-pointer"
                aria-label="Close menu"
              >
                <X className="w-5 h-5" />
              </button>
              {sidebarContent(true)}
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Desktop sidebar */}
      <motion.aside
        variants={sidebarVariants}
        animate={collapsed ? 'collapsed' : 'open'}
        className="hidden lg:flex lg:flex-col lg:shrink-0 relative h-screen overflow-hidden"
        style={{
          background:
            'linear-gradient(180deg, rgba(15, 23, 42, 0.97) 0%, rgba(2, 6, 23, 0.99) 100%)',
          borderRight: '1px solid rgba(255,255,255,0.08)',
        }}
      >
        {sidebarContent(false)}

        {/* Collapse toggle */}
        <motion.button
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          onClick={() => setCollapsed(!collapsed)}
          className="absolute top-7 -right-3 w-6 h-6 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-400 hover:text-white hover:border-blue-500 transition-colors shadow-lg cursor-pointer z-10"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <motion.div animate={{ rotate: collapsed ? 180 : 0 }}>
            <ChevronLeft className="w-3.5 h-3.5" />
          </motion.div>
        </motion.button>

        {/* Decorative glow */}
        <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-blue-500/5 to-transparent pointer-events-none" />
      </motion.aside>
    </>
  );
}
