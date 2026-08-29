import { ShieldAlert, Users } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { PlatformStatsWidget } from '@/components/admin/PlatformStatsWidget';
import { GlassCard } from '@/components/ui/GlassCard';
import { GradientButton } from '@/components/ui/GradientButton';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { useAuth } from '@/hooks/useAuth';
import { getAdminStats } from '@/services/adminService';
import type { AdminStats } from '@/services/adminService';

/** Admin overview: platform-wide stats and a link into user management. */
export function AdminPage() {
  const { user, isLoading: isAuthLoading } = useAuth();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isAdmin = Boolean(user?.is_admin);

  const loadStats = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getAdminStats();
      setStats(data);
    } catch {
      setError('Failed to load platform stats. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAdmin) {
      void loadStats();
    }
  }, [isAdmin, loadStats]);

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
      <div className="mb-8 flex items-center justify-between gap-4">
        <h1 className="text-xl font-semibold">Admin</h1>
        <Link to="/admin/users">
          <GradientButton>
            <Users className="h-4 w-4" />
            Manage users
          </GradientButton>
        </Link>
      </div>

      {error && (
        <GlassCard className="mb-6 border-destructive/30">
          <p className="text-sm text-destructive">{error}</p>
        </GlassCard>
      )}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading platform stats&hellip;</p>
      ) : (
        stats && <PlatformStatsWidget stats={stats} />
      )}
    </PageWrapper>
  );
}
