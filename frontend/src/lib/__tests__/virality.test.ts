import { describe, expect, it } from 'vitest';
import { clipToViralityInsights, getRatingLabel } from '@/lib/virality';

describe('getRatingLabel', () => {
  it('returns null for an unscored clip', () => {
    expect(getRatingLabel(null)).toBeNull();
  });

  it('bands a genuinely low score as "Needs Manual Review"', () => {
    expect(getRatingLabel(32)).toBe('Needs Manual Review');
  });

  it('bands the existing thresholds unchanged above 50', () => {
    expect(getRatingLabel(95)).toBe('Viral Potential');
    expect(getRatingLabel(85)).toBe('High Performing');
    expect(getRatingLabel(65)).toBe('Good Insight');
  });
});

describe('clipToViralityInsights', () => {
  it('discriminates two clips with different sub-scores instead of converging', () => {
    const strong = clipToViralityInsights({
      virality_score: 92,
      hook_score: 90,
      completeness_score: 95,
      framing_score: 1,
      virality_reason: 'Strong hook, clean sentence boundaries, confirmed framing.',
    });
    const weak = clipToViralityInsights({
      virality_score: 28,
      hook_score: 15,
      completeness_score: 30,
      framing_score: 0,
      virality_reason: 'Weak hook, mid-sentence cut, no confident subject found.',
    });

    expect(strong.score).not.toBe(weak.score);
    expect(strong.ratingLabel).toBe('Viral Potential');
    expect(weak.ratingLabel).toBe('Needs Manual Review');
    expect(strong.explanation).not.toBe(weak.explanation);
  });

  it('maps a null virality_score to the "not yet scored" state, not zero', () => {
    const insights = clipToViralityInsights({
      virality_score: null,
      hook_score: null,
      completeness_score: null,
      framing_score: null,
      virality_reason: null,
    });

    expect(insights.score).toBeNull();
    expect(insights.ratingLabel).toBeNull();
    expect(insights.explanation).toMatch(/hasn't been scored yet/);
  });

  it('maps framing_score to a pass/fail status, not a percentage', () => {
    expect(
      clipToViralityInsights({
        virality_score: 70,
        hook_score: 70,
        completeness_score: 70,
        framing_score: null,
        virality_reason: 'x',
      }).framingStatus,
    ).toBe('not_checked');

    expect(
      clipToViralityInsights({
        virality_score: 70,
        hook_score: 70,
        completeness_score: 70,
        framing_score: 0,
        virality_reason: 'x',
      }).framingStatus,
    ).toBe('not_confident');

    expect(
      clipToViralityInsights({
        virality_score: 70,
        hook_score: 70,
        completeness_score: 70,
        framing_score: 1,
        virality_reason: 'x',
      }).framingStatus,
    ).toBe('confirmed');
  });
});
