import { useState, useCallback, useRef } from 'react';
import { motion } from 'framer-motion';
import { Send, SkipForward, Loader2 } from 'lucide-react';
import { EASE_OUT_EXPO } from './constants';
import { BotAvatar } from './Atoms';
import type { PendingQuestion } from './types';

interface QuestionCardProps {
  pendingQuestion: PendingQuestion;
  disabled?: boolean;
  onSubmit: (params: { callId: string; answer: string | null; skipped: boolean }) => void | Promise<void>;
}

/**
 * Layout: bot avatar + question text (no bg, like the summary), then ONE
 * pill per row — including a final "type your own answer" pill that is
 * styled identically to the option pills but contains an input.
 *
 * Free-text-vs-chip rules:
 *   - Selecting a chip while the textarea has content stashes the textarea
 *     content and visually clears it. Selecting another chip leaves the
 *     stash alone.
 *   - Deselecting all chips restores the stashed text into the textarea.
 *   - Submitting prefers free text when present; otherwise the joined
 *     selected options.
 *
 * Buttons:
 *   - "Send" only renders when the user has at least one selection or some
 *     non-empty free text. Never disabled.
 *   - "Skip" only renders when the user has selected nothing AND typed
 *     nothing AND the question is skippable.
 */
export default function QuestionCard({ pendingQuestion, disabled, onSubmit }: QuestionCardProps) {
  const [submitting, setSubmitting] = useState(false);
  const {
    callId,
    question,
    options,
    answerType,
    skippable,
    selectedOptions: initialSelected,
    customAnswer: initialCustom,
    stashedFreeText: initialStash,
  } = pendingQuestion;

  const [selected, setSelected] = useState<string[]>(initialSelected);
  const [freeText, setFreeText] = useState<string>(initialCustom);
  const stashRef = useRef<string>(initialStash);

  const isMulti = answerType === 'multiple';
  const hasSelection = selected.length > 0;
  const hasFreeText = freeText.trim().length > 0;

  const showSend = !disabled && (hasSelection || hasFreeText);
  const showSkip = !disabled && skippable && !hasSelection && !hasFreeText;

  const toggleOption = useCallback(
    (opt: string) => {
      if (disabled || submitting) return;
      // Activating a chip while free text is present: stash it and clear.
      if (hasFreeText) {
        stashRef.current = freeText;
        setFreeText('');
      }
      setSelected((prev) => {
        if (isMulti) {
          return prev.includes(opt) ? prev.filter((o) => o !== opt) : [...prev, opt];
        }
        return prev.includes(opt) ? [] : [opt];
      });
    },
    [disabled, submitting, hasFreeText, freeText, isMulti],
  );

  const handleFreeTextChange = useCallback(
    (value: string) => {
      setFreeText(value);
      if (value.trim().length > 0 && selected.length > 0) {
        // Typing into the input overrides chips.
        setSelected([]);
      } else if (value.length === 0 && stashRef.current && !hasSelection) {
        // (no-op — the input is the live source while user is typing)
      }
    },
    [selected.length, hasSelection],
  );

  // When chips become deselected entirely, restore the stash if any.
  const handleChipPossiblyDeselectedToZero = useCallback(() => {
    if (selected.length === 0 && !hasFreeText && stashRef.current) {
      const stash = stashRef.current;
      setFreeText(stash);
      stashRef.current = '';
    }
  }, [selected.length, hasFreeText, stashRef]);

  const submit = useCallback(
    async (skip: boolean) => {
      if (submitting || disabled) return;
      setSubmitting(true);
      const payload =
        skip
          ? { callId, answer: null, skipped: true }
          : hasFreeText
          ? { callId, answer: freeText.trim(), skipped: false }
          : { callId, answer: selected.join(', '), skipped: false };
      try {
        await onSubmit(payload);
      } finally {
        setSubmitting(false);
      }
    },
    [submitting, disabled, callId, freeText, hasFreeText, selected, onSubmit],
  );

  // Shared pill base styling — option chips AND the text-input pill use
  // this so they look identical. The only difference is the input pill
  // contains a textarea instead of a button label.
  const pillBase =
    'w-full px-4 py-2.5 rounded-full text-base sm:text-sm font-semibold tracking-wide transition-all border text-left';
  const pillIdle =
    'bg-white/[0.04] border-white/10 text-white/70 hover:text-white hover:border-cyan/40';
  const pillActive =
    'bg-cyan text-black border-cyan shadow-[0_0_15px_rgba(102,252,241,0.4)]';

  return (
    <motion.div
      key={`question-${callId}`}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.35, ease: EASE_OUT_EXPO }}
      className="flex items-start gap-3 py-2"
    >
      <BotAvatar className="mt-0.5" />
      <div className="flex-1 flex flex-col gap-2.5">
        {/* Question text — same look as a final-summary message: no bg,
            just the prose-ish text in white/85. */}
        <div className="text-sm text-white/85 leading-relaxed pt-0">
          {question}
        </div>

        {/* Option chips — ONE PER LINE so they are easy to scan / tap. */}
        <div className="flex flex-col gap-2">
          {options.map((opt) => {
            const active = selected.includes(opt);
            return (
              <button
                key={opt}
                onClick={() => {
                  toggleOption(opt);
                  // If toggling left selected empty, restore the stashed text.
                  setTimeout(handleChipPossiblyDeselectedToZero, 0);
                }}
                disabled={disabled || submitting}
                className={[
                  pillBase,
                  active ? pillActive : pillIdle,
                  (disabled || submitting) ? 'opacity-50 cursor-not-allowed' : 'active:scale-[0.99]',
                ].join(' ')}
              >
                {opt}
              </button>
            );
          })}

          {/* Free-text pill — same shape as option pills, but contains
              a single-line auto-growing textarea. Looks exactly like the
              other chips, just with a placeholder when empty. */}
          <div
            className={[
              pillBase,
              pillIdle,
              'flex items-center cursor-text py-2',
              (disabled || submitting) ? 'opacity-50 cursor-not-allowed' : '',
            ].join(' ')}
            onClick={(e) => {
              const el = (e.currentTarget.querySelector('textarea') as HTMLTextAreaElement | null);
              el?.focus();
            }}
          >
            <textarea
              value={freeText}
              onChange={(e) => handleFreeTextChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  if (showSend) submit(false);
                }
              }}
              onInput={(e) => {
                const t = e.target as HTMLTextAreaElement;
                t.style.height = 'auto';
                t.style.height = `${Math.min(t.scrollHeight, 96)}px`;
              }}
              placeholder="Type in your answer…"
              disabled={disabled || submitting}
              rows={1}
              className="w-full bg-transparent border-none focus:outline-none focus:ring-0 resize-none scrollbar-hide text-base sm:text-sm font-semibold tracking-wide placeholder:text-white/40 placeholder:font-semibold"
              style={{ minHeight: '20px', maxHeight: '96px', color: 'inherit' }}
            />
          </div>
        </div>

        {/* Action row — only ONE of Send / Skip is visible at any time. */}
        {(showSend || showSkip) && (
          <div className="flex items-center gap-2 justify-end pt-1">
            {showSend && (
              <button
                onClick={() => submit(false)}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-full text-[11px] font-bold uppercase tracking-wider bg-cyan text-black hover:scale-105 active:scale-95 transition-all shadow-[0_0_10px_rgba(102,252,241,0.25)]"
              >
                {submitting ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                  <Send className="w-3 h-3" />
                )}
                <span>Send</span>
              </button>
            )}
            {showSkip && (
              <button
                onClick={() => submit(true)}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-full text-[11px] font-bold uppercase tracking-wider text-white/60 hover:text-white/90 hover:bg-white/[0.04] border border-white/10 transition-all"
              >
                <SkipForward className="w-3 h-3" />
                <span>Skip</span>
              </button>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}
