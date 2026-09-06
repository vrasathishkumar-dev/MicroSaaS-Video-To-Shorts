import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ViralityScoreBadge } from '@/components/clips/ViralityScoreBadge';
import { clipToViralityInsights } from '@/lib/virality';

describe('ViralityScoreBadge', () => {
  it('renders the "Not yet scored" neutral state for a null score, never a coerced 0', () => {
    render(
      <ViralityScoreBadge
        insights={clipToViralityInsights({
          virality_score: null,
          hook_score: null,
          completeness_score: null,
          framing_score: null,
          virality_reason: null,
        })}
      />,
    );
    expect(screen.getByText('Not yet scored')).toBeInTheDocument();
    expect(screen.queryByText(/Score .*\/100/)).not.toBeInTheDocument();
  });

  it('renders the sub-50 "Needs Manual Review" band at md size', () => {
    render(
      <ViralityScoreBadge
        size="md"
        insights={clipToViralityInsights({
          virality_score: 32,
          hook_score: 20,
          completeness_score: 40,
          framing_score: 0,
          virality_reason: 'Weak hook and a mid-sentence cut.',
        })}
      />,
    );
    expect(screen.getByText('Score 32/100')).toBeInTheDocument();
    expect(screen.getByText(/Needs Manual Review/)).toBeInTheDocument();
  });

  it('shows the "Estimate" marker only while framing has not yet been checked', () => {
    const { rerender } = render(
      <ViralityScoreBadge
        size="md"
        insights={clipToViralityInsights({
          virality_score: 70,
          hook_score: 70,
          completeness_score: 70,
          framing_score: null,
          virality_reason: 'x',
        })}
      />,
    );
    expect(screen.getByText(/Estimate/)).toBeInTheDocument();

    rerender(
      <ViralityScoreBadge
        size="md"
        insights={clipToViralityInsights({
          virality_score: 70,
          hook_score: 70,
          completeness_score: 70,
          framing_score: 1,
          virality_reason: 'x',
        })}
      />,
    );
    expect(screen.queryByText(/Estimate/)).not.toBeInTheDocument();
  });

  it('drops the rating-label text at sm size, keeping the numeric score', () => {
    render(
      <ViralityScoreBadge
        size="sm"
        insights={clipToViralityInsights({
          virality_score: 32,
          hook_score: 20,
          completeness_score: 40,
          framing_score: 0,
          virality_reason: 'x',
        })}
      />,
    );
    expect(screen.getByText('Score 32/100')).toBeInTheDocument();
    expect(screen.queryByText(/Needs Manual Review/)).not.toBeInTheDocument();
  });

  it('shows the framing pass/fail status, not a percentage, in the detail panel', () => {
    render(
      <ViralityScoreBadge
        size="lg"
        showDetails
        insights={clipToViralityInsights({
          virality_score: 90,
          hook_score: 90,
          completeness_score: 90,
          framing_score: 1,
          virality_reason: 'x',
        })}
      />,
    );
    expect(screen.getByText('Confirmed')).toBeInTheDocument();
    expect(screen.getByText('Speaker Framing')).toBeInTheDocument();
  });
});
