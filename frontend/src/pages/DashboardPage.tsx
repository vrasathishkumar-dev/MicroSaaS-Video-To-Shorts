import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Film, Flame, Play, Sparkles, Upload } from 'lucide-react';
import { StatsWidget } from '@/components/dashboard/StatsWidget';
import { UsageChart } from '@/components/dashboard/UsageChart';
import { ViralityScoreBadge } from '@/components/clips/ViralityScoreBadge';
import { GlassCard } from '@/components/ui/GlassCard';
import { GradientButton } from '@/components/ui/GradientButton';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { clipToViralityInsights } from '@/lib/virality';
import { getDashboardStats } from '@/services/dashboardService';
import type { DashboardStats } from '@/services/dashboardService';
import { listClips } from '@/services/clipService';
import type { Clip } from '@/types';

/** Landing page after login: at-a-glance stats, quick actions, and recent clips. */
export function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentClips, setRecentClips] = useState<Clip[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [statsData, clipsData] = await Promise.all([
        getDashboardStats(),
        listClips(undefined, 1).catch(() => ({ items: [] as Clip[], total: 0 })),
      ]);
      setStats(statsData);
      setRecentClips(clipsData.items.slice(0, 3));
    } catch {
      setError('Failed to load your dashboard stats. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  return (
    <PageWrapper className="mx-auto max-w-5xl px-4 py-10 space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Creator Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Overview of your video processing pipeline, virality metrics, and short-form assets.
        </p>
      </div>

      {error && (
        <GlassCard className="border-destructive/30">
          <p className="text-sm text-destructive">{error}</p>
        </GlassCard>
      )}

      {/* Quick Actions */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Link to="/videos/new" className="group">
          <GlassCard className="h-full p-5 transition-all duration-300 hover:border-primary/50 hover:shadow-lg hover:shadow-primary/5">
            <div className="flex items-center justify-between">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Upload className="h-5 w-5" />
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-primary" />
            </div>
            <h3 className="mt-4 font-semibold text-foreground">Upload Video</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              Upload footage or submit a YouTube link to extract viral clips.
            </p>
          </GlassCard>
        </Link>

        <Link to="/clips" className="group">
          <GlassCard className="h-full p-5 transition-all duration-300 hover:border-primary/50 hover:shadow-lg hover:shadow-primary/5">
            <div className="flex items-center justify-between">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/10 text-purple-400">
                <Film className="h-5 w-5" />
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-purple-400" />
            </div>
            <h3 className="mt-4 font-semibold text-foreground">Clip Library</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              Review generated shorts, filter by virality, and bulk export.
            </p>
          </GlassCard>
        </Link>

        <Link to="/generate" className="group">
          <GlassCard className="h-full p-5 transition-all duration-300 hover:border-primary/50 hover:shadow-lg hover:shadow-primary/5">
            <div className="flex items-center justify-between">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/10 text-amber-400">
                <Sparkles className="h-5 w-5" />
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-amber-400" />
            </div>
            <h3 className="mt-4 font-semibold text-foreground">AI Script Generator</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              Turn blog posts, ideas, or topics into hook-optimized short scripts.
            </p>
          </GlassCard>
        </Link>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading your stats&hellip;</p>
      ) : stats ? (
        <div className="flex flex-col gap-6">
          <StatsWidget stats={stats} />

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Status distribution breakdown */}
            <div className="lg:col-span-1">
              <UsageChart videosByStatus={stats.videos_by_status} className="h-full" />
            </div>

            {/* Recent Clips Preview */}
            <div className="lg:col-span-2">
              <GlassCard className="h-full p-5 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <Flame className="h-4 w-4 text-primary" />
                      <h2 className="text-sm font-medium text-foreground">Recent Clips</h2>
                    </div>
                    <Link
                      to="/clips"
                      className="text-xs text-primary hover:underline font-medium flex items-center gap-1"
                    >
                      View all clips &rarr;
                    </Link>
                  </div>

                  {recentClips.length === 0 ? (
                    <div className="py-8 text-center text-sm text-muted-foreground">
                      <p>No clips generated yet.</p>
                      <Link to="/videos/new" className="mt-3 inline-block">
                        <GradientButton className="text-xs py-1.5 px-3">
                          Upload your first video
                        </GradientButton>
                      </Link>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {recentClips.map((clip) => {
                        const duration = Math.round(clip.end_time - clip.start_time);
                        const insights = clipToViralityInsights(clip);
                        return (
                          <Link
                            key={clip.id}
                            to={`/clips/${clip.id}`}
                            className="group flex items-center justify-between rounded-xl border border-glass-border bg-background/40 p-3 transition-colors hover:border-primary/40 hover:bg-background/70"
                          >
                            <div className="flex items-center gap-3 min-w-0">
                              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                                <Play className="h-4 w-4 fill-current" />
                              </div>
                              <div className="min-w-0">
                                <p className="truncate text-sm font-medium text-foreground group-hover:text-primary transition-colors">
                                  {clip.title}
                                </p>
                                <p className="text-xs text-muted-foreground">
                                  {duration}s duration &bull; status: <span className="capitalize">{clip.status}</span>
                                </p>
                              </div>
                            </div>
                            <div className="shrink-0 ml-3">
                              <ViralityScoreBadge insights={insights} size="sm" />
                            </div>
                          </Link>
                        );
                      })}
                    </div>
                  )}
                </div>
              </GlassCard>
            </div>
          </div>
        </div>
      ) : null}
    </PageWrapper>
  );
}

