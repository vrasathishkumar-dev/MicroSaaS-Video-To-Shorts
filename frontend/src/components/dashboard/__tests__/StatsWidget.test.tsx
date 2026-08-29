import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { formatBytes, formatDuration, StatsWidget } from '@/components/dashboard/StatsWidget';
import type { DashboardStats } from '@/services/dashboardService';

describe('formatDuration', () => {
  it('formats seconds under a minute without a minutes segment', () => {
    expect(formatDuration(45)).toBe('45s');
  });

  it('formats minutes and remaining seconds', () => {
    expect(formatDuration(134)).toBe('2m 14s');
  });

  it('rounds fractional seconds', () => {
    expect(formatDuration(59.6)).toBe('1m 0s');
  });

  it('returns an em dash for null, undefined, or NaN', () => {
    expect(formatDuration(null)).toBe('—');
    expect(formatDuration(undefined)).toBe('—');
    expect(formatDuration(Number.NaN)).toBe('—');
  });
});

describe('formatBytes', () => {
  it('formats bytes below 1KB with a "B" unit', () => {
    expect(formatBytes(512)).toBe('512 B');
  });

  it('formats kilobytes with one decimal place', () => {
    expect(formatBytes(2048)).toBe('2.0 KB');
  });

  it('formats megabytes with one decimal place', () => {
    expect(formatBytes(128 * 1024 * 1024)).toBe('128.0 MB');
  });

  it('treats exactly zero bytes specially', () => {
    expect(formatBytes(0)).toBe('0 B');
  });

  it('returns an em dash for null, undefined, or NaN', () => {
    expect(formatBytes(null)).toBe('—');
    expect(formatBytes(undefined)).toBe('—');
    expect(formatBytes(Number.NaN)).toBe('—');
  });
});

describe('StatsWidget', () => {
  const stats: DashboardStats = {
    total_videos: 12,
    videos_by_status: {},
    total_clips: 34,
    clips_ready: 20,
    avg_processing_time_seconds: 95,
    storage_used_bytes: 2048,
  };

  it('renders formatted values for each stat tile', () => {
    render(<StatsWidget stats={stats} />);

    expect(screen.getByText('Total videos')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('Total clips')).toBeInTheDocument();
    expect(screen.getByText('34')).toBeInTheDocument();
    expect(screen.getByText('Clips ready')).toBeInTheDocument();
    expect(screen.getByText('20')).toBeInTheDocument();
    expect(screen.getByText('Avg. processing time')).toBeInTheDocument();
    expect(screen.getByText('1m 35s')).toBeInTheDocument();
    expect(screen.getByText('Storage used')).toBeInTheDocument();
    expect(screen.getByText('2.0 KB')).toBeInTheDocument();
  });

  it('renders placeholders when optional stats are null', () => {
    render(
      <StatsWidget
        stats={{
          ...stats,
          avg_processing_time_seconds: null,
          storage_used_bytes: null,
        }}
      />,
    );

    const placeholders = screen.getAllByText('—');
    expect(placeholders).toHaveLength(2);
  });
});
