import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { Mail } from 'lucide-react';
import { GlassCard } from '@/components/ui/GlassCard';
import { GradientButton } from '@/components/ui/GradientButton';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { MeshBackground } from '@/components/layout/MeshBackground';
import { cn } from '@/lib/utils';

function isValidEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

/**
 * Forgot-password placeholder. The backend reset-email endpoint isn't
 * built yet, so this only validates the address client-side and shows
 * a "check your email" success state — no request is sent.
 */
export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | undefined>(undefined);
  const [isSubmitted, setIsSubmitted] = useState(false);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim()) {
      setError('Email is required.');
      return;
    }
    if (!isValidEmail(email)) {
      setError('Enter a valid email address.');
      return;
    }
    setError(undefined);
    setIsSubmitted(true);
  }

  return (
    <PageWrapper className="flex items-center justify-center px-4">
      <MeshBackground />
      <GlassCard className="w-full max-w-sm">
        {isSubmitted ? (
          <>
            <h1 className="text-xl font-semibold">Check your email</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              If an account exists for <span className="font-medium text-foreground">{email}</span>,
              we&apos;ve sent instructions to reset your password.
            </p>
          </>
        ) : (
          <>
            <h1 className="text-xl font-semibold">Reset your password</h1>
            <p className="mb-6 mt-1 text-sm text-muted-foreground">
              Enter the email associated with your account and we&apos;ll send you a reset link.
            </p>
            <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
              <div>
                <label htmlFor="forgot-password-email" className="mb-1 block text-sm font-medium">
                  Email
                </label>
                <div className="relative">
                  <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    id="forgot-password-email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="you@example.com"
                    aria-invalid={Boolean(error)}
                    className={cn(
                      'w-full rounded-xl border bg-background/50 py-3 pl-10 pr-4 text-sm outline-none transition-colors focus:ring-2 focus:ring-ring/50',
                      error ? 'border-destructive' : 'border-input focus:border-primary',
                    )}
                  />
                </div>
                {error && <p className="mt-1 text-sm text-destructive">{error}</p>}
              </div>
              <GradientButton type="submit" className="w-full">
                Send reset link
              </GradientButton>
            </form>
          </>
        )}
        <p className="mt-6 text-center text-sm text-muted-foreground">
          <Link to="/login" className="font-medium text-primary hover:underline">
            Back to log in
          </Link>
        </p>
      </GlassCard>
    </PageWrapper>
  );
}
