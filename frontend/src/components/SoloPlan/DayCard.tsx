import { motion } from 'framer-motion';
import { ItineraryDay } from './types';
import { Calendar, DollarSign, Activity, Loader2, CheckCircle2 } from 'lucide-react';
import PlacesPolaroid from './PlacesPolaroid';

export function formatDate(date: string) {
  const year = date.split('-')[0];
  const month = date.split('-')[1];
  const day = date.split('-')[2];
  const monthMap = {
    '01': 'January',
    '02': 'February',
    '03': 'March',
    '04': 'April',
    '05': 'May',
    '06': 'June',
    '07': 'July',
    '08': 'August',
    '09': 'September',
    '10': 'October',
    '11': 'November',
    '12': 'December'
  }
  return `${day}-${monthMap[month as keyof typeof monthMap]}-${year}`;
}

export default function DayCard({ day }: { day: ItineraryDay }) {
  const isDefaultTitle = typeof day.title === 'string' && day.title.trim().toLowerCase() === `day ${day.dayNumber}`;
  const displayTitle = day.title && !isDefaultTitle ? `${day.title}` : `Day ${day.dayNumber}`;

  return (
    <motion.div
      layout
      transition={{ duration: 0.5, ease: 'easeOut' }}
      className={`relative flex flex-col gap-5 p-6 h-full overflow-hidden rounded-3xl backdrop-blur-md transition-all duration-300 ${day.isLoading
        ? 'bg-black/60 border border-cyan/40 shadow-[0_0_30px_rgba(102,252,241,0.15)] glow-cyan'
        : 'bg-black/40 border border-cyan/20 shadow-2xl hover:border-cyan/40'
        }`}
    >
      {/* Animated Loading Pulse Overlay */}
      {day.isLoading && (
        <motion.div
          animate={{ opacity: [0.2, 0.7, 0.2] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          className="absolute inset-0 bg-gradient-to-br from-cyan/20 via-cyan/10 to-cyan/20 blur-sm pointer-events-none z-0"
        />
      )}

      <div className="flex items-start justify-between relative z-10 min-h-[4rem]">
        <div className="flex flex-col flex-1 min-w-0 pr-4">
          <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-white/90 truncate block max-w-full" title={displayTitle}>
            {displayTitle}
          </h3>


          {/* Preserved height placeholder for Date */}
          <div className="h-7 mt-2 flex items-center">
            {day.date ? (
              <div className="flex items-center gap-1.5 text-cyan/70 bg-cyan/10 px-2.5 py-1 rounded-full w-fit">
                <Calendar className="w-3.5 h-3.5 shrink-0" />
                <span className="text-xs font-semibold uppercase tracking-wider">{formatDate(day.date)}</span>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="flex-1 relative z-10">
        <PlacesPolaroid day={day} />
      </div>

      <div className="flex items-center gap-5 pt-5 border-t border-white/[0.08] relative z-10">
        <div className="flex items-center gap-2 text-white/60 hover:text-white/90 transition-colors">
          <Activity className="w-4 h-4 text-cyan" />
          <span className="text-sm font-medium">{day.eventsCount} Activities</span>
        </div>
        <div className="flex items-center gap-1.5 text-white/60 hover:text-white/90 transition-colors">
          <DollarSign className="w-4 h-4 text-emerald-400" />
          <span className="text-sm font-medium">${day.cost.toFixed(2)}</span>
        </div>

        {/* Dynamic Loading Spinner (Bottom Right) */}
        {day.isLoading && (
          <div className="ml-auto flex items-center text-cyan">
            <Loader2 className="w-5 h-5 animate-spin" />
          </div>
        )}
        {!day.isLoading && (
          <div className="ml-auto flex items-center text-cyan">
            <CheckCircle2 className="w-5 h-5 text-cyan/70" />
          </div>
        )}
      </div>

      {/* Background radial highlight */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-cyan/5 via-transparent to-transparent pointer-events-none" />
    </motion.div>
  );
}
