/**
 * Virality scoring and AI explanation helper inspired by Wayin.ai / OpusClip.
 */

const VIRAL_HOOK_KEYWORDS = [
  'secret',
  'never',
  'always',
  'biggest mistake',
  'game changer',
  'how to',
  'why you',
  'stop doing',
  'what if',
  'imagine',
  'nobody tells you',
  'incredible',
  'truth about',
  'step by step',
  'warning',
  'watch this',
];

export interface ViralityInsights {
  score: number; // 0 - 100
  hookScore: number; // 0 - 100
  engagementScore: number; // 0 - 100
  flowScore: number; // 0 - 100
  ratingLabel: 'Viral Potential' | 'High Performing' | 'Good Insight' | 'Standard Clip';
  explanation: string;
}

export function computeViralityInsights(
  text: string,
  durationSeconds: number,
  baseScore?: number | null,
): ViralityInsights {
  const lower = text.toLowerCase();
  
  let hookHits = 0;
  for (const kw of VIRAL_HOOK_KEYWORDS) {
    if (lower.includes(kw)) hookHits++;
  }

  // Duration factor: 20s to 50s is the golden window for YouTube Shorts & TikTok
  let durationFactor = 85;
  if (durationSeconds >= 25 && durationSeconds <= 45) {
    durationFactor = 95;
  } else if (durationSeconds >= 15 && durationSeconds <= 60) {
    durationFactor = 88;
  } else {
    durationFactor = 70;
  }

  // Base raw score from backend (0.0 - 1.0) or fallback
  const rawBase = baseScore !== undefined && baseScore !== null ? baseScore : 0.65;
  const hookScore = Math.min(99, Math.round(70 + hookHits * 9 + (rawBase * 20)));
  const engagementScore = Math.min(98, Math.round(68 + (rawBase * 22) + (hookHits * 4)));
  const flowScore = durationFactor;

  const finalScore = Math.min(
    99,
    Math.max(65, Math.round(hookScore * 0.4 + engagementScore * 0.35 + flowScore * 0.25))
  );

  let ratingLabel: ViralityInsights['ratingLabel'] = 'Good Insight';
  let explanation =
    'Presents a focused idea with clear spoken delivery suited for short-form retention.';

  if (finalScore >= 90) {
    ratingLabel = 'Viral Potential';
    explanation =
      'Strong opening hook with high-retention keywords and fast narrative progression that drives watch-through.';
  } else if (finalScore >= 80) {
    ratingLabel = 'High Performing';
    explanation =
      'Engaging pacing with clear takeaways and high audience resonance for Shorts & Reels.';
  } else if (finalScore < 72) {
    ratingLabel = 'Standard Clip';
    explanation =
      'Solid segment that can be further elevated with dynamic B-roll and punchy captions.';
  }

  return {
    score: finalScore,
    hookScore,
    engagementScore,
    flowScore,
    ratingLabel,
    explanation,
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
