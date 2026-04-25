import { NavLink, Outlet } from 'react-router-dom';
import { LayoutDashboard, Shield, Activity, Menu, Bell, Settings } from 'lucide-react';
import { useState } from 'react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import WorldMapBackground from '../components/shared/WorldMapBackground';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export default function DashboardLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const navItems = [
    { name: 'SKU Management', href: '/rate-limits/skus', icon: Shield },
    { name: 'Usage Viewer', href: '/rate-limits/usage', icon: Activity },
  ];

  return (
    <div className="flex h-screen bg-[#FDFDFC] dark:bg-[#0B0C10] text-[#111111] dark:text-[#EEEEEE] overflow-hidden">
      <div className="absolute inset-0 z-0 pointer-events-none">
        <WorldMapBackground />
      </div>

      {/* Sidebar */}
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 border-r border-[#EAEAEA] dark:border-[#333333] bg-[#FFFFFF] dark:bg-[#0B0C10]/80 backdrop-blur-md transition-transform duration-300 ease-in-out md:static md:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-16 items-center px-6 border-b border-[#EAEAEA] dark:border-[#333333]">
          <LayoutDashboard className="h-6 w-6 text-blue-600 dark:text-blue-500" />
          <span className="ml-3 text-lg font-bold tracking-tight">BonPlan Admin</span>
        </div>

        <div className="px-4 py-6">
          <div className="text-xs font-semibold text-[#888888] uppercase tracking-wider mb-4 px-2">
            Rate Limiting
          </div>
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.name}
                  to={item.href}
                  onClick={() => setSidebarOpen(false)}
                  className={({ isActive }) =>
                    cn(
                      "group flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-all duration-200",
                      isActive
                        ? "bg-[#F5F5F5] dark:bg-[#1A1A1A] text-blue-600 dark:text-blue-500"
                        : "text-[#666666] dark:text-[#A0A0A0] hover:bg-[#FAFAFA] dark:hover:bg-[#111111] hover:text-[#111111] dark:hover:text-[#EEEEEE]"
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      <Icon
                        className={cn(
                          "mr-3 flex-shrink-0 h-5 w-5 transition-colors",
                          isActive
                            ? "text-blue-600 dark:text-blue-500"
                            : "text-[#888888] group-hover:text-[#666666] dark:text-[#666666] dark:group-hover:text-[#A0A0A0]"
                        )}
                        aria-hidden="true"
                      />
                      {item.name}
                    </>
                  )}
                </NavLink>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden relative z-10">
        {/* Header */}
        <header className="h-16 flex items-center justify-between px-4 sm:px-6 lg:px-8 border-b border-[#EAEAEA] dark:border-[#333333] bg-[#FFFFFF] dark:bg-[#0B0C10]/80 backdrop-blur-md z-40">
          <button
            type="button"
            className="md:hidden p-2 text-[#888888] hover:text-[#111111] dark:hover:text-[#EEEEEE] transition-colors"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            <Menu className="h-6 w-6" aria-hidden="true" />
          </button>

          <div className="flex-1 flex justify-end items-center gap-4">
            <button className="p-2 text-[#888888] hover:text-[#111111] dark:hover:text-[#EEEEEE] transition-colors rounded-full hover:bg-[#F5F5F5] dark:hover:bg-[#1A1A1A]">
              <Bell className="h-5 w-5" />
            </button>
            <button className="p-2 text-[#888888] hover:text-[#111111] dark:hover:text-[#EEEEEE] transition-colors rounded-full hover:bg-[#F5F5F5] dark:hover:bg-[#1A1A1A]">
              <Settings className="h-5 w-5" />
            </button>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8">
            <Outlet />
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
