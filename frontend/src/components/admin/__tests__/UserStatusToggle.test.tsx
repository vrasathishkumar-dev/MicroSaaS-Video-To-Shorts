import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { UserStatusToggle } from '@/components/admin/UserStatusToggle';

describe('UserStatusToggle', () => {
  it('shows "Activate" and fires onToggle when the user is inactive', async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    render(<UserStatusToggle isActive={false} onToggle={onToggle} />);

    const button = screen.getByRole('button', { name: /activate user/i });
    expect(button).toHaveTextContent('Activate');

    await user.click(button);
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it('shows "Deactivate" and fires onToggle when the user is active', async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    render(<UserStatusToggle isActive onToggle={onToggle} />);

    const button = screen.getByRole('button', { name: /deactivate user/i });
    expect(button).toHaveTextContent('Deactivate');

    await user.click(button);
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it('shows a loading spinner and disables the button while pending', () => {
    render(<UserStatusToggle isActive isLoading onToggle={vi.fn()} />);

    const button = screen.getByRole('button', { name: /deactivate user/i });
    expect(button).toBeDisabled();
    expect(button.querySelector('.animate-spin')).toBeInTheDocument();
  });

  it('does not call onToggle when disabled', async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    render(<UserStatusToggle isActive disabled onToggle={onToggle} />);

    await user.click(screen.getByRole('button', { name: /deactivate user/i }));
    expect(onToggle).not.toHaveBeenCalled();
  });
});
