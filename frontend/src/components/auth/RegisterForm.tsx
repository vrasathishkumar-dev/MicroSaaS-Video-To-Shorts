import { useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, EyeOff, Lock, Mail, User as UserIcon } from 'lucide-react';
import { GradientButton } from '@/components/ui/GradientButton';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';

interface FormErrors {
  fullName?: string;
  email?: string;
  password?: string;
  confirmPassword?: string;
  form?: string;
}

function isValidEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

const MIN_PASSWORD_LENGTH = 8;

const inputBaseClasses =
  'w-full rounded-xl border bg-background/50 py-3 pl-10 pr-4 text-sm outline-none transition-colors focus:ring-2 focus:ring-ring/50';

/**
 * Controlled registration form. Validates client-side (including a
 * password confirmation match), shows inline field errors plus a
 * form-level error banner, and disables submission while the
 * register + auto-login request is in flight.
 */
export function RegisterForm() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

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
    if (!password) {
      nextErrors.password = 'Password is required.';
    } else if (password.length < MIN_PASSWORD_LENGTH) {
      nextErrors.password = `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`;
    }
    if (confirmPassword !== password) {
      nextErrors.confirmPassword = 'Passwords do not match.';
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
    try {
      await register(email, password, fullName);
      navigate('/dashboard');
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: string; message?: string } } };
      const message =
        axiosError.response?.data?.detail ||
        axiosError.response?.data?.message ||
        'Could not create your account. Please check your details and try again.';
      setErrors({ form: message });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
      {errors.form && (
        <p
          role="alert"
          className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive"
        >
          {errors.form}
        </p>
      )}

      <div>
        <label htmlFor="register-full-name" className="mb-1 block text-sm font-medium">
          Full name
        </label>
        <div className="relative">
          <UserIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            id="register-full-name"
            name="full_name"
            type="text"
            autoComplete="name"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            placeholder="Jane Doe"
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
        <label htmlFor="register-email" className="mb-1 block text-sm font-medium">
          Email
        </label>
        <div className="relative">
          <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            id="register-email"
            name="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            aria-invalid={Boolean(errors.email)}
            className={cn(
              inputBaseClasses,
              errors.email ? 'border-destructive' : 'border-input focus:border-primary',
            )}
          />
        </div>
        {errors.email && <p className="mt-1 text-sm text-destructive">{errors.email}</p>}
      </div>

      <div>
        <label htmlFor="register-password" className="mb-1 block text-sm font-medium">
          Password
        </label>
        <div className="relative">
          <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            id="register-password"
            name="password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="••••••••"
            aria-invalid={Boolean(errors.password)}
            className={cn(
              inputBaseClasses,
              'pr-10',
              errors.password ? 'border-destructive' : 'border-input focus:border-primary',
            )}
          />
          <button
            type="button"
            onClick={() => setShowPassword((prev) => !prev)}
            aria-label={showPassword ? 'Hide password' : 'Show password'}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
          >
            {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
        {errors.password && <p className="mt-1 text-sm text-destructive">{errors.password}</p>}
      </div>

      <div>
        <label htmlFor="register-confirm-password" className="mb-1 block text-sm font-medium">
          Confirm password
        </label>
        <div className="relative">
          <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            id="register-confirm-password"
            name="confirm_password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            placeholder="••••••••"
            aria-invalid={Boolean(errors.confirmPassword)}
            className={cn(
              inputBaseClasses,
              errors.confirmPassword ? 'border-destructive' : 'border-input focus:border-primary',
            )}
          />
        </div>
        {errors.confirmPassword && (
          <p className="mt-1 text-sm text-destructive">{errors.confirmPassword}</p>
        )}
      </div>

      <GradientButton type="submit" disabled={isSubmitting} className="w-full">
        {isSubmitting ? 'Creating account...' : 'Create account'}
      </GradientButton>
    </form>
  );
}
