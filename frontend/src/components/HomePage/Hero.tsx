import { ArrowRight, ChevronLeft, ChevronRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import RoutingVisual from './RoutingVisual';
import { useAuth } from '../../context/AuthContext';
import { Plan } from '../../apis/plan';
import { useDraftPlans } from '../../hooks/useTripFilters';

interface HeroProps {
  plans?: Plan[];
  isLoadingPlans?: boolean;
}

export default function Hero({ plans = [], isLoadingPlans = false }: HeroProps) {
  const { isLoggedIn, user } = useAuth();
  const navigate = useNavigate();
  const firstName = user?.firstName;

  const draftPlans = useDraftPlans(plans);

  // Setup dynamic pills based on drafted plans
  const pills = [];
  if (draftPlans && draftPlans.length > 0) {
    pills.push({ label: 'Draft Plans', href: '#draft-plans' });
  }
  pills.push({ label: 'Explore Features', href: '#features' });

  const [activePillIndex, setActivePillIndex] = useState(0);

  // Auto-slide mobile pills carousel
  useEffect(() => {
    if (pills.length <= 1) return;
    const interval = setInterval(() => {
      setActivePillIndex((current) => (current + 1) % pills.length);
    }, 4000);
    return () => clearInterval(interval);
  }, [pills.length]);

  return (
    <section id="top" className="relative min-h-screen flex flex-col items-center justify-center px-6 lg:px-12 xl:px-20 pt-24 pb-24 sm:pb-32 overflow-hidden">
      {/* Ambient glow */}
      <div className="pointer-events-none absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[600px] rounded-full bg-cyan/[0.04] blur-[140px]" />

      {/* Headline */}
      <motion.h1
        initial={{ opacity: 0, y: 30, filter: 'blur(8px)' }}
        animate={{ opacity: 1, y: 0, filter: 'blur(0px)', willChange: 'transform, opacity, filter' }}
        transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
        className="relative text-center text-4xl sm:text-5xl lg:text-6xl xl:text-7xl font-extrabold leading-[1.08] tracking-tight text-white"
      >
        Tell us When.{' '}
        <span className="bg-gradient-to-r from-cyan to-cyan-dim bg-clip-text text-transparent">
          We Tell the How.
        </span>
      </motion.h1>

      {/* Subheadline */}
      <motion.p
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0, willChange: 'transform, opacity' }}
        transition={{ delay: 0.15, duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
        className="relative mt-6 max-w-3xl text-center text-base sm:text-lg lg:text-xl leading-relaxed text-slate/80"
      >
        An AI travel agent built entirely on <span className="text-cyan font-medium">constraint-based planning</span>.
        We route your trip around your non-negotiables.
      </motion.p>

      {/* Welcome + CTA */}
      {isLoggedIn && firstName && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1, willChange: 'opacity' }}
          transition={{ delay: 0.3, duration: 0.8 }}
          className="relative mt-10 mb-0 text-xl sm:text-2xl font-medium text-white/90"
        >
          Welcome, <span className="text-cyan font-semibold">{firstName}</span>
        </motion.p>
      )}
      <motion.button
        initial={{ opacity: 0, scale: 0.8, clipPath: 'inset(10% 30% 10% 30% round 16px)', filter: 'blur(8px)', willChange: 'transform, opacity, filter, clip-path' }}
        whileInView={{ opacity: 1, scale: 1, clipPath: 'inset(0% 0% 0% 0% round 16px)', filter: 'blur(0px)' }}
        whileHover={{ scale: 1.03, boxShadow: '0 0 40px rgba(102,252,241,0.6)' }}
        whileTap={{ scale: 0.97 }}
        viewport={{ once: true, margin: "-50px" }}
        transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
        onClick={() => navigate(isLoggedIn ? '/draft-plan' : '/register')}
        className={`relative group ${isLoggedIn && firstName ? 'mt-4' : 'mt-10'} inline-flex items-center gap-2.5 bg-cyan text-midnight font-bold text-lg tracking-wide rounded-xl px-8 py-3.5 hover:shadow-[0_0_30px_rgba(102,252,241,0.4)] transition-[box-shadow,background-color] duration-300 cursor-pointer`}
      >
        BUILD A BON PLAN
        <ArrowRight size={16} className="transition-transform duration-300 group-hover:translate-x-1.5 group-hover:scale-110" />
      </motion.button>

      {/* Visual */}
      <div className="relative mt-16 w-full max-w-5xl xl:max-w-6xl">
        <RoutingVisual />
      </div>

      {/* Dynamic Scroll Pills */}
      <div className="mt-12 flex flex-col items-center min-h-[50px]">
        {/* We only animate/render pills when we know how many there are! */}
        {!isLoadingPlans && (
          <motion.div
            initial={{ opacity: 0, y: 20, filter: 'blur(4px)', willChange: 'transform, opacity, filter' }}
            animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
            className="w-full flex flex-col items-center justify-center"
          >
            {/* Desktop View */}
            <div className="hidden sm:flex items-center justify-center gap-6">
              {pills.map((pill) => (
                <a
                  key={pill.label}
                  href={pill.href}
                  className="inline-flex justify-center w-[180px] items-center gap-2 rounded-full border border-cyan/25 bg-cyan/[0.06] px-5 py-2 text-xs text-cyan/70 shadow-[0_0_15px_rgba(102,252,241,0.12)] hover:text-cyan hover:border-cyan/40 hover:shadow-[0_0_25px_rgba(102,252,241,0.25)] transition-all duration-300 animate-[pill-pulse_2s_ease-in-out_infinite]"
                >
                  <span>{pill.label}</span>
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="animate-bounce">
                    <path d="M6 2v8M3 7l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </a>
              ))}
            </div>

            {/* Mobile Carousel View */}
            <div className="flex sm:hidden items-center justify-center gap-3 relative w-full px-4">
              {pills.length > 1 && (
                <button
                  onClick={() => setActivePillIndex((current) => (current - 1 + pills.length) % pills.length)}
                  className="p-2 text-cyan/50 hover:text-cyan hover:bg-cyan/[0.05] rounded-full transition-colors flex-shrink-0"
                >
                  <ChevronLeft size={18} />
                </button>
              )}

              <div className="flex-1 flex justify-center overflow-hidden pr-4 pl-4 pb-2 pt-2">
                <a
                  key={pills[activePillIndex % pills.length].label}
                  href={pills[activePillIndex % pills.length].href}
                  className="inline-flex items-center justify-center gap-2 w-[180px] rounded-full border border-cyan/25 bg-cyan/[0.06] px-5 py-2 text-xs text-cyan/70 shadow-[0_0_15px_rgba(102,252,241,0.12)] hover:text-cyan hover:border-cyan/40 hover:shadow-[0_0_25px_rgba(102,252,241,0.25)] transition-all duration-300 animate-[pill-pulse_2s_ease-in-out_infinite]"
                >
                  <span className="truncate">{pills[activePillIndex % pills.length].label}</span>
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="animate-bounce shrink-0">
                    <path d="M6 2v8M3 7l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </a>
              </div>

              {pills.length > 1 && (
                <button
                  onClick={() => setActivePillIndex((current) => (current + 1) % pills.length)}
                  className="p-2 text-cyan/50 hover:text-cyan hover:bg-cyan/[0.05] rounded-full transition-colors flex-shrink-0"
                >
                  <ChevronRight size={18} />
                </button>
              )}
            </div>
          </motion.div>
        )}
      </div>
    </section>
  );
}
