import { RefObject, useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { User, Wrench, Brain, ChevronDown, Loader2, CheckCircle2, AlertTriangle, RefreshCw } from 'lucide-react';
import { EASE_OUT_EXPO } from './constants';
import { ToolEntry, SystemLog } from './types';
import { BotAvatar, BouncingDots } from './Atoms';

// ─── Sub-sections ─────────────────────────────────────────────

function UserContextMessage({ text }: { text: string }) {
  if (!text.trim()) return null;
  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 10, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.35, ease: EASE_OUT_EXPO }}
        className="flex items-start justify-end gap-3 mb-2"
      >
        <div className="max-w-[80%] px-4 py-3 text-right">
          <p className="text-sm text-white/80 leading-relaxed whitespace-pre-wrap text-justify">{text}</p>
        </div>
        <div className="w-7 h-7 rounded-full bg-cyan/10 border border-cyan/20 flex items-center justify-center shrink-0 mt-1">
          <User className="w-3.5 h-3.5 text-cyan" />
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

function ToolHistoryAccordion({
  toolHistory,
  expanded,
  onToggle,
}: {
  toolHistory: ToolEntry[];
  expanded: boolean;
  onToggle: () => void;
}) {
  if (toolHistory.length === 0) return null;
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="overflow-hidden"
    >
      <button
        onClick={onToggle}
        className="flex items-center gap-2.5 px-4 py-2 text-xs font-semibold text-white/60 hover:text-white/80 transition-colors group"
      >
        <Wrench className="w-3.5 h-3.5 text-cyan/70" />
        <span>Tool Calls ({toolHistory.length})</span>
        <motion.div animate={{ rotate: expanded ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <ChevronDown className="w-3.5 h-3.5" />
        </motion.div>
      </button>
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: EASE_OUT_EXPO }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-3 flex flex-col gap-3">
              {toolHistory.map((tool) => (
                <div key={tool.call_id} className="rounded-lg border border-white/[0.06] bg-black/30 p-3">
                  <div className="flex items-center gap-2 mb-2">
                    {tool.response ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-green-400/70" />
                    ) : (
                      <Loader2 className="w-3.5 h-3.5 text-cyan/70 animate-spin" />
                    )}
                    <span className="text-xs font-bold text-cyan/90 font-mono">{tool.name}</span>
                  </div>
                  {tool.args && (
                    <div className="mb-2">
                      <span className="text-[10px] uppercase tracking-wider text-white/30 font-semibold">Query</span>
                      <pre className="mt-1 text-[11px] text-white/50 bg-black/40 rounded-lg p-2 max-h-24 overflow-y-auto scrollbar-hide font-mono whitespace-pre-wrap break-all">
                        {typeof tool.args === 'string' ? tool.args : JSON.stringify(tool.args, null, 2)}
                      </pre>
                    </div>
                  )}
                  {tool.response && (
                    <div>
                      <span className="text-[10px] uppercase tracking-wider text-white/30 font-semibold">Response</span>
                      <pre className="mt-1 text-[11px] text-white/50 bg-black/40 rounded-lg p-2 max-h-32 overflow-y-auto scrollbar-hide font-mono whitespace-pre-wrap break-all">
                        {typeof tool.response === 'string' ? tool.response : JSON.stringify(tool.response, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

function ThoughtsAccordion({
  thoughtHistory,
  expanded,
  onToggle,
}: {
  thoughtHistory: string;
  expanded: boolean;
  onToggle: () => void;
}) {
  if (!thoughtHistory) return null;
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="overflow-hidden"
    >
      <button
        onClick={onToggle}
        className="flex items-center gap-2.5 px-4 py-2 text-xs font-semibold text-white/60 hover:text-white/80 transition-colors group"
      >
        <Brain className="w-3.5 h-3.5 text-cyan/70" />
        <span>Thoughts ({thoughtHistory.split('\n\n---\n\n').filter(Boolean).length})</span>
        <motion.div animate={{ rotate: expanded ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <ChevronDown className="w-3.5 h-3.5" />
        </motion.div>
      </button>
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: EASE_OUT_EXPO }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-3">
              <div className="text-xs text-white/40 leading-relaxed whitespace-pre-wrap max-h-60 overflow-y-auto scrollbar-hide">
                {thoughtHistory}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

function WaitingDots({ visible }: { visible: boolean }) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="dots"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.25 }}
          className="flex items-start gap-3"
        >
          <BotAvatar />
          <div className="flex items-center gap-1.5 px-4 py-4 mt-0.5">
            <BouncingDots />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function ActiveToolIndicator({ activeTool }: { activeTool: { name: string; call_id: string } | null }) {
  return (
    <AnimatePresence>
      {activeTool && (
        <motion.div
          initial={{ opacity: 0, y: 10, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -5, scale: 0.97 }}
          transition={{ duration: 0.3, ease: EASE_OUT_EXPO }}
          className="flex items-center gap-3 px-4 py-2"
        >
          <Loader2 className="w-4 h-4 text-cyan animate-spin shrink-0" />
          <span className="text-xs font-bold text-cyan/70 font-mono italic">Executing {activeTool.name}...</span>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function ActiveThinkingBubble({
  activeThinking,
  finalSummary,
  thinkingEndRef,
}: {
  activeThinking: string;
  finalSummary: string | null;
  thinkingEndRef: RefObject<HTMLDivElement>;
}) {
  return (
    <AnimatePresence>
      {activeThinking && !finalSummary && (
        <motion.div
          key="thinking"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -5 }}
          transition={{ duration: 0.3 }}
          className="flex items-start gap-3"
        >
          <BotAvatar icon={Brain} className="mt-0.5" />
          <div className="flex-1 px-4 py-3">
            <div className="max-h-30 overflow-y-auto scrollbar-hide pointer-events-none relative">
              <p className="text-xs text-white/50 leading-relaxed whitespace-pre-wrap">
                {activeThinking.trim()}
                <div className="flex items-center py-2 gap-1.5 mt-0.5">
                  <BouncingDots />
                </div>
              </p>
              <div ref={thinkingEndRef} />
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function useSystemLogExpiration(systemLog: SystemLog | null) {
  const [isExpired, setIsExpired] = useState(false);
  useEffect(() => {
    if (systemLog && systemLog.type === 'system') {
      setTimeout(() => {
        setIsExpired(true);
      }, 5000);
    }
  }, [systemLog]);
  return isExpired;
}
function SystemMessageAccordion({
  systemLog,
  expanded,
  onToggle,
}: {
  systemLog: SystemLog | null;
  expanded: boolean;
  onToggle: () => void;
}) {
  if (!systemLog || systemLog.type !== 'system') return null;
  const isExpired = useSystemLogExpiration(systemLog);
  return (
    <AnimatePresence mode="wait">
      {!isExpired && (
      <motion.div
        key={systemLog.content}
        initial={{ opacity: 0, y: 6, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -6, scale: 0.97 }}
        transition={{ duration: 0.25 }}
        className="overflow-hidden"
      >
        <button
          onClick={onToggle}
          className="w-full flex items-center justify-between px-4 py-3 text-xs font-semibold text-amber-300/80 hover:text-amber-200 transition-colors"
        >
          <div className="flex items-center gap-2 min-w-0">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
            <span className="truncate">
              {systemLog.content.slice(0, 60)}
              {systemLog.content.length > 60 ? '...' : ''}
            </span>
          </div>
          <motion.div animate={{ rotate: expanded ? 180 : 0 }} transition={{ duration: 0.2 }} className="shrink-0 ml-2">
            <ChevronDown className="w-4 h-4" />
          </motion.div>
        </button>
        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.25, ease: EASE_OUT_EXPO }}
              className="overflow-hidden"
            >
              <div className="px-4 pb-3">
                <p className="text-xs text-amber-300/70 leading-relaxed whitespace-pre-wrap">{systemLog.content}</p>
                <br />
                <p className="text-xs text-amber-300/70 leading-relaxed whitespace-pre-wrap">{systemLog.error}</p>
              </div>
            </motion.div>
          )}
          </AnimatePresence>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function FinalSummaryMessage({ finalSummary }: { finalSummary: string | null }) {
  const [displayedText, setDisplayedText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const summaryEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!finalSummary) {
      setDisplayedText('');
      setIsTyping(false);
      return;
    }

    setIsTyping(true);
    setDisplayedText('');
    let index = 0;

    const interval = setInterval(() => {
      if (index < finalSummary.length) {
        setDisplayedText(finalSummary.slice(0, index + 1));
        index++;
        summaryEndRef.current?.scrollIntoView({ behavior: 'auto' });
      } else {
        setIsTyping(false);
        clearInterval(interval);
      }
    }, 15);

    return () => clearInterval(interval);
  }, [finalSummary]);

  return (
    <AnimatePresence>
      {finalSummary && (
        <motion.div
          initial={{ opacity: 0, y: 15, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.5, ease: EASE_OUT_EXPO }}
          className="flex items-start gap-3"
        >
          <BotAvatar className="mt-0.5" />
          <div className="flex-1 px-4 py-3">
            <p className="text-sm text-white/80 leading-relaxed whitespace-pre-wrap text-justify">
              {displayedText}
              {isTyping && (
                <span className="inline-flex items-center gap-1 ml-1 align-middle">
                  <BouncingDots />
                </span>
              )}
            </p>
            <div ref={summaryEndRef} />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function ErrorRecoveryMessage({ systemLog, onRetry }: { systemLog: SystemLog | null; onRetry: () => void }) {
  if (!systemLog || systemLog.type !== 'error') return null;
  return (
    <AnimatePresence>
      <motion.div
        key="error-state"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="flex items-start gap-3 py-4"
      >
        <BotAvatar className="mt-0.5" />
        <div className="flex-1 flex flex-col items-start gap-2 pt-1">
          <div className="text-white/80 font-medium text-sm">
            {systemLog.userStopped ? 'You stopped the execution.' : 'Something went wrong'}
          </div>
          <button
            onClick={onRetry}
            className="flex items-center gap-2 text-cyan/70 hover:text-cyan transition-colors text-[10px] font-bold uppercase tracking-wider group"
          >
            <RefreshCw className="w-3.5 h-3.5 group-hover:rotate-180 transition-transform duration-500" />
            <span>Try Again</span>
          </button>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

// ─── Composite Component ──────────────────────────────────────

interface MessageCanvasProps {
  chatInput: string;
  toolHistory: ToolEntry[];
  toolsExpanded: boolean;
  onToggleTools: () => void;
  thoughtHistory: string;
  thoughtsExpanded: boolean;
  onToggleThoughts: () => void;
  activeThinking: string;
  isStreamComplete: boolean;
  finalSummary: string | null;
  activeTool: { name: string; call_id: string } | null;
  systemLog: SystemLog | null;
  systemLogExpanded: boolean;
  onToggleSystemLog: () => void;
  onRetry: () => void;
  messageEndRef: RefObject<HTMLDivElement>;
  thinkingEndRef: RefObject<HTMLDivElement>;
}

export default function MessageCanvas({
  chatInput,
  toolHistory,
  toolsExpanded,
  onToggleTools,
  thoughtHistory,
  thoughtsExpanded,
  onToggleThoughts,
  activeThinking,
  isStreamComplete,
  finalSummary,
  activeTool,
  systemLog,
  systemLogExpanded,
  onToggleSystemLog,
  onRetry,
  messageEndRef,
  thinkingEndRef,
}: MessageCanvasProps) {
  return (
    <div className="flex-1 min-h-0 overflow-y-auto px-6 py-5 scrollbar-hide">
      <div className="max-w-3xl mx-auto flex flex-col gap-1.5 relative">
        <UserContextMessage text={chatInput} />

        <ToolHistoryAccordion toolHistory={toolHistory} expanded={toolsExpanded} onToggle={onToggleTools} />

        <ThoughtsAccordion thoughtHistory={thoughtHistory} expanded={thoughtsExpanded} onToggle={onToggleThoughts} />

        <WaitingDots visible={!activeThinking && !isStreamComplete && !finalSummary} />

        <ActiveToolIndicator activeTool={activeTool} />

        <ActiveThinkingBubble
          activeThinking={activeThinking}
          finalSummary={finalSummary}
          thinkingEndRef={thinkingEndRef}
        />

        <SystemMessageAccordion systemLog={systemLog} expanded={systemLogExpanded} onToggle={onToggleSystemLog} />

        <FinalSummaryMessage finalSummary={finalSummary} />

        <ErrorRecoveryMessage systemLog={systemLog} onRetry={onRetry} />

        {/* Invisible scroll anchor */}
        <div ref={messageEndRef} />
      </div>
    </div>
  );
}
