import { ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import RoutingVisual from './RoutingVisual';
import { useAuth } from '../../context/AuthContext';

export default function Hero() {
  const { isLoggedIn, user } = useAuth();
  const navigate = useNavigate();
  const firstName = user?.firstName;

  return (
    <section id="top" className="relative min-h-screen flex flex-col items-center justify-center px-6 lg:px-12 xl:px-20 pt-24 pb-16 overflow-hidden">
      {/* Ambient glow */}
      <div className="pointer-events-none absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[600px] rounded-full bg-cyan/[0.04] blur-[140px]" />

      {/* Headline */}
      <h1 className="relative text-center text-4xl sm:text-5xl lg:text-6xl xl:text-7xl font-extrabold leading-[1.08] tracking-tight text-white">
        Tell us When.{' '}
        <span className="bg-gradient-to-r from-cyan to-cyan-dim bg-clip-text text-transparent">
          We Tell the How.
        </span>
      </h1>

      {/* Subheadline */}
      <p className="relative mt-6 max-w-3xl text-center text-base sm:text-lg lg:text-xl leading-relaxed text-slate/80">
        An AI travel agent built entirely on <span className="text-cyan font-medium">constraint-based planning</span>.
        We route your trip around your non-negotiables.
      </p>

      {/* Welcome + CTA */}
      {isLoggedIn && firstName && (
        <p className="relative mt-10 mb-0 text-xl sm:text-2xl font-medium text-white/90 animate-[fade-in_500ms_ease-out]">
          Welcome, <span className="text-cyan font-semibold">{firstName}</span>
        </p>
      )}
      <button
        onClick={() => navigate(isLoggedIn ? '/draft-plan' : '/register')}
        className={`relative group ${isLoggedIn && firstName ? 'mt-4' : 'mt-10'} inline-flex items-center gap-2.5 bg-cyan text-midnight font-bold text-lg tracking-wide rounded-xl px-8 py-3.5 hover:shadow-[0_0_30px_rgba(102,252,241,0.4)] transition-all duration-300 cursor-pointer`}
      >
        BUILD A BON PLAN
        <ArrowRight size={16} className="transition-transform duration-200 group-hover:translate-x-0.5" />
      </button>

      {/* Visual */}
      <div className="relative mt-16 w-full max-w-5xl xl:max-w-6xl">
        <RoutingVisual />
      </div>

      {/* Scroll pill */}
      <a
        href="#features"
        className="mt-12 inline-flex items-center gap-2 rounded-full border border-cyan/25 bg-cyan/[0.06] px-5 py-2 text-xs text-cyan/70 shadow-[0_0_15px_rgba(102,252,241,0.12)] hover:text-cyan hover:border-cyan/40 hover:shadow-[0_0_25px_rgba(102,252,241,0.25)] transition-all duration-300 animate-[pill-pulse_2s_ease-in-out_infinite]"
      >
        <span>Explore Features</span>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="animate-bounce">
          <path d="M6 2v8M3 7l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </a>
    </section>
  );
}
