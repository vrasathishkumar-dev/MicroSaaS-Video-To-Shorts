import api from '@/services/api';
import type { PaginatedResponse } from '@/types';

/**
 * Response shape for the admin user endpoints (AdminUserResponse on the
 * backend). Defined here (rather than in the shared `@/types` module, owned
 * by another module team) to avoid cross-team edit conflicts during Phase 2.
 */
export interface AdminUser {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_verified: boolean;
  is_admin: boolean;
  created_at: string;
}

/** Response shape for GET /admin/stats. */
export interface AdminStats {
  total_users: number;
  total_videos: number;
  total_clips: number;
  active_users_last_30_days: number;
}

/** Fetch a page of users for the admin console, optionally filtered by search query. */
export async function listUsers(
  query = '',
  page = 1,
): Promise<PaginatedResponse<AdminUser>> {
  const { data } = await api.get<PaginatedResponse<AdminUser>>(
    '/admin/users',
    {
      params: {
        q: query || undefined,
        page,
      },
    },
  );
  return data;
}

/** Activate or deactivate a user account. */
export async function updateUserStatus(
  id: number,
  isActive: boolean,
): Promise<AdminUser> {
  const { data } = await api.put<AdminUser>(`/admin/users/${id}`, {
    is_active: isActive,
  });
  return data;
}

/** Fetch platform-wide aggregate stats for the admin overview page. */
export async function getAdminStats(): Promise<AdminStats> {
  const { data } = await api.get<AdminStats>('/admin/stats');
  return data;
}
