import { ChevronLeft, ChevronRight, Search, ShieldAlert } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { UserTable } from '@/components/admin/UserTable';
import { GlassCard } from '@/components/ui/GlassCard';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { useAuth } from '@/hooks/useAuth';
import { listUsers } from '@/services/adminService';
import type { AdminUser } from '@/services/adminService';

const PAGE_SIZE_FALLBACK = 20;

/** Admin user management: searchable, paginated table with activate/deactivate actions. */
export function AdminUsersPage() {
  const { user, isLoading: isAuthLoading } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [query, setQuery] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(PAGE_SIZE_FALLBACK);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isAdmin = Boolean(user?.is_admin);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const loadUsers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await listUsers(query, page);
      setUsers(result.items);
      setTotal(result.total);
      setPageSize(result.page_size || PAGE_SIZE_FALLBACK);
    } catch {
      setError('Failed to load users. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [query, page]);

  useEffect(() => {
    if (isAdmin) {
      void loadUsers();
    }
  }, [isAdmin, loadUsers]);

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    setQuery(searchInput.trim());
  }

  function handleUserUpdated(updated: AdminUser) {
    setUsers((current) =>
      current.map((existing) =>
        existing.id === updated.id ? updated : existing,
      ),
    );
  }

  if (isAuthLoading) {
    return (
      <PageWrapper className="mx-auto max-w-5xl px-4 py-10">
        <p className="text-sm text-muted-foreground">Loading&hellip;</p>
      </PageWrapper>
    );
  }

  if (!isAdmin) {
    return (
      <PageWrapper className="mx-auto max-w-5xl px-4 py-10">
        <GlassCard className="flex flex-col items-center gap-3 py-12 text-center">
          <ShieldAlert className="h-8 w-8 text-destructive" />
          <p className="text-lg font-medium">Access denied</p>
          <p className="max-w-sm text-sm text-muted-foreground">
            You need admin privileges to view this page.
          </p>
        </GlassCard>
      </PageWrapper>
    );
  }

  return (
    <PageWrapper className="mx-auto max-w-5xl px-4 py-10">
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-xl font-semibold">Users</h1>
        <form
          onSubmit={handleSearchSubmit}
          className="flex w-full max-w-sm items-center gap-2"
        >
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Search by email or name&hellip;"
              className="w-full rounded-full border border-glass-border bg-glass-bg py-2 pl-9 pr-4 text-sm outline-none focus:border-primary"
            />
          </div>
          <button
            type="submit"
            className="shrink-0 rounded-full border border-glass-border px-4 py-2 text-sm font-medium transition-colors hover:bg-accent"
          >
            Search
          </button>
        </form>
      </div>

      {error && (
        <GlassCard className="mb-6 border-destructive/30">
          <p className="text-sm text-destructive">{error}</p>
        </GlassCard>
      )}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading users&hellip;</p>
      ) : users.length === 0 ? (
        <GlassCard className="flex flex-col items-center gap-2 py-12 text-center">
          <p className="text-lg font-medium">No users found</p>
          <p className="max-w-sm text-sm text-muted-foreground">
            Try a different search term.
          </p>
        </GlassCard>
      ) : (
        <>
          <UserTable
            users={users}
            onUserUpdated={handleUserUpdated}
            onError={setError}
          />

          <div className="mt-6 flex items-center justify-between gap-4">
            <p className="text-sm text-muted-foreground">
              Page {page} of {totalPages} &middot; {total} user
              {total === 1 ? '' : 's'}
            </p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                disabled={page <= 1}
                aria-label="Previous page"
                className="inline-flex items-center justify-center rounded-full border border-glass-border p-2 transition-colors hover:bg-accent disabled:pointer-events-none disabled:opacity-50"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() =>
                  setPage((current) => Math.min(totalPages, current + 1))
                }
                disabled={page >= totalPages}
                aria-label="Next page"
                className="inline-flex items-center justify-center rounded-full border border-glass-border p-2 transition-colors hover:bg-accent disabled:pointer-events-none disabled:opacity-50"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </>
      )}
    </PageWrapper>
  );
}
