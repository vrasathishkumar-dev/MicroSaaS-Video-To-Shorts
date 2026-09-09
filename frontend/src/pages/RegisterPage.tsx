import { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Clapperboard } from 'lucide-react';
import { RegisterForm } from '@/components/auth/RegisterForm';
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
    <PageWrapper className="flex min-h-screen flex-col items-center justify-center px-4">
      <MeshBackground />

      {/* Logo */}
      <Link
        to="/"
        className="mb-10 flex items-center gap-2 text-[15px] font-semibold text-foreground transition-opacity hover:opacity-70"
      >
        <div
          className="flex h-8 w-8 items-center justify-center rounded-lg"
          style={{ backgroundColor: 'oklch(0.60 0.20 264)' }}
        >
          <Clapperboard className="h-4 w-4 text-white" />
        </div>
        Video<span style={{ color: 'oklch(0.60 0.20 264)' }}>ToShorts</span>
      </Link>

      {/* Auth card */}
      <div
        className="w-full max-w-sm rounded-2xl border p-8"
        style={{
          borderColor: 'oklch(1 0 0 / 10%)',
          backgroundColor: 'oklch(0.10 0.02 264)',
        }}
      >
        <h1 className="mb-1 text-xl font-semibold text-foreground">Create account</h1>
        <p className="mb-7 text-sm text-muted-foreground">
          Start turning long videos into shorts in minutes.
        </p>
        <RegisterForm />
        <p className="mt-6 text-center text-sm text-muted-foreground">
          Already have an account?{' '}
          <Link
            to="/login"
            className="font-medium text-primary transition-opacity hover:opacity-80"
          >
            Log in
          </Link>
        </p>
      </div>
    </PageWrapper>
  );
}
