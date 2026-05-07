import { RefObject, useState, useEffect, useRef, useCallback, useLayoutEffect, MutableRefObject } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { User, Brain, ChevronDown, Loader2, AlertTriangle, RefreshCw, Play, ArrowUp, ArrowDown, CalendarCheck } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import type { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { EASE_OUT_EXPO } from './constants';
import { SystemLog, ChatTurn, BotTurn, UserTurn, QAPairTurn } from './types';
import { BotAvatar, BouncingDots } from './Atoms';
import QuestionCard from './QuestionCard';

// ─── Sub-sections ─────────────────────────────────────────────

const markdownComponents: Components = {
  table({ node: _node, ...props }) {
    return (
      <div className="my-3 block w-full max-w-full overflow-x-auto rounded-md border border-white/10">
        <table {...props} className="w-max min-w-full max-w-none border-collapse text-left text-xs" />
      </div>
    );
  },
  th({ node: _node, ...props }) {
    return (
      <th
        {...props}
        className="border-b border-white/10 bg-white/[0.06] px-3 py-2 font-semibold text-white"
      />
    );
  },
  td({ node: _node, ...props }) {
    return <td {...props} className="border-b border-white/10 px-3 py-2 align-top text-white/75" />;
  },
};

function MarkdownContent({
  children,
  className = '',
}: {
  children: string;
  className?: string;
}) {
  return (
    <div
      className={`min-w-0 max-w-full overflow-x-hidden text-sm text-white/80 leading-relaxed prose prose-invert prose-sm prose-strong:text-white prose-em:text-white/70 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-p:my-1 prose-headings:text-white prose-headings:mt-2 prose-headings:mb-1 prose-pre:max-w-full prose-pre:overflow-x-auto prose-code:break-words ${className}`}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {children}
      </ReactMarkdown>
    </div>
  );
}

function UserMessage({ text, attachedEventsCount = 0 }: { text: string; attachedEventsCount?: number }) {
  const [expanded, setExpanded] = useState(false);
  if (!text.trim()) return null;
  const needsTruncation = text.length > 50;
  const displayText = needsTruncation && !expanded ? text.slice(0, 50) + '...' : text;
  const hasAttachedEvents = attachedEventsCount > 0;
  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.35, ease: EASE_OUT_EXPO }}
      className="flex items-start justify-end gap-2.5"
    >
      <div className="max-w-70 px-4 py-2.5 bg-white/[0.04] border border-white/[0.06] rounded-2xl rounded-tr-sm">
        <p className="text-sm text-white/80 leading-relaxed whitespace-pre-wrap break-words">
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
        {hasAttachedEvents && (
          <div className="mt-2 flex justify-end">
            <span
              className="inline-flex items-center gap-1 rounded-full border border-cyan/25 bg-cyan/10 px-2 py-0.5 text-[11px] font-semibold leading-none text-cyan/85"
              title={`${attachedEventsCount} attached ${attachedEventsCount === 1 ? 'event' : 'events'}`}
              aria-label={`${attachedEventsCount} attached ${attachedEventsCount === 1 ? 'event' : 'events'}`}
            >
              <CalendarCheck className="w-3 h-3" />
              +{attachedEventsCount}
            </span>
          </div>
        )}
      </div>
      <div className="w-7 h-7 rounded-full bg-cyan/10 border border-cyan/20 flex items-center justify-center shrink-0 mt-0.5">
        <User className="w-3.5 h-3.5 text-cyan" />
      </div>
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
          <div className="flex items-center gap-1.5 px-0 py-3 mt-0.5">
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
                <pre className="mt-2 text-[11px] text-white/50 bg-black/40 rounded-lg p-3 max-h-48 overflow-y-auto scrollbar-hide font-mono whitespace-pre-wrap break-words">
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
          className="flex w-full min-w-0 max-w-full items-start gap-3 overflow-x-hidden"
        >
          <BotAvatar icon={Brain} className="mt-0.5" />
          <div className="min-w-0 max-w-full flex-1 px-0 py-0">
            <div
              ref={scrollRef}
              className="relative max-h-20 max-w-full overflow-y-auto overflow-x-hidden scrollbar-hide pointer-events-none"
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
          className="flex w-full min-w-0 max-w-full items-start gap-3 overflow-x-hidden"
        >
          <BotAvatar className="mt-0.5" />
          <div className="min-w-0 max-w-full flex-1 px-0 py-0">
            <MarkdownContent>{finalSummary.trim()}</MarkdownContent>
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

// ─── Past-message renderers (frozen turns shown below the live latest turn) ───

/**
 * Composite Q&A block. ALWAYS renders the AI question above the user's
 * answer — regardless of the surrounding newest-first / chronological
 * ordering of other turns. This is intentional: a Q&A pair only reads
 * naturally as Q-then-A.
 *
 * The AI question matches the summary-message style (no bg, just prose
 * next to the bot avatar). Only the user's answer carries a bubble bg,
 * matching the rest of the chat's user-message style.
 */
function QAPairMessage({ turn }: { turn: QAPairTurn }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="flex flex-col gap-2 mb-2"
    >
      {/* AI question — no bg, just text + bot avatar (summary chunk style) */}
      {turn.question?.trim() && (
        <div className="flex items-start gap-3">
          <BotAvatar className="mt-0.5" />
          <div className="flex-1 px-0 py-0">
            <div className="text-sm text-white/80 leading-relaxed whitespace-pre-wrap">
              {turn.question}
            </div>
          </div>
        </div>
      )}
      {/* User's answer — same bubble style as a regular user message */}
      <div className="flex items-start justify-end gap-2.5">
        <div className="max-w-70 px-4 py-2.5 bg-white/[0.04] border border-white/[0.06] rounded-2xl rounded-tr-sm">
          <p className="text-sm text-white/80 leading-relaxed whitespace-pre-wrap break-words">
            {turn.answer || (turn.skipped ? 'Skipped' : '')}
          </p>
        </div>
        <div className="w-7 h-7 rounded-full bg-cyan/10 border border-cyan/20 flex items-center justify-center shrink-0 mt-0.5">
          <User className="w-3.5 h-3.5 text-cyan" />
        </div>
      </div>
    </motion.div>
  );
}

function FrozenBotTurn({ turn }: { turn: BotTurn }) {
  const [thoughtsExpanded, setThoughtsExpanded] = useState(false);
  const [systemLogExpanded, setSystemLogExpanded] = useState(false);

  const hasThoughts = !!turn.thoughtHistory?.trim();
  const hasSummary = !!turn.finalSummary?.trim();
  const hasSystemLog = turn.systemLog?.type === 'system';

  const hasContent = hasThoughts || hasSummary || hasSystemLog;
  if (!hasContent) return null;
  // History view of a completed bot turn — collapsed accordion pills only,
  // no in-progress indicators (no active tool, no active thinking bubble,
  // no pruning, no pending question, no waiting dots).
  return (
    <div className="mb-3 flex min-w-0 max-w-full flex-col gap-1.5 overflow-x-hidden">
      <ThoughtsAccordion thoughtHistory={turn.thoughtHistory} expanded={thoughtsExpanded} onToggle={() => setThoughtsExpanded(p => !p)} />
      <FinalSummaryMessage finalSummary={turn.finalSummary} />
      <SystemMessageAccordion
        systemLog={turn.systemLog}
        expanded={systemLogExpanded}
        onToggle={() => setSystemLogExpanded(p => !p)}
      />
    </div>
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
  onAnswerQuestion?: (params: { callId: string; answer: string | null; skipped: boolean }) => void;
  isWaitingForUser?: boolean;
}

export default function MessageCanvas({
  turns,
  toolsExpanded,
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
  onAnswerQuestion,
  isWaitingForUser,
}: MessageCanvasProps) {
  // Split turns into history (older) vs latest bot turn for sticky-top.
  const lastBotIdx = (() => {
    for (let i = turns.length - 1; i >= 0; i -= 1) {
      if (turns[i].type === 'bot') return i;
    }
    return -1;
  })();
  const latestBot: BotTurn | null = lastBotIdx >= 0 ? (turns[lastBotIdx] as BotTurn) : null;
  const historyTurns: ChatTurn[] = lastBotIdx >= 0 ? turns.slice(0, lastBotIdx) : turns;

  const handleQuestionSubmit = useCallback(
    async (params: { callId: string; answer: string | null; skipped: boolean }) => {
      if (onAnswerQuestion) await onAnswerQuestion(params);
    },
    [onAnswerQuestion],
  );
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const [showScrollTop, setShowScrollTop] = useState(false);
  const [showScrollBottom, setShowScrollBottom] = useState(false);

  // Standard chat semantics: chronological top-to-bottom in DOM, auto-scroll
  // to BOTTOM where the latest live turn sits. `isAtBottomRef` is the
  // "follow newest" sentinel — true when the user is parked at the bottom
  // of the chat (the default reading position).
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
    const timer = setTimeout(updateScrollState, 100);
    return () => clearTimeout(timer);
  }, [turns, updateScrollState]);

  useLayoutEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    if (isAtBottomRef.current) {
      // Auto-follow: pin to the bottom where the latest live turn sits.
      container.scrollTo({ top: container.scrollHeight, behavior: 'auto' });
    } else {
      container.scrollTop = scrollPositionRef.current;
    }
  }, [turns, toolsExpanded, thoughtsExpanded, systemLogExpanded]);

  const scrollToTop = () => {
    scrollContainerRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  };

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
    <div className="relative flex min-h-0 flex-1 flex-col overflow-x-hidden pb-3">

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

      {/*
        Chronological chat layout: oldest at top, newest at bottom. Auto-scroll
        keeps the latest live bot turn parked at the bottom of the viewport.
        A horizontal rule sits ABOVE the latest live turn to separate it from
        the frozen past (frozen previous bot turns + qa_pair past blocks).
      */}
      <div ref={scrollContainerRef} onScroll={handleScroll} className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden px-6 py-5 chat-scrollbar">
        <div className="relative mx-auto flex w-full max-w-3xl min-w-0 flex-col gap-1.5 overflow-x-hidden">

          {/* History (older turns) — chronological top-to-bottom (oldest
              first, newest just before the separator). */}
          {historyTurns.map((turn) => {
            if (turn.type === 'user') {
              const userTurn = turn as UserTurn;
              return (
                <UserMessage
                  key={userTurn.id}
                  text={userTurn.text}
                  attachedEventsCount={userTurn.attachedEvents?.length || 0}
                />
              );
            }
            if (turn.type === 'qa_pair') {
              return <QAPairMessage key={turn.id} turn={turn as QAPairTurn} />;
            }
            return (
              <FrozenBotTurn
                key={turn.id}
                turn={turn as BotTurn}
              />
            );
          })}

          {/* Latest (live) bot turn — at the BOTTOM of DOM. Auto-scroll
              parks the viewport here. */}
          {latestBot && (
            <div key={latestBot.id} className="flex min-w-0 max-w-full flex-col gap-1.5 overflow-x-hidden">
              <ThoughtsAccordion thoughtHistory={latestBot.thoughtHistory} expanded={thoughtsExpanded} onToggle={onToggleThoughts} />
              <WaitingDots visible={latestBot.isStreaming && !latestBot.activeThinkingBubble && !latestBot.finalSummary && !latestBot.pendingQuestion} />
              <ActiveToolIndicator activeTool={latestBot.activeToolIndicator} />
              <ActivePruningIndicator activePruningChunk={latestBot.activePruningChunk} />
              <ActiveThinkingBubble activeThinking={latestBot.activeThinkingBubble} thinkingEndRef={thinkingEndRef} />
              <FinalSummaryMessage finalSummary={latestBot.finalSummary} summaryEndRef={summaryEndRef} />
              <SystemMessageAccordion
                systemLog={latestBot.systemLog}
                expanded={systemLogExpanded}
                onToggle={onToggleSystemLog}
              />
              {latestBot.pendingQuestion && (
                <QuestionCard
                  pendingQuestion={latestBot.pendingQuestion}
                  disabled={!isWaitingForUser}
                  onSubmit={handleQuestionSubmit}
                />
              )}
              <ErrorRecoveryMessage systemLog={latestBot.systemLog} errorType={errorType} onRetry={onRetry} />
            </div>
          )}

          <div ref={messageEndRef} />
        </div>
      </div>
    </div>
  );
}
