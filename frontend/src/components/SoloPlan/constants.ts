// ─── Shared Animation Presets ─────────────────────────────────
export const EASE_OUT_EXPO = [0.16, 1, 0.3, 1] as const;

export const SPRING_PILL = { type: 'spring' as const, stiffness: 400, damping: 30 };

export const BOUNCE_DOT_TRANSITION = (i: number) => ({
  duration: 1.2,
  repeat: Infinity,
  delay: i * 0.2,
  ease: 'easeInOut' as const,
});

export const SHIMMER_WIDTHS = [0.5, 0.7, 0.9, 0.6, 0.8];

// ─── Shared Utilities ─────────────────────────────────────────
export const safelyParseJSON = (jsonString: any) => {
  if (typeof jsonString === 'object') return jsonString;
  try {
    return JSON.parse(jsonString);
  } catch {
    return null;
  }
};

export const formatDate = (dateObj: any) => {
  if (!dateObj) return '';
  const parsed = safelyParseJSON(dateObj);
  if (parsed?.year && parsed?.month && parsed?.day) {
    const d = new Date(parsed.year, parsed.month - 1, parsed.day);
    if (!isNaN(d.getTime()))
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  }
  return '';
};
