import { useContext } from 'react';
import { AuthContext } from '@/context/AuthContext';
import type { AuthContextValue } from '@/context/AuthContext';

/**
 * Access the current auth state ({ user, isLoading, login, register,
 * logout, refreshUser }). Must be called under an `<AuthProvider>`.
 */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
