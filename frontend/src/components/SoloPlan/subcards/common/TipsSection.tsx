import { Sparkles } from 'lucide-react';

interface TipsSectionProps {
  title?: string;
  tips?: string | null;
}

/**
 * Pretty-prints a tips string. Splits on newlines or numbered/bulleted markers.
 * Falls back to a single paragraph when no clear delimiters exist.
 */
export default function TipsSection({ title = 'Tips', tips }: TipsSectionProps) {
  if (!tips) return null;
  const cleaned = tips.trim();
  if (!cleaned) return null;

  const byNewline = cleaned
    .split(/\r?\n+/)
    .map((s) => s.replace(/^\s*(?:[-•*]|\d+[.)])\s*/, '').trim())
    .filter(Boolean);

  const items = byNewline.length > 1 ? byNewline : [cleaned];

  return (
    <div className="mt-4 rounded-xl bg-cyan/[0.04] border border-cyan/15 p-4">
      <div className="flex items-center gap-2 text-cyan text-xs font-bold uppercase tracking-wider mb-3">
        <Sparkles className="w-3.5 h-3.5" />
        {title}
      </div>
      <ul className="space-y-2">
        {items.map((item, i) => (
          <li key={i} className="text-xs text-white/75 leading-relaxed border-l-2 border-cyan/30 pl-3">
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
