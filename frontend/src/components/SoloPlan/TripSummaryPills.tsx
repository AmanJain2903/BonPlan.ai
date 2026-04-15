import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MapPin, CalendarDays, Route, DollarSign } from 'lucide-react';
import { SPRING_PILL, EASE_OUT_EXPO, safelyParseJSON, formatDate } from './constants';
import { Plan } from '../../apis/plan';

interface TripSummaryPillsProps {
  plan: Plan;
  tripCostEstimate?: number;
  actualCost?: number;
  planStatus: string;
  dynamicTitle?: string;
  dynamicJourney?: string[];
}

/** Derives trip display data from a Plan object */
function useTripDisplayData(plan: Plan, dynamicTitle?: string, dynamicJourney?: string[]) {
  const originData = safelyParseJSON(plan.origin);
  const originCity = originData?.city || 'Origin';

  let destinationsArray: any[] = [];
  if (Array.isArray(plan.destinations)) {
    destinationsArray = plan.destinations.map((d: any) => safelyParseJSON(d)).filter(Boolean);
  } else if (typeof plan.destinations === 'string') {
    const parsedArray = safelyParseJSON(plan.destinations);
    if (Array.isArray(parsedArray)) {
      destinationsArray = parsedArray.map((d: any) => safelyParseJSON(d)).filter(Boolean);
    }
  }

  const destCount = destinationsArray.length;
  const firstDestCity = destCount > 0 ? (destinationsArray[0]?.city || 'Destination') : 'Destination';

  const defaultTitle = destCount > 1
    ? `${originCity} to ${firstDestCity} and ${destCount - 1} others`
    : `${originCity} to ${firstDestCity}`;

  const tripTitle = dynamicTitle || defaultTitle;

  const journeyFlow = dynamicJourney && dynamicJourney.length > 0
    ? [originCity, ...dynamicJourney].join(' ➔ ')
    : [originCity, ...destinationsArray.map((d: any) => d.city || 'Dest')].join(' ➔ ');

  const startDate = formatDate(plan.start_date);
  const endDate = formatDate(plan.end_date);
  const datesLabel = startDate && endDate ? `${startDate} - ${endDate}` : 'Dates TBD';

  return { tripTitle, journeyFlow, datesLabel };
}

/** A single hoverable info pill */
function Pill({
  id,
  icon: Icon,
  label,
  hoveredPill,
  onHover,
  onLeave,
}: {
  id: string;
  icon: typeof MapPin;
  label: string;
  hoveredPill: string | null;
  onHover: () => void;
  onLeave: () => void;
}) {
  const isActive = hoveredPill === id;
  const isFaded = hoveredPill !== null && !isActive;

  return (
    <motion.div
      layout
      transition={SPRING_PILL}
      onMouseEnter={onHover}
      onMouseLeave={onLeave}
      className={`flex items-center gap-2.5 bg-black/60 border border-white/10 rounded-full px-5 py-2.5 backdrop-blur-md shadow-xl overflow-hidden cursor-default transition-[filter,opacity] duration-300 ${isActive ? 'max-w-[800px] z-20 shadow-[0_0_20px_rgba(102,252,241,0.15)] border-cyan/30' : 'max-w-[200px] sm:max-w-[250px] z-10'} ${isFaded ? 'blur-sm opacity-40' : 'opacity-100'}`}
    >
      <Icon className="text-cyan w-4 h-4 shrink-0" />
      <span className="text-xs sm:text-sm font-semibold text-white/90 truncate whitespace-nowrap">{label}</span>
    </motion.div>
  );
}

const PILLS_CONFIG = [
  { id: 'title', icon: MapPin, dataKey: 'tripTitle' as const },
  { id: 'route', icon: Route, dataKey: 'journeyFlow' as const },
  { id: 'dates', icon: CalendarDays, dataKey: 'datesLabel' as const },
];

export default function TripSummaryPills({ plan, tripCostEstimate, actualCost, planStatus, dynamicTitle, dynamicJourney }: TripSummaryPillsProps) {
  const [hoveredPill, setHoveredPill] = useState<string | null>(null);
  const data = useTripDisplayData(plan, dynamicTitle, dynamicJourney);

  return (
    <AnimatePresence>
      {plan && (
        <motion.div
          initial={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20, height: 0, marginBottom: 0 }}
          transition={{ duration: 0.4, ease: EASE_OUT_EXPO }}
          className="w-full shrink-0 flex flex-wrap items-center justify-center gap-4 sm:gap-6 lg:gap-8 mb-6 sm:mb-8"
        >
          {PILLS_CONFIG.map(({ id, icon, dataKey }) => (
            <Pill
              key={id}
              id={id}
              icon={icon}
              label={data[dataKey]}
              hoveredPill={hoveredPill}
              onHover={() => setHoveredPill(id)}
              onLeave={() => setHoveredPill(null)}
            />
          ))}
          {tripCostEstimate !== undefined && (
            <Pill
              id="cost"
              icon={DollarSign}
              label={
                planStatus !== 'generating' && actualCost !== undefined
                  ? `Trip Cost: $${actualCost.toFixed(2)}`
                  : `Estimated Cost: $${tripCostEstimate.toFixed(2)}`
              }
              hoveredPill={hoveredPill}
              onHover={() => setHoveredPill('cost')}
              onLeave={() => setHoveredPill(null)}
            />
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
