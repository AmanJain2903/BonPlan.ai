import { ReactNode, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, type LucideIcon } from 'lucide-react';
import { EASE_OUT_EXPO, getDateDifference } from '../../constants';

interface SubCardShellProps {
  eventType: string;
  label: string;
  Icon: LucideIcon;
  accent: { text: string; bg: string; border: string };
  collapsedContent: ReactNode;
  expandedContent?: ReactNode;
  viewOnMapButton?: ReactNode;
  onExpandChange?: (expanded: boolean) => void;
  initiallyExpanded?: boolean;
  /** Change this key whenever the event data updates to trigger a content crossfade. */
  contentKey?: string | number;
  startTime?: any;
  endTime?: any;
}

const CONTENT_SWAP = {
  initial: { opacity: 0, y: 4, filter: 'blur(2px)' },
  animate: { opacity: 1, y: 0, filter: 'blur(0px)' },
  exit: { opacity: 0, y: -4, filter: 'blur(2px)' },
  transition: { duration: 0.3, ease: EASE_OUT_EXPO },
};

/**
 * Full-width row subcard with a leading "purpose" pill, a trailing view-on-map slot,
 * and an animated expandable body. Click anywhere on the header toggles expansion.
 *
 * When `contentKey` changes (e.g. on an AI edit), all dynamic content crossfades
 * smoothly while structural elements (pill, chevron, map button, bg) stay stable.
 */
export default function SubCardShell({
  eventType,
  label,
  Icon,
  accent,
  collapsedContent,
  expandedContent,
  viewOnMapButton,
  onExpandChange,
  initiallyExpanded = false,
  contentKey,
  startTime,
  endTime,
}: SubCardShellProps) {
  const [expanded, setExpanded] = useState(initiallyExpanded);
  const canExpand = Boolean(expandedContent);

  const toggle = () => {
    if (!canExpand) return;
    const next = !expanded;
    setExpanded(next);
    onExpandChange?.(next);
  };

  const isCommute = eventType === 'COMMUTE' || eventType.startsWith('FLIGHT') || eventType.startsWith('CAR');
  const dateDiff = (!isCommute && startTime && endTime) ? getDateDifference(startTime, endTime) : 0;

  // Use contentKey if provided, otherwise the collapsed content itself is stable
  const animKey = contentKey ?? 'stable';

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.35, ease: EASE_OUT_EXPO }}
      className={`relative w-full rounded-2xl bg-black/50 border ${accent.border} backdrop-blur-sm overflow-hidden shadow-lg hover:shadow-cyan/10 transition-shadow`}
    >
      {/* Date Difference Badge */}
      {dateDiff > 0 && (
        <div className="absolute top-0 right-0 bg-cyan text-black px-2 py-0.5 rounded-bl-xl text-[10px] font-bold shadow-md z-20">
          +{dateDiff}
        </div>
      )}

      <div
        aria-hidden
        className="absolute inset-0 bg-gradient-to-br from-cyan/15 via-transparent to-cyan/15 pointer-events-none z-0"
      />
      <div
        aria-hidden
        className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(102,252,241,0.08),transparent_60%)] pointer-events-none z-0"
      />

      <div
        role={canExpand ? 'button' : undefined}
        tabIndex={canExpand ? 0 : -1}
        onClick={toggle}
        onKeyDown={(e) => {
          if (!canExpand) return;
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            toggle();
          }
        }}
        className={`relative z-10 flex items-center gap-4 px-4 py-3 select-none ${canExpand ? 'cursor-pointer hover:bg-white/[0.03]' : ''}`}
      >
        {/* Purpose pill — stable, does not crossfade */}
        <AnimatePresence mode="wait">
          <motion.div
            key={`${accent.text}-${label}`}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ duration: 0.25 }}
            className={`flex items-center gap-2 shrink-0 px-2.5 py-1 rounded-full min-w-[6.5rem] justify-center ${accent.bg} ${accent.border} border ${accent.text}`}
          >
            <Icon className="w-3.5 h-3.5" />
            <span className="text-[10px] font-bold uppercase tracking-wider">{label}</span>
          </motion.div>
        </AnimatePresence>

        {/* Dynamic collapsed content — crossfades on contentKey change */}
        <div className="flex-1 min-w-0 flex items-center gap-3 overflow-hidden">
          <AnimatePresence mode="wait">
            <motion.div
              key={animKey}
              {...CONTENT_SWAP}
              className="flex-1 min-w-0 flex items-center gap-3"
            >
              {collapsedContent}
            </motion.div>
          </AnimatePresence>
        </div>

        {viewOnMapButton && (
          <div className="shrink-0" onClick={(e) => e.stopPropagation()}>
            {viewOnMapButton}
          </div>
        )}

        {canExpand && (
          <motion.div
            animate={{ rotate: expanded ? 180 : 0 }}
            transition={{ duration: 0.25, ease: EASE_OUT_EXPO }}
            className="shrink-0 text-white/40"
          >
            <ChevronDown className="w-4 h-4" />
          </motion.div>
        )}
      </div>

      <AnimatePresence initial={false}>
        {expanded && expandedContent && (
          <motion.div
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.35, ease: EASE_OUT_EXPO }}
            className="relative z-10 overflow-hidden"
          >
            <div className="px-4 pb-4 pt-1 border-t border-white/[0.06]">
              {/* Expanded content crossfades on contentKey change */}
              <AnimatePresence mode="wait">
                <motion.div
                  key={animKey}
                  {...CONTENT_SWAP}
                >
                  {expandedContent}
                </motion.div>
              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
