import { Flame, Sparkles, TrendingUp, Info } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ViralityInsights } from '@/lib/virality';

export interface ViralityScoreBadgeProps {
  insights: ViralityInsights;
  showDetails?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function ViralityScoreBadge({
  insights,
  showDetails = false,
  size = 'md',
  className,
}: ViralityScoreBadgeProps) {
  const isTopTier = insights.score >= 90;
  const isHighTier = insights.score >= 80 && insights.score < 90;

  const badgeColor = isTopTier
    ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
    : isHighTier
      ? 'bg-amber-500/15 text-amber-400 border-amber-500/30'
      : 'bg-primary/15 text-primary border-primary/30';

  const icon = isTopTier ? (
    <Flame className={cn(size === 'sm' ? 'h-3 w-3' : 'h-4 w-4', 'text-emerald-400 animate-pulse')} />
  ) : isHighTier ? (
    <Sparkles className={cn(size === 'sm' ? 'h-3 w-3' : 'h-4 w-4', 'text-amber-400')} />
  ) : (
    <TrendingUp className={cn(size === 'sm' ? 'h-3 w-3' : 'h-4 w-4', 'text-primary')} />
  );

  return (
    <div className={cn('flex flex-col gap-2', className)}>
      <div
        className={cn(
          'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-semibold tracking-wide backdrop-blur-md',
          badgeColor,
          size === 'sm' ? 'text-xs' : size === 'lg' ? 'text-base px-3.5 py-1.5' : 'text-xs',
        )}
      >
        {icon}
        <span>Score {insights.score}/100</span>
        <span className="opacity-75 font-normal">&bull; {insights.ratingLabel}</span>
      </div>

      {showDetails && (
        <div className="rounded-xl border border-glass-border bg-glass-bg p-4 backdrop-blur-md">
          <div className="mb-3 flex items-center justify-between">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              AI Virality Analysis
            </h4>
            <span className="text-xs font-medium text-primary">Wayin AI Score</span>
          </div>

          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            <div className="rounded-lg bg-background/50 p-2 border border-glass-border">
              <div className="font-semibold text-foreground">{insights.hookScore}%</div>
              <div className="text-[10px] text-muted-foreground">Hook Strength</div>
            </div>
            <div className="rounded-lg bg-background/50 p-2 border border-glass-border">
              <div className="font-semibold text-foreground">{insights.engagementScore}%</div>
              <div className="text-[10px] text-muted-foreground">Retention</div>
            </div>
            <div className="rounded-lg bg-background/50 p-2 border border-glass-border">
              <div className="font-semibold text-foreground">{insights.flowScore}%</div>
              <div className="text-[10px] text-muted-foreground">Shorts Flow</div>
            </div>
          </div>

          <div className="mt-3 flex items-start gap-2 text-xs text-muted-foreground">
            <Info className="h-3.5 w-3.5 mt-0.5 text-primary shrink-0" />
            <p className="leading-relaxed">{insights.explanation}</p>
          </div>
        </div>
      )}
    </div>
  );
}
