/**
 * Score -> label/color mapping for the virality badge. The scores
 * themselves (`virality_score`, `hook_score`, `completeness_score`,
 * `framing_score`, `virality_reason`) are server-computed on `Clip` — this
 * file only maps those real numbers to a rating label, never invents one.
 */

/**
 * Below this, a clip's rating label instructs manual review rather than
 * reading as "fine." Starting point per Designer spec; recalibrate here
 * once real score distributions are visible.
 */
export const REVIEW_THRESHOLD = 50;

export type FramingStatus = 'confirmed' | 'not_confident' | 'not_checked';

export interface ViralityInsights {
  /** 0-100, or `null` for a clip not yet scored (legacy/pre-migration). */
  score: number | null;
  hookScore: number | null;
  completenessScore: number | null;
  /** Pass/fail signal — never rendered as a percentage. */
  framingStatus: FramingStatus;
  ratingLabel:
    | 'Viral Potential'
    | 'High Performing'
    | 'Good Insight'
    | 'Needs Manual Review'
    | null;
  explanation: string;
}

const NOT_SCORED_EXPLANATION =
  "This clip hasn't been scored yet — it'll be scored the next time it's edited or re-rendered.";

export function getRatingLabel(score: number | null): ViralityInsights['ratingLabel'] {
  if (score === null) return null;
  if (score >= 90) return 'Viral Potential';
  if (score >= 80) return 'High Performing';
  if (score >= REVIEW_THRESHOLD) return 'Good Insight';
  return 'Needs Manual Review';
}

function framingStatusFromScore(framingScore: number | null): FramingStatus {
  // `undefined`/`null` (not `!framingScore`) so a real `0` (checked, no
  // confident subject) isn't mistaken for "not checked yet".
  if (framingScore === null || framingScore === undefined) return 'not_checked';
  return framingScore > 0 ? 'confirmed' : 'not_confident';
}

interface ScoredClip {
  virality_score: number | null;
  hook_score: number | null;
  completeness_score: number | null;
  framing_score: number | null;
  virality_reason: string | null;
}

/** Builds badge insights directly from a clip's own backend-computed fields. */
export function clipToViralityInsights(clip: ScoredClip): ViralityInsights {
  const score = clip.virality_score;
  return {
    score,
    hookScore: clip.hook_score,
    completenessScore: clip.completeness_score,
    framingStatus: framingStatusFromScore(clip.framing_score),
    ratingLabel: getRatingLabel(score),
    explanation: score === null ? NOT_SCORED_EXPLANATION : (clip.virality_reason ?? ''),
  };
}

export function getExpectedShortsCount(durationSeconds: number | null): string {
  if (!durationSeconds || durationSeconds <= 0) return '3-5 Shorts';
  if (durationSeconds <= 60) return '1 Short';
  if (durationSeconds <= 180) return '2 Shorts';
  if (durationSeconds <= 360) return '3 Shorts';
  if (durationSeconds <= 600) return '4-5 Shorts';
  if (durationSeconds <= 1200) return '6-7 Shorts';
  if (durationSeconds <= 1800) return '8-10 Shorts';
  if (durationSeconds <= 3600) return '12-15 Shorts';
  const estimate = Math.min(25, Math.max(12, Math.floor(durationSeconds / 240)));
  return `${estimate} Shorts`;
}
