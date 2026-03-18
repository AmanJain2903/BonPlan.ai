import { MapPin, Route, User, Users } from 'lucide-react';
import type { PlanningStyle } from '../../../context/TripContext';
import { COMMON_PLAN_STEPS } from '../Plan';

type Props = {
  planningStyle: PlanningStyle | null;
  onSelect: (routing: 'single-hub' | 'multi-hop') => void;
};

// --- 1. Generate dynamic theme colors based on Step 1's choice ---
const getTheme = (isSolo: boolean) => {
  const baseRgb = isSolo ? '102,252,241' : '168,85,247'; // Cyan vs Purple-400

  return {
    borderColor: isSolo ? 'border-cyan/20' : 'border-purple-400/20',
    iconBg: isSolo ? 'bg-cyan/10' : 'bg-purple-400/10',
    textColor: isSolo ? 'text-cyan' : 'text-purple-400',
    shadowColor: isSolo ? 'shadow-[0_0_60px_rgba(102,252,241,0.06)]' : 'shadow-[0_0_60px_rgba(168,85,247,0.06)]',
    hoverShadowBtn: isSolo ? 'hover:shadow-[0_0_28px_rgba(102,252,241,0.06)]' : 'hover:shadow-[0_0_28px_rgba(168,85,247,0.06)]',
    boxGradient: `linear-gradient(135deg, rgba(${baseRgb},0.10), rgba(31,40,51,0.18))`,
    sweepGradient: `linear-gradient(90deg, rgba(${baseRgb},0), rgba(${baseRgb},0.10), rgba(${baseRgb},0))`,
    glowColorStrong: `rgba(${baseRgb},0.55)`,
    glowBoxShadow: `0 0 18px rgba(${baseRgb},0.35)`,
    getRadialGradient: (pos: string) => `radial-gradient(circle at ${pos}, rgba(${baseRgb},0.18), rgba(${baseRgb},0) 55%)`,
    HeaderIcon: isSolo ? User : Users,
  };
};

type ThemeConfig = ReturnType<typeof getTheme>;

// --- 2. Extract the unique animated visuals ---
const SingleHubVisual = ({ theme }: { theme: ThemeConfig }) => (
  <>
    {/* Sweep Gradient (Only appears on Single Hub) */}
    <div
      className="pointer-events-none absolute -left-1/2 top-0 h-full w-[60%] rotate-12 opacity-0 group-hover:opacity-100 transition-opacity duration-300"
      style={{ background: theme.sweepGradient }}
    />
    <div className="relative">
      <MapPin size={28} className="text-white/30 group-hover:text-white/50 transition-colors duration-300" />
      <div
        className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-10 h-10 rounded-full border border-white/10 group-hover:border-white/20 transition-colors duration-300"
        style={{ animation: 'pulse 3s ease-in-out infinite' }}
      />
      <div
        className="absolute -bottom-3 left-1/2 -translate-x-1/2 w-16 h-16 rounded-full border border-white/5 group-hover:border-white/10 transition-colors duration-300"
        style={{ animation: 'pulse 3s ease-in-out 0.5s infinite' }}
      />
    </div>
  </>
);

const MultiHopVisual = ({ theme }: { theme: ThemeConfig }) => (
  <>
    <div className="absolute inset-0">
      <div
        className="absolute left-1/2 top-1/2 h-2 w-2 rounded-full"
        style={{
          backgroundColor: theme.glowColorStrong,
          transform: 'translate(-50%, -50%)',
          boxShadow: theme.glowBoxShadow,
        }}
      />
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="absolute left-1/2 top-1/2 h-2.5 w-2.5 rounded-full bg-white/10"
          style={{
            transform: 'translate(-50%, -50%)',
            animation: `orbit ${3.6 + i * 0.9}s linear ${i * 0.35}s infinite`,
            filter: 'blur(0.1px)',
          }}
        />
      ))}
    </div>
    <div className="relative flex items-center gap-2">
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex items-center gap-2">
          <div
            className="h-4 w-4 rounded-full bg-white/15 group-hover:bg-white/25 transition-colors duration-300"
            style={{ animation: `pulse 2s ease-in-out ${i * 0.4}s infinite` }}
          />
          {i < 2 && <div className="h-0.5 w-6 bg-white/10 group-hover:bg-white/15 transition-colors duration-300" />}
        </div>
      ))}
    </div>
    <Route size={20} className="absolute bottom-2 right-3 text-white/10 group-hover:text-white/20 transition-colors duration-300" />
  </>
);

// --- 3. Map the options to their specific visual configurations ---
const ROUTE_CONFIG: Record<string, { radialPosition: string; Visual: React.FC<{ theme: ThemeConfig }> }> = {
  'single-hub': { radialPosition: '30% 30%', Visual: SingleHubVisual },
  'multi-hop': { radialPosition: '70% 30%', Visual: MultiHopVisual },
};

export function Step2RoutingStyle({ planningStyle, onSelect }: Props) {
  const isSolo = planningStyle === 'solo';
  const theme = getTheme(isSolo);

  // Fetch contextual texts exactly once
  const planStep = COMMON_PLAN_STEPS.find((step) => step.id === 'planning-style');
  const selectedPlanText = planStep?.options?.find((opt) => opt.id === planningStyle);
  
  const routeStep = COMMON_PLAN_STEPS.find((step) => step.id === 'routing-style');
  const routeOptions = routeStep?.options || [];

  return (
    <div
      className="w-full max-w-[calc(50%_-_1rem)] min-w-[360px] max-w-lg:max-w-full animate-[scale-in_350ms_ease-out]"
      style={{ maxWidth: 'min(calc(50% - 1rem), 600px)', minWidth: '340px' }}
    >
      <div className={`relative rounded-2xl border backdrop-blur-sm p-10 bg-carbon/50 ${theme.borderColor} ${theme.shadowColor}`}>
        
        {/* Panel Badge & Context Description */}
        <div className="flex items-center gap-3 mb-2">
          <div className={`h-10 w-10 rounded-xl flex items-center justify-center ${theme.iconBg}`}>
            <theme.HeaderIcon size={20} className={theme.textColor} />
          </div>
          <h2 className={`text-lg font-bold ${theme.textColor}`}>
            {selectedPlanText?.title}
          </h2>
        </div>
        <p className="text-sm text-white/40 mb-8 leading-relaxed">
          {selectedPlanText?.description}
        </p>

        {/* Trip type options mapped dynamically */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {routeOptions.map((option) => {
            const config = ROUTE_CONFIG[option.id];
            if (!config) return null;

            const AnimatedVisual = config.Visual;

            return (
              <button
                key={option.id}
                onClick={() => onSelect(option.id as 'single-hub' | 'multi-hop')}
                className={`group relative rounded-2xl border p-6 text-left transition-all duration-300 cursor-pointer overflow-hidden border-white/[0.08] bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.05] ${theme.hoverShadowBtn}`}
              >
                {/* Background Radial Glow (Position maps to 30% or 70%) */}
                <div
                  className="pointer-events-none absolute -inset-20 opacity-0 group-hover:opacity-100 transition-opacity duration-300 blur-2xl"
                  style={{ background: theme.getRadialGradient(config.radialPosition) }}
                />

                {/* Animated Visual Box */}
                <div
                  className="relative h-20 mb-5 rounded-xl border overflow-hidden flex items-center justify-center border-white/[0.06]"
                  style={{ background: theme.boxGradient }}
                >
                  <AnimatedVisual theme={theme} />
                </div>

                {/* Texts */}
                <div className="flex items-center gap-2 mb-2">
                  <h3 className="text-base font-bold text-white transition-colors duration-300">
                    {option.title}
                  </h3>
                </div>
                <p className="text-xs text-white/30 leading-relaxed">
                  {option.description}
                </p>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}