'use client';

import React, { useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  className?: string;
}

const overlayVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
};

const modalVariants = {
  hidden: {
    opacity: 0,
    scale: 0.95,
    y: 16,
  },
  visible: {
    opacity: 1,
    scale: 1,
    y: 0,
    transition: {
      type: 'spring' as const,
      stiffness: 300,
      damping: 25,
    },
  },
  exit: {
    opacity: 0,
    scale: 0.95,
    y: 16,
    transition: { duration: 0.15, ease: 'easeIn' as const },
  },
};

const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  className = '',
}) => {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    },
    [onClose],
  );

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isOpen, handleKeyDown]);

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Overlay */}
          <motion.div
            variants={overlayVariants}
            initial="hidden"
            animate="visible"
            exit="hidden"
            transition={{ duration: 0.2 }}
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={onClose}
            aria-hidden="true"
          />

          {/* Modal panel */}
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={title ?? 'Modal dialog'}
            variants={modalVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            className={`
              relative z-10 w-full max-w-lg
              rounded-2xl border border-white/20 p-6
              bg-white/90 backdrop-blur-xl shadow-2xl
              dark:bg-slate-800/90 dark:border-slate-700/50
              ${className}
            `}
          >
            {/* Header */}
            {(title != null) && (
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                  {title}
                </h2>
                <button
                  onClick={onClose}
                  aria-label="Close modal"
                  className="
                    rounded-lg p-1.5 text-slate-400 transition-colors duration-150
                    hover:bg-slate-100 hover:text-slate-600
                    dark:hover:bg-slate-700 dark:hover:text-slate-300
                    focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500
                  "
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            )}

            {/* Close button when there is no title */}
            {title == null && (
              <button
                onClick={onClose}
                aria-label="Close modal"
                className="
                  absolute right-4 top-4
                  rounded-lg p-1.5 text-slate-400 transition-colors duration-150
                  hover:bg-slate-100 hover:text-slate-600
                  dark:hover:bg-slate-700 dark:hover:text-slate-300
                  focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500
                "
              >
                <X className="h-5 w-5" />
              </button>
            )}

            {/* Content */}
            <div className="text-slate-700 dark:text-slate-300">{children}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};

Modal.displayName = 'Modal';

export default Modal;
