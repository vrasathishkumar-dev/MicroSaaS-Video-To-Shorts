import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UserTable } from '@/components/admin/UserTable';
import { useAuth } from '@/hooks/useAuth';
import * as adminService from '@/services/adminService';
import type { AdminUser } from '@/services/adminService';

vi.mock('@/hooks/useAuth');
vi.mock('@/services/adminService');

const mockedUseAuth = vi.mocked(useAuth);
const mockedUpdateUserStatus = vi.mocked(adminService.updateUserStatus);

const users: AdminUser[] = [
  {
    id: 1,
    email: 'admin@example.com',
    full_name: 'Admin Person',
    is_active: true,
    is_verified: true,
    is_admin: true,
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 2,
    email: 'user@example.com',
    full_name: 'Regular User',
    is_active: true,
    is_verified: false,
    is_admin: false,
    created_at: '2024-02-01T00:00:00Z',
  },
];

describe('UserTable', () => {
  beforeEach(() => {
    mockedUpdateUserStatus.mockReset();
    mockedUseAuth.mockReturnValue({
      user: {
        id: 1,
        email: 'admin@example.com',
        full_name: 'Admin',
        is_active: true,
        is_verified: true,
        created_at: '2024-01-01T00:00:00Z',
        is_admin: true,
      },
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });
  });

  it('renders a row per user with email and status badges', () => {
    render(<UserTable users={users} onUserUpdated={vi.fn()} />);

    expect(screen.getByText('admin@example.com')).toBeInTheDocument();
    expect(screen.getByText('user@example.com')).toBeInTheDocument();
    expect(screen.getByText('Admin')).toBeInTheDocument();
    expect(screen.getByText('Unverified')).toBeInTheDocument();
  });

  it('shows "(your account)" instead of a toggle for the current user', () => {
    render(<UserTable users={users} onUserUpdated={vi.fn()} />);

    expect(screen.getByText('(your account)')).toBeInTheDocument();
    // Only the other user should get an actionable toggle button.
    expect(screen.getAllByRole('button')).toHaveLength(1);
  });

  it('calls updateUserStatus and onUserUpdated when toggling another user', async () => {
    const user = userEvent.setup();
    const updated: AdminUser = { ...users[1], is_active: false };
    mockedUpdateUserStatus.mockResolvedValueOnce(updated);
    const onUserUpdated = vi.fn();

    render(<UserTable users={users} onUserUpdated={onUserUpdated} />);
    await user.click(screen.getByRole('button', { name: /deactivate user/i }));

    await waitFor(() => {
      expect(mockedUpdateUserStatus).toHaveBeenCalledWith(2, false);
      expect(onUserUpdated).toHaveBeenCalledWith(updated);
    });
  });

  it('calls onError when the toggle request fails', async () => {
    const user = userEvent.setup();
    mockedUpdateUserStatus.mockRejectedValueOnce(new Error('boom'));
    const onError = vi.fn();

    render(<UserTable users={users} onUserUpdated={vi.fn()} onError={onError} />);
    await user.click(screen.getByRole('button', { name: /deactivate user/i }));

    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith(
        'Failed to update user@example.com. Please try again.',
      );
    });
  });
});
