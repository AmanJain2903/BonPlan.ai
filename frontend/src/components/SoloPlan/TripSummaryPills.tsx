import { useState, type ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MapPin, CalendarDays, Route, DollarSign } from 'lucide-react';
import { SPRING_PILL, EASE_OUT_EXPO, safelyParseJSON, formatDate } from './constants';
import { Plan } from '../../apis/plan';

interface TripSummaryPillsProps {
  plan: Plan;
  tripCostEstimate?: number;
  actualCost?: number;
  isGenerating: boolean;
  dynamicTitle?: string;
  dynamicJourney?: string[];
  leftControl?: ReactNode;
  shareControl?: ReactNode;
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
  index,
  hoveredPill,
  onHover,
  onLeave,
}: {
  id: string;
  icon: typeof MapPin;
  label: string;
  index: number;
  hoveredPill: string | null;
  onHover: () => void;
  onLeave: () => void;
}) {
  const isActive = hoveredPill === id;
  const isFaded = hoveredPill !== null && !isActive;
  const activeWidth = `calc(${label.length}ch + 4rem)`;

  return (
    <motion.div
      initial={{ opacity: 0, y: -8, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ ...SPRING_PILL, delay: 0.1 + index * 0.08 }}
      onMouseEnter={onHover}
      onMouseLeave={onLeave}
      style={{
        width: isActive ? activeWidth : undefined,
      }}
      className={`flex h-9 sm:h-11 min-w-0 flex-none items-center gap-2 sm:gap-2.5 bg-black/60 border border-white/10 rounded-full px-3 sm:px-4 lg:px-5 py-2 sm:py-2.5 backdrop-blur-md shadow-xl overflow-hidden cursor-default transition-[filter,opacity,width,border-color,box-shadow] duration-300 ${isActive ? 'z-20 shadow-[0_0_20px_rgba(102,252,241,0.15)] border-cyan/30' : 'w-28 sm:w-40 lg:w-48 xl:w-52 z-10'} ${isFaded ? 'blur-sm opacity-40' : 'opacity-100'}`}
    >
      <Icon className="text-cyan w-4 h-4 shrink-0" />
      <AnimatePresence mode="wait">
        <motion.span
          key={label}
          initial={{ opacity: 0, y: 0 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4, transition: { duration: 0.3  } }}
          transition={{ duration: 0.2 }}
          className="text-xs sm:text-sm font-semibold text-white/90 truncate whitespace-nowrap"
        >
          {label}
        </motion.span>
      </AnimatePresence>
    </motion.div>
  );
}

const PILLS_CONFIG = [
  { id: 'title', icon: MapPin, dataKey: 'tripTitle' as const },
  { id: 'route', icon: Route, dataKey: 'journeyFlow' as const },
  { id: 'dates', icon: CalendarDays, dataKey: 'datesLabel' as const },
];

export default function TripSummaryPills({ plan, tripCostEstimate, actualCost, isGenerating, dynamicTitle, dynamicJourney, leftControl, shareControl }: TripSummaryPillsProps) {
  const [hoveredPill, setHoveredPill] = useState<string | null>(null);
  const data = useTripDisplayData(plan, dynamicTitle, dynamicJourney);

  return (
    <AnimatePresence>
      {plan && (
        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20, height: 0, marginBottom: 0, transition: { duration: 0.3  } }}
          transition={{ duration: 0.4, ease: EASE_OUT_EXPO }}
          className="w-full shrink-0 relative mb-2 sm:mb-6 lg:mb-8"
        >
          {/* Mobile: two-row — controls on top, pills below */}
          {(leftControl || shareControl) && (
            <div className="flex sm:hidden items-center justify-between px-2 mb-2">
              <div>{leftControl}</div>
              <div>{shareControl}</div>
            </div>
          )}

          {/* Pills row */}
          <div className="scrollbar-hide flex min-h-11 w-full flex-nowrap items-center justify-start gap-2 sm:gap-3 overflow-x-auto overflow-y-visible px-3 sm:justify-center sm:px-14 lg:gap-4 lg:px-20">
            {PILLS_CONFIG.map(({ id, icon, dataKey }, i) => (
              <Pill
                key={id}
                id={id}
                icon={icon}
                label={data[dataKey]}
                index={i}
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
                  !isGenerating && actualCost !== undefined
                    ? `Estimated Cost: $${actualCost.toFixed(2)}`
                    : `Estimated Cost: $${tripCostEstimate.toFixed(2)}`
                }
                index={PILLS_CONFIG.length}
                hoveredPill={hoveredPill}
                onHover={() => setHoveredPill('cost')}
                onLeave={() => setHoveredPill(null)}
              />
            )}
          </div>

          {/* Desktop: absolute-positioned controls */}
          {leftControl && (
            <div className="hidden sm:block absolute left-0 top-0 z-[70]">
              {leftControl}
            </div>
          )}
          {shareControl && (
            <div className="hidden sm:block absolute right-0 top-0 z-[70]">
              {shareControl}
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
