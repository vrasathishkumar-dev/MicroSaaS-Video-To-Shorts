import { cn } from '@/lib/utils';
import type { VideoProjectStatus } from '@/types';

interface StatusConfig {
  label: string;
  className: string;
  pulsing: boolean;
}

const STATUS_CONFIG: Record<VideoProjectStatus, StatusConfig> = {
  pending: {
    label: 'Pending',
    className: 'bg-muted text-muted-foreground',
    pulsing: false,
  },
  downloading: {
    label: 'Downloading',
    className: 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
    pulsing: true,
  },
  transcribing: {
    label: 'Transcribing',
    className: 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
    pulsing: true,
  },
  analyzing: {
    label: 'Analyzing',
    className: 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
    pulsing: true,
  },
  generating: {
    label: 'Generating Shorts',
    className: 'bg-primary/15 text-primary',
    pulsing: true,
  },
  ready: {
    label: 'Ready',
    className: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400',
    pulsing: false,
  },
  failed: {
    label: 'Failed',
    className: 'bg-destructive/15 text-destructive',
    pulsing: false,
  },
};

export interface StatusBadgeProps {
  status: VideoProjectStatus;
  className?: string;
}

/** Small color-coded pill reflecting a video project's pipeline status. */
export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status];

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium',
        config.className,
        className,
      )}
    >
      {config.pulsing && (
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-75" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-current" />
        </span>
      )}
      {config.label}
    </span>
  );
}
