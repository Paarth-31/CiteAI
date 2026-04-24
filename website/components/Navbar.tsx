"use client"

import React, { useState } from 'react';
import { useAuth } from '@/components/contexts/AuthContext';
import { Layers, ChevronDown, Menu, X } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function Navbar() {
  const { user, logout, showAuthModal } = useAuth();
  const [showProfileDropdown, setShowProfileDropdown] = useState(false);
  const [showMobileMenu, setShowMobileMenu] = useState(false);
  const pathname = usePathname();

  const isActive = (path: string) => pathname === path;

  return (
    <nav className="sticky top-0 z-40 bg-[#0f1117]/90 backdrop-blur-md border-b border-[#242c3a] shadow-sm">
      <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 py-4">
        <div className="flex items-center justify-between">
          {/* Left: Title */}
          <Link href="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#29b6f6] to-[#1a6fa3] flex items-center justify-center shadow-[0_0_15px_rgba(41,182,246,0.3)]">
              <Layers className="text-[#050a0e] flex-shrink-0" size={22} strokeWidth={2.5} />
            </div>
            {/* Made Cite-AI significantly bigger and used the new heading font */}
           <h1 className="text-2xl sm:text-2xl font-bold text-[#f0f4f8] tracking-tight font-['Passero One']">
  CITE-AI
</h1>
          </Link>

          {/* Mobile Menu Button */}
          <button
            onClick={() => setShowMobileMenu(!showMobileMenu)}
            className="md:hidden p-2 text-[#6b7a8d] hover:bg-[#1e2433] rounded-lg transition-colors"
            aria-label="Toggle menu"
          >
            {showMobileMenu ? <X size={24} className="text-[#f0f4f8]" /> : <Menu size={24} className="text-[#f0f4f8]" />}
          </button>

          {/* Desktop: Center Navigation + Right Auth */}
          <div className="hidden md:flex items-center gap-8">
            {/* Center: Navigation */}
            <div className="flex items-center gap-2">
              <Link
                href="/"
                className={`transition-colors font-medium text-sm px-4 py-2 rounded-lg font-[var(--font-sans)] ${
                  isActive('/') 
                    ? 'text-[#29b6f6] bg-[#1e2433]' 
                    : 'text-[#6b7a8d] hover:text-[#f0f4f8] hover:bg-[#1e2433]/50'
                }`}
              >
                Workspaces
              </Link>
              <Link
                href="/search"
                className={`transition-colors font-medium text-sm px-4 py-2 rounded-lg font-[var(--font-sans)] ${
                  isActive('/search') 
                    ? 'text-[#29b6f6] bg-[#1e2433]' 
                    : 'text-[#6b7a8d] hover:text-[#f0f4f8] hover:bg-[#1e2433]/50'
                }`}
              >
                Global Search
              </Link>
            </div>

            {/* Right: Auth */}
            <div>
              {user ? (
                <div className="relative">
                  <button
                    onClick={() => setShowProfileDropdown(!showProfileDropdown)}
                    className="flex items-center gap-3 bg-[#161b25] hover:bg-[#1e2433] text-[#f0f4f8] px-3 py-1.5 rounded-full transition-all border border-[#242c3a]"
                  >
                    <div className="w-7 h-7 bg-[#29b6f6] rounded-full flex items-center justify-center text-[#050a0e] font-bold text-xs font-[var(--font-heading)]">
                      {user.name.charAt(0).toUpperCase()}
                    </div>
                    <span className="font-medium text-sm hidden lg:inline font-[var(--font-sans)]">{user.name}</span>
                    <ChevronDown size={16} className="text-[#6b7a8d] mr-1" />
                  </button>

                  {showProfileDropdown && (
                    <>
                      <div 
                        className="fixed inset-0 z-10" 
                        onClick={() => setShowProfileDropdown(false)}
                      />
                      <div className="absolute right-0 mt-3 w-52 glass-card rounded-xl overflow-hidden z-20 border border-[#242c3a] shadow-soft p-1.5">
                        <button
                          onClick={() => {
                            setShowProfileDropdown(false);
                            showAuthModal('editProfile');
                          }}
                          className="w-full text-left px-4 py-2.5 text-[#c9d1dc] hover:bg-[#1e2433] hover:text-[#f0f4f8] transition-colors text-sm rounded-lg font-[var(--font-sans)]"
                        >
                          Edit Profile
                        </button>
                        <button
                          onClick={() => {
                            setShowProfileDropdown(false);
                            logout();
                          }}
                          className="w-full text-left px-4 py-2.5 text-[#f43f5e] hover:bg-[#f43f5e]/10 transition-colors mt-1 text-sm rounded-lg font-[var(--font-sans)]"
                        >
                          Sign Out
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ) : (
                <button
                  onClick={() => showAuthModal('signIn')}
                  className="btn-primary"
                >
                  Sign In
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Mobile Menu */}
        {showMobileMenu && (
          <div className="md:hidden mt-4 pt-4 border-t border-[#242c3a] space-y-2">
            <Link
              href="/"
              onClick={() => setShowMobileMenu(false)}
              className={`block w-full text-left transition-colors font-medium py-3 px-4 rounded-xl text-sm ${
                isActive('/') 
                  ? 'text-[#29b6f6] bg-[#1e2433]' 
                  : 'text-[#6b7a8d] hover:text-[#f0f4f8] hover:bg-[#1e2433]'
              }`}
            >
              Workspaces
            </Link>
            <Link
              href="/search"
              onClick={() => setShowMobileMenu(false)}
              className={`block w-full text-left transition-colors font-medium py-3 px-4 rounded-xl text-sm ${
                isActive('/search') 
                  ? 'text-[#29b6f6] bg-[#1e2433]' 
                  : 'text-[#6b7a8d] hover:text-[#f0f4f8] hover:bg-[#1e2433]'
              }`}
            >
              Global Search
            </Link>
            
            <div className="pt-4 mt-2 border-t border-[#242c3a]">
              {user ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-3 py-2 px-4 mb-2">
                    <div className="w-10 h-10 bg-[#29b6f6] rounded-full flex items-center justify-center text-[#050a0e] font-bold text-base font-[var(--font-heading)]">
                      {user.name.charAt(0).toUpperCase()}
                    </div>
                    <span className="text-[#f0f4f8] font-medium">{user.name}</span>
                  </div>
                  <button
                    onClick={() => {
                      setShowMobileMenu(false);
                      showAuthModal('editProfile');
                    }}
                    className="w-full text-left bg-[#161b25] hover:bg-[#1e2433] text-[#f0f4f8] px-4 py-3 rounded-xl transition-colors border border-[#242c3a] text-sm"
                  >
                    Edit Profile
                  </button>
                  <button
                    onClick={() => {
                      setShowMobileMenu(false);
                      logout();
                    }}
                    className="w-full text-left bg-[#161b25] hover:bg-[#1e2433] text-[#f43f5e] px-4 py-3 rounded-xl transition-colors border border-[#242c3a] text-sm"
                  >
                    Sign Out
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => {
                    setShowMobileMenu(false);
                    showAuthModal('signIn');
                  }}
                  className="w-full btn-primary justify-center py-3"
                >
                  Sign In
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}