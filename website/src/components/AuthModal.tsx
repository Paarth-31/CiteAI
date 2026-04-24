"use client"

import React, { useState } from 'react';
import { useAuth } from '@/components/contexts/AuthContext';
import { X, Loader2 } from 'lucide-react';

export default function AuthModal() {
  const { authModalView, hideAuthModal, login, register, updateProfile, user, showAuthModal } = useAuth();
  const [formData, setFormData] = useState({
    name: user?.name || '',
    email: '',
    password: '',
    confirmPassword: '',
    rememberMe: false,
  });
  const [showEmailVerification, setShowEmailVerification] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  if (!authModalView) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    
    try {
      if (authModalView === 'signIn') {
        await login(formData.email, formData.password, formData.rememberMe);
      } else if (authModalView === 'register') {
        if (formData.password !== formData.confirmPassword) {
          alert('Passwords do not match');
          setIsLoading(false);
          return;
        }
        const success = await register(formData.name, formData.email, formData.password);
        if (success) {
          setShowEmailVerification(true);
        }
      } else if (authModalView === 'editProfile') {
        await updateProfile(formData.name);
      }
    } catch (error) {
      // Errors should be handled/displayed via AuthContext or a toast system
    } finally {
      setIsLoading(false);
    }
  };

  const switchToRegister = () => {
    setShowEmailVerification(false);
    setFormData({ name: '', email: '', password: '', confirmPassword: '', rememberMe: false });
    showAuthModal('register');
  };

  const switchToSignIn = () => {
    setShowEmailVerification(false);
    setFormData({ name: '', email: '', password: '', confirmPassword: '', rememberMe: false });
    showAuthModal('signIn');
  };

  const inputClasses = "w-full bg-[#161b25] border border-[#242c3a] text-[#f0f4f8] placeholder-[#6b7a8d] rounded-xl px-4 py-3 focus:outline-none focus:ring-1 focus:ring-[#29b6f6] focus:border-[#29b6f6] font-[var(--font-sans)] transition-all";
  const labelClasses = "block text-[#c9d1dc] text-xs font-bold mb-2 font-[var(--font-mono)] tracking-wider uppercase";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#0f1117]/80 backdrop-blur-md">
      <div className="relative w-full max-w-md glass-card rounded-2xl p-8 sm:p-10 border border-[#242c3a] shadow-soft">
        <button
          onClick={hideAuthModal}
          className="absolute top-5 right-5 text-[#6b7a8d] hover:text-[#f0f4f8] hover:bg-[#1e2433] p-1.5 rounded-lg transition-colors"
          disabled={isLoading}
        >
          <X size={20} />
        </button>

        {/* Sign In View */}
        {authModalView === 'signIn' && (
          <div className="animate-fade-up">
            <h2 className="text-3xl font-bold text-[#f0f4f8] mb-8 font-[var(--font-heading)] tracking-tight">
              Sign In
            </h2>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className={labelClasses}>Email</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className={inputClasses}
                  placeholder="your@email.com"
                  required
                  disabled={isLoading}
                  autoComplete="off"
                />
              </div>
              <div>
                <label className={labelClasses}>Password</label>
                <input
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className={inputClasses}
                  placeholder="••••••••"
                  required
                  disabled={isLoading}
                  autoComplete="off"
                />
              </div>
              <div className="flex items-center pt-1">
                <input
                  type="checkbox"
                  id="rememberMe"
                  checked={formData.rememberMe}
                  onChange={(e) => setFormData({ ...formData, rememberMe: e.target.checked })}
                  className="w-4 h-4 text-[#29b6f6] bg-[#161b25] border-[#242c3a] rounded focus:ring-[#29b6f6] focus:ring-offset-[#0f1117]"
                  disabled={isLoading}
                />
                <label htmlFor="rememberMe" className="ml-3 text-sm text-[#c9d1dc] font-[var(--font-sans)]">
                  Remember me on this device
                </label>
              </div>
              <button
                type="submit"
                disabled={isLoading}
                className="w-full btn-primary justify-center py-3.5 mt-2"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="animate-spin" size={18} />
                    Authenticating...
                  </>
                ) : (
                  'Sign In'
                )}
              </button>
            </form>

            <p className="text-[#6b7a8d] text-sm text-center mt-8 font-[var(--font-sans)]">
              Don't have an account?{' '}
              <button
                onClick={switchToRegister}
                className="text-[#29b6f6] hover:text-[#81d4fa] font-bold transition-colors underline-cyan"
                disabled={isLoading}
              >
                Create one now
              </button>
            </p>
          </div>
        )}

        {/* Register View */}
        {authModalView === 'register' && (
          <div className="animate-fade-up">
            {showEmailVerification ? (
              <div className="text-center py-4">
                <div className="w-20 h-20 bg-[rgba(41,182,246,0.1)] border border-[rgba(41,182,246,0.2)] rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-[0_0_20px_rgba(41,182,246,0.15)]">
                  <svg className="w-10 h-10 text-[#29b6f6]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h2 className="text-2xl font-bold text-[#f0f4f8] mb-3 font-[var(--font-heading)]">Account Created</h2>
                <p className="text-[#6b7a8d] mb-8 text-sm font-[var(--font-sans)] leading-relaxed">
                  Your secure analysis workspace is ready. You can now sign in.
                </p>
                <button
                  onClick={switchToSignIn}
                  className="w-full btn-primary justify-center py-3.5"
                >
                  Proceed to Sign In
                </button>
              </div>
            ) : (
              <>
                <h2 className="text-3xl font-bold text-[#f0f4f8] mb-8 font-[var(--font-heading)] tracking-tight">
                  Create Account
                </h2>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <label className={labelClasses}>Full Name</label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      className={inputClasses}
                      placeholder="John Doe"
                      required
                      disabled={isLoading}
                      autoComplete="off"
                    />
                  </div>
                  <div>
                    <label className={labelClasses}>Email</label>
                    <input
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      className={inputClasses}
                      placeholder="your@email.com"
                      required
                      disabled={isLoading}
                      autoComplete="off"
                    />
                  </div>
                  <div>
                    <label className={labelClasses}>Password</label>
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                      className={inputClasses}
                      placeholder="••••••••"
                      required
                      disabled={isLoading}
                      autoComplete="off"
                    />
                  </div>
                  <div>
                    <label className={labelClasses}>Confirm Password</label>
                    <input
                      type="password"
                      value={formData.confirmPassword}
                      onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                      className={inputClasses}
                      placeholder="••••••••"
                      required
                      disabled={isLoading}
                      autoComplete="off"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full btn-primary justify-center py-3.5 mt-4"
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="animate-spin" size={18} />
                        Creating workspace...
                      </>
                    ) : (
                      'Register Account'
                    )}
                  </button>
                </form>

                <p className="text-[#6b7a8d] text-sm text-center mt-6 font-[var(--font-sans)]">
                  Already have an account?{' '}
                  <button
                    onClick={switchToSignIn}
                    className="text-[#29b6f6] hover:text-[#81d4fa] font-bold transition-colors underline-cyan"
                    disabled={isLoading}
                  >
                    Sign In
                  </button>
                </p>
              </>
            )}
          </div>
        )}

        {/* Edit Profile View */}
        {authModalView === 'editProfile' && (
          <div className="animate-fade-up">
            <h2 className="text-3xl font-bold text-[#f0f4f8] mb-8 font-[var(--font-heading)] tracking-tight">
              Edit Profile
            </h2>
            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className={labelClasses}>Full Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className={inputClasses}
                  placeholder="John Doe"
                  required
                  disabled={isLoading}
                />
              </div>
              <div>
                <label className={labelClasses}>Email Address</label>
                <input
                  type="email"
                  value={user?.email || ''}
                  className={`${inputClasses} opacity-60 cursor-not-allowed`}
                  disabled
                />
                <p className="text-[10px] text-[#6b7a8d] mt-2 font-[var(--font-mono)] uppercase">Email cannot be changed.</p>
              </div>
              <button
                type="submit"
                disabled={isLoading}
                className="w-full btn-primary justify-center py-3.5 mt-4"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="animate-spin" size={18} />
                    Saving...
                  </>
                ) : (
                  'Save Changes'
                )}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}