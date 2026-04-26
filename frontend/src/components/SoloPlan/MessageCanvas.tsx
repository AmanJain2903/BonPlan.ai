import { RefObject, useState, useEffect, useRef, useCallback, useLayoutEffect, MutableRefObject } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { User, Wrench, Brain, ChevronDown, Loader2, CheckCircle2, AlertTriangle, RefreshCw, Play, ArrowUp, ArrowDown } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { EASE_OUT_EXPO } from './constants';
import { ToolEntry, SystemLog, ChatTurn } from './types';
import { BotAvatar, BouncingDots } from './Atoms';

// ─── Sub-sections ─────────────────────────────────────────────

function UserMessage({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  if (!text.trim()) return null;
  const needsTruncation = text.length > 50;
  const displayText = needsTruncation && !expanded ? text.slice(0, 50) + '...' : text;
  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.35, ease: EASE_OUT_EXPO }}
      className="flex items-start justify-end gap-2.5 mb-2"
    >
      <div className="max-w-70 px-4 py-2.5 bg-white/[0.04] border border-white/[0.06] rounded-2xl rounded-tr-sm">
        <p className="text-sm text-white/80 leading-relaxed whitespace-pre-wrap break-word">
          {displayText}
          {needsTruncation && (
            <button
              onClick={() => setExpanded((p) => !p)}
              className="ml-1 text-cyan/70 hover:text-cyan text-xs font-semibold transition-colors"
            >
              {expanded ? 'Show less' : 'Show more'}
            </button>
          )}
        </p>
      </div>
      <div className="w-7 h-7 rounded-full bg-cyan/10 border border-cyan/20 flex items-center justify-center shrink-0 mt-0.5">
        <User className="w-3.5 h-3.5 text-cyan" />
      </div>
    </motion.div>
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
            <div className="px-4 pb-3 flex flex-col gap-3 max-h-60 overflow-y-auto scrollbar-hide">
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
                      <pre className="mt-1 text-[11px] text-white/50 bg-black/40 rounded-lg p-2 max-h-24 overflow-y-auto scrollbar-hide font-mono whitespace-pre-wrap break-word">
                        {typeof tool.args === 'string' ? tool.args : JSON.stringify(tool.args, null, 2)}
                      </pre>
                    </div>
                  )}
                  {tool.response && (
                    <div>
                      <span className="text-[10px] uppercase tracking-wider text-white/30 font-semibold">Response</span>
                      <pre className="mt-1 text-[11px] text-white/50 bg-black/40 rounded-lg p-2 max-h-32 overflow-y-auto scrollbar-hide font-mono whitespace-pre-wrap break-word">
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

function ActivePruningIndicator({ activePruningChunk }: { activePruningChunk: any | null }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <AnimatePresence>
      {activePruningChunk && (
        <motion.div
          initial={{ opacity: 0, y: 10, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -5, scale: 0.97 }}
          transition={{ duration: 0.3, ease: EASE_OUT_EXPO }}
          className="flex flex-col px-4 py-2"
        >
          <div className="flex items-center gap-3">
            <Loader2 className="w-4 h-4 text-cyan animate-spin shrink-0" />
            <span className="text-xs font-bold text-cyan/70 font-mono italic">Compacting Memory...</span>
            <button onClick={() => setExpanded(p => !p)} className="p-1 text-cyan/70 hover:text-cyan transition-colors ml-auto mr-2">
              <motion.div animate={{ rotate: expanded ? 180 : 0 }} transition={{ duration: 0.2 }}>
                <ChevronDown className="w-4 h-4" />
              </motion.div>
            </button>
          </div>
          <AnimatePresence>
            {expanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.3, ease: EASE_OUT_EXPO }}
                className="overflow-hidden"
              >
                <pre className="mt-2 text-[11px] text-white/50 bg-black/40 rounded-lg p-3 max-h-48 overflow-y-auto scrollbar-hide font-mono whitespace-pre-wrap break-word">
                  {typeof activePruningChunk.content === 'string'
                    ? activePruningChunk.content
                    : JSON.stringify(activePruningChunk, null, 2)}
                </pre>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function ActiveThinkingBubble({
  activeThinking,
  thinkingEndRef,
}: {
  activeThinking: string;
  thinkingEndRef: RefObject<HTMLDivElement>;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Keep the bubble pinned to the bottom as new thinking tokens stream in.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [activeThinking]);

  return (
    <AnimatePresence>
      {activeThinking && (
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
            <div
              ref={scrollRef}
              className="max-w-70 max-h-20 overflow-y-auto scrollbar-hide pointer-events-none relative"
            >
              <p className="text-xs text-white/50 leading-relaxed whitespace-normal">
                <ReactMarkdown>{activeThinking.trim()}</ReactMarkdown>
              </p>
              <div ref={thinkingEndRef} />
            </div>
            {/* Dots live OUTSIDE the scroll-clipped box so they remain
                visible even after the text grows past max-h-20. */}
            <div className="flex items-center py-2 gap-1.5 mt-0.5">
              <BouncingDots />
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function useSystemLogExpiration(systemLog: SystemLog | null, expanded: boolean) {
  const [isExpired, setIsExpired] = useState(false);
  useEffect(() => {
    setIsExpired(false);
    if (systemLog && systemLog.type === 'system' && !expanded) {
      const timer = setTimeout(() => setIsExpired(true), 5000);
      return () => clearTimeout(timer);
    }
  }, [systemLog, expanded]);
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
  const isExpired = useSystemLogExpiration(systemLog, expanded);
  if (!systemLog || systemLog.type !== 'system') return null;
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
                  {systemLog.error && (
                    <>
                      <br />
                      <p className="text-xs text-amber-300/70 leading-relaxed whitespace-pre-wrap">{systemLog.error}</p>
                    </>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function FinalSummaryMessage({
  finalSummary,
  summaryEndRef,
}: {
  finalSummary: string | null;
  summaryEndRef?: RefObject<HTMLDivElement>;
}) {
  return (
    <AnimatePresence>
      {finalSummary?.trim() && (
        <motion.div
          key="summary"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -5 }}
          transition={{ duration: 0.3 }}
          className="flex items-start gap-3"
        >
          <BotAvatar className="mt-0.5" />
          <div className="flex-1 px-4 py-3">
            <div className="text-sm text-white/80 leading-relaxed prose prose-invert prose-sm max-w-none prose-strong:text-white prose-em:text-white/70 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-p:my-1 prose-headings:text-white prose-headings:mt-2 prose-headings:mb-1">
              <ReactMarkdown>{finalSummary.trim()}</ReactMarkdown>
            </div>
            {summaryEndRef && <div ref={summaryEndRef} />}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function ErrorRecoveryMessage({
  systemLog,
  errorType,
  onRetry,
}: {
  systemLog: SystemLog | null;
  errorType: 'stopped' | 'error' | null;
  onRetry: () => void;
}) {
  if (!systemLog || systemLog.type !== 'error') return null;
  const isStopped = errorType === 'stopped' || systemLog.userStopped;
  return (
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
          {isStopped ? 'You stopped the execution.' : 'Something went wrong'}
        </div>
        <button
          onClick={onRetry}
          className="flex items-center gap-2 text-cyan/70 hover:text-cyan transition-colors text-[10px] font-bold uppercase tracking-wider group"
        >
          {isStopped ? (
            <>
              <Play className="w-3.5 h-3.5 group-hover:scale-110 transition-transform" />
              <span>Resume</span>
            </>
          ) : (
            <>
              <RefreshCw className="w-3.5 h-3.5 group-hover:rotate-180 transition-transform duration-500" />
              <span>Try Again</span>
            </>
          )}
        </button>
      </div>
    </motion.div>
  );
}

// ─── Composite Component ──────────────────────────────────────

interface MessageCanvasProps {
  turns: ChatTurn[];
  toolsExpanded: boolean;
  onToggleTools: () => void;
  thoughtsExpanded: boolean;
  onToggleThoughts: () => void;
  systemLogExpanded: boolean;
  onToggleSystemLog: () => void;
  onRetry: () => void;
  errorType: 'stopped' | 'error' | null;
  messageEndRef: RefObject<HTMLDivElement>;
  thinkingEndRef: RefObject<HTMLDivElement>;
  summaryEndRef: RefObject<HTMLDivElement>;
  scrollPositionRef: MutableRefObject<number>;
  isAtBottomRef: MutableRefObject<boolean>;
}

export default function MessageCanvas({
  turns,
  toolsExpanded,
  onToggleTools,
  thoughtsExpanded,
  onToggleThoughts,
  systemLogExpanded,
  onToggleSystemLog,
  onRetry,
  errorType,
  messageEndRef,
  thinkingEndRef,
  summaryEndRef,
  scrollPositionRef,
  isAtBottomRef,
}: MessageCanvasProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const [showScrollTop, setShowScrollTop] = useState(false);
  const [showScrollBottom, setShowScrollBottom] = useState(false);

  const updateScrollState = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const { scrollTop, scrollHeight, clientHeight } = container;
    scrollPositionRef.current = scrollTop;

    const atBottom = scrollHeight - scrollTop - clientHeight <= 10;
    isAtBottomRef.current = atBottom;

    setShowScrollTop(scrollTop > 100);
    setShowScrollBottom(!atBottom && scrollHeight > clientHeight);
  }, [scrollPositionRef, isAtBottomRef]);

  const handleScroll = () => updateScrollState();

  useEffect(() => {
    // Small timeout to ensure the DOM has rendered the height
    const timer = setTimeout(updateScrollState, 100);
    return () => clearTimeout(timer);
  }, [turns, updateScrollState]);

  useLayoutEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    if (isAtBottomRef.current) {
      container.scrollTo({ top: container.scrollHeight, behavior: 'auto' });
    } else {
      // If user is scrolled up, keep them exactly where they were
      container.scrollTop = scrollPositionRef.current;
    }
  }, [turns, toolsExpanded, thoughtsExpanded, systemLogExpanded]);

  const scrollToTop = () => {
    scrollContainerRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  };[turns, toolsExpanded, thoughtsExpanded, systemLogExpanded]

  const scrollToBottom = () => {
    scrollContainerRef.current?.scrollTo({
      top: scrollContainerRef.current.scrollHeight,
      behavior: 'smooth'
    });
  };

  // useEffect(() => {
  //   if (!isUserAtBottomRef.current) return;
  //   const container = scrollContainerRef.current;
  //   if (container) {
  //     container.scrollTo({ top: container.scrollHeight, behavior: 'auto' });
  //   }
  // }, [turns]);

  return (
    <div className="relative flex-1 flex flex-col min-h-0">
      {/* Scroll Navigation Controls */}
      {/* <div className="absolute left-6 top-1/2 -translate-y-1/2 z-20 flex flex-col gap-2 pointer-events-none">
        <AnimatePresence>
          {showScrollTop && (
            <motion.button
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              onClick={scrollToTop}
              className="p-2 rounded-full bg-white/5 border border-white/10 text-white/40 hover:text-cyan hover:bg-white/10 transition-all pointer-events-auto backdrop-blur-md"
            >
              <ArrowUp className="w-4 h-4" />
            </motion.button>
          )}
          {showScrollBottom && (
            <motion.button
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              onClick={scrollToBottom}
              className="p-2 rounded-full bg-white/5 border border-white/10 text-white/40 hover:text-cyan hover:bg-white/10 transition-all pointer-events-auto backdrop-blur-md"
            >
              <ArrowDown className="w-4 h-4" />
            </motion.button>
          )}
        </AnimatePresence>
      </div> */}

      {/* Scroll to Top - Top Right */}
      <div className="absolute right-0 top-0 z-20 pointer-events-none">
        <AnimatePresence>
          {showScrollTop && (
            <motion.button
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              onClick={scrollToTop}
              className="p-2.5 text-cyan/40 hover:text-cyan hover:scale-120 transition-all pointer-events-auto shadow-lg"
            >
              <ArrowUp className="w-4 h-4" />
            </motion.button>
          )}
        </AnimatePresence>
      </div>

      {/* Scroll to Bottom - Bottom Right */}
      <div className="absolute right-0 bottom-0 z-20 pointer-events-none">
        <AnimatePresence>
          {showScrollBottom && (
            <motion.button
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              onClick={scrollToBottom}
              className="p-2.5 text-cyan/40 hover:text-cyan hover:scale-120 transition-all pointer-events-auto shadow-lg"
            >
              <ArrowDown className="w-4 h-4" />
            </motion.button>
          )}
        </AnimatePresence>
      </div>

      <div ref={scrollContainerRef} onScroll={handleScroll} className="flex-1 min-h-0 overflow-y-auto px-6 py-5 pb-20 chat-scrollbar">
        <div className="max-w-3xl mx-auto flex flex-col gap-1.5 relative">
          {turns.map((turn) =>
            turn.type === 'user' ? (
              <UserMessage key={turn.id} text={turn.text} />
            ) : (
              <div key={turn.id} className="flex flex-col gap-1.5">
                <ToolHistoryAccordion toolHistory={turn.toolHistory} expanded={toolsExpanded} onToggle={onToggleTools} />
                <ThoughtsAccordion thoughtHistory={turn.thoughtHistory} expanded={thoughtsExpanded} onToggle={onToggleThoughts} />
                <WaitingDots visible={turn.isStreaming && !turn.activeThinkingBubble && !turn.finalSummary} />
                <ActiveToolIndicator activeTool={turn.activeToolIndicator} />
                <ActivePruningIndicator activePruningChunk={turn.activePruningChunk} />
                <ActiveThinkingBubble activeThinking={turn.activeThinkingBubble} thinkingEndRef={thinkingEndRef} />
                <FinalSummaryMessage finalSummary={turn.finalSummary} summaryEndRef={summaryEndRef} />
                <SystemMessageAccordion
                  systemLog={turn.systemLog}
                  expanded={systemLogExpanded}
                  onToggle={onToggleSystemLog}
                />
                <ErrorRecoveryMessage systemLog={turn.systemLog} errorType={errorType} onRetry={onRetry} />
              </div>
            )
          )}

          <div ref={messageEndRef} />
        </div>
      </div>
    </div>
  );
}
