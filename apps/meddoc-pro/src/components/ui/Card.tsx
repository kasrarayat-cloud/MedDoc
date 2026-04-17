'use client';

import React from 'react';
import { motion, type HTMLMotionProps } from 'framer-motion';

interface CardProps extends Omit<HTMLMotionProps<'div'>, 'children'> {
  children: React.ReactNode;
  hoverable?: boolean;
  className?: string;
}

const Card: React.FC<CardProps> = ({
  children,
  hoverable = false,
  className = '',
  ...props
}) => {
  return (
    <motion.div
      whileHover={
        hoverable
          ? { y: -4, scale: 1.01, transition: { duration: 0.2, ease: 'easeOut' } }
          : undefined
      }
      className={`
        rounded-2xl border border-white/20 p-6
        bg-white/70 backdrop-blur-lg
        shadow-sm
        dark:bg-slate-800/70 dark:border-slate-700/50
        transition-shadow duration-300 ease-in-out
        ${hoverable ? 'hover:shadow-xl hover:shadow-blue-500/5 dark:hover:shadow-blue-400/5 cursor-pointer' : ''}
        ${className}
      `}
      {...props}
    >
      {children}
    </motion.div>
  );
};

Card.displayName = 'Card';

export default Card;
