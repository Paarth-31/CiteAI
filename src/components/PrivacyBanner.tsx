"use client"

import React from 'react';
import { Lock, Check } from 'lucide-react';

export default function PrivacyBanner() {
  return (
    <div className="bg-[#0b0e15] border-b border-[#242c3a] py-2.5">
      <div className="max-w-screen-2xl mx-auto px-4 sm:px-6">
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-8">
          {/* Main Privacy Message */}
          <div className="flex items-center gap-2 text-[#f0f4f8]">
            <Lock size={14} className="text-[#29b6f6] flex-shrink-0" />
            <p className="text-[11px] sm:text-xs font-bold tracking-widest font-[var(--font-mono)] text-[#c9d1dc] uppercase">
              100% Local Processing
            </p>
          </div>

          {/* Separator */}
          <div className="hidden sm:block w-px h-3.5 bg-[#242c3a]" />

          {/* 3 Checkmarks - Key Features */}
          <div className="flex flex-wrap items-center justify-center gap-4 sm:gap-6 text-[11px] sm:text-xs text-[#6b7a8d] font-[var(--font-sans)]">
            <div className="flex items-center gap-1.5">
              <Check size={14} className="text-[#29b6f6] flex-shrink-0" />
              <span>Data stays on your machine</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Check size={14} className="text-[#29b6f6] flex-shrink-0" />
              <span>Secure processing</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Check size={14} className="text-[#29b6f6] flex-shrink-0" />
              <span>Privacy guaranteed</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}