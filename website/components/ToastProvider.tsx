"use client";

import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';

export type ToastVariant = 'info' | 'success' | 'error' | 'warning';

export interface ToastOptions {
  message: string;
  variant?: ToastVariant;
  durationMs?: number;
}

interface ToastItem extends Required<ToastOptions> {
  id: string;
}

interface ToastContextValue {
  showToast: (opts: ToastOptions) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}

function ToastStack({ toasts, dismiss }: { toasts: ToastItem[]; dismiss: (id: string) => void }) {
  return (
    <div className="fixed top-4 right-4 z-50 space-y-3">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={
            'glass-card min-w-[260px] max-w-[380px] px-4 py-3 rounded-xl shadow-soft text-sm flex items-start gap-3 border ' +
            (t.variant === 'success'
              ? 'border-[#29b6f6]/40 text-[#f0f4f8]'
              : t.variant === 'error'
              ? 'border-[#f43f5e]/40 text-[#f0f4f8]'
              : t.variant === 'warning'
              ? 'border-amber-500/40 text-[#f0f4f8]'
              : 'border-[#242c3a] text-[#f0f4f8]')
          }
        >
          <span className="mt-0.5 text-base">
            {t.variant === 'success' && '✨'}
            {t.variant === 'error' && '🛑'}
            {t.variant === 'warning' && '⚠️'}
            {t.variant === 'info' && '💡'}
          </span>
          <div className="flex-1 font-[var(--font-sans)] font-medium leading-relaxed">{t.message}</div>
          <button
            onClick={() => dismiss(t.id)}
            className="text-[#6b7a8d] hover:text-[#f0f4f8] transition-colors bg-[#1e2433] hover:bg-[#242c3a] rounded-md p-1 mt-0.5"
            aria-label="Dismiss"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback((opts: ToastOptions) => {
    const id = Math.random().toString(36).slice(2);
    const toast: ToastItem = {
      id,
      message: opts.message,
      variant: opts.variant ?? 'info',
      durationMs: opts.durationMs ?? 3000,
    };
    setToasts((prev) => [...prev, toast]);
    window.setTimeout(() => dismiss(id), toast.durationMs);
  }, [dismiss]);

  const value = useMemo(() => ({ showToast }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastStack toasts={toasts} dismiss={dismiss} />
    </ToastContext.Provider>
  );
}