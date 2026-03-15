import { useState } from 'react';
import { Menu, X } from 'lucide-react';

export default function Navbar() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-midnight/80 backdrop-blur-xl border-b border-white/5">
      <div className="w-full flex items-center justify-between px-6 lg:px-12 xl:px-20 py-4">
        {/* Logo */}
        <a href="#top" className="flex items-center gap-1.5 text-xl font-bold tracking-tight text-white select-none">
          <img src="/logo.png" alt="BonPlan.ai" className="h-9 w-9 object-contain" />
          <span>BonPlan<span className="text-cyan">.</span>ai</span>
        </a>

        {/* Desktop links */}
        <div className="hidden md:flex items-center gap-6">
          <button className="text-sm text-white border border-white/20 rounded-lg px-5 py-2 hover:border-white/40 transition-colors duration-200 cursor-pointer">
            Login
          </button>
          <button className="text-sm font-semibold bg-cyan text-midnight rounded-lg px-5 py-2 hover:shadow-[0_0_20px_rgba(102,252,241,0.35)] transition-all duration-200 cursor-pointer">
            Sign Up
          </button>
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden text-white cursor-pointer"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Toggle menu"
        >
          {mobileOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="md:hidden border-t border-white/5 bg-midnight/95 backdrop-blur-xl px-6 pb-6 pt-4 flex flex-col gap-4">
          <button className="text-sm text-white border border-white/20 rounded-lg px-5 py-2.5 hover:border-white/40 transition-colors cursor-pointer">
            Login
          </button>
          <button className="text-sm font-semibold bg-cyan text-midnight rounded-lg px-5 py-2.5 hover:shadow-[0_0_20px_rgba(102,252,241,0.35)] transition-all cursor-pointer">
            Sign Up
          </button>
        </div>
      )}
    </nav>
  );
}
