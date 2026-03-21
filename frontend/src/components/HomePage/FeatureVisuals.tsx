import { useEffect, useState } from 'react';
import {
  Plane, Utensils, Lock, GripVertical, ArrowRightLeft,
  ThumbsUp, ThumbsDown, Send, MapPin, Navigation,
  CloudRain, Bell, Sun
} from 'lucide-react';

/* ─── 1. Smart Anchors ─── */
export function AnchorsVisual() {
  const [pulse, setPulse] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setPulse((p) => (p + 1) % 3), 1800);
    return () => clearInterval(id);
  }, []);

  const items = [
    { label: 'Flight SFO→LAS', time: '2:00 PM', locked: true },
    { label: 'Hotel Check-in', time: '5:30 PM', locked: false },
    { label: 'Dinner at Hell\'s Kitchen', time: '8:00 PM', locked: true },
  ];

  return (
    <div className="flex flex-col gap-3 w-full">
      {items.map((item, i) => (
        <div
          key={i}
          className={`flex items-center gap-3 rounded-xl px-4 py-3 border transition-all duration-500 ${item.locked
              ? `border-cyan/30 bg-cyan/[0.06] ${pulse === i ? 'shadow-[0_0_20px_rgba(102,252,241,0.15)]' : ''}`
              : 'border-white/[0.06] bg-white/[0.02]'
            }`}
        >
          {item.locked ? (
            <Lock size={14} className="text-cyan shrink-0" />
          ) : (
            <div className="w-3.5 h-3.5 rounded-full border border-white/20 shrink-0" />
          )}
          <div className="flex-1 min-w-0">
            <p className={`text-xs font-medium truncate ${item.locked ? 'text-cyan' : 'text-white/60'}`}>
              {item.label}
            </p>
          </div>
          <span className="text-[10px] tabular-nums text-white/30">{item.time}</span>
        </div>
      ))}
    </div>
  );
}

/* ─── 2. Auto-Shuffling ─── */
export function ShuffleVisual() {
  const [shifted, setShifted] = useState(false);
  useEffect(() => {
    const id = setInterval(() => setShifted((s) => !s), 2500);
    return () => clearInterval(id);
  }, []);

  const blocks = [
    { label: 'Museum Visit', dur: shifted ? 'h-14' : 'h-10', color: 'bg-cyan/15 border-cyan/30' },
    { label: 'Lunch Break', dur: 'h-8', color: 'bg-white/[0.04] border-white/10' },
    { label: 'Walking Tour', dur: shifted ? 'h-8' : 'h-12', color: 'bg-white/[0.04] border-white/10' },
    { label: 'Dinner', dur: 'h-10', color: 'bg-cyan/15 border-cyan/30', locked: true },
  ];

  return (
    <div className="flex gap-2.5 items-end w-full h-48">
      {blocks.map((b, i) => (
        <div key={i} className="flex-1 flex flex-col items-center gap-1.5">
          <div className={`w-full ${b.dur} rounded-lg border ${b.color} flex flex-col items-center justify-center gap-1 transition-all duration-700`}>
            {i === 0 && <GripVertical size={12} className="text-cyan/40" />}
            {b.locked && <Lock size={10} className="text-cyan/50" />}
          </div>
          <span className="text-[9px] text-white/30 truncate max-w-full">{b.label}</span>
        </div>
      ))}
    </div>
  );
}

/* ─── 3. Surgical Swaps ─── */
export function SwapVisual() {
  const [swapped, setSwapped] = useState(false);
  useEffect(() => {
    const id = setInterval(() => setSwapped((s) => !s), 3000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex items-center gap-3 w-full justify-center">
      <div className={`flex-1 rounded-xl border px-4 py-5 text-center transition-all duration-700 ${swapped
          ? 'border-cyan/30 bg-cyan/[0.08] scale-105'
          : 'border-white/10 bg-white/[0.03] opacity-50 scale-95'
        }`}>
        <Utensils size={18} className={`mx-auto mb-2 transition-colors duration-500 ${swapped ? 'text-cyan' : 'text-white/30'}`} />
        <p className="text-[11px] font-medium text-white/60">Food Tour</p>
        <p className="text-[9px] text-white/25 mt-0.5">2:00 – 4:00 PM</p>
      </div>

      <ArrowRightLeft size={16} className="text-cyan/40 shrink-0 animate-pulse" />

      <div className={`flex-1 rounded-xl border px-4 py-5 text-center transition-all duration-700 ${!swapped
          ? 'border-cyan/30 bg-cyan/[0.08] scale-105'
          : 'border-white/10 bg-white/[0.03] opacity-50 scale-95'
        }`}>
        <MapPin size={18} className={`mx-auto mb-2 transition-colors duration-500 ${!swapped ? 'text-cyan' : 'text-white/30'}`} />
        <p className="text-[11px] font-medium text-white/60">Museum</p>
        <p className="text-[9px] text-white/25 mt-0.5">2:00 – 4:00 PM</p>
      </div>
    </div>
  );
}

/* ─── 4. Customized Pacing ─── */
export function PacingVisual() {
  const [level, setLevel] = useState(1);
  useEffect(() => {
    const id = setInterval(() => setLevel((l) => (l + 1) % 3), 2200);
    return () => clearInterval(id);
  }, []);

  const labels = ['Leisurely', 'Balanced', 'Action-Packed'];
  const counts = [3, 5, 8];

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-4">
        {labels.map((l, i) => (
          <span
            key={l}
            className={`text-[10px] font-medium transition-all duration-500 ${i === level ? 'text-cyan scale-110' : 'text-white/25'}`}
          >
            {l}
          </span>
        ))}
      </div>
      <div className="h-2 rounded-full bg-white/[0.06] overflow-hidden mb-5">
        <div
          className="h-full rounded-full bg-gradient-to-r from-cyan-dim to-cyan transition-all duration-700"
          style={{ width: `${((level + 1) / 3) * 100}%` }}
        />
      </div>
      <div className="flex gap-1.5 justify-center">
        {Array.from({ length: counts[level] }).map((_, i) => (
          <div
            key={i}
            className="h-8 flex-1 rounded-md bg-cyan/10 border border-cyan/20 transition-all duration-500"
            style={{ animationDelay: `${i * 80}ms` }}
          />
        ))}
      </div>
      <p className="text-center text-[10px] text-white/25 mt-2">{counts[level]} activities per day</p>
    </div>
  );
}

/* ─── 5. Multiplayer ─── */
export function MultiplayerVisual() {
  const [votes, setVotes] = useState([1, 0, -1]);
  useEffect(() => {
    const id = setInterval(() => {
      setVotes((v) => v.map(() => [-1, 0, 1][Math.floor(Math.random() * 3)]));
    }, 2000);
    return () => clearInterval(id);
  }, []);

  const activities = ['Eiffel Tower', 'Louvre Museum', 'Seine Cruise'];
  const avatarColors = ['bg-cyan/30', 'bg-purple-400/30', 'bg-amber-400/30'];

  return (
    <div className="w-full">
      <div className="flex items-center gap-2 mb-4">
        {avatarColors.map((c, i) => (
          <div key={i} className={`w-7 h-7 rounded-full ${c} border border-white/10 -ml-${i > 0 ? '2' : '0'}`} />
        ))}
        <span className="text-[10px] text-white/30 ml-1">3 collaborators</span>
      </div>
      <div className="flex flex-col gap-2">
        {activities.map((a, i) => (
          <div key={a} className="flex items-center gap-3 rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
            <span className="text-[11px] text-white/60 flex-1">{a}</span>
            <div className="flex items-center gap-2">
              <ThumbsUp size={12} className={`transition-colors duration-500 ${votes[i] === 1 ? 'text-cyan' : 'text-white/15'}`} />
              <ThumbsDown size={12} className={`transition-colors duration-500 ${votes[i] === -1 ? 'text-red-400/60' : 'text-white/15'}`} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── 6. Conversational Context ─── */
export function ConversationalVisual() {
  const [typing, setTyping] = useState(false);
  const [showReply, setShowReply] = useState(false);

  useEffect(() => {
    const cycle = () => {
      setTyping(true);
      setShowReply(false);
      setTimeout(() => {
        setTyping(false);
        setShowReply(true);
      }, 2000);
    };
    cycle();
    const id = setInterval(cycle, 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="w-full flex flex-col gap-3">
      <div className="self-end max-w-[85%] rounded-2xl rounded-br-sm bg-cyan/10 border border-cyan/20 px-4 py-2.5">
        <p className="text-[11px] text-cyan/80">
          "5 days in Tokyo, mix of tourist spots and chill evenings, I love ramen"
        </p>
      </div>
      {typing && (
        <div className="self-start flex items-center gap-1.5 px-3 py-2">
          <span className="w-1.5 h-1.5 rounded-full bg-white/30 animate-bounce" style={{ animationDelay: '0ms' }} />
          <span className="w-1.5 h-1.5 rounded-full bg-white/30 animate-bounce" style={{ animationDelay: '150ms' }} />
          <span className="w-1.5 h-1.5 rounded-full bg-white/30 animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
      )}
      {showReply && (
        <div className="self-start max-w-[85%] rounded-2xl rounded-bl-sm bg-white/[0.04] border border-white/[0.08] px-4 py-2.5 animate-[fade-in_0.4s_ease-out]">
          <p className="text-[11px] text-white/60">
            Day 1: Shibuya → Meiji Shrine → Ichiran Ramen
          </p>
          <p className="text-[10px] text-white/30 mt-1">Generating 5 days...</p>
        </div>
      )}
      <div className="flex items-center gap-2 rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2 mt-1">
        <span className="text-[11px] text-white/20 flex-1">Describe your trip vibe...</span>
        <Send size={13} className="text-cyan/40" />
      </div>
    </div>
  );
}

/* ─── 7. Real-World Grounded ─── */
export function MapVisual() {
  const [activePin, setActivePin] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setActivePin((p) => (p + 1) % 3), 2000);
    return () => clearInterval(id);
  }, []);

  const pins = [
    { label: 'Eiffel Tower', status: 'Open Now', x: 25, y: 35 },
    { label: 'Le Meurice', status: 'Verified', x: 55, y: 50 },
    { label: 'Louvre', status: 'Open until 6 PM', x: 70, y: 30 },
  ];

  return (
    <div className="w-full">
      <div className="relative rounded-xl border border-white/[0.06] bg-white/[0.02] h-40 overflow-hidden">
        {/* Grid lines for map feel */}
        <div className="absolute inset-0 opacity-[0.03]" style={{
          backgroundImage: 'linear-gradient(white 1px, transparent 1px), linear-gradient(90deg, white 1px, transparent 1px)',
          backgroundSize: '24px 24px',
        }} />
        {/* Route line */}
        <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
          <polyline
            points={pins.map((p) => `${p.x},${p.y}`).join(' ')}
            fill="none"
            stroke="rgba(102,252,241,0.2)"
            strokeWidth="1.5"
            strokeDasharray="6 4"
          />
        </svg>
        {/* Pins */}
        {pins.map((pin, i) => (
          <div
            key={i}
            className="absolute flex flex-col items-center transition-all duration-500"
            style={{ left: `${pin.x}%`, top: `${pin.y}%`, transform: 'translate(-50%, -100%)' }}
          >
            <Navigation
              size={16}
              className={`transition-all duration-500 ${i === activePin ? 'text-cyan scale-125' : 'text-white/25'}`}
            />
            {i === activePin && (
              <span className="mt-1 text-[8px] text-cyan whitespace-nowrap bg-midnight/80 px-1.5 py-0.5 rounded">
                {pin.status}
              </span>
            )}
          </div>
        ))}
      </div>
      <div className="flex items-center gap-4 mt-3">
        {pins.map((pin, i) => (
          <span key={i} className={`text-[10px] transition-colors duration-500 ${i === activePin ? 'text-cyan' : 'text-white/25'}`}>
            {pin.label}
          </span>
        ))}
      </div>
    </div>
  );
}

/* ─── 8. Live Concierge ─── */
export function ConciergeVisual() {
  const [activeCard, setActiveCard] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setActiveCard((c) => (c + 1) % 3), 2500);
    return () => clearInterval(id);
  }, []);

  const cards = [
    {
      icon: Sun,
      title: 'Morning Summary',
      body: '3 activities today · 24°C and sunny',
      accent: 'border-cyan/25 bg-cyan/[0.06]',
    },
    {
      icon: CloudRain,
      title: 'Weather Alert',
      body: 'Rain at 3PM — swap park walk for indoor gallery?',
      accent: 'border-amber-400/25 bg-amber-400/[0.06]',
    },
    {
      icon: Plane,
      title: 'Flight Delayed +2h',
      body: 'Tap to auto-compress Day 1 itinerary',
      accent: 'border-red-400/25 bg-red-400/[0.06]',
    },
  ];

  return (
    <div className="w-full flex flex-col gap-2.5">
      {cards.map((card, i) => (
        <div
          key={i}
          className={`flex items-start gap-3 rounded-xl border px-4 py-3 transition-all duration-500 ${i === activeCard ? `${card.accent} scale-[1.02]` : 'border-white/[0.04] bg-white/[0.01] opacity-40 scale-100'
            }`}
        >
          <div className="mt-0.5 shrink-0">
            {i === activeCard ? (
              <Bell size={14} className="text-cyan animate-[wiggle_0.5s_ease-in-out]" />
            ) : (
              <card.icon size={14} className="text-white/20" />
            )}
          </div>
          <div className="min-w-0">
            <p className={`text-[11px] font-medium ${i === activeCard ? 'text-white/80' : 'text-white/30'}`}>
              {card.title}
            </p>
            <p className={`text-[10px] mt-0.5 ${i === activeCard ? 'text-white/50' : 'text-white/15'}`}>
              {card.body}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
