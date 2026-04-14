'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { FileText, Plus, Clock } from 'lucide-react';
import Link from 'next/link';
import Button from '@/components/ui/Button';

export default function HistoryPage() {
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8">
      {/* Header */}
      <motion.div
        initial={{ y: 10, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.5 }}
      >
        <h1 className="text-2xl font-bold text-slate-800 dark:text-white">
          Document History
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          View and manage your previously generated documents.
        </p>
      </motion.div>

      {/* Empty state */}
      <motion.div
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.15, duration: 0.5 }}
        className="mt-12 flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-slate-50/50 px-6 py-16 text-center dark:border-slate-700 dark:bg-slate-800/30"
      >
        {/* Icon stack */}
        <div className="relative mb-6">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-100 dark:bg-slate-800">
            <FileText className="h-8 w-8 text-slate-400 dark:text-slate-500" />
          </div>
          <div className="absolute -right-2 -top-2 flex h-8 w-8 items-center justify-center rounded-full border-2 border-white bg-slate-200 dark:border-slate-900 dark:bg-slate-700">
            <Clock className="h-4 w-4 text-slate-400 dark:text-slate-500" />
          </div>
        </div>

        <h2 className="text-lg font-semibold text-slate-700 dark:text-slate-200">
          No documents edited yet
        </h2>
        <p className="mt-1.5 max-w-sm text-sm text-slate-400 dark:text-slate-500">
          Your edited procedure documents will appear here. Upload a document
          in the Doc Editor to get started.
        </p>

        <Link href="/dashboard/doc-editor" className="mt-6">
          <Button>
            <Plus className="h-4 w-4" />
            Open Doc Editor
          </Button>
        </Link>
      </motion.div>
    </div>
  );
}
