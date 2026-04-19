"use client"

import React from 'react';
import { useAuth } from '../components/contexts/AuthContext';

export default function AuthModal() {
  const { user, login, logout } = useAuth();

  return (
    <div className="absolute top-4 right-4 z-50">
      {user ? (
        <div className="flex items-center gap-4 bg-white px-4 py-2 rounded-lg shadow-sm border border-gray-200">
          <span className="text-sm font-medium text-gray-700">Hi, {user.name}</span>
          <button 
            onClick={logout}
            className="text-sm text-red-600 hover:text-red-700 font-medium"
          >
            Sign Out
          </button>
        </div>
      ) : (
        <button
          onClick={login}
          className="bg-black text-white px-6 py-2 rounded-lg hover:bg-gray-800 transition shadow-sm font-medium"
        >
          Sign In (Dummy)
        </button>
      )}
    </div>
  );
}