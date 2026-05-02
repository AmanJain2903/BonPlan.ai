import { motion, AnimatePresence } from 'framer-motion';
import { Bot } from 'lucide-react';

interface FloatingRestoreButtonProps {
  visible: boolean;
  onRestore: () => void;
}

export default function FloatingRestoreButton({ visible, onRestore }: FloatingRestoreButtonProps) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ scale: 0.9, opacity: 0, y: 20 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0.9, opacity: 0, y: 20 }}
          className="fixed bottom-4 right-9 z-50 group"
        >
          <button
            onClick={onRestore}
            className="relative inline-flex items-center rounded-full shadow-[0_0_15px_rgba(102,252,241,0.4)]"
          >
            <span className="h-12 pl-4 pr-3 rounded-l-full backdrop-blur-md text-cyan text-xs font-semibold tracking-wide inline-flex items-center">
              Ask AI
            </span>
            <span className="-ml-px h-12 w-12 rounded-full border border-cyan/60 bg-cyan inline-flex items-center justify-center transition-transform duration-200 group-hover:scale-105 z-10">
              <Bot className="w-6 h-6 text-black group-hover:rotate-12 transition-transform" />
            </span>
          </button>
          <div className="pointer-events-none absolute -inset-0.5 rounded-full bg-gradient-to-r from-cyan/25 to-blue/20 blur opacity-25 group-hover:opacity-40 transition-opacity" />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
