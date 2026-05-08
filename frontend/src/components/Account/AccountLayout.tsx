import { Link, useNavigate, useParams, Navigate } from 'react-router-dom';
import { LogOut, Menu } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { sidebarItems } from './sidebarItems';
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import SettingsPanel from './SettingsPanel';
import ProfilePanel from './ProfilePanel';
import PreferencesPanel from './PreferencesPanel';
import SupportPanel from './SupportPanel';

const SECTION_LABELS: Record<number, string> = {
  1: 'Account',
  2: 'Security',
  3: 'Help',
};

export default function AccountLayout() {
  const { section } = useParams<{ section: string }>();
  const { isLoggedIn, user, logout } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  if (!isLoggedIn) return <Navigate to="/" replace />;

  const active = section ?? 'profile';
  const fullName = user ? `${user.firstName} ${user.lastName}`.trim() : '';
  const initials = user
    ? `${user.firstName?.[0] ?? ''}${user.lastName?.[0] ?? ''}`.toUpperCase()
    : '';

  const handleLogout = () => { logout(); navigate('/'); };

  const sections = [1, 2, 3] as const;
  const activeItem = sidebarItems.find((i) => i.key === active);

  return (
    <div className="min-h-screen">
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm md:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}
      </AnimatePresence>

      <div className="flex pt-[65px]">
        {/* Sidebar */}
        <aside
          className={`fixed md:sticky top-[65px] left-0 z-40 h-[calc(100vh-65px)] w-72 flex flex-col overflow-y-auto transition-transform duration-300 ease-out md:translate-x-0 ${
            sidebarOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
        >
          <div className="absolute inset-0 bg-[#07090d] md:bg-transparent border-r border-white/[0.04] md:border-none" />
          <div className="relative flex flex-col h-full">
            {/* User card */}
            <div className="px-4 py-5 border-b border-white/[0.04]">
              <div className="flex items-center gap-3 px-3 py-3 rounded-xl bg-white/[0.025] border border-white/[0.05]">
                <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-cyan/35 via-cyan/15 to-cyan/5 border border-cyan/20 flex items-center justify-center text-sm font-bold text-cyan shrink-0">
                  {initials || '?'}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-white truncate">{fullName || 'User'}</p>
                  <p className="text-[11px] text-white/30 truncate">{user?.email}</p>
                </div>
              </div>
            </div>

            {/* Nav */}
            <nav className="flex-1 px-3 py-4 overflow-y-auto">
              {sections.map((sec, si) => (
                <div key={sec} className={si > 0 ? 'mt-5' : ''}>
                  <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-white/20 px-3 mb-1.5">
                    {SECTION_LABELS[sec]}
                  </p>
                  <div className="space-y-0.5">
                    {sidebarItems.filter((item) => item.section === sec).map((item) => {
                      const isActive = item.key === active;
                      return (
                        <Link
                          key={item.key}
                          to={`/account/${item.key}`}
                          onClick={() => setSidebarOpen(false)}
                          className={`group flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 border ${
                            isActive
                              ? 'bg-cyan/[0.08] text-cyan border-cyan/[0.12]'
                              : 'text-white/45 hover:text-white/90 hover:bg-white/[0.04] border-transparent'
                          }`}
                        >
                          <item.icon
                            size={16}
                            className={`shrink-0 transition-colors ${
                              isActive ? 'text-cyan' : 'text-white/22 group-hover:text-white/50'
                            }`}
                          />
                          {item.label}
                          {isActive && (
                            <span className="ml-auto h-1.5 w-1.5 rounded-full bg-cyan/60" />
                          )}
                        </Link>
                      );
                    })}
                  </div>
                </div>
              ))}
            </nav>

            {/* Sign out */}
            <div className="px-3 py-4 border-t border-white/[0.04]">
              <button
                onClick={handleLogout}
                className="group w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-white/30 hover:text-red-400 hover:bg-red-400/[0.06] border border-transparent hover:border-red-400/10 transition-all duration-150 cursor-pointer"
              >
                <LogOut
                  size={16}
                  className="shrink-0 text-white/18 group-hover:text-red-400 transition-colors"
                />
                Sign Out
              </button>
            </div>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 min-w-0 overflow-hidden min-h-[calc(100vh-65px)] px-4 sm:px-8 md:px-10 lg:px-14 py-6 sm:py-10 z-2">
          <AnimatePresence mode="wait">
            <motion.div
              key={active}
              initial={{ opacity: 0, y: 14, filter: 'blur(4px)' }}
              animate={{ opacity: 1, y: 0, filter: 'blur(0px)', willChange: 'transform, opacity, filter' }}
              exit={{ opacity: 0, y: -14, filter: 'blur(4px)' }}
              transition={{ duration: 0.28, ease: 'easeOut' }}
            >
              {/* Page header */}
              <div className="mb-8">
                <div className="flex items-center gap-3">
                  {/* Mobile hamburger — left side */}
                  <button
                    onClick={() => setSidebarOpen(true)}
                    className="md:hidden flex items-center justify-center h-9 w-9 rounded-xl border border-white/10 text-white/40 hover:text-white hover:bg-white/[0.05] transition-all cursor-pointer shrink-0"
                  >
                    <Menu size={17} />
                  </button>
                  {activeItem && (
                    <div className="h-9 w-9 rounded-xl bg-cyan/10 border border-cyan/[0.14] flex items-center justify-center shrink-0">
                      <activeItem.icon size={17} className="text-cyan" />
                    </div>
                  )}
                  <div>
                    <h1 className="text-xl font-extrabold text-white tracking-tight">
                      {activeItem?.label ?? 'Account'}
                    </h1>
                    <p className="text-[11px] text-white/30 mt-0.5">
                      {active === 'profile' && 'Manage your personal information and contact details'}
                      {active === 'preferences' && 'Customize your travel preferences and planning defaults'}
                      {active === 'settings' && 'Manage account security and privacy settings'}
                      {active === 'support' && 'Get help or reach out to the BonPlan.ai team'}
                    </p>
                  </div>
                </div>
                <div className="mt-6 h-px bg-gradient-to-r from-white/[0.06] via-white/[0.02] to-transparent" />
              </div>

              {active === 'profile' ? (
                <ProfilePanel />
              ) : active === 'preferences' ? (
                <PreferencesPanel />
              ) : active === 'settings' ? (
                <SettingsPanel />
              ) : active === 'support' ? (
                <SupportPanel />
              ) : (
                <div className="max-w-2xl rounded-2xl border border-white/[0.06] bg-carbon/30 backdrop-blur-sm p-14 flex flex-col items-center justify-center gap-3 min-h-[280px]">
                  {activeItem && (
                    <div className="h-14 w-14 rounded-2xl bg-white/[0.03] border border-white/[0.05] flex items-center justify-center mb-2">
                      <activeItem.icon size={24} className="text-white/12" />
                    </div>
                  )}
                  <p className="text-sm font-semibold text-white/20">Coming Soon</p>
                  <p className="text-xs text-white/12 text-center">This feature is currently under development.</p>
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
