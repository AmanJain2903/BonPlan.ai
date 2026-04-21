import { motion, AnimatePresence } from 'framer-motion';
import { Bot, Info, Sparkles } from 'lucide-react';


interface HeroPanelProps {
  plannerMode: 'autonomous' | 'collaborative';
  setPlannerMode: (mode: 'autonomous' | 'collaborative') => void;
  contextInput: string;
  setContextInput: (val: string) => void;
  onStart: () => void;
}


function AutoResizeTextarea({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (val: string) => void;
  placeholder: string;
}) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onInput={(e) => {
        const target = e.target as HTMLTextAreaElement;
        target.style.height = 'auto';
        target.style.height = `${Math.min(target.scrollHeight, 120)}px`;
      }}
      placeholder={placeholder}
      className="w-full bg-transparent border-none text-white text-sm focus:outline-none focus:ring-0 py-3 resize-none overflow-y-auto scrollbar-hide"
      rows={1}
      style={{ minHeight: '44px', maxHeight: '120px' }}
    />
  );
}

export default function HeroPanel({ plannerMode, setPlannerMode, contextInput, setContextInput, onStart }: HeroPanelProps) {
  return (
    <motion.div
      key="hero"
      initial={{ opacity: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.3 }}
      className="flex-1 flex flex-col min-h-0"
    >
      <div className="flex-1 flex flex-col items-center justify-center min-h-0 overflow-y-auto px-6 py-6 sm:px-14 scrollbar-hide">
        <div className="flex items-center justify-center mb-6 shrink-0 mt-auto">
          <Bot className="w-16 h-16 text-cyan" />
        </div>

        <div className="text-center mb-8 shrink-0">
          <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">BonPlan AI Travel Planner</h2>
          <p className="text-white/60 text-sm">
            Your trip parameters are locked in. Choose your planning mode and generate your detailed end-to-end
            itinerary.
          </p>
        </div>

        {/* Mode Toggle */}
        <div className="flex flex-col items-center gap-4 w-full shrink-0 mb-auto">
          <div className="flex flex-col items-center max-w-md w-full gap-2">
            <div className="flex items-center justify-between bg-black/50 border border-white/10 rounded-full p-1.5 w-full relative">
              <button
                onClick={() => setPlannerMode('autonomous')}
                className={`flex-1 flex items-center justify-center py-2.5 px-4 rounded-full text-xs font-bold uppercase tracking-wider transition-all duration-300 z-10 ${plannerMode === 'autonomous' ? 'text-black bg-cyan shadow-[0_0_15px_rgba(102,252,241,0.4)]' : 'text-white/50 hover:text-white'}`}
              >
                Autonomous
              </button>
              <button
                onClick={() => {}}
                disabled
                className="flex-1 flex items-center justify-center py-2.5 px-4 rounded-full text-xs font-bold uppercase tracking-wider transition-all duration-300 z-10 text-white/30 cursor-not-allowed"
                title="Collaborative Mode Coming Soon"
              >
                Collaborative
              </button>
            </div>

            <AnimatePresence mode="wait">
              <motion.div
                key={plannerMode}
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -5 }}
                transition={{ duration: 0.2 }}
                className="flex items-start justify-center gap-2 text-center px-4"
              >
                <Info className="w-4 h-4 text-cyan shrink-0 mt-0.5" />
                <p className="text-xs text-white/50 leading-relaxed">
                  {plannerMode === 'autonomous'
                    ? "The AI takes full control. It will independently research, construct routes, lock in flights & hotels, and output the entire finalized trip without asking questions."
                    : "The AI will build the trip step-by-step alongside you, pausing to ask for your confirmation and offering options before locking in bookings."}
                </p>
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </div>

      {/* Bottom: Chat + Start Button */}
      <div className="w-full shrink-0 flex flex-col px-6 pb-6 sm:px-14 sm:pb-8 mt-auto">
        <div className="w-full max-w-4xl mx-auto flex flex-col">
          <div className="relative group w-full mb-4">
            <div className="absolute -inset-0.5 bg-gradient-to-r from-cyan/30 to-blue/30 rounded-2xl blur opacity-20 group-hover:opacity-40 transition duration-500" />
            <div className="relative flex items-end bg-black border border-white/10 rounded-2xl p-2 px-4 focus-within:border-cyan/50 transition-colors">
              <AutoResizeTextarea
                value={contextInput}
                onChange={setContextInput}
                placeholder="Add any conversational context you want to provide, or leave blank for a surprise"
              />
            </div>
          </div>

          <button
            onClick={onStart}
            className="w-full relative group overflow-hidden rounded-2xl bg-cyan text-black font-bold py-4 px-6 transition-all hover:scale-[1.02] active:scale-[0.98] shadow-[0_0_20px_rgba(102,252,241,0.2)] hover:shadow-[0_0_40px_rgba(102,252,241,0.4)] flex items-center justify-center gap-3"
          >
            <Sparkles className="w-5 h-5 fill-black" />
            <span className="uppercase tracking-widest text-sm relative z-10 transition-transform group-hover:-translate-x-1 duration-300">
              Start {plannerMode} Planning
            </span>
          </button>
        </div>
      </div>
    </motion.div>
  );
}
