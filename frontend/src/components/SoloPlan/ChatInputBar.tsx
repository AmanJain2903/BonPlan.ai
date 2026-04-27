import { motion, AnimatePresence } from 'framer-motion';
import { Send, Square, Clock } from 'lucide-react';
import type { ChatMode } from './types';

interface ChatInputBarProps {
  isGenerating: boolean;
  chatMode: ChatMode;
  chatInput: string;
  setChatInput: (val: string) => void;
  onSend: () => void;
  onStop: () => void;
  elapsedSeconds: number;
  errorType?: 'stopped' | 'error' | null;
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export default function ChatInputBar({
  isGenerating,
  chatMode,
  chatInput,
  setChatInput,
  onSend,
  onStop,
  elapsedSeconds,
  errorType,
}: ChatInputBarProps) {
  const isEditingMode = chatMode === 'editing';
  return (
    <div className="w-full shrink-0 px-3 pb-5 sm:px-6 sm:pb-6 relative items-center flex flex-col">
      <AnimatePresence>
        {isGenerating && !errorType && (
          <motion.div
            layout
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            className={`${isEditingMode ? 'absolute -top-10' : 'relative'} flex items-center gap-3 z-20`}
          >
            <div className="flex items-center gap-1.5 px-3 py-2 bg-black/40 backdrop-blur-md border border-white/10 rounded-full text-[10px] font-bold uppercase tracking-widest text-white/50">
              <Clock className="w-3 h-3 text-cyan/60" />
              <span className="font-mono">{formatElapsed(elapsedSeconds)}</span>
            </div>

            <button
              onClick={onStop}
              className="flex items-center gap-2 px-4 py-2 bg-black/40 backdrop-blur-md border border-white/10 rounded-full text-[10px] font-bold uppercase tracking-widest text-white/60 hover:text-white hover:border-red-500/30 hover:bg-red-500/5 transition-all group"
            >
              <Square className="w-3 h-3 text-red-500 group-hover:scale-110 transition-transform fill-red-500/20" />
              <span>Stop Generation</span>
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.div
        initial={false}
        animate={{
          opacity: isEditingMode ? 1 : 0,
          y: isEditingMode ? 0 : 20,
          pointerEvents: isEditingMode ? 'auto' : 'none'
        }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        className="w-full max-w-3xl mx-auto"
      >
        <div className="relative group w-full">
          <div className="absolute -inset-0.5 bg-gradient-to-r from-cyan/20 to-blue/20 rounded-2xl blur opacity-15 group-hover:opacity-30 transition duration-500" />
          <div className="relative flex items-center bg-black/60 backdrop-blur-xl border border-white/10 rounded-2xl p-1.5 px-4 focus-within:border-cyan/50 transition-all duration-300 shadow-2xl">
            <textarea
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  if (isEditingMode && chatInput.trim()) onSend();
                }
              }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement;
                target.style.height = 'auto';
                target.style.height = `${Math.min(target.scrollHeight, 120)}px`;
              }}
              disabled={!isEditingMode}
              placeholder="Want to make edits?"
              className="w-full bg-transparent border-none text-white text-sm focus:outline-none focus:ring-0 py-2.5 resize-none overflow-y-auto scrollbar-hide disabled:opacity-30 disabled:cursor-not-allowed placeholder:text-white/40"
              rows={1}
              style={{ minHeight: '24px', maxHeight: '120px' }}
            />
            <button
              onClick={onSend}
              disabled={!isEditingMode || !chatInput.trim()}
              className="shrink-0 ml-2 p-2 rounded-xl bg-cyan/90 text-black disabled:opacity-20 disabled:cursor-not-allowed hover:bg-cyan hover:scale-110 active:scale-90 transition-all"
            >
              <Send className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
