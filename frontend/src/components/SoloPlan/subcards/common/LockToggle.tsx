import { Lock, LockOpen } from 'lucide-react';

interface LockToggleProps {
  isLocked: boolean;
  onToggle: () => void;
}

export default function LockToggle({ isLocked, onToggle }: LockToggleProps) {
  return (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); onToggle(); }}
      className={`p-1.5 rounded-lg transition-all cursor-pointer ${
        isLocked
          ? 'text-cyan/70 hover:text-cyan hover:bg-cyan/10'
          : 'text-white/25 hover:text-white/50 hover:bg-white/5'
      }`}
      title={isLocked ? 'Locked — click to unlock' : 'Unlocked — click to lock'}
    >
      {isLocked
        ? <Lock className="w-3.5 h-3.5" />
        : <LockOpen className="w-3.5 h-3.5" />
      }
    </button>
  );
}
