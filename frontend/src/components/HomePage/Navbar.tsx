import { useState, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Menu, X, User, LogOut, ChevronDown, Settings, Headset, UserCircle, SlidersHorizontal, Plug, Bell } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export default function Navbar() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const { isLoggedIn, user, logout } = useAuth();
  const navigate = useNavigate();
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = () => {
    setMenuOpen(false);
    setMobileOpen(false);
    logout();
    navigate('/');
  };

  const fullName = user ? `${user.firstName} ${user.lastName}`.trim() : '';
  const initials = user
    ? `${user.firstName?.[0] ?? ''}${user.lastName?.[0] ?? ''}`.toUpperCase()
    : '';

  const menuItemClass =
    'w-full flex items-center gap-3 px-4 py-2.5 text-sm text-white/70 hover:bg-white/[0.06] hover:text-white transition-all duration-150 cursor-pointer';

  return (
    <>
    <nav className="fixed top-0 left-0 right-0 z-50 bg-midnight/70 backdrop-blur-md border-b border-white/5">
      <div className="w-full flex items-center justify-between px-6 lg:px-12 xl:px-20 py-4">
        {/* Logo */}
        <a href="#top" className="flex items-center gap-1.5 text-xl font-bold tracking-tight text-white select-none">
        <Link to="/" className="flex items-center gap-1.5 text-xl font-bold tracking-tight text-white select-none">
            <img src="/logo.png" alt="BonPlan.ai" className="h-9 w-9 object-contain" />
            <span>BonPlan<span className="text-cyan">.</span>ai</span>
          </Link>
        </a>

        {/* Desktop */}
        <div className="hidden md:flex items-center gap-6">
          {isLoggedIn ? (
            <div className="relative" ref={menuRef}>
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                className={`flex items-center gap-2.5 rounded-full border border-cyan/30 bg-cyan/10 pl-2 pr-3 py-1.5 text-sm font-medium text-cyan hover:bg-cyan/20 hover:shadow-[0_0_15px_rgba(102,252,241,0.15)] transition-all duration-300 cursor-pointer ${menuOpen ? 'bg-cyan/20 shadow-[0_0_15px_rgba(102,252,241,0.15)]' : ''}`}
              >
                <div className="h-7 w-7 rounded-full bg-cyan/20 flex items-center justify-center text-xs font-bold text-cyan">
                  {initials || <User size={14} />}
                </div>
                <span className="hidden lg:inline">{user?.firstName || 'Account'}</span>
                <ChevronDown
                  size={14}
                  className={`transition-transform duration-300 ${menuOpen ? 'rotate-180' : ''}`}
                />
              </button>

              {/* Dropdown */}
              <div
                className={`absolute right-0 mt-2 w-64 rounded-2xl border border-white/10 bg-carbon/95 backdrop-blur-xl shadow-2xl overflow-hidden transition-all duration-200 origin-top-right ${
                  menuOpen
                    ? 'opacity-100 scale-100 translate-y-0'
                    : 'opacity-0 scale-95 -translate-y-1 pointer-events-none'
                }`}
              >
                {/* User header */}
                <div className="px-4 py-4 flex items-center gap-3 border-b border-white/5">
                  <div className="h-10 w-10 rounded-full bg-gradient-to-br from-cyan/30 to-cyan/10 flex items-center justify-center text-sm font-bold text-cyan shrink-0">
                    {initials || <User size={18} />}
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-white truncate">{fullName || 'User'}</p>
                    <p className="text-xs text-white/40 truncate">{user?.email}</p>
                  </div>
                </div>

                {/* Section 1 */}
                <div className="py-1.5">
                  <Link to="/account/profile" onClick={() => setMenuOpen(false)} className={menuItemClass}>
                    <UserCircle size={16} className="shrink-0 text-white/40" />
                    My Profile
                  </Link>
                  <Link to="/account/preferences" onClick={() => setMenuOpen(false)} className={menuItemClass}>
                    <SlidersHorizontal size={16} className="shrink-0 text-white/40" />
                    Preferences
                  </Link>
                  <Link to="/account/integrations" onClick={() => setMenuOpen(false)} className={menuItemClass}>
                    <Plug size={16} className="shrink-0 text-white/40" />
                    Integrations
                  </Link>
                </div>

                <div className="h-px bg-white/5" />

                {/* Section 2 */}
                <div className="py-1.5">
                  <Link to="/account/notifications" onClick={() => setMenuOpen(false)} className={menuItemClass}>
                    <Bell size={16} className="shrink-0 text-white/40" />
                    Notifications
                  </Link>
                  <Link to="/account/settings" onClick={() => setMenuOpen(false)} className={menuItemClass}>
                    <Settings size={16} className="shrink-0 text-white/40" />
                    Settings
                  </Link>
                </div>

                <div className="h-px bg-white/5" />

                {/* Section 3 */}
                <div className="py-1.5">
                  <Link to="/account/support" onClick={() => setMenuOpen(false)} className={menuItemClass}>
                    <Headset size={16} className="shrink-0 text-white/40" />
                    Support
                  </Link>
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-red-400/80 hover:bg-red-400/10 hover:text-red-400 transition-all duration-150 cursor-pointer"
                  >
                    <LogOut size={16} className="shrink-0" />
                    Sign Out
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-6 animate-[fade-in_300ms_ease-out]">
              <Link
                to="/login"
                className="text-sm text-white border border-white/20 rounded-lg px-5 py-2 hover:border-white/40 transition-colors duration-200"
              >
                Login
              </Link>
              <Link
                to="/register"
                className="text-sm font-semibold bg-cyan text-midnight rounded-lg px-5 py-2 hover:shadow-[0_0_20px_rgba(102,252,241,0.35)] transition-all duration-200"
              >
                Sign Up
              </Link>
            </div>
          )}
        </div>

        {/* Mobile toggle */}
        {isLoggedIn ? (
          <button
            className={`md:hidden flex items-center gap-1.5 rounded-full border border-cyan/30 bg-cyan/10 pl-1.5 pr-2 py-1 text-xs font-medium text-cyan hover:bg-cyan/20 transition-all duration-300 cursor-pointer ${mobileOpen ? 'bg-cyan/20' : ''}`}
            onClick={() => setMobileOpen(!mobileOpen)}
          >
            <div className="h-6 w-6 rounded-full bg-cyan/20 flex items-center justify-center text-[10px] font-bold text-cyan">
              {initials || <User size={12} />}
            </div>
            <ChevronDown size={12} className={`transition-transform duration-300 ${mobileOpen ? 'rotate-180' : ''}`} />
          </button>
        ) : (
          <button
            className="md:hidden text-white cursor-pointer"
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label="Toggle menu"
          >
            {mobileOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        )}
      </div>

      {/* Mobile menu */}
      <div
        className={`md:hidden border-t border-white/5 bg-midnight/95 backdrop-blur-xl px-6 flex flex-col overflow-hidden transition-all duration-300 ease-in-out ${
          mobileOpen ? 'max-h-[400px] pb-5 pt-3 opacity-100' : 'max-h-0 pb-0 pt-0 opacity-0'
        }`}
      >
        {isLoggedIn ? (
          <>
            {/* User info */}
            <div className="flex items-center gap-3 pb-3 mb-2 border-b border-white/5">
              <div className="h-9 w-9 rounded-full bg-gradient-to-br from-cyan/30 to-cyan/10 flex items-center justify-center text-xs font-bold text-cyan shrink-0">
                {initials || <User size={16} />}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-white truncate">{fullName || 'User'}</p>
                <p className="text-[11px] text-white/40 truncate">{user?.email}</p>
              </div>
            </div>

            <Link to="/account/profile" onClick={() => setMobileOpen(false)} className="flex items-center gap-3 py-2.5 text-sm text-white/70 hover:text-white transition-colors">
              <UserCircle size={16} className="text-white/40" />
              My Profile
            </Link>
            <Link to="/account/preferences" onClick={() => setMobileOpen(false)} className="flex items-center gap-3 py-2.5 text-sm text-white/70 hover:text-white transition-colors">
              <SlidersHorizontal size={16} className="text-white/40" />
              Preferences
            </Link>
            <Link to="/account/integrations" onClick={() => setMobileOpen(false)} className="flex items-center gap-3 py-2.5 text-sm text-white/70 hover:text-white transition-colors">
              <Plug size={16} className="text-white/40" />
              Integrations
            </Link>

            <div className="h-px bg-white/5 my-1.5" />

            <Link to="/account/notifications" onClick={() => setMobileOpen(false)} className="flex items-center gap-3 py-2.5 text-sm text-white/70 hover:text-white transition-colors">
              <Bell size={16} className="text-white/40" />
              Notifications
            </Link>
            <Link to="/account/settings" onClick={() => setMobileOpen(false)} className="flex items-center gap-3 py-2.5 text-sm text-white/70 hover:text-white transition-colors">
              <Settings size={16} className="text-white/40" />
              Settings
            </Link>

            <div className="h-px bg-white/5 my-1.5" />

            <Link to="/account/support" onClick={() => setMobileOpen(false)} className="flex items-center gap-3 py-2.5 text-sm text-white/70 hover:text-white transition-colors">
              <Headset size={16} className="text-white/40" />
              Support
            </Link>
            <button
              onClick={handleLogout}
              className="flex items-center gap-3 py-2.5 text-sm text-red-400/80 hover:text-red-400 transition-colors cursor-pointer"
            >
              <LogOut size={16} />
              Sign Out
            </button>
          </>
        ) : (
          <>
            <Link
              to="/login"
              className="text-sm text-white text-center border border-white/20 rounded-lg px-5 py-2.5 hover:border-white/40 transition-colors mt-1"
              onClick={() => setMobileOpen(false)}
            >
              Login
            </Link>
            <Link
              to="/register"
              className="text-sm font-semibold text-center bg-cyan text-midnight rounded-lg px-5 py-2.5 hover:shadow-[0_0_20px_rgba(102,252,241,0.35)] transition-all mt-3"
              onClick={() => setMobileOpen(false)}
            >
              Sign Up
            </Link>
          </>
        )}
      </div>
    </nav>
    </>
  );
}
