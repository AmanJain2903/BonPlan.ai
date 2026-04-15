import { motion } from 'framer-motion';
import { Bot } from 'lucide-react';
import { BOUNCE_DOT_TRANSITION } from './constants';

/** Small cyan bot avatar used in multiple message rows */
export function BotAvatar({ icon: Icon = Bot, className = '' }: { icon?: typeof Bot; className?: string }) {
  return (
    <div className={`w-7 h-7 rounded-full bg-cyan/10 border border-cyan/20 flex items-center justify-center shrink-0 ${className}`}>
      <Icon className="w-3.5 h-3.5 text-cyan" />
    </div>
  );
}

/** Three bouncing dot animation */
export function BouncingDots() {
  return (
    <>
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-cyan/40"
          animate={{ y: [0, -3, 0], opacity: [0.3, 0.8, 0.3] }}
          transition={BOUNCE_DOT_TRANSITION(i)}
        />
      ))}
    </>
  );
}
