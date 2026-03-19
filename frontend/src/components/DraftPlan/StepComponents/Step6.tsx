import { useEffect, useRef, useState } from 'react';
import { Sparkles } from 'lucide-react';
import type { TripData } from '../../../context/TripContext';
import { PLACEHOLDERS, CHIPS } from '../../../data/conversations';

type Props = {
  tripData: TripData | null;
  updateTripData: (patch: Partial<TripData>) => void;
  onNext: () => void;
  registerCommit?: (fn: () => void) => void;
};

function appendToken(prev: string, token: string) {
  const trimmed = prev.trim();
  if (!trimmed) return token;
  const needsComma = !/[,.!?]$/.test(trimmed);
  return `${trimmed}${needsComma ? ',' : ''} ${token}`;
}

export function Step6Conversation({ tripData, updateTripData, onNext, registerCommit }: Props) {
  const [value, setValue] = useState(() => tripData?.conversationalContext ?? '');
  const [placeholderIdx, setPlaceholderIdx] = useState(0);
  const [chips, setChips] = useState(CHIPS);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Auto-resize textarea as user types (no scrollbar)
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);

  // Cycle placeholder every ~3.5s
  useEffect(() => {
    const id = window.setInterval(() => {
      setPlaceholderIdx((i) => (i + 1) % PLACEHOLDERS.length);
    }, 3500);
    return () => window.clearInterval(id);
  }, []);

  // Shuffle chips on every page load
  useEffect(() => {
    const shuffledChips = [...CHIPS].sort(() => Math.random() - 0.5);
    setChips(shuffledChips);
  }, [CHIPS]);

  const hasText = value.trim().length > 0;

  const onConfirm = () => {
    updateTripData({ conversationalContext: value.trim() });
    onNext();
  };

  useEffect(() => {
    registerCommit?.(() => {
      updateTripData({ conversationalContext: value.trim() });
    });
  }, [registerCommit, updateTripData, value]);

  return (
    <>
    <div className={`w-full max-w-5xl animate-[fade-in_400ms_ease-out] ${hasText ? 'pb-24' : ''}`}>
      {/* Chip rail */}
      <div className="w-full relative [mask-image:linear-gradient(to_right,transparent,black_5%,black_95%,transparent)]">
        <div className="w-full overflow-x-auto scrollbar-hide">
          <div className="flex gap-3 min-w-max pb-3 px-4">
            
            {chips.map((chip) => (
              <button
                key={chip}
                type="button"
                onClick={() => setValue((prev) => appendToken(prev, chip))}
                className="group relative rounded-full border px-4 py-2 text-left transition-all duration-300 cursor-pointer overflow-hidden border-white/[0.08] bg-white/[0.02] hover:border-cyan/25 hover:bg-cyan/5 hover:shadow-[0_0_28px_rgba(102,252,241,0.06)]"
              >
                <div
                  className="pointer-events-none absolute -inset-10 opacity-0 group-hover:opacity-100 transition-opacity duration-300 blur-2xl"
                  style={{
                    background: 'radial-gradient(circle at 40% 40%, rgba(102,252,241,0.14), transparent 60%)',
                  }}
                />
                <span className="relative text-xs font-semibold text-white/80">{chip}</span>
              </button>
            ))}
            
          </div>
        </div>
      </div>

      {/* Textarea card */}
      <div className="group relative mt-2 rounded-2xl border border-white/[0.08] bg-carbon/40 backdrop-blur-sm p-8 overflow-hidden">
        <div className="pointer-events-none absolute -inset-24 opacity-0 group-hover:opacity-100 transition-opacity duration-300 blur-3xl">
          <div
            className="absolute inset-0"
            style={{
              background: 'radial-gradient(circle at 30% 20%, rgba(102,252,241,0.18), transparent 58%)',
            }}
          />
        </div>

        <div className="relative flex items-center gap-3 mb-3">
          <div className="h-11 w-11 rounded-xl bg-cyan/10 border border-cyan/15 flex items-center justify-center">
            <Sparkles size={18} className="text-cyan" />
          </div>
          <div className="min-w-0">
            <h2 className="text-lg font-bold text-white group-hover:text-cyan transition-colors">
              Paint a picture of your ideal trip
            </h2>
            <p className="text-xs text-white/35">Any must-dos, dietary needs, or hidden gems you're chasing? The more details, the better the plan</p>
          </div>
        </div>

        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={PLACEHOLDERS[placeholderIdx]}
          rows={4}
          className="relative w-full rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-4 text-sm text-white/85 placeholder:text-white/30 outline-none transition-all focus:border-cyan/35 focus:ring-2 focus:ring-cyan/15 resize-none overflow-hidden"
          style={{ minHeight: 'calc(8 * 1.5rem + 2rem)' }}
        />
      </div>
      </div>

      {/* Sticky footer pill (same architecture as Step5) */}
        <div className="fixed bottom-0 left-0 w-full z-50 pointer-events-none flex justify-center pb-8 pt-32 bg-gradient-to-t from-black via-black/80 to-transparent">
          <div className="pointer-events-auto">
            <div className="flex items-center gap-4 rounded-full px-6 py-3">
                {hasText ? (
            <span className="text-sm text-white/70 text-center">
                Do you want to
                <span className="text-cyan font-semibold"> LOCK IT IN</span>?
              </span>
              ) : (
                <span className="text-sm text-white/70 text-center">
                Do you want to
                <span className="text-cyan font-semibold"> SKIP THIS STEP</span>?
              </span>
              )}
              <button
                type="button"
                onClick={onConfirm}
                className="ml-2 inline-flex items-center justify-center rounded-full bg-cyan text-midnight font-extrabold text-xs px-4 py-2 transition-transform duration-300 hover:scale-105 hover:bg-[#80fdf6] hover:shadow-[0_0_15px_rgba(102,252,241,0.4)] cursor-pointer"
              >
                YES
              </button>
            </div>
          </div>
        </div>
      <div className="h-16 shrink-0" aria-hidden />
    </>
  );
}

