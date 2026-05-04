import { Info, User, Users } from 'lucide-react';
import type { PlanningStyle } from '../../../context/TripContext';
import { PLAN_STEPS } from '../Plan';

type Props = {
  hoveredTip: string | null;
  planningStyle: PlanningStyle | null;
  onTipChange: (id: string | null) => void;
  onSelect: (value: PlanningStyle) => void;
};

// --- 1. Extract the unique animated visuals into clean sub-components ---
const SoloVisual = () => (
  <div className="absolute inset-0 flex items-center justify-center gap-5 px-6">
    <div className="relative">
      <div className="h-14 w-14 rounded-full bg-cyan/15 flex items-center justify-center">
        <User size={24} className="text-cyan/80" />
      </div>
      <div className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-cyan/50 animate-[pulse_2s_ease-in-out_infinite]" />
    </div>
    <div className="flex-1 space-y-2.5">
      <div className="flex gap-2">
        <div className="h-3 flex-1 rounded-full bg-cyan/12 animate-[pulse_2.5s_ease-in-out_infinite]" />
        <div className="h-3 w-16 rounded-full bg-cyan/8 animate-[pulse_2.5s_ease-in-out_0.3s_infinite]" />
      </div>
      <div className="flex gap-2">
        <div className="h-3 w-20 rounded-full bg-cyan/8 animate-[pulse_2.5s_ease-in-out_0.6s_infinite]" />
        <div className="h-3 flex-1 rounded-full bg-cyan/12 animate-[pulse_2.5s_ease-in-out_0.9s_infinite]" />
      </div>
      <div className="flex gap-2">
        <div className="h-3 flex-1 rounded-full bg-cyan/10 animate-[pulse_2.5s_ease-in-out_1.2s_infinite]" />
        <div className="h-3 w-12 rounded-full bg-cyan/6 animate-[pulse_2.5s_ease-in-out_1.5s_infinite]" />
      </div>
    </div>
  </div>
);

const SquadVisual = () => (
  <div className="absolute inset-0 flex items-center px-4 sm:px-6 gap-2 sm:gap-3">
    <div className="flex -space-x-2 sm:-space-x-3 shrink-0">
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          className="h-9 w-9 sm:h-12 sm:w-12 rounded-full bg-cyan/15 border-2 border-carbon/60 flex items-center justify-center"
          style={{ animation: `fade-in 400ms ease-out ${i * 120}ms both`, zIndex: 4 - i }}
        >
          <User size={14} className="text-cyan/70 sm:hidden" />
          <User size={18} className="text-cyan/70 hidden sm:block" />
        </div>
      ))}
    </div>
    <div className="flex-1 flex flex-col items-center gap-1.5 min-w-0">
      <div className="flex gap-1">
        {[0, 1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-1.5 w-1.5 sm:h-2 sm:w-2 rounded-full bg-cyan/30"
            style={{ animation: `pulse 1.5s ease-in-out ${i * 0.2}s infinite` }}
          />
        ))}
      </div>
      <div className="h-2.5 sm:h-3 w-16 sm:w-24 rounded-full bg-cyan/10 animate-[pulse_2s_ease-in-out_infinite]" />
    </div>
  </div>
);

// --- 2. Map the Tailwind styles and icons to the Option IDs ---
// (We must spell out full Tailwind classes so the compiler doesn't purge them)
const THEME_MAP: Record<string, any> = {
  solo: {
    borderColorHover: 'hover:border-cyan/30',
    shadowHover: 'hover:shadow-[0_0_60px_rgba(102,252,241,0.08)]',
    radialGradient: 'radial-gradient(circle at 30% 30%, rgba(102,252,241,0.20), rgba(102,252,241,0) 58%)',
    linearGradient: 'linear-gradient(90deg, rgba(102,252,241,0), rgba(102,252,241,0.10), rgba(102,252,241,0))',
    iconBg: 'bg-cyan/10',
    iconColor: 'text-cyan',
    titleHover: 'group-hover:text-cyan',
    Icon: User,
    Visual: SoloVisual,
  },
  squad: {
    borderColorHover: 'hover:border-cyan/30',
    shadowHover: 'hover:shadow-[0_0_60px_rgba(102,252,241,0.08)]',
    radialGradient: 'radial-gradient(circle at 70% 30%, rgba(102,252,241,0.20), rgba(102,252,241,0) 58%)',
    linearGradient: 'linear-gradient(90deg, rgba(102,252,241,0), rgba(102,252,241,0.10), rgba(102,252,241,0))',
    iconBg: 'bg-cyan/10',
    iconColor: 'text-cyan',
    titleHover: 'group-hover:text-cyan',
    Icon: Users,
    Visual: SquadVisual,
  },
};

export function Step1PlanningStyle({ hoveredTip, onTipChange, onSelect }: Props) {
  // Grab the options from the config once
  const stepData = PLAN_STEPS.find((step) => step.id === 'planning-style');
  const options = stepData?.options || [];

  return (
    <div className="animate-[fade-in_500ms_ease-out]">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-5xl w-full">

        {/* 3. Map over the options instead of hardcoding buttons */}
        {options.map((option) => {
          const theme = THEME_MAP[option.id];
          if (!theme) return null;

          const IconComponent = theme.Icon;
          const AnimatedVisual = theme.Visual;

          return (
            <button
              key={option.id}
              onClick={() => onSelect(option.id as PlanningStyle)}
              className={`group relative rounded-2xl border border-white/[0.08] bg-carbon/40 backdrop-blur-sm p-6 sm:p-10 text-left transition-all duration-300 hover:bg-carbon/60 cursor-pointer overflow-hidden ${theme.borderColorHover} ${theme.shadowHover}`}
            >
              {/* Background Glows */}
              <div className="pointer-events-none absolute -inset-24 opacity-0 group-hover:opacity-100 transition-opacity duration-300 blur-3xl">
                <div
                  className="absolute inset-0"
                  style={{ background: theme.radialGradient }}
                />
              </div>
              <div
                className="pointer-events-none absolute -left-1/2 top-0 h-full w-[70%] rotate-12 opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                style={{
                  background: theme.linearGradient,
                  animation: 'orbit 7s linear infinite',
                }}
              />

              {/* Header section */}
              <div className="flex items-center gap-3 mb-2">
                <div className={`h-9 w-9 rounded-xl flex items-center justify-center ${theme.iconBg}`}>
                  <IconComponent size={18} className={theme.iconColor} />
                </div>
                <h2 className={`text-2xl font-bold text-white transition-colors duration-300 ${theme.titleHover}`}>
                  {option.title}
                </h2>

                {/* Tooltip */}
                <div
                  className="relative"
                  onMouseEnter={(e) => {
                    e.stopPropagation();
                    onTipChange(option.id);
                  }}
                  onMouseLeave={() => onTipChange(null)}
                >
                  <Info size={15} className="text-white/25 hover:text-white/50 transition-colors cursor-help" />
                  {hoveredTip === option.id && (
                    <div className="absolute left-0 mb-2 w-60 rounded-lg border border-white/10 bg-midnight p-3 text-[11px] text-white/50 leading-relaxed shadow-xl z-10">
                      {option.helpText}
                    </div>
                  )}
                </div>
              </div>

              {/* Description */}
              <p className="text-sm text-white/40 mb-8 leading-relaxed">
                {option.description}
              </p>

              {/* Animated visual wrapper */}
              <div className="relative h-28 rounded-xl bg-white/[0.02] border border-white/[0.04] overflow-hidden">
                <AnimatedVisual />
              </div>
            </button>
          );
        })}

      </div>
    </div>
  );
}