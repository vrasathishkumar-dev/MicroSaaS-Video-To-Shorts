import { Flame, Sparkles, TrendingUp, AlertCircle, Info } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ViralityInsights } from '@/lib/virality';

export interface ViralityScoreBadgeProps {
  insights: ViralityInsights;
  showDetails?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const FRAMING_STATUS_LABEL: Record<ViralityInsights['framingStatus'], string> = {
  confirmed: 'Confirmed',
  not_confident: 'Not confident',
  not_checked: 'Not checked',
};

export function ViralityScoreBadge({
  insights,
  showDetails = false,
  size = 'md',
  className,
}: ViralityScoreBadgeProps) {
  const iconSize = size === 'sm' ? 'h-3 w-3' : 'h-4 w-4';
  const isPartial = insights.score !== null && insights.framingStatus === 'not_checked';

  if (insights.score === null) {
    // Legacy/pre-migration clip — never coerce to 0, never hide the badge.
    return (
      <div className={cn('flex flex-col gap-2', className)}>
        <div
          className={cn(
            'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-semibold tracking-wide backdrop-blur-md bg-muted text-muted-foreground',
            size === 'sm' ? 'text-xs' : size === 'lg' ? 'text-base px-3.5 py-1.5' : 'text-xs',
          )}
        >
          <Info className={iconSize} />
          <span>Not yet scored</span>
        </div>

        {showDetails && (
          <div className="rounded-xl border border-glass-border bg-glass-bg p-4 backdrop-blur-md">
            <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              AI Virality Analysis
            </h4>

            <div className="grid grid-cols-3 gap-2 text-center text-xs">
              <div className="rounded-lg bg-background/50 p-2 border border-glass-border">
                <div className="font-semibold text-foreground">&mdash;</div>
                <div className="text-[10px] text-muted-foreground">Hook Strength</div>
              </div>
              <div className="rounded-lg bg-background/50 p-2 border border-glass-border">
                <div className="font-semibold text-foreground">&mdash;</div>
                <div className="text-[10px] text-muted-foreground">Retention</div>
              </div>
              <div className="rounded-lg bg-background/50 p-2 border border-glass-border">
                <div className="font-semibold text-foreground">&mdash;</div>
                <div className="text-[10px] text-muted-foreground">Speaker Framing</div>
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

  // Derived from the label (itself driven by `REVIEW_THRESHOLD` in
  // virality.ts) rather than re-comparing the raw number here, so the
  // color band can never drift out of sync with the label it's paired with.
  const isTopTier = insights.ratingLabel === 'Viral Potential';
  const isHighTier = insights.ratingLabel === 'High Performing';
  const isReviewTier = insights.ratingLabel === 'Needs Manual Review';

  const badgeColor = isTopTier
    ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
    : isHighTier
      ? 'bg-amber-500/15 text-amber-400 border-amber-500/30'
      : isReviewTier
        ? 'bg-destructive/15 text-destructive border-destructive/30'
        : 'bg-primary/15 text-primary border-primary/30';

  const icon = isTopTier ? (
    <Flame className={cn(iconSize, 'text-emerald-400 animate-pulse')} />
  ) : isHighTier ? (
    <Sparkles className={cn(iconSize, 'text-amber-400')} />
  ) : isReviewTier ? (
    <AlertCircle className={cn(iconSize, 'text-destructive')} />
  ) : (
    <TrendingUp className={cn(iconSize, 'text-primary')} />
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
        {/* sm shares a tight footer row with the Download pill — the color
            already encodes the tier, so drop the label text there. */}
        {size !== 'sm' && (
          <span className="opacity-75 font-normal">&bull; {insights.ratingLabel}</span>
        )}
        {isPartial && <span className="opacity-75 font-normal">&bull; Estimate</span>}
      </div>

      {showDetails && (
        <div className="rounded-xl border border-glass-border bg-glass-bg p-4 backdrop-blur-md">
          <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            AI Virality Analysis
          </h4>

          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            <div className="rounded-lg bg-background/50 p-2 border border-glass-border">
              <div className="font-semibold text-foreground">
                {insights.hookScore !== null ? `${Math.round(insights.hookScore)}%` : '—'}
              </div>
              <div className="text-[10px] text-muted-foreground">Hook Strength</div>
            </div>
            <div className="rounded-lg bg-background/50 p-2 border border-glass-border">
              <div className="font-semibold text-foreground">
                {insights.completenessScore !== null
                  ? `${Math.round(insights.completenessScore)}%`
                  : '—'}
              </div>
              <div className="text-[10px] text-muted-foreground">Retention</div>
            </div>
            <div className="rounded-lg bg-background/50 p-2 border border-glass-border">
              <div className="font-semibold text-foreground">
                {FRAMING_STATUS_LABEL[insights.framingStatus]}
              </div>
              <div className="text-[10px] text-muted-foreground">Speaker Framing</div>
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
