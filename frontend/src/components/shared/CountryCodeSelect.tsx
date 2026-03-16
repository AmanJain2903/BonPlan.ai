import { useState, useRef, useEffect, useMemo } from 'react';
import { ChevronDown } from 'lucide-react';
import { countryCodes } from '../../data/countryCodes.ts';

type Props = {
  value: string;
  onChange: (dial: string) => void;
  id?: string;
  disabled?: boolean;
};

export default function CountryCodeSelect({ value, onChange, id, disabled }: Props) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, []);

  useEffect(() => {
    if (open) {
      setSearch('');
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  const filtered = useMemo(() => {
    if (!search) return countryCodes;
    const q = search.toLowerCase();
    return countryCodes.filter(
      (c) => c.name.toLowerCase().includes(q) || c.dial.includes(q) || c.code.toLowerCase().includes(q),
    );
  }, [search]);

  const selected = countryCodes.find((c) => c.dial === value);

  return (
    <div ref={wrapperRef} className="relative">
      <button
        id={id}
        type="button"
        disabled={disabled}
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2.5 text-sm text-white outline-none focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20 transition-all duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <span className={value ? 'text-white' : 'text-white/20'}>
          {selected ? `${selected.dial}` : 'Code'}
        </span>
        <ChevronDown size={14} className={`text-white/40 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute z-50 top-full left-0 mt-1 w-64 max-h-60 rounded-xl border border-white/10 bg-carbon shadow-xl overflow-hidden">
          <div className="px-2 py-2 border-b border-white/5">
            <input
              ref={inputRef}
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search country..."
              className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-white placeholder-white/20 outline-none focus:border-cyan/40"
            />
          </div>
          <div className="overflow-y-auto max-h-48">
            {filtered.length === 0 ? (
              <p className="px-3 py-3 text-xs text-white/30 text-center">No results</p>
            ) : (
              filtered.map((c) => (
                <button
                  key={c.code}
                  type="button"
                  onClick={() => { onChange(c.dial); setOpen(false); }}
                  className={`w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-white/[0.06] transition-colors cursor-pointer ${
                    value === c.dial ? 'bg-cyan/10 text-cyan' : 'text-white/70'
                  }`}
                >
                  <span className="font-mono w-12 shrink-0">{c.dial}</span>
                  <span className="truncate">{c.name}</span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
