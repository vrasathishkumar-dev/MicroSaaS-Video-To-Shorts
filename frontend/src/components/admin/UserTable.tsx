import { useState } from 'react';
import { UserStatusToggle } from '@/components/admin/UserStatusToggle';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';
import type { AdminUser } from '@/services/adminService';
import { updateUserStatus } from '@/services/adminService';

export interface UserTableProps {
  users: AdminUser[];
  /** Called with the updated user after a successful activate/deactivate call. */
  onUserUpdated: (user: AdminUser) => void;
  /** Called if an activate/deactivate call fails, so the page can surface an error. */
  onError?: (message: string) => void;
}

interface BadgeProps {
  label: string;
  active: boolean;
  activeClassName: string;
}

function Badge({ label, active, activeClassName }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        active ? activeClassName : 'bg-muted text-muted-foreground',
      )}
    >
      {label}
    </span>
  );
}

function formatDate(isoString: string): string {
  return new Date(isoString).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/** Table of platform users with status badges and an activate/deactivate action per row. */
export function UserTable({ users, onUserUpdated, onError }: UserTableProps) {
  const { user: currentUser } = useAuth();
  const [pendingId, setPendingId] = useState<number | null>(null);

  async function handleToggle(target: AdminUser) {
    setPendingId(target.id);
    try {
      const updated = await updateUserStatus(target.id, !target.is_active);
      onUserUpdated(updated);
    } catch {
      onError?.(`Failed to update ${target.email}. Please try again.`);
    } finally {
      setPendingId(null);
    }
  }

  return (
    <div className="overflow-x-auto rounded-2xl border border-glass-border">
      <table className="w-full min-w-[720px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-glass-border bg-glass-bg text-xs uppercase tracking-wide text-muted-foreground">
            <th className="px-4 py-3 font-medium">Email</th>
            <th className="px-4 py-3 font-medium">Name</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Joined</th>
            <th className="px-4 py-3 font-medium">Action</th>
          </tr>
        </thead>
        <tbody>
          {users.map((rowUser) => {
            const isSelf = currentUser?.id === rowUser.id;
            return (
              <tr
                key={rowUser.id}
                className="border-b border-glass-border last:border-b-0"
              >
                <td className="px-4 py-3 font-medium">{rowUser.email}</td>
                <td className="px-4 py-3 text-muted-foreground">
                  {rowUser.full_name ?? '—'}
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1.5">
                    <Badge
                      label={rowUser.is_active ? 'Active' : 'Inactive'}
                      active={rowUser.is_active}
                      activeClassName="bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                    />
                    <Badge
                      label={rowUser.is_verified ? 'Verified' : 'Unverified'}
                      active={rowUser.is_verified}
                      activeClassName="bg-primary/15 text-primary"
                    />
                    {rowUser.is_admin && (
                      <Badge
                        label="Admin"
                        active
                        activeClassName="bg-pink-500/15 text-pink-600 dark:text-pink-400"
                      />
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {formatDate(rowUser.created_at)}
                </td>
                <td className="px-4 py-3">
                  {isSelf ? (
                    <span className="text-xs text-muted-foreground">
                      (your account)
                    </span>
                  ) : (
                    <UserStatusToggle
                      isActive={rowUser.is_active}
                      isLoading={pendingId === rowUser.id}
                      onToggle={() => void handleToggle(rowUser)}
                    />
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
