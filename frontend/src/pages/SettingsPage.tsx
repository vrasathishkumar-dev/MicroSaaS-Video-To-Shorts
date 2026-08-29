import { useState } from 'react';
import type { FormEvent } from 'react';
import { GlassCard } from '@/components/ui/GlassCard';
import { GradientButton } from '@/components/ui/GradientButton';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { useAuth } from '@/hooks/useAuth';
import * as authService from '@/services/authService';

/** Account settings: update display name, view email, and log out. */
export function SettingsPage() {
  const { user, logout, refreshUser } = useAuth();
  const [fullName, setFullName] = useState(user?.full_name ?? '');
  const [isSaving, setIsSaving] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    setSuccessMessage(null);
    try {
      await authService.updateProfile({ full_name: fullName });
      await refreshUser();
      setSuccessMessage('Your profile has been updated.');
    } catch {
      setError('Failed to update your profile. Please try again.');
    } finally {
      setIsSaving(false);
    }
  }

  async function handleLogout() {
    setIsLoggingOut(true);
    try {
      await logout();
    } finally {
      setIsLoggingOut(false);
    }
  }

  return (
    <PageWrapper className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="mb-8 text-xl font-semibold">Settings</h1>

      <GlassCard className="flex flex-col gap-6">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="full_name" className="text-sm font-medium">
              Full name
            </label>
            <input
              id="full_name"
              type="text"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              className="rounded-lg border border-glass-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              placeholder="Your name"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium">Email</span>
            <p className="rounded-lg border border-glass-border bg-muted px-3 py-2 text-sm text-muted-foreground">
              {user?.email}
            </p>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
          {successMessage && (
            <p className="text-sm text-emerald-600 dark:text-emerald-400">
              {successMessage}
            </p>
          )}

          <GradientButton type="submit" disabled={isSaving} className="self-start">
            {isSaving ? 'Saving…' : 'Save changes'}
          </GradientButton>
        </form>

        <div className="border-t border-glass-border pt-6">
          <GradientButton
            type="button"
            variant="outline"
            onClick={() => void handleLogout()}
            disabled={isLoggingOut}
          >
            {isLoggingOut ? 'Logging out…' : 'Log out'}
          </GradientButton>
        </div>
      </GlassCard>
    </PageWrapper>
  );
}
