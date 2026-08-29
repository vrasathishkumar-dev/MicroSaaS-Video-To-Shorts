import { useState } from 'react';
import {
  Film,
  LayoutDashboard,
  LogOut,
  Menu,
  Scissors,
  Settings,
  User,
  Video,
  X,
} from 'lucide-react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';

interface NavLinkItem {
  to: string;
  label: string;
  icon: React.ReactNode;
}

const NAV_LINKS: NavLinkItem[] = [
  {
    to: '/dashboard',
    label: 'Dashboard',
    icon: <LayoutDashboard className="h-4 w-4" />,
  },
  {
    to: '/videos',
    label: 'Videos',
    icon: <Video className="h-4 w-4" />,
  },
  {
    to: '/clips',
    label: 'Clips',
    icon: <Scissors className="h-4 w-4" />,
  },
];

/**
 * Persistent top navigation bar for authenticated pages.
 * Glassmorphic design matching the app's visual language.
 * Collapses to a hamburger menu on mobile viewports.
 */
export function Navbar() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  if (!user) return null;

  async function handleLogout() {
    await logout();
    navigate('/login');
  }

  const initials = user.full_name
    ? user.full_name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : user.email[0].toUpperCase();

  return (
    <nav className="sticky top-0 z-50 border-b border-glass-border bg-glass-bg backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
        {/* Logo */}
        <Link
          to="/dashboard"
          className="flex items-center gap-2 text-lg font-bold text-foreground transition-colors hover:text-primary"
        >
          <Film className="h-6 w-6 text-primary" />
          <span className="hidden sm:inline">VideoToShorts</span>
        </Link>

        {/* Desktop nav links */}
        <div className="hidden items-center gap-1 md:flex">
          {NAV_LINKS.map((link) => {
            const isActive =
              location.pathname === link.to ||
              location.pathname.startsWith(link.to + '/');
            return (
              <Link
                key={link.to}
                to={link.to}
                className={cn(
                  'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                )}
              >
                {link.icon}
                {link.label}
              </Link>
            );
          })}
        </div>

        {/* Right side: user menu + mobile toggle */}
        <div className="flex items-center gap-3">
          {/* User dropdown (desktop) */}
          <div className="relative hidden md:block">
            <UserMenu
              initials={initials}
              email={user.email}
              onLogout={handleLogout}
            />
          </div>

          {/* Mobile hamburger */}
          <button
            type="button"
            onClick={() => setIsMobileOpen(!isMobileOpen)}
            className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground md:hidden"
            aria-label="Toggle navigation menu"
          >
            {isMobileOpen ? (
              <X className="h-5 w-5" />
            ) : (
              <Menu className="h-5 w-5" />
            )}
          </button>
        </div>
      </div>

      {/* Mobile nav */}
      {isMobileOpen && (
        <div className="border-t border-glass-border bg-glass-bg px-4 pb-4 pt-2 backdrop-blur-xl md:hidden">
          <div className="flex flex-col gap-1">
            {NAV_LINKS.map((link) => {
              const isActive =
                location.pathname === link.to ||
                location.pathname.startsWith(link.to + '/');
              return (
                <Link
                  key={link.to}
                  to={link.to}
                  onClick={() => setIsMobileOpen(false)}
                  className={cn(
                    'flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium transition-all',
                    isActive
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                  )}
                >
                  {link.icon}
                  {link.label}
                </Link>
              );
            })}
            <hr className="my-2 border-glass-border" />
            <Link
              to="/profile"
              onClick={() => setIsMobileOpen(false)}
              className="flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              <User className="h-4 w-4" />
              Profile
            </Link>
            <Link
              to="/settings"
              onClick={() => setIsMobileOpen(false)}
              className="flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              <Settings className="h-4 w-4" />
              Settings
            </Link>
            <button
              type="button"
              onClick={() => {
                setIsMobileOpen(false);
                void handleLogout();
              }}
              className="flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium text-destructive hover:bg-destructive/10"
            >
              <LogOut className="h-4 w-4" />
              Log out
            </button>
          </div>
        </div>
      )}
    </nav>
  );
}

/* ------------------------------------------------------------------ */
/*  User dropdown for desktop                                         */
/* ------------------------------------------------------------------ */
function UserMenu({
  initials,
  email,
  onLogout,
}: {
  initials: string;
  email: string;
  onLogout: () => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-gradient-from to-gradient-to text-xs font-bold text-primary-foreground transition-shadow hover:shadow-lg"
        aria-label="User menu"
      >
        {initials}
      </button>

      {open && (
        <>
          {/* Backdrop overlay to close on click-away */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
            aria-hidden
          />
          <div className="absolute right-0 z-50 mt-2 w-56 rounded-xl border border-glass-border bg-glass-bg p-1 shadow-xl backdrop-blur-xl">
            <div className="px-3 py-2">
              <p className="truncate text-sm font-medium text-foreground">
                {email}
              </p>
            </div>
            <hr className="my-1 border-glass-border" />
            <Link
              to="/profile"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              <User className="h-4 w-4" />
              Profile
            </Link>
            <Link
              to="/settings"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              <Settings className="h-4 w-4" />
              Settings
            </Link>
            <hr className="my-1 border-glass-border" />
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                onLogout();
              }}
              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-destructive transition-colors hover:bg-destructive/10"
            >
              <LogOut className="h-4 w-4" />
              Log out
            </button>
          </div>
        </>
      )}
    </div>
  );
}
