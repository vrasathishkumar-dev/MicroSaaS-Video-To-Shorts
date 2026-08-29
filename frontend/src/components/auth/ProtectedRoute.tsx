import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { Navbar } from '@/components/layout/Navbar';
import { useAuth } from '@/hooks/useAuth';

export interface ProtectedRouteProps {
  children: ReactNode;
}

/**
 * Gate for authenticated-only routes. Renders children once a user is
 * hydrated; redirects to /login once hydration finishes and no user
 * was found. Shows a lightweight loading state in between so a valid
 * session isn't bounced to /login on a page refresh.
 *
 * Also renders the persistent Navbar above children so every
 * authenticated page gets consistent navigation without needing to
 * include it individually.
 */
export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        Loading...
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return (
    <>
      <Navbar />
      {children}
    </>
  );
}

