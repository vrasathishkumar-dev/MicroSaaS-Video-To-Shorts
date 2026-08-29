import { motion } from 'framer-motion';
import { Clock, Film, Trash2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import type { Clip, ClipStatus } from '@/types';

export interface ClipCardProps {
  clip: Clip;
  onDelete?: (id: number) => void;
  className?: string;
}

const STATUS_STYLES: Record<ClipStatus, string> = {
  draft: 'bg-muted text-muted-foreground',
  rendering: 'bg-accent text-accent-foreground',
  ready: 'bg-primary/15 text-primary',
  failed: 'bg-destructive/15 text-destructive',
};

function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * A single clip tile: thumbnail (or placeholder), title, status badge,
 * duration, and a delete action. Clicking the card navigates to the
 * clip editor at /clips/{id}.
 */
export function ClipCard({ clip, onDelete, className }: ClipCardProps) {
  const duration = formatDuration(clip.end_time - clip.start_time);

  return (
    <motion.div
      whileHover={{ scale: 1.02, y: -4 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className={cn(
        'group relative overflow-hidden rounded-2xl border border-border bg-card shadow-md',
        className,
      )}
    >
      <button
        type="button"
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onDelete?.(clip.id);
        }}
        aria-label={`Delete ${clip.title}`}
        className="absolute right-2 top-2 z-10 rounded-full bg-black/50 p-1.5 text-white opacity-0 transition-opacity hover:bg-destructive focus-visible:opacity-100 group-hover:opacity-100"
      >
        <Trash2 className="h-4 w-4" />
      </button>

      <Link to={`/clips/${clip.id}`} className="block">
        <div className="flex aspect-video items-center justify-center bg-muted">
          {clip.thumbnail_path ? (
            <img
              src={clip.thumbnail_path}
              alt={clip.title}
              className="h-full w-full object-cover"
            />
          ) : (
            <Film className="h-10 w-10 text-muted-foreground" />
          )}
        </div>

        <div className="space-y-2 p-4">
          <div className="flex items-center justify-between gap-2">
            <h3 className="truncate text-sm font-semibold text-foreground">
              {clip.title}
            </h3>
            <span
              className={cn(
                'shrink-0 rounded-full px-2 py-0.5 text-xs font-medium capitalize',
                STATUS_STYLES[clip.status],
              )}
            >
              {clip.status}
            </span>
          </div>
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <Clock className="h-3.5 w-3.5" />
            <span>{duration}</span>
          </div>
        </div>
      </Link>
    </motion.div>
  );
}
