import { motion } from 'framer-motion';
import { Clock, Trash2, Play, Download } from 'lucide-react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { computeViralityInsights } from '@/lib/virality';
import { ViralityScoreBadge } from '@/components/clips/ViralityScoreBadge';
import type { Clip, ClipStatus } from '@/types';

export interface ClipCardProps {
  clip: Clip;
  onDelete?: (id: number) => void;
  className?: string;
}

const STATUS_STYLES: Record<ClipStatus, string> = {
  draft: 'bg-muted text-muted-foreground',
  rendering: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  ready: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  failed: 'bg-destructive/15 text-destructive border-destructive/30',
};

function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export function ClipCard({ clip, onDelete, className }: ClipCardProps) {
  const rawDuration = clip.end_time - clip.start_time;
  const duration = formatDuration(rawDuration);
  const virality = computeViralityInsights(clip.caption_text || clip.title, rawDuration);

  return (
    <motion.div
      whileHover={{ scale: 1.02, y: -4 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className={cn(
        'group relative flex flex-col overflow-hidden rounded-2xl border border-glass-border bg-card shadow-lg backdrop-blur-md transition-all',
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
        className="absolute right-3 top-3 z-20 rounded-full bg-black/60 p-2 text-white opacity-0 transition-opacity hover:bg-destructive focus-visible:opacity-100 group-hover:opacity-100"
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>

      <Link to={`/clips/${clip.id}`} className="flex flex-col flex-1">
        {/* 9:16 vertical short thumbnail ratio */}
        <div className="relative flex aspect-[9/16] max-h-64 w-full items-center justify-center bg-black/70 overflow-hidden">
          {clip.thumbnail_path ? (
            <img
              src={clip.thumbnail_path}
              alt={clip.title}
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex flex-col items-center gap-2 text-muted-foreground p-4 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/20 text-primary">
                <Play className="h-6 w-6 ml-0.5" />
              </div>
              <span className="text-[11px] font-mono text-muted-foreground">9:16 Short Clip</span>
            </div>
          )}

          {/* Top-left status badge */}
          <span
            className={cn(
              'absolute left-3 top-3 rounded-full border px-2.5 py-0.5 text-[10px] font-semibold capitalize backdrop-blur-md',
              STATUS_STYLES[clip.status],
            )}
          >
            {clip.status}
          </span>

          {/* Bottom-right duration badge */}
          <div className="absolute bottom-3 right-3 flex items-center gap-1 rounded-full bg-black/80 px-2 py-0.5 text-[10px] font-mono text-white backdrop-blur-md">
            <Clock className="h-3 w-3" />
            <span>{duration}</span>
          </div>
        </div>

        {/* Card Body */}
        <div className="flex flex-1 flex-col justify-between p-4 gap-3">
          <div className="space-y-1.5">
            <h3 className="line-clamp-2 text-sm font-semibold text-foreground leading-snug">
              {clip.title}
            </h3>
            {clip.caption_text && (
              <p className="line-clamp-1 text-xs text-muted-foreground italic">
                &ldquo;{clip.caption_text}&rdquo;
              </p>
            )}
          </div>

          <div className="pt-2 border-t border-glass-border flex items-center justify-between gap-2">
            <ViralityScoreBadge insights={virality} size="sm" />
            <span className="flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-[11px] font-semibold text-primary group-hover:bg-primary group-hover:text-white transition-colors">
              <Download className="h-3 w-3" />
              {clip.status === 'ready' ? 'Download' : 'Export 9:16'}
            </span>
          </div>
        </div>
      </Link>
    </motion.div>
  );
}
