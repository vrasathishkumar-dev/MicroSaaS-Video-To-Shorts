import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { AlertCircle, CheckCircle2, KeyRound, Loader2, Lock } from 'lucide-react';
import { GlassCard } from '@/components/ui/GlassCard';
import { GradientButton } from '@/components/ui/GradientButton';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { MeshBackground } from '@/components/layout/MeshBackground';
import { resetPassword } from '@/services/authService';

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const initialToken = searchParams.get('token') || '';

  const [token, setToken] = useState(initialToken);
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(undefined);

    const cleanToken = token.trim();
    if (!cleanToken) {
      setError('Reset token is required.');
      return;
    }

    if (!password) {
      setError('New password is required.');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setIsLoading(true);
    try {
      const res = await resetPassword(cleanToken, password);
      setSuccessMessage(res.message);
      setIsSuccess(true);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setError(msg || 'Failed to reset password. The link may have expired or is invalid.');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <PageWrapper className="flex items-center justify-center px-4">
      <MeshBackground />
      <GlassCard className="w-full max-w-sm">
        {isSuccess ? (
          <div className="text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-400">
              <CheckCircle2 className="h-6 w-6" />
            </div>
            <h1 className="text-xl font-semibold">Password Reset Complete</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              {successMessage || 'Your password has been updated successfully.'}
            </p>
            <div className="mt-6">
              <Link to="/login">
                <GradientButton type="button" className="w-full">
                  Log in with new password
                </GradientButton>
              </Link>
            </div>
          </div>
        ) : (
          <>
            <h1 className="text-xl font-semibold">Set New Password</h1>
            <p className="mb-6 mt-1 text-sm text-muted-foreground">
              Enter your reset token and choose a secure new password.
            </p>

            {error && (
              <div className="mb-4 flex items-start gap-2 rounded-xl border border-destructive/20 bg-destructive/10 p-3 text-xs text-destructive">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
              <div>
                <label htmlFor="reset-token" className="mb-1 block text-sm font-medium">
                  Reset Token
                </label>
                <div className="relative">
                  <KeyRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    id="reset-token"
                    name="token"
                    type="text"
                    value={token}
                    onChange={(e) => setToken(e.target.value)}
                    placeholder="Paste token here"
                    className="w-full rounded-xl border border-input bg-background/50 py-3 pl-10 pr-4 text-sm font-mono outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-ring/50"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="new-password" className="mb-1 block text-sm font-medium">
                  New Password
                </label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    id="new-password"
                    name="password"
                    type="password"
                    autoComplete="new-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="At least 8 characters"
                    className="w-full rounded-xl border border-input bg-background/50 py-3 pl-10 pr-4 text-sm outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-ring/50"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="confirm-password" className="mb-1 block text-sm font-medium">
                  Confirm New Password
                </label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    id="confirm-password"
                    name="confirm-password"
                    type="password"
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Repeat password"
                    className="w-full rounded-xl border border-input bg-background/50 py-3 pl-10 pr-4 text-sm outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-ring/50"
                  />
                </div>
              </div>

              <GradientButton
                type="submit"
                disabled={isLoading}
                className="w-full flex items-center justify-center gap-2 mt-2"
              >
                {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
                {isLoading ? 'Updating password...' : 'Update password'}
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
