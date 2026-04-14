'use client';

import React, { useState, useTransition } from 'react';
import { motion } from 'framer-motion';
import { User, CreditCard, Shield, Lock, Check, AlertCircle, Loader2 } from 'lucide-react';
import Input from '@/components/ui/Input';
import { updateProfile, updatePassword } from './actions';

interface SettingsProps {
  user: {
    name: string;
    email: string;
    role: string;
    mfaEnabled: boolean;
  };
}

function StatusBanner({ type, message }: { type: 'success' | 'error'; message: string }) {
  const isSuccess = type === 'success';
  return (
    <div
      className={`flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm ${
        isSuccess
          ? 'border border-green-200 bg-green-50 text-green-700 dark:border-green-800 dark:bg-green-900/20 dark:text-green-400'
          : 'border border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400'
      }`}
    >
      {isSuccess ? <Check className="h-4 w-4 flex-shrink-0" /> : <AlertCircle className="h-4 w-4 flex-shrink-0" />}
      <span>{message}</span>
    </div>
  );
}

function roleBadge(role: string) {
  switch (role) {
    case 'DOCTOR':
      return 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300';
    case 'ADMIN':
      return 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300';
    default:
      return 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300';
  }
}

export default function SettingsClient({ user }: SettingsProps) {
  // ── Profile form ──
  const [profileName, setProfileName] = useState(user.name);
  const [profilePending, startProfileTransition] = useTransition();
  const [profileStatus, setProfileStatus] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  function handleProfileSubmit(e: React.FormEvent) {
    e.preventDefault();
    setProfileStatus(null);
    const fd = new FormData();
    fd.append('name', profileName);
    startProfileTransition(async () => {
      const result = await updateProfile(fd);
      if (result.ok) {
        setProfileStatus({ type: 'success', message: 'Profile updated successfully.' });
      } else {
        setProfileStatus({ type: 'error', message: result.error ?? 'Update failed.' });
      }
    });
  }

  // ── Password form ──
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [passwordPending, startPasswordTransition] = useTransition();
  const [passwordStatus, setPasswordStatus] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  function handlePasswordSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPasswordStatus(null);

    if (newPassword.length < 6) {
      setPasswordStatus({ type: 'error', message: 'New password must be at least 6 characters.' });
      return;
    }
    if (newPassword !== confirmNewPassword) {
      setPasswordStatus({ type: 'error', message: 'New passwords do not match.' });
      return;
    }

    const fd = new FormData();
    fd.append('currentPassword', currentPassword);
    fd.append('newPassword', newPassword);
    fd.append('confirmNewPassword', confirmNewPassword);
    startPasswordTransition(async () => {
      const result = await updatePassword(fd);
      if (result.ok) {
        setPasswordStatus({ type: 'success', message: 'Password changed successfully.' });
        setCurrentPassword('');
        setNewPassword('');
        setConfirmNewPassword('');
      } else {
        setPasswordStatus({ type: 'error', message: result.error ?? 'Password change failed.' });
      }
    });
  }

  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-8">
      {/* Header */}
      <motion.div
        initial={{ y: 10, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.5 }}
      >
        <h1 className="text-2xl font-bold text-slate-800 dark:text-white">
          Account Settings
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Manage your profile and subscription.
        </p>
      </motion.div>

      <div className="mt-8 space-y-8">
        {/* ── Profile Section ── */}
        <motion.section
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.1, duration: 0.5 }}
          className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800/60"
        >
          <div className="mb-5 flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-100 text-blue-600 dark:bg-blue-900/40 dark:text-blue-400">
              <User className="h-5 w-5" />
            </div>
            <h2 className="text-lg font-semibold text-slate-800 dark:text-white">
              Profile
            </h2>
          </div>

          <form onSubmit={handleProfileSubmit} className="space-y-5">
            <div className="grid gap-5 sm:grid-cols-2">
              <Input
                label="Full Name"
                name="name"
                value={profileName}
                onChange={(e) => setProfileName(e.target.value)}
                placeholder="Dr. Jane Smith"
                disabled={profilePending}
              />
              <Input
                label="Email Address"
                type="email"
                value={user.email}
                disabled
              />
            </div>

            <div className="flex items-center gap-3">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Role:</span>
              <span className={`rounded-full px-3 py-1 text-xs font-medium ${roleBadge(user.role)}`}>
                {user.role}
              </span>
            </div>

            {profileStatus && <StatusBanner type={profileStatus.type} message={profileStatus.message} />}

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={profilePending || profileName.trim() === user.name}
                className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-blue-600 to-teal-500 px-5 py-2 text-sm font-semibold text-white shadow-md shadow-blue-500/20 transition-all hover:shadow-blue-500/30 hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
              >
                {profilePending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  'Update Profile'
                )}
              </button>
            </div>
          </form>
        </motion.section>

        {/* ── Subscription Section (static for now) ── */}
        <motion.section
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.2, duration: 0.5 }}
          className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800/60"
        >
          <div className="mb-5 flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-100 text-teal-600 dark:bg-teal-900/40 dark:text-teal-400">
              <CreditCard className="h-5 w-5" />
            </div>
            <h2 className="text-lg font-semibold text-slate-800 dark:text-white">
              Subscription
            </h2>
          </div>

          <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-5 py-4 dark:border-slate-700 dark:bg-slate-800/40">
            <div>
              <p className="text-sm font-semibold text-slate-800 dark:text-white">
                Professional Plan
              </p>
              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                Unlimited document generation
              </p>
            </div>
            <span className="rounded-full bg-teal-100 px-3 py-1 text-xs font-medium text-teal-700 dark:bg-teal-900/40 dark:text-teal-300">
              Active
            </span>
          </div>

          <p className="mt-4 text-xs text-slate-400 dark:text-slate-500">
            Manage billing and invoices from the billing portal.
          </p>
        </motion.section>

        {/* ── Security Section ── */}
        <motion.section
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.3, duration: 0.5 }}
          className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800/60"
        >
          <div className="mb-5 flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-100 text-amber-600 dark:bg-amber-900/40 dark:text-amber-400">
              <Shield className="h-5 w-5" />
            </div>
            <h2 className="text-lg font-semibold text-slate-800 dark:text-white">
              Security
            </h2>
          </div>

          {/* 2FA status */}
          <div className="mb-6 flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-5 py-4 dark:border-slate-700 dark:bg-slate-800/40">
            <div>
              <p className="text-sm font-semibold text-slate-800 dark:text-white">
                Two-Factor Authentication
              </p>
              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                Add an extra layer of security to your account
              </p>
            </div>
            <span
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                user.mfaEnabled
                  ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
                  : 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-400'
              }`}
            >
              {user.mfaEnabled ? 'Enabled' : 'Not Enabled'}
            </span>
          </div>

          {/* Change password */}
          <div className="border-t border-slate-200 pt-5 dark:border-slate-700">
            <div className="mb-4 flex items-center gap-2">
              <Lock className="h-4 w-4 text-slate-500 dark:text-slate-400" />
              <h3 className="text-sm font-semibold text-slate-800 dark:text-white">
                Change Password
              </h3>
            </div>

            <form onSubmit={handlePasswordSubmit} className="space-y-4">
              <Input
                label="Current Password"
                name="currentPassword"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Enter current password"
                disabled={passwordPending}
              />

              <div className="grid gap-4 sm:grid-cols-2">
                <Input
                  label="New Password"
                  name="newPassword"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Min. 6 characters"
                  disabled={passwordPending}
                />
                <Input
                  label="Confirm New Password"
                  name="confirmNewPassword"
                  type="password"
                  value={confirmNewPassword}
                  onChange={(e) => setConfirmNewPassword(e.target.value)}
                  placeholder="Re-enter new password"
                  disabled={passwordPending}
                />
              </div>

              {passwordStatus && <StatusBanner type={passwordStatus.type} message={passwordStatus.message} />}

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={passwordPending || !currentPassword || !newPassword || !confirmNewPassword}
                  className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-amber-500 to-orange-500 px-5 py-2 text-sm font-semibold text-white shadow-md shadow-amber-500/20 transition-all hover:shadow-amber-500/30 hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
                >
                  {passwordPending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Changing...
                    </>
                  ) : (
                    'Change Password'
                  )}
                </button>
              </div>
            </form>
          </div>
        </motion.section>
      </div>
    </div>
  );
}
