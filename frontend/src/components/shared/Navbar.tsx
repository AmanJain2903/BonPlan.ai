import { useState, useRef, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Menu, X, User, LogOut, ChevronDown, Settings, Headset, UserCircle, SlidersHorizontal, Shield } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../../context/AuthContext';

export default function Navbar() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const { isLoggedIn, user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
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

  useEffect(() => {
    setMobileOpen(false);
    setMenuOpen(false);
  }, [location.pathname]);

  const handleLogout = () => {
    setMenuOpen(false);
    setMobileOpen(false);
    logout();
    navigate('/');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const fullName = user ? `${user.firstName} ${user.lastName}`.trim() : '';
  const initials = user
    ? `${user.firstName?.[0] ?? ''}${user.lastName?.[0] ?? ''}`.toUpperCase()
    : '';

  const isActive = (path: string) => location.pathname === path || location.pathname.startsWith(path + '/');

  const menuItemClass = (path: string) => {
    const active = isActive(path);
    return `w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-all duration-150 cursor-pointer ${
      active
        ? 'bg-cyan/10 text-cyan'
        : 'text-white/70 hover:bg-white/[0.06] hover:text-white'
    }`;
  };

  const mobileItemClass = (path: string) => {
    const active = isActive(path);
    return `flex items-center gap-3 py-2.5 text-sm transition-colors ${
      active ? 'text-cyan' : 'text-white/70 hover:text-white'
    }`;
  };

  const dropdownVariants = {
    hidden: { opacity: 0, scale: 0.95, y: -6, filter: 'blur(4px)' },
    visible: { opacity: 1, scale: 1, y: 0, filter: 'blur(0px)' },
  };

  const mobileVariants = {
    hidden: { opacity: 0, height: 0 },
    visible: { opacity: 1, height: 'auto' },
  };

  return (
    <>
      <nav className="fixed top-0 left-0 right-0 z-50 bg-midnight/80 backdrop-blur-lg border-b border-white/[0.06]">
        <div className="w-full flex items-center justify-between px-4 sm:px-6 lg:px-12 xl:px-20 py-4 max-w-8xl mx-auto">
          {/* Logo */}
          <Link
            to="/"
            onClick={(e) => {
              sessionStorage.setItem('force-scroll-top', 'true');
              if (window.location.pathname === '/') {
                e.preventDefault();
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }
            }}
            className="flex items-center gap-1.5 text-lg sm:text-xl font-bold tracking-tight text-white select-none opacity-100 hover:opacity-75 transition-opacity duration-200 flex-shrink-0"
          >
            <img src="/logo.png" alt="BonPlan.ai" className="h-7 w-7 sm:h-9 sm:w-9 object-contain" />
            <span>BonPlan<span className="text-cyan">.</span>ai</span>
          </Link>

          {/* Desktop */}
          <div className="hidden md:flex items-center gap-6 h-10">
            <AnimatePresence mode="wait">
              {isLoggedIn ? (
                <motion.div
                  key="user-menu"
                  initial={{ opacity: 0, scale: 0.95, filter: 'blur(4px)' }}
                  animate={{ opacity: 1, scale: 1, filter: 'blur(0px)', willChange: 'transform, opacity, filter' }}
                  exit={{ opacity: 0, scale: 0.95, filter: 'blur(4px)' }}
                  transition={{ duration: 0.3, ease: 'easeOut' }}
                  className="relative"
                  ref={menuRef}
                >
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
                  <AnimatePresence>
                    {menuOpen && (
                      <motion.div
                        initial="hidden"
                        animate="visible"
                        exit="hidden"
                        variants={dropdownVariants}
                        transition={{ duration: 0.18, ease: 'easeOut' }}
                        className="absolute right-0 mt-2 w-64 rounded-2xl border border-white/10 bg-carbon/95 backdrop-blur-xl shadow-2xl overflow-hidden origin-top-right"
                      >
                        {/* User header */}
                        <div className="px-4 py-4 flex items-center gap-3 border-b border-white/[0.08]">
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
                          {user?.isAdmin && (
                            <Link to="/admin" className={menuItemClass('/admin')}>
                              <Shield size={16} className="shrink-0 text-white/40" />
                              Admin Dashboard
                            </Link>
                          )}
                          <Link to="/account/profile" className={menuItemClass('/account/profile')}>
                            <UserCircle size={16} className="shrink-0 text-white/40" />
                            My Profile
                          </Link>
                          <Link to="/account/preferences" className={menuItemClass('/account/preferences')}>
                            <SlidersHorizontal size={16} className="shrink-0 text-white/40" />
                            Preferences
                          </Link>
                        </div>

                        <div className="h-px bg-white/[0.08]" />

                        {/* Section 2 */}
                        <div className="py-1.5">
                          <Link to="/account/settings" className={menuItemClass('/account/settings')}>
                            <Settings size={16} className="shrink-0 text-white/40" />
                            Settings
                          </Link>
                        </div>

                        <div className="h-px bg-white/[0.08]" />

                        {/* Section 3 */}
                        <div className="py-1.5">
                          <Link to="/account/support" className={menuItemClass('/account/support')}>
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
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              ) : (
                <motion.div
                  key="auth-buttons"
                  initial={{ opacity: 0, scale: 0.95, filter: 'blur(4px)' }}
                  animate={{ opacity: 1, scale: 1, filter: 'blur(0px)', willChange: 'transform, opacity, filter' }}
                  exit={{ opacity: 0, scale: 0.95, filter: 'blur(4px)' }}
                  transition={{ duration: 0.3, ease: 'easeOut' }}
                  className="flex items-center gap-6"
                >
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
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Mobile toggle */}
          {isLoggedIn ? (
            <button
              className={`md:hidden flex-shrink-0 flex items-center gap-1.5 rounded-full border border-cyan/30 bg-cyan/10 pl-1.5 pr-2 py-1 text-xs font-medium text-cyan hover:bg-cyan/20 transition-all duration-300 cursor-pointer ${mobileOpen ? 'bg-cyan/20' : ''}`}
              onClick={() => setMobileOpen(!mobileOpen)}
            >
              <div className="h-6 w-6 rounded-full bg-cyan/20 flex items-center justify-center text-[10px] font-bold text-cyan">
                {initials || <User size={12} />}
              </div>
              <ChevronDown size={12} className={`transition-transform duration-300 ${mobileOpen ? 'rotate-180' : ''}`} />
            </button>
          ) : (
            <button
              className="md:hidden flex-shrink-0 text-white cursor-pointer"
              onClick={() => setMobileOpen(!mobileOpen)}
              aria-label="Toggle menu"
            >
              {mobileOpen ? <X size={22} /> : <Menu size={22} />}
            </button>
          )}
        </div>

        {/* Mobile menu */}
        <AnimatePresence>
          {mobileOpen && (
            <motion.div
              initial="hidden"
              animate="visible"
              exit="hidden"
              variants={mobileVariants}
              transition={{ duration: 0.22, ease: 'easeInOut' }}
              className="md:hidden border-t border-white/[0.06] bg-midnight/95 backdrop-blur-xl px-6 pb-5 pt-3 overflow-hidden"
            >
              {isLoggedIn ? (
                <>
                  {/* User info */}
                  <div className="flex items-center gap-3 pb-3 mb-2 border-b border-white/[0.08]">
                    <div className="h-9 w-9 rounded-full bg-gradient-to-br from-cyan/30 to-cyan/10 flex items-center justify-center text-xs font-bold text-cyan shrink-0">
                      {initials || <User size={16} />}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-white truncate">{fullName || 'User'}</p>
                      <p className="text-[11px] text-white/40 truncate">{user?.email}</p>
                    </div>
                  </div>

                  {user?.isAdmin && (
                    <Link to="/admin" className={mobileItemClass('/admin')}>
                      <Shield size={16} className="text-white/40" />
                      Admin Dashboard
                    </Link>
                  )}
                  <Link to="/account/profile" className={mobileItemClass('/account/profile')}>
                    <UserCircle size={16} className="text-white/40" />
                    My Profile
                  </Link>
                  <Link to="/account/preferences" className={mobileItemClass('/account/preferences')}>
                    <SlidersHorizontal size={16} className="text-white/40" />
                    Preferences
                  </Link>

                  <div className="h-px bg-white/[0.08] my-1.5" />

                  <Link to="/account/settings" className={mobileItemClass('/account/settings')}>
                    <Settings size={16} className="text-white/40" />
                    Settings
                  </Link>

                  <div className="h-px bg-white/[0.08] my-1.5" />

                  <Link to="/account/support" className={mobileItemClass('/account/support')}>
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
                    className="text-sm text-white text-center border border-white/20 rounded-lg px-5 py-2.5 hover:border-white/40 transition-colors mt-1 block"
                  >
                    Login
                  </Link>
                  <Link
                    to="/register"
                    className="text-sm font-semibold text-center bg-cyan text-midnight rounded-lg px-5 py-2.5 hover:shadow-[0_0_20px_rgba(102,252,241,0.35)] transition-all mt-3 block"
                  >
                    Sign Up
                  </Link>
                </>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </nav>
    </>
  );
}
