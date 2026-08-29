import api from '@/services/api';

/**
 * Response shape for GET /dashboard/stats.
 *
 * Defined here (rather than in the shared `@/types` module, owned by
 * another module team) to avoid cross-team edit conflicts during Phase 2.
 */
export interface DashboardStats {
  total_videos: number;
  videos_by_status: Record<string, number>;
  total_clips: number;
  clips_ready: number;
  avg_processing_time_seconds: number | null;
  storage_used_bytes: number | null;
}

/** Fetch aggregate stats (video/clip counts, status breakdown, storage) for the current user. */
export async function getDashboardStats(): Promise<DashboardStats> {
  const { data } = await api.get<DashboardStats>('/dashboard/stats');
  return data;
}
