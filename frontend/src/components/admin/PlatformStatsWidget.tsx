import { Activity, Film, Scissors, Users } from 'lucide-react';
import type { ComponentType } from 'react';
import { GlassCard } from '@/components/ui/GlassCard';
import { cn } from '@/lib/utils';
import type { AdminStats } from '@/services/adminService';

export interface StatTileProps {
  label: string;
  value: string;
  icon?: ComponentType<{ className?: string }>;
  className?: string;
}

/**
 * A single stat tile: label + value, with an optional lucide icon, styled
 * as a GlassCard. Mirrors the Dashboard module's StatTile convention
 * (see components/dashboard/StatsWidget.tsx) so admin and user-facing
 * stats read as one visual system.
 */
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

export interface PlatformStatsWidgetProps {
  stats: AdminStats;
  className?: string;
}

/** Grid of platform-wide stat tiles for the admin overview page. */
export function PlatformStatsWidget({
  stats,
  className,
}: PlatformStatsWidgetProps) {
  return (
    <div
      className={cn(
        'grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4',
        className,
      )}
    >
      <StatTile
        label="Total users"
        value={stats.total_users.toLocaleString()}
        icon={Users}
      />
      <StatTile
        label="Total videos"
        value={stats.total_videos.toLocaleString()}
        icon={Film}
      />
      <StatTile
        label="Total clips"
        value={stats.total_clips.toLocaleString()}
        icon={Scissors}
      />
      <StatTile
        label="Active users (30d)"
        value={stats.active_users_last_30_days.toLocaleString()}
        icon={Activity}
      />
    </div>
  );
}
