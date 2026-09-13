import { Trash2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { GlassCard } from '@/components/ui/GlassCard';
import { StatusBadge } from '@/components/videos/StatusBadge';
import type { VideoProject } from '@/types';

export interface VideoProjectCardProps {
  video: VideoProject;
  onDelete?: (id: number) => void;
  /** Set while a delete request for this card is in flight. */
  isDeleting?: boolean;
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return '--:--';
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function formatDate(isoString: string): string {
  return new Date(isoString).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/** Grid card summarizing a single video project, linking to its detail page. */
export function VideoProjectCard({
  video,
  onDelete,
  isDeleting = false,
}: VideoProjectCardProps) {
  return (
    <GlassCard className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <Link
          to={`/videos/${video.id}`}
          className="min-w-0 flex-1 truncate text-lg font-semibold hover:underline"
        >
          {video.title}
        </Link>
        {onDelete && (
          <button
            type="button"
            onClick={() => onDelete(video.id)}
            disabled={isDeleting}
            aria-label={`Delete ${video.title}`}
            className="shrink-0 rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:pointer-events-none disabled:opacity-50"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <StatusBadge status={video.status} />
        <span className="text-sm text-muted-foreground">
          {formatDuration(video.duration_seconds)}
        </span>
        {video.copyright_declaration && (
          <span
            className={
              video.copyright_declaration === 'fair_use'
                ? 'inline-flex items-center rounded-md bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-500 ring-1 ring-amber-500/20'
                : 'inline-flex items-center rounded-md bg-muted/60 px-2 py-0.5 text-[10px] font-medium text-muted-foreground ring-1 ring-glass-border'
            }
          >
            {video.copyright_declaration === 'own_content' && 'Own content'}
            {video.copyright_declaration === 'licensed' && 'Licensed'}
            {video.copyright_declaration === 'public_domain' && 'Public domain'}
            {video.copyright_declaration === 'fair_use' && 'Fair use ⚠'}
          </span>
        )}
      </div>

      {['pending', 'downloading', 'transcribing', 'analyzing'].includes(video.status) && (
        <div className="flex flex-col gap-1">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-gradient-to-r from-gradient-from to-gradient-to animate-pulse transition-all"
              style={{
                width:
                  video.status === 'downloading'
                    ? '35%'
                    : video.status === 'transcribing'
                      ? '65%'
                      : video.status === 'analyzing'
                        ? '85%'
                        : '15%',
              }}
            />
          </div>
          <span className="text-[11px] text-muted-foreground">
            {video.status === 'downloading'
              ? 'Downloading video stream...'
              : video.status === 'transcribing'
                ? 'Transcribing audio...'
                : video.status === 'analyzing'
                  ? 'Analyzing highlight moments...'
                  : 'Queued for processing...'}
          </span>
        </div>
      )}

      {video.status === 'failed' && video.error_message && (
        <p className="line-clamp-2 text-sm text-destructive">
          {video.error_message}
        </p>
      )}

      <p className="text-xs text-muted-foreground">
        Created {formatDate(video.created_at)}
      </p>

      <Link
        to={`/videos/${video.id}`}
        className="text-sm font-medium text-primary hover:underline"
      >
        View details &rarr;
      </Link>
    </GlassCard>
  );
}
