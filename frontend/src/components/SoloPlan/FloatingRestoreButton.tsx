import { motion, AnimatePresence } from 'framer-motion';
import { Bot, Maximize2 } from 'lucide-react';

interface FloatingRestoreButtonProps {
  visible: boolean;
  onRestore: () => void;
  /** If true, renders the finalized-view variant with the pulse badge */
  withBadge?: boolean;
}

export default function FloatingRestoreButton({ visible, onRestore, withBadge = false }: FloatingRestoreButtonProps) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.button
          initial={{ scale: 0, opacity: 0, y: 20 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0, opacity: 0, y: 20 }}
          whileHover={{ scale: 1.1, y: -5 }}
          whileTap={{ scale: 0.9 }}
          onClick={onRestore}
          className="fixed bottom-10 right-10 z-50 w-16 h-16 rounded-full bg-cyan shadow-[0_0_30px_rgba(102,252,241,0.4)] flex items-center justify-center group"
        >
          <div className="relative">
            <Bot className="w-8 h-8 text-black group-hover:rotate-12 transition-transform" />
            {withBadge && (
              <motion.div
                className="absolute -top-1 -right-1 bg-black rounded-full p-0.5"
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                <Maximize2 className="w-3 h-3 text-cyan" />
              </motion.div>
            )}
          </div>
        </motion.button>
      )}
    </AnimatePresence>
  );
}
