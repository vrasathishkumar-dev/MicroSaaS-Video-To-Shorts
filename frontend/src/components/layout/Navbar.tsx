import { useState } from 'react';
import {
  Clapperboard,
  LayoutDashboard,
  LogOut,
  Menu,
  Scissors,
  Settings,
  User,
  Video,
  Wand2,
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
  {
    to: '/generate',
    label: 'AI Generator',
    icon: <Wand2 className="h-4 w-4" />,
  },
];

/**
 * Persistent top navigation bar for authenticated pages.
 * Restream-inspired: dark sticky nav, semi-transparent, clean layout.
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
    <nav
      className="sticky top-0 z-50 transition-all duration-500"
      style={{
        backgroundColor: 'oklch(0.08 0.025 264 / 92%)',
        backdropFilter: 'blur(20px)',
        borderBottom: '1px solid oklch(1 0 0 / 8%)',
      }}
    >
      <div className="mx-auto flex h-16 max-w-[1344px] items-center justify-between px-6 lg:px-8">
        {/* ── Logo ── */}
        <Link
          to="/dashboard"
          className="flex items-center gap-2.5 text-[15px] font-semibold text-foreground transition-opacity hover:opacity-80"
        >
          <div
            className="flex h-8 w-8 items-center justify-center rounded-lg"
            style={{ backgroundColor: 'oklch(0.60 0.20 264)' }}
          >
            <Clapperboard className="h-4 w-4 text-white" />
          </div>
          <span>
            Video<span style={{ color: 'oklch(0.60 0.20 264)' }}>ToShorts</span>
          </span>
        </Link>

        {/* ── Desktop nav ── */}
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
                  'flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-all duration-200',
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

        {/* ── Right side ── */}
        <div className="flex items-center gap-3">
          {/* User avatar dropdown (desktop) */}
          <div className="relative hidden md:block">
            <UserMenu
              initials={initials}
              email={user.email}
              onLogout={handleLogout}
            />
          </div>

          {/* Mobile toggle */}
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

      {/* ── Mobile nav panel ── */}
      {isMobileOpen && (
        <div
          className="border-t px-4 pb-5 pt-3 md:hidden"
          style={{ borderColor: 'oklch(1 0 0 / 8%)' }}
        >
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
                    'flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium transition-all',
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

            <div
              className="my-2 border-t"
              style={{ borderColor: 'oklch(1 0 0 / 8%)' }}
            />

            <Link
              to="/profile"
              onClick={() => setIsMobileOpen(false)}
              className="flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              <User className="h-4 w-4" />
              Profile
            </Link>
            <Link
              to="/settings"
              onClick={() => setIsMobileOpen(false)}
              className="flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground"
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
              className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium text-destructive hover:bg-destructive/10"
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
/*  User avatar dropdown for desktop                                   */
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
        className="flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold text-white transition-opacity hover:opacity-80"
        style={{ backgroundColor: 'oklch(0.60 0.20 264)' }}
        aria-label="User menu"
      >
        {initials}
      </button>

      {open && (
        <>
          {/* Click-away backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
            aria-hidden
          />
          <div
            className="absolute right-0 z-50 mt-2 w-56 rounded-2xl border p-1.5 shadow-2xl"
            style={{
              backgroundColor: 'oklch(0.12 0.02 264)',
              borderColor: 'oklch(1 0 0 / 10%)',
            }}
          >
            <div className="px-3 py-2">
              <p className="truncate text-xs font-medium text-muted-foreground">
                Signed in as
              </p>
              <p className="truncate text-sm font-medium text-foreground mt-0.5">
                {email}
              </p>
            </div>
            <div
              className="my-1 border-t"
              style={{ borderColor: 'oklch(1 0 0 / 8%)' }}
            />
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
            <div
              className="my-1 border-t"
              style={{ borderColor: 'oklch(1 0 0 / 8%)' }}
            />
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
