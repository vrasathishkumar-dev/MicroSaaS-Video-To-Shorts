import { CheckCircle2, Download, FileText, Loader2, Sparkles, Wand2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import type { VideoProjectStatus } from '@/types';

export interface ProcessingProgressProps {
  status: VideoProjectStatus;
  isGeneratingClips?: boolean;
  className?: string;
}

interface Step {
  id: string;
  title: string;
  description: string;
  icon: typeof Download;
  isComplete: (status: VideoProjectStatus) => boolean;
  isActive: (status: VideoProjectStatus) => boolean;
}

const STEPS: Step[] = [
  {
    id: 'download',
    title: 'Source Fetch',
    description: 'Downloading & preparing source video stream',
    icon: Download,
    isComplete: (s) => ['transcribing', 'analyzing', 'ready'].includes(s),
    isActive: (s) => s === 'pending' || s === 'downloading',
  },
  {
    id: 'transcribe',
    title: 'Whisper Transcription',
    description: 'Converting speech into timestamped transcript',
    icon: FileText,
    isComplete: (s) => ['analyzing', 'ready'].includes(s),
    isActive: (s) => s === 'transcribing',
  },
  {
    id: 'analyze',
    title: 'Highlight Detection',
    description: 'AI scoring hooks, keywords & viral moments',
    icon: Sparkles,
    isComplete: (s) => s === 'ready',
    isActive: (s) => s === 'analyzing',
  },
  {
    id: 'ready',
    title: 'Ready for Splitting',
    description: 'Timeline analyzed and ready to generate vertical clips',
    icon: Wand2,
    isComplete: (s) => s === 'ready',
    isActive: (s) => s === 'ready',
  },
];

const STATUS_PROGRESS: Record<VideoProjectStatus, number> = {
  pending: 15,
  downloading: 35,
  transcribing: 65,
  analyzing: 85,
  ready: 100,
  failed: 0,
};

export function ProcessingProgress({
  status,
  isGeneratingClips = false,
  className,
}: ProcessingProgressProps) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const isProcessing = status !== 'ready' && status !== 'failed';

  useEffect(() => {
    if (!isProcessing && !isGeneratingClips) {
      setElapsedSeconds(0);
      return;
    }

    const interval = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);

    return () => clearInterval(interval);
  }, [isProcessing, isGeneratingClips]);

  const progressPercent = isGeneratingClips
    ? 90
    : STATUS_PROGRESS[status] ?? 10;

  const formatTimer = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  if (status === 'failed') {
    return null;
  }

  return (
    <div
      className={cn(
        'rounded-2xl border border-glass-border bg-glass-bg/60 p-5 backdrop-blur-md shadow-lg',
        className,
      )}
    >
      {/* Header Info */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {isProcessing || isGeneratingClips ? (
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
          ) : (
            <CheckCircle2 className="h-5 w-5 text-emerald-500" />
          )}
          <span className="font-semibold text-foreground">
            {isGeneratingClips
              ? 'Splitting into Short Clips...'
              : isProcessing
                ? 'Processing Video Pipeline...'
                : 'Pipeline Complete'}
          </span>
        </div>

        <div className="flex items-center gap-3 text-xs font-medium text-muted-foreground">
          {(isProcessing || isGeneratingClips) && (
            <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-primary">
              <span className="h-1.5 w-1.5 animate-ping rounded-full bg-primary" />
              Elapsed: {formatTimer(elapsedSeconds)}
            </span>
          )}
          <span className="font-semibold text-foreground">
            {progressPercent}%
          </span>
        </div>
      </div>

      {/* Main Animated Progress Bar */}
      <div className="relative mb-6 h-3 w-full overflow-hidden rounded-full bg-muted/80">
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-gradient-from via-primary to-gradient-to shadow-sm"
          initial={{ width: 0 }}
          animate={{ width: `${progressPercent}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        />
      </div>

      {/* Steps list */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map((step) => {
          const completed = step.isComplete(status);
          const active = step.isActive(status);
          const Icon = step.icon;

          return (
            <div
              key={step.id}
              className={cn(
                'relative flex flex-col rounded-xl border p-3 transition-all duration-300',
                completed
                  ? 'border-emerald-500/30 bg-emerald-500/5'
                  : active
                    ? 'border-primary/50 bg-primary/10 shadow-sm'
                    : 'border-glass-border/40 bg-background/20 opacity-60',
              )}
            >
              <div className="mb-2 flex items-center justify-between">
                <div
                  className={cn(
                    'flex h-7 w-7 items-center justify-center rounded-lg',
                    completed
                      ? 'bg-emerald-500/20 text-emerald-500'
                      : active
                        ? 'bg-primary/20 text-primary'
                        : 'bg-muted text-muted-foreground',
                  )}
                >
                  {completed ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : active ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Icon className="h-4 w-4" />
                  )}
                </div>

                <span
                  className={cn(
                    'text-[11px] font-semibold uppercase tracking-wider',
                    completed
                      ? 'text-emerald-500'
                      : active
                        ? 'text-primary'
                        : 'text-muted-foreground',
                  )}
                >
                  {completed ? 'Done' : active ? 'In progress' : 'Queued'}
                </span>
              </div>

              <h4 className="text-xs font-semibold text-foreground">
                {step.title}
              </h4>
              <p className="mt-0.5 text-[11px] text-muted-foreground leading-snug">
                {step.description}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
