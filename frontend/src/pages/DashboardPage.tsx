import { useCallback, useEffect, useState } from 'react';
import { StatsWidget } from '@/components/dashboard/StatsWidget';
import { UsageChart } from '@/components/dashboard/UsageChart';
import { GlassCard } from '@/components/ui/GlassCard';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { getDashboardStats } from '@/services/dashboardService';
import type { DashboardStats } from '@/services/dashboardService';

/** Landing page after login: at-a-glance stats and a status breakdown. */
export function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadStats = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getDashboardStats();
      setStats(data);
    } catch {
      setError('Failed to load your dashboard stats. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadStats();
  }, [loadStats]);

  return (
    <PageWrapper className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="mb-8 text-xl font-semibold">Dashboard</h1>

      {error && (
        <GlassCard className="mb-6 border-destructive/30">
          <p className="text-sm text-destructive">{error}</p>
        </GlassCard>
      )}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading your stats&hellip;</p>
      ) : stats ? (
        <div className="flex flex-col gap-6">
          <StatsWidget stats={stats} />
          <UsageChart videosByStatus={stats.videos_by_status} />
        </div>
      ) : null}
    </PageWrapper>
  );
}
