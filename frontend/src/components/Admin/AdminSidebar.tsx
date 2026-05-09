import { NavLink } from 'react-router-dom';
import { LayoutDashboard, ArrowLeft } from 'lucide-react';
import { cn } from '../../utils/tailwind';
import { adminSections } from './adminNav';

interface AdminSidebarProps {
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
}

export default function AdminSidebar({ sidebarOpen, setSidebarOpen }: AdminSidebarProps) {
  return (
    <div
      className={cn(
        "fixed inset-y-0 left-0 z-50 w-64 border-r border-white/10 bg-midnight/70 backdrop-blur-xl transition-transform duration-300 ease-in-out md:static md:translate-x-0 flex flex-col",
        sidebarOpen ? "translate-x-0" : "-translate-x-full"
      )}
    >
      <div className="flex h-16 items-center px-6 border-b border-white/10 shrink-0">
        <LayoutDashboard className="h-6 w-6 text-cyan" />
        <span className="ml-3 text-lg font-bold tracking-tight text-white">BonPlan Admin</span>
      </div>

      <div className="px-4 py-6 flex-1 overflow-y-auto space-y-6">
        {adminSections.map((section) => (
          <div key={section.label}>
            <div className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-3 px-2">
              {section.label}
            </div>
            <nav className="space-y-1">
              {section.items.map((item) => {
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
                          ? "bg-white/[0.06] text-cyan"
                          : "text-white/70 hover:bg-white/[0.06] hover:text-white"
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <Icon
                          className={cn(
                            "mr-3 flex-shrink-0 h-5 w-5 transition-colors",
                            isActive
                              ? "text-cyan"
                              : "text-white/40 group-hover:text-white/70"
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
        ))}
      </div>
      
      <div className="p-4 border-t border-white/10 shrink-0">
        <NavLink
          to="/"
          className="group flex items-center px-3 py-2.5 text-sm font-medium rounded-lg text-white/70 hover:bg-white/[0.06] hover:text-white transition-all duration-200"
        >
          <ArrowLeft className="mr-3 flex-shrink-0 h-5 w-5 text-white/40 group-hover:text-white/70 transition-colors" />
          Back to App
        </NavLink>
      </div>
    </div>
  );
}
