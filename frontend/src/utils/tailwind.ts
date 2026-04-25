type ClassValue = string | number | boolean | null | undefined;

export function cn(...values: ClassValue[]): string {
  return values
    .flatMap((v) => {
      if (!v) return [];
      if (typeof v === 'string' || typeof v === 'number') return [String(v)];
      return [];
    })
    .join(' ');
}

