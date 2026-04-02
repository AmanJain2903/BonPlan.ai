import { Link, useNavigate, useParams, Navigate } from 'react-router-dom';
import { LogOut } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { sidebarItems } from './sidebarItems';
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import SettingsPanel from './SettingsPanel';
import ProfilePanel from './ProfilePanel';
import PreferencesPanel from './PreferencesPanel';

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

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const sections = [1, 2, 3] as const;

  const activeItem = sidebarItems.find((i) => i.key === active);

  return (
    <div className="min-h-screen">

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <div className="flex pt-[65px]">
        {/* Sidebar */}
        <aside
          className={`fixed md:sticky top-[65px] left-0 z-40 h-[calc(100vh-65px)] w-72 border-r border-white/5 bg-midnight md:bg-transparent flex flex-col overflow-y-auto transition-transform duration-300 md:translate-x-0 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'
            }`}
        >
          <motion.div
            className="flex flex-col h-full"
          >
            {/* User info */}
            <div className="px-5 py-6 border-b border-white/5">
              <div className="flex items-center gap-3">
                <div className="h-11 w-11 rounded-full bg-gradient-to-br from-cyan/30 to-cyan/10 flex items-center justify-center text-sm font-bold text-cyan shrink-0">
                  {initials}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-white truncate">{fullName || 'User'}</p>
                  <p className="text-xs text-white/40 truncate">{user?.email}</p>
                </div>
              </div>
            </div>

            {/* Nav items */}
            <nav className="flex-1 py-3 px-3">
              {sections.map((sec, si) => (
                <div key={sec}>
                  {si > 0 && <div className="h-px bg-white/5 my-2 mx-2" />}
                  {sidebarItems
                    .filter((item) => item.section === sec)
                    .map((item) => {
                      const isActive = item.key === active;
                      return (
                        <Link
                          key={item.key}
                          to={`/account/${item.key}`}
                          onClick={() => setSidebarOpen(false)}
                          className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150 mb-0.5 ${isActive
                            ? 'bg-cyan/10 text-cyan font-medium'
                            : 'text-white/60 hover:bg-white/[0.04] hover:text-white'
                            }`}
                        >
                          <item.icon size={17} className={isActive ? 'text-cyan' : 'text-white/35'} />
                          {item.label}
                        </Link>
                      );
                    })}
                </div>
              ))}
            </nav>

            {/* Mobile sign out */}
            <div className="md:hidden px-3 pb-4">
              <div className="h-px bg-white/5 mb-3" />
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-red-400/80 hover:bg-red-400/10 hover:text-red-400 transition-all cursor-pointer"
              >
                <LogOut size={17} />
                Sign Out
              </button>
            </div>
          </motion.div>
        </aside>

        {/* Main content */}
        <main className="flex-1 min-w-0 overflow-hidden min-h-[calc(100vh-65px)] px-6 md:px-10 lg:px-16 py-10 z-2">
          <AnimatePresence mode="wait">
            <motion.div
              key={active}
              initial={{ opacity: 0, y: 15, filter: 'blur(4px)' }}
              animate={{ opacity: 1, y: 0, filter: 'blur(0px)', willChange: 'transform, opacity, filter' }}
              exit={{ opacity: 0, y: -15, filter: 'blur(4px)' }}
              transition={{ duration: 0.3, ease: 'easeOut' }}
            >
              <h1 className="text-3xl font-extrabold text-cyan mb-2">
                {activeItem?.label ?? 'Account'}
              </h1>
              <p className="text-sm text-white mb-10">
                {active === 'profile' && 'Manage your personal information.'}
                {active === 'preferences' && 'Customize your travel preferences and planning defaults.'}
                {active === 'integrations' && 'Connect third-party services and APIs.'}
                {active === 'notifications' && 'Control how and when you receive notifications.'}
                {active === 'settings' && 'Manage your account settings and security.'}
                {active === 'support' && 'Get help or reach out to the BonPlan.ai team.'}
              </p>

              {active === 'profile' ? (
                <ProfilePanel />
              ) : active === 'preferences' ? (
                <PreferencesPanel />
              ) : active === 'settings' ? (
                <SettingsPanel />
              ) : (
                <div className="max-w-7xl rounded-2xl border border-white/[0.06] bg-carbon/30 backdrop-blur-sm p-8 min-h-[300px] flex items-center justify-center">
                  <p className="text-white/20 text-sm">Coming soon...</p>
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
