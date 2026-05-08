import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { Menu } from 'lucide-react';
import AdminSidebar from './AdminSidebar';
import { adminSections } from './adminNav';
import { cn } from '../../utils/tailwind';

export default function AdminLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen pt-[65px] bg-transparent text-white overflow-hidden relative z-40">
      {/* Sidebar */}
      <AdminSidebar sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden relative z-10">
        {/* Page Content */}
        <main className="flex-1 overflow-y-auto">
          <div className="sticky top-0 z-30 flex items-center gap-2 border-b border-white/10 bg-[#07090d]/90 px-4 py-3 backdrop-blur-xl sm:px-6 md:hidden">
            <button
              onClick={() => setSidebarOpen(true)}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03] text-white/55 transition-all hover:bg-white/[0.06] hover:text-white"
              aria-label="Open admin navigation"
            >
              <Menu className="h-4 w-4" />
            </button>
            <div className="relative min-w-0 flex-1">
              <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-5 bg-gradient-to-r from-[#07090d]/95 to-transparent" />
              <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-7 bg-gradient-to-l from-[#07090d]/95 to-transparent" />
              <nav className="flex min-w-0 gap-2 overflow-x-auto pb-0.5 pl-1 pr-6 scrollbar-hide">
                {adminSections.flatMap(section => section.items).map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.href}
                      to={item.href}
                      className={({ isActive }) => cn(
                        "inline-flex shrink-0 items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold transition-all",
                        isActive
                          ? "border-cyan/[0.18] bg-cyan/[0.10] text-cyan"
                          : "border-white/[0.07] bg-white/[0.025] text-white/45 hover:border-white/15 hover:text-white/80"
                      )}
                    >
                      {({ isActive }) => (
                        <>
                          <Icon className={cn("h-3.5 w-3.5", isActive ? "text-cyan" : "text-white/35")} />
                          {item.name}
                        </>
                      )}
                    </NavLink>
                  );
                })}
              </nav>
            </div>
          </div>
          <div className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8">
            <Outlet context={{ setSidebarOpen }} />
          </div>
        </main>
      </div>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
    </div>
  );
}
