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
          </div>
        </motion.button>
      )}
    </AnimatePresence>
  );
}
