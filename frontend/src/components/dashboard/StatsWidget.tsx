import { Clapperboard, Clock3, Film, HardDrive, ListChecks } from 'lucide-react';
import type { ComponentType } from 'react';
import { GlassCard } from '@/components/ui/GlassCard';
import { cn } from '@/lib/utils';
import type { DashboardStats } from '@/services/dashboardService';

/** Formats a duration in seconds as e.g. "2m 14s" (or "12s" under a minute). Null/undefined -> "—". */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds)) {
    return '—';
  }
  const totalSeconds = Math.round(seconds);
  const minutes = Math.floor(totalSeconds / 60);
  const remainingSeconds = totalSeconds % 60;
  if (minutes === 0) {
    return `${remainingSeconds}s`;
  }
  return `${minutes}m ${remainingSeconds}s`;
}

/** Formats a byte count as e.g. "128 MB". Null/undefined -> "—". */
export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null || Number.isNaN(bytes)) {
    return '—';
  }
  if (bytes === 0) {
    return '0 B';
  }
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const exponent = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );
  const value = bytes / 1024 ** exponent;
  const formatted = exponent === 0 ? value.toFixed(0) : value.toFixed(1);
  return `${formatted} ${units[exponent]}`;
}

export interface StatTileProps {
  label: string;
  value: string;
  icon?: ComponentType<{ className?: string }>;
  className?: string;
}

/** A single stat tile: label + value, with an optional lucide icon, styled as a GlassCard. */
export function StatTile({ label, value, icon: Icon, className }: StatTileProps) {
  return (
    <GlassCard className={cn('flex flex-col gap-3 p-5', className)}>
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">{label}</span>
        {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
      </div>
      <span className="text-2xl font-semibold tracking-tight">{value}</span>
    </GlassCard>
  );
}

export interface StatsWidgetProps {
  stats: DashboardStats;
  className?: string;
}

/** Grid of stat tiles summarizing a user's dashboard stats. */
export function StatsWidget({ stats, className }: StatsWidgetProps) {
  return (
    <div
      className={cn(
        'grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5',
        className,
      )}
    >
      <StatTile label="Total videos" value={String(stats.total_videos)} icon={Film} />
      <StatTile label="Total clips" value={String(stats.total_clips)} icon={Clapperboard} />
      <StatTile label="Clips ready" value={String(stats.clips_ready)} icon={ListChecks} />
      <StatTile
        label="Avg. processing time"
        value={formatDuration(stats.avg_processing_time_seconds)}
        icon={Clock3}
      />
      <StatTile
        label="Storage used"
        value={formatBytes(stats.storage_used_bytes)}
        icon={HardDrive}
      />
    </div>
  );
}
