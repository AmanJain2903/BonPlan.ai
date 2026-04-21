import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';
import { EASE_OUT_EXPO } from '../constants';

export default function PlaceholderSubCard() {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{
        opacity: 1,
        y: 0,
        boxShadow: [
          '0 0 0 rgba(102,252,241,0)',
          '0 0 28px rgba(102,252,241,0.35)',
          '0 0 0 rgba(102,252,241,0)',
        ],
      }}
      exit={{ opacity: 0, y: -4, transition: { duration: 0.25 } }}
      transition={{
        duration: 0.35,
        ease: EASE_OUT_EXPO,
        boxShadow: { duration: 1.8, repeat: Infinity, ease: 'easeInOut' },
      }}
      className="relative w-full rounded-2xl bg-black/50 border border-cyan/40 overflow-hidden"
    >
      {/* Base pulsing tint */}
      <motion.div
        aria-hidden
        animate={{ opacity: [0.4, 0.85, 0.4] }}
        transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
        className="absolute inset-0 bg-gradient-to-br from-cyan/30 via-cyan/5 to-cyan/30 pointer-events-none"
      />

      {/* Shimmer sweep A */}
      <motion.div
        aria-hidden
        animate={{ x: ['-60%', '180%'] }}
        transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
        className="absolute inset-y-0 left-0 w-1/2 bg-gradient-to-r from-transparent via-cyan/35 to-transparent pointer-events-none blur-[1px]"
      />

      {/* Shimmer sweep B (second pass, offset phase) */}
      <motion.div
        aria-hidden
        animate={{ x: ['-60%', '180%'] }}
        transition={{ duration: 1.2, repeat: Infinity, ease: 'linear', delay: 0.6 }}
        className="absolute inset-y-0 left-0 w-1/2 bg-gradient-to-r from-transparent via-white/15 to-transparent pointer-events-none"
      />

      <div className="relative z-10 flex items-center gap-4 px-4 py-3">
        <div className="flex items-center gap-2 shrink-0 px-2.5 py-1 rounded-full bg-cyan/20 border border-cyan/50 text-cyan min-w-[6.5rem] justify-center">
          <motion.span
            animate={{ rotate: [0, 360], scale: [1, 1.15, 1] }}
            transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
            className="inline-flex"
          >
            <Sparkles className="w-3.5 h-3.5" />
          </motion.span>
          <span className="text-[10px] font-bold uppercase tracking-wider">Generating</span>
        </div>

        <div className="flex-1 min-w-0 flex flex-col gap-2">
          <motion.div
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
            className="h-3.5 rounded-full bg-white/[0.14] w-3/4"
          />
          <motion.div
            animate={{ opacity: [0.4, 0.85, 0.4] }}
            transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut', delay: 0.2 }}
            className="h-2.5 rounded-full bg-white/[0.09] w-1/2"
          />
        </div>

        <motion.div
          animate={{ opacity: [0.4, 0.85, 0.4] }}
          transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut', delay: 0.4 }}
          className="hidden sm:block h-5 w-14 rounded-full bg-white/[0.1]"
        />
      </div>
    </motion.div>
  );
}
