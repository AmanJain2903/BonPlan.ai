import { useEffect, useState } from 'react';
import { Plane, MapPin, Utensils, Dices, Coffee } from 'lucide-react';

const nodes = [
  { icon: Plane, label: 'Flight From SFO', time: '12:00 PM', anchor: true },
  { icon: Plane, label: 'Flight Lands in LAS', time: '2:00 PM', anchor: true },
  { icon: Coffee, label: 'Check-in at Venetian', time: '4:00 PM', anchor: false },
  { icon: Dices, label: 'Casino at Bellagio', time: '5:15 PM', anchor: false },
  { icon: Utensils, label: 'Dinner at Hell\'s Kitchen', time: '8:00 PM', anchor: true },
  { icon: MapPin, label: 'Night Walk on the Strip', time: '10:00 PM', anchor: false },
];

export default function RoutingVisual() {
  const [activeIndex, setActiveIndex] = useState(-1);
  const [scanX, setScanX] = useState(0);

  useEffect(() => {
    const nodeInterval = setInterval(() => {
      setActiveIndex((prev) => (prev + 1) % nodes.length);
    }, 2000);
    return () => clearInterval(nodeInterval);
  }, []);

  useEffect(() => {
    const scanInterval = setInterval(() => {
      setScanX((prev) => (prev >= 100 ? 0 : prev + 0.5));
    }, 30);
    return () => clearInterval(scanInterval);
  }, []);

  return (
    <div className="relative rounded-2xl border border-white/[0.06] bg-carbon/60 backdrop-blur-sm p-6 sm:p-8 overflow-hidden">
      {/* Scanning beam */}
      <div
        className="pointer-events-none absolute top-0 bottom-0 w-24 z-10 transition-none"
        style={{
          left: `${scanX}%`,
          background: 'linear-gradient(90deg, transparent, rgba(102,252,241,0.06), transparent)',
        }}
      />

      {/* Header */}
      <div className="relative z-20 flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <div className="h-2.5 w-2.5 rounded-full bg-cyan/80 animate-pulse" />
          <span className="text-xs font-medium text-white/50 tracking-wide uppercase">
            AI Route Preview
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[10px] text-cyan/50 font-mono tracking-wider animate-pulse">
            PROCESSING
          </span>
        </div>
      </div>

      {/* Timeline nodes */}
      <div className="relative z-20 overflow-x-auto pt-6 pb-6 px-6 scrollbar-hide" style={{ WebkitOverflowScrolling: 'touch' }}>
        <div className="flex items-center" style={{ minWidth: `${nodes.length * 120}px` }}>
          {nodes.map((node, i) => {
            const isActive = i === activeIndex;
            const isPassed = i < activeIndex;

            return (
              <div key={i} className={`flex items-center ${i < nodes.length - 1 ? 'flex-1' : ''}`}>
                {/* Node */}
                <div className="flex flex-col items-center gap-2 w-[72px] shrink-0 mx-auto">
                  <div
                    className={`
                      relative flex items-center justify-center w-11 h-11 rounded-xl
                      transition-all duration-700
                      ${node.anchor
                        ? 'bg-cyan/15 border border-cyan/40 shadow-[0_0_15px_rgba(102,252,241,0.15)]'
                        : 'bg-white/[0.04] border border-white/10'
                      }
                      ${isActive ? 'scale-110 !shadow-[0_0_25px_rgba(102,252,241,0.35)] !border-cyan/60' : ''}
                      ${isPassed && !node.anchor ? '!bg-cyan/[0.06] !border-cyan/20' : ''}
                    `}
                  >
                    <node.icon
                      size={18}
                      className={`transition-colors duration-500 ${
                        node.anchor || isActive || isPassed ? 'text-cyan' : 'text-white/40'
                      }`}
                    />
                    {node.anchor && (
                      <span className="absolute -top-1 -right-1 flex h-3 w-3">
                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan/50" />
                        <span className="relative inline-flex h-3 w-3 rounded-full bg-cyan" />
                      </span>
                    )}
                    {isActive && !node.anchor && (
                      <span className="absolute -top-1 -right-1 flex h-3 w-3">
                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan/40" />
                      </span>
                    )}
                  </div>
                  <div className="text-center w-full">
                    <p className={`text-[10px] sm:text-xs font-medium truncate transition-colors duration-500 ${
                      node.anchor || isActive || isPassed ? 'text-cyan' : 'text-white/60'
                    }`}>
                      {node.label}
                    </p>
                    <p className="text-[9px] sm:text-[10px] text-white/30 tabular-nums">{node.time}</p>
                  </div>
                </div>

                {/* Connector line */}
                {i < nodes.length - 1 && (
                  <div className="flex-1 relative h-px">
                    <div className="absolute inset-0 bg-gradient-to-r from-white/10 via-white/5 to-white/10" />
                    <div
                      className="absolute inset-y-0 left-0 bg-gradient-to-r from-cyan/60 to-cyan/20 transition-all duration-700"
                      style={{ width: isPassed || isActive ? '100%' : '0%' }}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Bottom status bar */}
      <div className="relative z-20 mt-6 flex items-center gap-3 text-[10px] sm:text-xs text-white/30">
        <span className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-cyan/60" />
          Smart Anchor
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-white/20" />
          AI Generated
        </span>
        <span className="ml-auto tabular-nums text-white/20 hidden sm:inline">
          Transit verified via <span className="text-cyan/40">Google Maps API</span>
        </span>
      </div>
    </div>
  );
}
