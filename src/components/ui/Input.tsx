'use client';

import React, { useId } from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  icon?: React.ReactNode;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, icon, className = '', id, ...props }, ref) => {
    const generatedId = useId();
    const inputId = id ?? generatedId;

    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={inputId}
            className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300"
          >
            {label}
          </label>
        )}

        <div className="relative">
          {icon && (
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500">
              {icon}
            </span>
          )}

          <input
            ref={ref}
            id={inputId}
            aria-invalid={!!error}
            aria-describedby={error ? `${inputId}-error` : undefined}
            className={`
              w-full rounded-lg border bg-white px-4 py-2.5 text-sm text-slate-900
              transition-all duration-200 ease-in-out
              placeholder:text-slate-400
              focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500
              dark:bg-slate-800 dark:text-slate-100 dark:placeholder:text-slate-500
              dark:focus:ring-blue-400 dark:focus:border-blue-400
              disabled:cursor-not-allowed disabled:opacity-50 disabled:bg-slate-50
              dark:disabled:bg-slate-900
              ${icon ? 'pl-10' : ''}
              ${
                error
                  ? 'border-red-500 focus:ring-red-500 focus:border-red-500 dark:border-red-400 dark:focus:ring-red-400 dark:focus:border-red-400'
                  : 'border-slate-300 hover:border-slate-400 dark:border-slate-600 dark:hover:border-slate-500'
              }
              ${className}
            `}
            {...props}
          />
        </div>

        {error && (
          <p
            id={`${inputId}-error`}
            role="alert"
            className="mt-1.5 text-sm text-red-600 dark:text-red-400"
          >
            {error}
          </p>
        )}
      </div>
    );
  },
);

Input.displayName = 'Input';

export default Input;
