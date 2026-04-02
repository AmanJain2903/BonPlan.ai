import { motion, AnimatePresence } from 'framer-motion';
import { Settings, ArrowRight, X } from 'lucide-react';

type Props = {
  open: boolean;
  onSetup: () => void;
  onSkip: () => void;
};

export default function WelcomePreferencesModal({ open, onSetup, onSkip }: Props) {
  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm rounded-2xl"
            onClick={onSkip}
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.92, y: 30 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.92, y: 30 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            className="fixed inset-0 z-[101] flex items-center justify-center p-4"
          >
            <div className="relative w-full max-w-md rounded-2xl border border-white/[0.06] bg-carbon/40 backdrop-blur-xl p-8 shadow-[0_25px_80px_rgba(0,0,0,0.6)]">
              {/* Close button */}
              <button
                onClick={onSkip}
                className="absolute top-4 right-4 p-2 rounded-lg text-white/30 hover:text-white/60 transition-colors cursor-pointer"
              >
                <X size={18} />
              </button>

              {/* Icon */}
              <div className="flex justify-center mb-6">
                <div className="h-16 w-16 rounded-2xl bg-cyan/10 border border-cyan/20 flex items-center justify-center">
                  <Settings size={28} className="text-cyan" />
                </div>
              </div>

              {/* Content */}
              <h2 className="text-xl font-bold text-white text-center tracking-tight">
                Set Up Your Travel Preferences?
              </h2>
              <p className="text-sm text-white/45 text-center mt-3 leading-relaxed max-w-sm mx-auto">
                Personalise your experience by setting dietary needs, travel style, and more.
                You can always change them later in the <span className="text-cyan/70 font-medium">Account</span> panel.
              </p>

              {/* Actions */}
              <div className="flex flex-col gap-3 mt-8">
                <button
                  onClick={onSetup}
                  className="w-full flex items-center justify-center gap-2.5 rounded-xl bg-cyan text-midnight font-bold text-sm py-3.5 hover:shadow-[0_0_25px_rgba(102,252,241,0.3)] hover:scale-[1.02] transition-all duration-300 cursor-pointer"
                >
                  Yes, let's set it up
                  <ArrowRight size={16} />
                </button>
                <button
                  onClick={onSkip}
                  className="w-full rounded-xl border border-white/10 bg-white/[0.03] text-white/50 font-semibold text-sm py-3.5 hover:text-white/80 hover:bg-white/[0.06] transition-all duration-200 cursor-pointer"
                >
                  Skip for now
                </button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
