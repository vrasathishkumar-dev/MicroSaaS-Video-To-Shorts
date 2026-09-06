import { useState, useEffect } from 'react';
import { Scissors, FileText, Check, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import { GradientButton } from '@/components/ui/GradientButton';
import type { TranscriptSegment } from '@/types';

export interface TextBasedTrimmerProps {
  segments: TranscriptSegment[];
  clipStartTime: number;
  clipEndTime: number;
  onApplyTrim: (startTime: number, endTime: number) => Promise<void> | void;
  className?: string;
}

export function TextBasedTrimmer({
  segments,
  clipStartTime,
  clipEndTime,
  onApplyTrim,
  className,
}: TextBasedTrimmerProps) {
  const [selectedStart, setSelectedStart] = useState<number>(clipStartTime);
  const [selectedEnd, setSelectedEnd] = useState<number>(clipEndTime);
  const [isApplying, setIsApplying] = useState(false);

  useEffect(() => {
    setSelectedStart(clipStartTime);
    setSelectedEnd(clipEndTime);
  }, [clipStartTime, clipEndTime]);

  const isDirty = selectedStart !== clipStartTime || selectedEnd !== clipEndTime;

  const handleSegmentClick = (segment: TranscriptSegment) => {
    // If clicking before start, extend start
    if (segment.start_time < selectedStart) {
      setSelectedStart(segment.start_time);
    } else if (segment.end_time > selectedEnd) {
      // If clicking after end, extend end
      setSelectedEnd(segment.end_time);
    } else {
      // If clicked inside, toggle closest boundary
      const distToStart = Math.abs(segment.start_time - selectedStart);
      const distToEnd = Math.abs(segment.end_time - selectedEnd);
      if (distToStart < distToEnd) {
        setSelectedStart(segment.end_time);
      } else {
        setSelectedEnd(segment.start_time);
      }
    }
  };

  const handleSave = async () => {
    if (selectedEnd <= selectedStart) return;
    setIsApplying(true);
    try {
      await onApplyTrim(selectedStart, selectedEnd);
    } finally {
      setIsApplying(false);
    }
  };

  return (
    <div className={cn('space-y-3', className)}>
      <div className="flex items-center justify-between">
        <label className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          <FileText className="h-3.5 w-3.5 text-primary" />
          Text-Based Video Trimmer
        </label>
        <span className="text-xs text-muted-foreground">
          Click sentences to expand or trim clip
        </span>
      </div>

      <div className="max-h-56 overflow-y-auto rounded-xl border border-glass-border bg-glass-bg p-3 backdrop-blur-md space-y-1.5 text-xs">
        {segments.length === 0 ? (
          <p className="text-muted-foreground py-4 text-center">
            No transcript segments available for text trimming.
          </p>
        ) : (
          segments.map((seg) => {
            const isIncluded =
              seg.start_time >= selectedStart - 0.5 && seg.end_time <= selectedEnd + 0.5;

            return (
              <div
                key={seg.id}
                className={cn(
                  'w-full rounded-lg p-2 transition-all flex items-start justify-between gap-3 border',
                  isIncluded
                    ? 'border-primary/40 bg-primary/10 text-foreground font-medium shadow-sm'
                    : 'border-transparent text-muted-foreground hover:bg-muted/40 opacity-70 hover:opacity-100',
                )}
              >
                <button
                  type="button"
                  onClick={() => handleSegmentClick(seg)}
                  className="flex-1 text-left"
                >
                  <span className="mr-2 font-mono text-[10px] text-muted-foreground">
                    {Math.floor(seg.start_time)}s - {Math.floor(seg.end_time)}s
                  </span>
                  {seg.is_highlight && (
                    <span
                      title="AI-picked viral hook"
                      className="mr-1.5 inline-flex items-center gap-0.5 rounded-full bg-amber-400/20 px-1.5 py-0.5 text-[9px] font-semibold text-amber-600"
                    >
                      <Sparkles className="h-2.5 w-2.5" />
                      AI pick
                    </span>
                  )}
                  <span>{seg.text}</span>
                </button>

                <div className="flex shrink-0 items-center gap-1">
                  <button
                    type="button"
                    title="Start the clip here"
                    onClick={() => setSelectedStart(seg.start_time)}
                    className="rounded-md border border-glass-border px-1.5 py-0.5 text-[9px] font-semibold text-muted-foreground hover:border-primary/40 hover:text-primary"
                  >
                    Start
                  </button>
                  <button
                    type="button"
                    title="End the clip here"
                    onClick={() => setSelectedEnd(seg.end_time)}
                    className="rounded-md border border-glass-border px-1.5 py-0.5 text-[9px] font-semibold text-muted-foreground hover:border-primary/40 hover:text-primary"
                  >
                    End
                  </button>
                  {isIncluded && (
                    <span className="rounded-full bg-primary/20 p-0.5 text-primary">
                      <Check className="h-3 w-3" />
                    </span>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      <div className="flex items-center justify-between pt-1">
        <div className="text-xs text-muted-foreground">
          Selected duration:{' '}
          <span className="font-semibold text-foreground">
            {Math.max(0, Math.round(selectedEnd - selectedStart))}s
          </span>{' '}
          ({selectedStart.toFixed(1)}s &ndash; {selectedEnd.toFixed(1)}s)
        </div>

        <GradientButton
          type="button"
          onClick={handleSave}
          disabled={!isDirty || selectedEnd <= selectedStart || isApplying}
          className="px-3 py-1.5 text-xs gap-1.5"
        >
          <Scissors className="h-3 w-3" />
          {isApplying ? 'Updating…' : 'Apply text trim'}
        </GradientButton>
      </div>
    </div>
  );
}
