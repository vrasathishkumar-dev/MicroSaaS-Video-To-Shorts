import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StatusBadge } from '@/components/videos/StatusBadge';
import type { VideoProjectStatus } from '@/types';

describe('StatusBadge', () => {
  it.each<[VideoProjectStatus, string, string]>([
    ['pending', 'Pending', 'bg-muted'],
    ['downloading', 'Downloading', 'bg-amber-500/15'],
    ['transcribing', 'Transcribing', 'bg-amber-500/15'],
    ['analyzing', 'Analyzing', 'bg-amber-500/15'],
    ['ready', 'Ready', 'bg-emerald-500/15'],
    ['failed', 'Failed', 'bg-destructive/15'],
  ])('renders the correct label and color class for "%s"', (status, label, colorClass) => {
    render(<StatusBadge status={status} />);
    const badge = screen.getByText(label);
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain(colorClass);
  });

  it('shows a pulsing indicator for in-progress statuses', () => {
    const { container } = render(<StatusBadge status="downloading" />);
    expect(container.querySelector('.animate-ping')).toBeInTheDocument();
  });

  it('does not show a pulsing indicator for terminal statuses', () => {
    const { container } = render(<StatusBadge status="ready" />);
    expect(container.querySelector('.animate-ping')).not.toBeInTheDocument();
  });

  it('merges a custom className onto the badge', () => {
    render(<StatusBadge status="pending" className="custom-class" />);
    expect(screen.getByText('Pending').className).toContain('custom-class');
  });
});
