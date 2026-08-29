import { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { RegisterForm } from '@/components/auth/RegisterForm';
import { GlassCard } from '@/components/ui/GlassCard';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { MeshBackground } from '@/components/layout/MeshBackground';
import { useAuth } from '@/hooks/useAuth';

export function RegisterPage() {
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
        <h1 className="text-xl font-semibold">Create account</h1>
        <p className="mb-6 mt-1 text-sm text-muted-foreground">
          Start turning long videos into shorts in minutes.
        </p>
        <RegisterForm />
        <p className="mt-6 text-center text-sm text-muted-foreground">
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-primary hover:underline">
            Log in
          </Link>
        </p>
      </GlassCard>
    </PageWrapper>
  );
}
