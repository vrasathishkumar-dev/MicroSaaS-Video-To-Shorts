import { GlassCard } from '@/components/ui/GlassCard';
import { cn } from '@/lib/utils';

/** Tailwind bg/text color pair for each known video status; unknown statuses fall back to `DEFAULT_COLOR`. */
const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-muted-foreground/40',
  downloading: 'bg-amber-500',
  transcribing: 'bg-amber-500',
  analyzing: 'bg-amber-500',
  ready: 'bg-emerald-500',
  failed: 'bg-destructive',
};

const DEFAULT_COLOR = 'bg-primary/60';

function statusColor(status: string): string {
  return STATUS_COLORS[status] ?? DEFAULT_COLOR;
}

function statusLabel(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

export interface UsageChartProps {
  videosByStatus: Record<string, number>;
  className?: string;
}

/**
 * Dependency-free breakdown of video projects by status: a proportional
 * stacked bar plus a legend with counts and percentages.
 */
export function UsageChart({ videosByStatus, className }: UsageChartProps) {
  const entries = Object.entries(videosByStatus).filter(([, count]) => count > 0);
  const total = entries.reduce((sum, [, count]) => sum + count, 0);

  return (
    <GlassCard className={cn('flex flex-col gap-4 p-5', className)}>
      <h2 className="text-sm font-medium text-muted-foreground">
        Videos by status
      </h2>

      {total === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          No videos yet.
        </p>
      ) : (
        <>
          <div className="flex h-3 w-full overflow-hidden rounded-full bg-muted">
            {entries.map(([status, count]) => (
              <div
                key={status}
                className={cn('h-full', statusColor(status))}
                style={{ width: `${(count / total) * 100}%` }}
                title={`${statusLabel(status)}: ${count}`}
              />
            ))}
          </div>

          <ul className="flex flex-col gap-2">
            {entries.map(([status, count]) => {
              const percentage = Math.round((count / total) * 100);
              return (
                <li
                  key={status}
                  className="flex items-center justify-between text-sm"
                >
                  <span className="flex items-center gap-2">
                    <span
                      className={cn('h-2 w-2 rounded-full', statusColor(status))}
                    />
                    {statusLabel(status)}
                  </span>
                  <span className="text-muted-foreground">
                    {count} ({percentage}%)
                  </span>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </GlassCard>
  );
}
