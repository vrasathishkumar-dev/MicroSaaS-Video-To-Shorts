import { LoaderCircle, UserCheck, UserX } from 'lucide-react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';

export interface UserStatusToggleProps {
  isActive: boolean;
  isLoading?: boolean;
  disabled?: boolean;
  onToggle: () => void;
}

/**
 * Small pill button that activates/deactivates a user account. Shows a
 * spinner while the request is in flight and can be disabled (e.g. to
 * prevent an admin from deactivating their own account).
 */
export function UserStatusToggle({
  isActive,
  isLoading = false,
  disabled = false,
  onToggle,
}: UserStatusToggleProps) {
  const isDisabled = disabled || isLoading;

  return (
    <motion.button
      type="button"
      whileHover={isDisabled ? undefined : { scale: 1.03 }}
      whileTap={isDisabled ? undefined : { scale: 0.97 }}
      onClick={onToggle}
      disabled={isDisabled}
      aria-label={isActive ? 'Deactivate user' : 'Activate user'}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors disabled:pointer-events-none disabled:opacity-50',
        isActive
          ? 'bg-destructive/10 text-destructive hover:bg-destructive/20'
          : 'bg-emerald-500/15 text-emerald-600 hover:bg-emerald-500/25 dark:text-emerald-400',
      )}
    >
      {isLoading ? (
        <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
      ) : isActive ? (
        <UserX className="h-3.5 w-3.5" />
      ) : (
        <UserCheck className="h-3.5 w-3.5" />
      )}
      {isActive ? 'Deactivate' : 'Activate'}
    </motion.button>
  );
}
