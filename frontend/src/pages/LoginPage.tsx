import { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { LoginForm } from '@/components/auth/LoginForm';
import { GlassCard } from '@/components/ui/GlassCard';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { MeshBackground } from '@/components/layout/MeshBackground';
import { useAuth } from '@/hooks/useAuth';

export function LoginPage() {
  const { user, isLoading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isLoading && user) {
      navigate('/dashboard', { replace: true });
    }
  }, [user, isLoading, navigate]);

  return (
    <PageWrapper className="flex items-center justify-center px-4">
      <MeshBackground />
      <GlassCard className="w-full max-w-sm">
        <h1 className="text-xl font-semibold">Log in</h1>
        <p className="mb-6 mt-1 text-sm text-muted-foreground">
          Welcome back — enter your details to continue.
        </p>
        <LoginForm />
        <p className="mt-6 text-center text-sm text-muted-foreground">
          Don&apos;t have an account?{' '}
          <Link to="/register" className="font-medium text-primary hover:underline">
            Sign up
          </Link>
        </p>
      </GlassCard>
    </PageWrapper>
  );
}
