import { useState } from 'react';
import type { FormEvent } from 'react';
import { Mail, User as UserIcon } from 'lucide-react';
import { updateProfile } from '@/services/authService';
import { GlassCard } from '@/components/ui/GlassCard';
import { GradientButton } from '@/components/ui/GradientButton';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';
import type { User } from '@/types';

function isValidEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

interface FormErrors {
  fullName?: string;
  email?: string;
  form?: string;
}

const inputBaseClasses =
  'w-full rounded-xl border bg-background/50 py-3 pl-10 pr-4 text-sm outline-none transition-colors focus:ring-2 focus:ring-ring/50';

interface ProfileEditFormProps {
  user: User;
  onSaved: () => Promise<void>;
}

/**
 * Mounted only once `user` is known, so its fields can initialize
 * straight from props (no effect needed to sync state after an async
 * fetch resolves).
 */
function ProfileEditForm({ user, onSaved }: ProfileEditFormProps) {
  const [fullName, setFullName] = useState(user.full_name ?? '');
  const [email, setEmail] = useState(user.email);
  const [errors, setErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | undefined>(undefined);

  function validate(): boolean {
    const nextErrors: FormErrors = {};
    if (!fullName.trim()) {
      nextErrors.fullName = 'Full name is required.';
    }
    if (!email.trim()) {
      nextErrors.email = 'Email is required.';
    } else if (!isValidEmail(email)) {
      nextErrors.email = 'Enter a valid email address.';
    }
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!validate()) {
      return;
    }

    setIsSubmitting(true);
    setErrors({});
    setSuccessMessage(undefined);
    try {
      await updateProfile({ full_name: fullName, email });
      await onSaved();
      setSuccessMessage('Profile updated.');
    } catch {
      setErrors({ form: 'Could not update your profile. Please try again.' });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <>
      <dl className="mb-6 grid grid-cols-2 gap-4 text-sm">
        <div>
          <dt className="text-muted-foreground">Account status</dt>
          <dd className="font-medium">{user.is_active ? 'Active' : 'Inactive'}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Email verified</dt>
          <dd className="font-medium">{user.is_verified ? 'Verified' : 'Unverified'}</dd>
        </div>
        <div className="col-span-2">
          <dt className="text-muted-foreground">Member since</dt>
          <dd className="font-medium">
            {new Date(user.created_at).toLocaleDateString(undefined, {
              year: 'numeric',
              month: 'long',
              day: 'numeric',
            })}
          </dd>
        </div>
      </dl>

      {errors.form && (
        <p
          role="alert"
          className="mb-4 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive"
        >
          {errors.form}
        </p>
      )}
      {successMessage && (
        <p className="mb-4 rounded-xl border border-primary/30 bg-primary/10 px-4 py-2 text-sm text-primary">
          {successMessage}
        </p>
      )}

      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        <div>
          <label htmlFor="profile-full-name" className="mb-1 block text-sm font-medium">
            Full name
          </label>
          <div className="relative">
            <UserIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              id="profile-full-name"
              name="full_name"
              type="text"
              autoComplete="name"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              aria-invalid={Boolean(errors.fullName)}
              className={cn(
                inputBaseClasses,
                errors.fullName ? 'border-destructive' : 'border-input focus:border-primary',
              )}
            />
          </div>
          {errors.fullName && <p className="mt-1 text-sm text-destructive">{errors.fullName}</p>}
        </div>

        <div>
          <label htmlFor="profile-email" className="mb-1 block text-sm font-medium">
            Email
          </label>
          <div className="relative">
            <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              id="profile-email"
              name="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              aria-invalid={Boolean(errors.email)}
              className={cn(
                inputBaseClasses,
                errors.email ? 'border-destructive' : 'border-input focus:border-primary',
              )}
            />
          </div>
          {errors.email && <p className="mt-1 text-sm text-destructive">{errors.email}</p>}
        </div>

        <GradientButton type="submit" disabled={isSubmitting} className="w-full sm:w-auto">
          {isSubmitting ? 'Saving...' : 'Save changes'}
        </GradientButton>
      </form>
    </>
  );
}

/**
 * Shows the current user's account info (via `useAuth`) and an edit
 * form that calls `authService.updateProfile`, refreshing the shared
 * auth state on success.
 */
export function ProfilePage() {
  const { user, isLoading, refreshUser } = useAuth();

  return (
    <PageWrapper className="mx-auto max-w-lg px-4 py-10">
      <GlassCard>
        <h1 className="text-xl font-semibold">Profile</h1>
        <p className="mb-6 mt-1 text-sm text-muted-foreground">Manage your account details.</p>

        {isLoading && <p className="text-muted-foreground">Loading profile...</p>}
        {!isLoading && !user && (
          <p className="text-muted-foreground">You need to be logged in to view this page.</p>
        )}
        {!isLoading && user && <ProfileEditForm user={user} onSaved={refreshUser} />}
      </GlassCard>
    </PageWrapper>
  );
}
