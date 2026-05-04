import { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  Save, Sparkles, Map, User, Clock, Check, X,
  Sunrise, Sun, Moon, ChevronDown,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../../api';
import { useAuth } from '../../context/AuthContext';
import {
  DEFAULT_PREFERENCES,
  ACTIVITY_INTERESTS,
  DINING_STYLES,
  ACCOMMODATION_STYLES,
  TRAVEL_TO_OPTIONS,
  TRAVEL_AROUND_OPTIONS,
  POPULAR_DIETS,
  ACCESSIBILITY_OPTIONS,
  LIFESTYLE_TOGGLES,
  FIELD_DESCRIPTIONS,
  TripPreferences,
  TravelPreferences,
  OtherPreferences,
} from '../../data/preferences';

const formatInterest = (s: string) => {
  return s
    .split(' ')
    .filter(Boolean)
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
};

/* ──────────────────────── Shared Sub-Components ──────────────────────── */

/** Glassmorphism section card wrapper */
const Section = ({ icon: Icon, title, subtitle, children, className = '' }: {
  icon: React.ElementType; title: string; subtitle?: string; children: React.ReactNode; className?: string;
}) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.4, ease: 'easeOut' }}
    className={`rounded-2xl border border-white/[0.06] bg-carbon/40 backdrop-blur-sm p-6 sm:p-8 space-y-6 ${className}`}
  >
    <div className="flex items-center gap-3 border-b border-white/5 pb-5">
      <div className="h-10 w-10 rounded-xl bg-cyan/10 border border-cyan/15 flex items-center justify-center text-cyan shrink-0">
        <Icon size={20} />
      </div>
      <div>
        <h3 className="text-lg font-bold text-white tracking-wide">{title}</h3>
        {subtitle && <p className="text-xs text-white/40 mt-0.5">{subtitle}</p>}
      </div>
    </div>
    {children}
  </motion.div>
);

/** Sub-section label with optional icon + description */
const SubLabel = ({ children, fieldKey }: { children: React.ReactNode; fieldKey?: string }) => {
  const meta = fieldKey ? FIELD_DESCRIPTIONS[fieldKey] : undefined;
  const Icon = meta?.icon;
  return (
    <div className="mb-3">
      <div className="flex items-center gap-2">
        {Icon && <Icon size={14} className="text-cyan/50" />}
        <p className="text-xs font-semibold text-white/80 uppercase tracking-widest">{children}</p>
      </div>
      {meta?.desc && <p className="text-[11px] text-white/40 mt-1 ml-[22px]">{meta.desc}</p>}
    </div>
  );
};

/** Toggle pill button */
const TogglePill = ({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) => (
  <button
    type="button"
    onClick={onClick}
    className={`px-4 py-2 rounded-full text-xs font-semibold border transition-all duration-200 cursor-pointer whitespace-nowrap shrink-0 ${active
      ? 'border-cyan/40 bg-cyan/10 text-cyan shadow-[0_0_12px_rgba(102,252,241,0.12)]'
      : 'border-white/10 bg-white/[0.03] text-white/55 hover:bg-white/[0.06] hover:text-white/80'
      }`}
  >
    {label}
  </button>
);

const CustomInterestInput = ({ onAdd }: { onAdd: (val: string) => void }) => {
  const [val, setVal] = useState('');

  const handleAdd = () => {
    const formatted = formatInterest(val.trim());
    if (formatted) {
      onAdd(formatted);
      setVal('');
    }
  };

  return (
    <div className="flex items-center gap-2 px-4 py-1.5 rounded-full border border-dashed border-white/20 bg-white/[0.02] focus-within:border-cyan/50 focus-within:bg-cyan/5 transition-all group shrink-0">
      <input
        type="text"
        value={val}
        maxLength={36}
        onChange={(e) => setVal(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            handleAdd();
          }
        }}
        placeholder="Add custom..."
        className="bg-transparent text-xs font-semibold text-white/80 outline-none w-24 placeholder:text-white/30"
      />
      <button
        type="button"
        onClick={handleAdd}
        className="text-white/40 hover:text-cyan transition-colors cursor-pointer"
      >
        <Check size={14} strokeWidth={3} />
      </button>
    </div>
  );
};

/** iOS-style toggle switch */
const ToggleSwitch = ({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) => (
  <button
    type="button"
    onClick={() => onChange(!checked)}
    className="flex items-center justify-between p-3.5 rounded-xl border border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.04] transition-colors cursor-pointer"
  >
    <span className="text-sm font-medium text-white/80">{label}</span>
    <div className={`relative inline-flex h-[22px] w-[42px] shrink-0 items-center rounded-full transition-colors duration-200 ${checked ? 'bg-cyan shadow-[0_0_12px_rgba(102,252,241,0.35)]' : 'bg-white/20'
      }`}>
      <span className={`inline-block h-[16px] w-[16px] transform rounded-full bg-white transition-transform duration-200 ${checked ? 'translate-x-[22px]' : 'translate-x-[3px]'
        }`} />
    </div>
  </button>
);

/** Horizontally scrollable row with masked fading edges + auto-scroll to active item */
const ScrollRow = ({ children, activeIndex }: { children: React.ReactNode; activeIndex?: number }) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (activeIndex == null || !scrollRef.current) return;
    const container = scrollRef.current;
    const child = container.children[activeIndex] as HTMLElement | undefined;
    if (!child) return;
    const offset = child.offsetLeft - container.offsetWidth / 2 + child.offsetWidth / 2;
    container.scrollTo({ left: offset, behavior: 'smooth' });
  }, [activeIndex]);

  return (
    <div className="relative w-full">
      <div
        ref={scrollRef}
        className="flex gap-2 overflow-x-auto scrollbar-hide px-4 py-1"
        style={{
          maskImage: 'linear-gradient(to right, transparent, black 24px, black calc(100% - 24px), transparent)',
          WebkitMaskImage: 'linear-gradient(to right, transparent, black 24px, black calc(100% - 24px), transparent)'
        }}
      >
        {children}
      </div>
    </div>
  );
};

/* ──────────────────────── Custom Travel Dropdown ──────────────────────── */
const TravelSelect = ({ label, value, options, onChange, zIdx = 50, fieldKey }: {
  label: string;
  value: string;
  options: { value: string; label: string; icon: React.ElementType | null }[];
  onChange: (v: string) => void;
  zIdx?: number;
  fieldKey?: string;
}) => {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const selected = options.find(o => o.value === value) || options[0];

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={ref} className="relative flex-1" style={{ zIndex: open ? zIdx : 1 }}>
      <SubLabel fieldKey={fieldKey}>{label}</SubLabel>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-white hover:border-white/20 transition-colors cursor-pointer"
      >
        <span className="flex items-center gap-2.5">
          {selected.icon && <selected.icon size={15} className="text-cyan/70" />}
          <span>{selected.label}</span>
        </span>
        <ChevronDown size={15} className={`text-white/40 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.97 }}
            transition={{ duration: 0.15 }}
            className="absolute z-[100] mt-1.5 w-full rounded-xl border border-white/10 bg-midnight/95 backdrop-blur-xl shadow-[0_10px_40px_rgba(0,0,0,0.5)] py-1 max-h-56 overflow-y-auto scrollbar-hide"
          >
            {options.map(opt => (
              <button
                key={opt.value}
                type="button"
                onClick={() => { onChange(opt.value); setOpen(false); }}
                className={`w-full flex items-center gap-2.5 px-4 py-2.5 text-sm transition-colors cursor-pointer ${opt.value === value
                  ? 'text-cyan bg-cyan/[0.07]'
                  : 'text-white/70 hover:bg-white/[0.04] hover:text-white'
                  }`}
              >
                {opt.icon && <opt.icon size={14} className={opt.value === value ? 'text-cyan' : 'text-white/40'} />}
                {opt.label}
                {opt.value === value && <Check size={13} className="ml-auto text-cyan" />}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

/* ──────────────────────── Creatable Multi-Select ──────────────────────── */
const CreatableMultiSelect = ({ selected, onChange, suggestions }: {
  selected: string[];
  onChange: (v: string[]) => void;
  suggestions: string[];
}) => {
  const [input, setInput] = useState('');

  const addTag = (tag: string) => {
    const clean = tag.trim();
    if (!clean) return;
    const lower = clean.toLowerCase();
    if (!selected.some(s => s.toLowerCase() === lower)) {
      onChange([...selected, clean]);
    }
    setInput('');
  };

  const removeTag = (tag: string) => {
    onChange(selected.filter(s => s !== tag));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') { e.preventDefault(); addTag(input); }
    if (e.key === 'Backspace' && !input && selected.length > 0) {
      removeTag(selected[selected.length - 1]);
    }
  };

  const remaining = suggestions.filter(s => !selected.some(sel => sel.toLowerCase() === s.toLowerCase()));

  const tagsRef = useRef<HTMLDivElement>(null);

  // auto-scroll tags to the end when a new one is added
  useEffect(() => {
    if (tagsRef.current) {
      tagsRef.current.scrollLeft = tagsRef.current.scrollWidth;
    }
  }, [selected.length]);

  const maskStyle = {
    maskImage: 'linear-gradient(to right, transparent, black 24px, black calc(100% - 24px), transparent)',
    WebkitMaskImage: 'linear-gradient(to right, transparent, black 24px, black calc(100% - 24px), transparent)'
  };

  return (
    <div className="space-y-3">
      {/* Tags + Input */}
      <div className="rounded-xl border border-white/10 bg-white/[0.03] min-h-[44px] focus-within:border-cyan/40 focus-within:ring-1 focus-within:ring-cyan/20 transition-all">
        <div
          ref={tagsRef}
          className="flex gap-2 overflow-x-auto scrollbar-hide px-3 py-2.5"
          style={selected.length > 0 ? maskStyle : undefined}
        >
          {selected.map(tag => (
            <span key={tag} className="inline-flex items-center gap-1.5 bg-cyan/10 border border-cyan/25 text-cyan text-xs font-semibold px-2.5 py-1 rounded-full shrink-0 whitespace-nowrap">
              {tag}
              <button type="button" onClick={() => removeTag(tag)} className="hover:text-white transition-colors cursor-pointer">
                <X size={12} />
              </button>
            </span>
          ))}
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={selected.length === 0 ? 'Type & press Enter to add...' : ''}
            className="flex-1 min-w-[120px] bg-transparent text-sm text-white outline-none placeholder-white/25 shrink-0"
          />
        </div>
      </div>

      {/* Suggestions — scrollable row */}
      {remaining.length > 0 && (
        <div
          className="flex gap-1.5 overflow-x-auto scrollbar-hide px-4 py-0.5"
          style={maskStyle}
        >
          {remaining.map(s => (
            <button
              key={s}
              type="button"
              onClick={() => addTag(s)}
              className="px-3 py-1.5 rounded-full border border-dashed border-white/15 text-xs text-white/45 hover:border-cyan/30 hover:text-cyan/80 hover:bg-cyan/[0.04] transition-all cursor-pointer shrink-0 whitespace-nowrap"
            >
              + {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

/* ──────────────────────── Main Component ──────────────────────── */
export default function PreferencesPanel() {
  const { token, user, login } = useAuth();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [form, setForm] = useState<TripPreferences>(DEFAULT_PREFERENCES);
  const snapshot = useRef<TripPreferences>(DEFAULT_PREFERENCES);

  const [status, setStatus] = useState<'loading' | 'idle' | 'saving' | 'error'>('loading');
  const [message, setMessage] = useState('');



  // Load preferences
  useEffect(() => {
    if (!token) return;
    if (user?.preferences) {
      setForm(user.preferences as TripPreferences);
      snapshot.current = user.preferences as TripPreferences;
      setStatus('idle');
    } else {
      (async () => {
        try {
          const res = await api.auth.getProfile(token);
          const prefs = res.preferences || DEFAULT_PREFERENCES;
          setForm(prefs);
          snapshot.current = prefs;
          setStatus('idle');
        } catch {
          setStatus('error');
          setMessage('Failed to load preferences.');
        }
      })();
    }
  }, [token, user]);

  const isDirty = JSON.stringify(form) !== JSON.stringify(snapshot.current);

  // Save
  const handleSave = async () => {
    if (!token) return;
    setStatus('saving');
    try {
      const res = await api.auth.updateProfile(token, user?.firstName || '', user?.lastName || '', null, null, form);
      snapshot.current = res.preferences || form;
      setForm({ ...snapshot.current });
      setStatus('idle');
      const store = !!localStorage.getItem('token');
      login(token, store, { ...user, preferences: snapshot.current });

      // If user arrived from the welcome modal, take them home
      if (searchParams.get('from') === 'welcome') {
        navigate('/');
      }
    } catch (err: any) {
      setStatus('error');
      setMessage(err?.response?.data?.detail || 'Failed to save preferences.');
      setTimeout(() => setMessage(''), 3000);
    }
  };

  // Field updaters
  const updateField = useCallback(<K extends keyof TripPreferences>(key: K, value: TripPreferences[K]) => {
    setForm(prev => ({ ...prev, [key]: value }));
  }, []);

  const updateOtherPref = useCallback(<K extends keyof OtherPreferences>(key: K, value: OtherPreferences[K]) => {
    setForm(prev => ({ ...prev, other_preferences: { ...prev.other_preferences, [key]: value } }));
  }, []);

  const updateTravelPref = useCallback(<K extends keyof TravelPreferences>(key: K, value: TravelPreferences[K]) => {
    setForm(prev => ({ ...prev, travel_preferences: { ...prev.travel_preferences, [key]: value } }));
  }, []);

  const toggleArrayItem = useCallback((key: 'activity_interests' | 'dietary_restrictions', item: string) => {
    setForm(prev => {
      const arr = prev[key] as string[];
      return { ...prev, [key]: arr.includes(item) ? arr.filter(i => i !== item) : [...arr, item] };
    });
  }, []);



  // Loading state
  if (status === 'loading') {
    return (
      <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-xl p-8 min-h-[300px] flex items-center justify-center">
        <span className="h-6 w-6 border-2 border-cyan/30 border-t-cyan rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-7xl pb-32 space-y-6">
      {/* Error message */}
      {message && (
        <div className="rounded-xl px-4 py-3 text-sm text-red-400 bg-red-400/5 border border-red-400/20">
          {message}
        </div>
      )}

      {/* ═════════════ SECTION 1: Trip Vibe & Rhythm ═════════════ */}
      <Section icon={Sparkles} title="Trip Vibe & Rhythm" subtitle="Define how you experience a destination." className="relative z-10">
        {/* Schedule Rhythm - Segmented Control */}
        <div>
          <SubLabel fieldKey="schedule_rhythm">Schedule Rhythm</SubLabel>
          <div className="flex rounded-xl border border-white/10 bg-white/[0.02] p-1 w-full sm:w-auto sm:inline-flex">
            {[
              { value: 'early_bird', label: 'Early Bird', icon: Sunrise },
              { value: 'standard', label: 'Standard', icon: Sun },
              { value: 'night_owl', label: 'Night Owl', icon: Moon },
            ].map(opt => {
              const active = form.schedule_rhythm === opt.value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => updateField('schedule_rhythm', opt.value)}
                  className={`flex-1 flex items-center justify-center gap-1.5 sm:gap-2 px-3 sm:px-5 py-2.5 rounded-lg text-xs font-semibold transition-all duration-200 cursor-pointer ${active
                    ? 'bg-cyan/15 text-cyan border border-cyan/25 shadow-[0_0_15px_rgba(102,252,241,0.1)]'
                    : 'text-white/50 hover:text-white/80 border border-transparent'
                    }`}
                >
                  <opt.icon size={15} className="shrink-0" />
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Activity Interests — multi-select scrollable row */}
        <div>
          <SubLabel fieldKey="activity_interests">Activity Interests</SubLabel>
          <ScrollRow>
            <CustomInterestInput onAdd={(val) => toggleArrayItem('activity_interests', val)} />

            {/* User-added custom interests first */}
            {form.activity_interests
              .filter(item => !ACTIVITY_INTERESTS.some(opt => opt.value === item))
              .map(item => (
                <button
                  key={item}
                  type="button"
                  onClick={() => toggleArrayItem('activity_interests', item)}
                  className="flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold border transition-all duration-200 cursor-pointer whitespace-nowrap shrink-0 border-cyan/40 bg-cyan/10 text-cyan shadow-[0_0_12px_rgba(102,252,241,0.12)]"
                >
                  <span className="flex items-center justify-center h-4 w-4 rounded-md border border-cyan/50 bg-cyan/25 transition-all duration-200">
                    <Check size={10} strokeWidth={3} />
                  </span>
                  {item}
                </button>
              ))}

            {/* Predefined interests */}
            {ACTIVITY_INTERESTS.map(opt => {
              const active = form.activity_interests.includes(opt.value);
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => toggleArrayItem('activity_interests', opt.value)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold border transition-all duration-200 cursor-pointer whitespace-nowrap shrink-0 ${active
                    ? 'border-cyan/40 bg-cyan/10 text-cyan shadow-[0_0_12px_rgba(102,252,241,0.12)]'
                    : 'border-white/10 bg-white/[0.03] text-white/55 hover:bg-white/[0.06] hover:text-white/80'
                    }`}
                >
                  <span className={`flex items-center justify-center h-4 w-4 rounded-md border transition-all duration-200 ${active
                    ? 'bg-cyan/25 border-cyan/50'
                    : 'border-white/20 bg-white/[0.04]'
                    }`}>
                    {active && <Check size={10} strokeWidth={3} />}
                  </span>
                  {opt.label}
                </button>
              );
            })}
          </ScrollRow>
        </div>

        {/* Travel Preferences — side by side */}
        <div className="flex flex-col sm:flex-row gap-4 sm:gap-6">
          <TravelSelect
            label="Getting There"
            value={form.travel_preferences?.travel_to_destination || 'any'}
            options={TRAVEL_TO_OPTIONS}
            onChange={(v) => updateTravelPref('travel_to_destination', v)}
            zIdx={60}
            fieldKey="travel_to"
          />
          <TravelSelect
            label="Getting Around"
            value={form.travel_preferences?.travel_around_destination || 'any'}
            options={TRAVEL_AROUND_OPTIONS}
            onChange={(v) => updateTravelPref('travel_around_destination', v)}
            zIdx={50}
            fieldKey="travel_around"
          />
        </div>
      </Section>

      {/* ═════════════ SECTION 2: Logistics & Basecamp ═════════════ */}
      <Section icon={Map} title="Logistics & Basecamp" subtitle="Where you stay and how you eat.">
        {/* Accommodation Style — single select, scrollable */}
        <div>
          <SubLabel fieldKey="accommodation_style">Accommodation Style</SubLabel>
          <ScrollRow activeIndex={ACCOMMODATION_STYLES.findIndex(o => o.value === form.accommodation_style)}>
            {ACCOMMODATION_STYLES.map(opt => (
              <TogglePill
                key={opt.value}
                label={opt.label}
                active={form.accommodation_style === opt.value}
                onClick={() => updateField('accommodation_style', opt.value)}
              />
            ))}
          </ScrollRow>
        </div>

        {/* Dining Style — single select, scrollable */}
        <div>
          <SubLabel fieldKey="dining_style">Dining Style</SubLabel>
          <ScrollRow activeIndex={DINING_STYLES.findIndex(o => o.value === form.dining_style)}>
            {DINING_STYLES.map(opt => (
              <TogglePill
                key={opt.value}
                label={opt.label}
                active={form.dining_style === opt.value}
                onClick={() => updateField('dining_style', opt.value)}
              />
            ))}
          </ScrollRow>
        </div>
      </Section>

      {/* ═════════════ SECTION 3: Personal Needs & Accessibility ═════════════ */}
      <Section icon={User} title="Personal Needs & Accessibility" subtitle="Dietary, mobility, and lifestyle requirements.">
        {/* Dietary Restrictions */}
        <div>
          <SubLabel fieldKey="dietary_restrictions">Dietary Restrictions</SubLabel>
          <CreatableMultiSelect
            selected={form.dietary_restrictions}
            onChange={(v) => updateField('dietary_restrictions', v)}
            suggestions={POPULAR_DIETS}
          />
        </div>

        {/* Accessibility — horizontal scrollable on large screens */}
        <div>
          <SubLabel fieldKey="accessibility">Accessibility</SubLabel>
          <ScrollRow activeIndex={ACCESSIBILITY_OPTIONS.findIndex(o => o.value === form.accessibility_preferences)}>
            {ACCESSIBILITY_OPTIONS.map(opt => {
              const active = form.accessibility_preferences === opt.value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => updateField('accessibility_preferences', opt.value)}
                  className={`flex items-start gap-3 p-4 rounded-xl border text-left transition-all duration-200 cursor-pointer shrink-0 min-w-[200px] max-w-[260px] ${active
                    ? 'border-cyan/35 bg-cyan/[0.06] shadow-[0_0_15px_rgba(102,252,241,0.06)]'
                    : 'border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.04]'
                    }`}
                >
                  <div className={`mt-0.5 flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full border-2 transition-colors ${active ? 'border-cyan bg-cyan' : 'border-white/30 bg-transparent'
                    }`}>
                    {active && <Check size={11} className="text-midnight" strokeWidth={3} />}
                  </div>
                  <div>
                    <p className={`text-sm font-semibold ${active ? 'text-cyan' : 'text-white/80'}`}>{opt.label}</p>
                    <p className="text-xs text-white/35 mt-0.5 line-clamp-2">{opt.desc}</p>
                  </div>
                </button>
              );
            })}
          </ScrollRow>
        </div>

        {/* Lifestyle Toggles */}
        <div>
          <SubLabel fieldKey="lifestyle">Lifestyle</SubLabel>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {LIFESTYLE_TOGGLES.map(t => (
              <ToggleSwitch
                key={t.key}
                label={t.label}
                checked={!!form.other_preferences?.[t.key]}
                onChange={(v) => updateOtherPref(t.key, v as never)}
              />
            ))}
          </div>
        </div>

        {/* Additional Notes */}
        <div>
          <SubLabel fieldKey="additional_notes">Additional Notes</SubLabel>
          <textarea
            value={form.other_preferences?.additional_notes || ''}
            onChange={(e) => updateOtherPref('additional_notes', e.target.value)}
            placeholder="e.g. We always need a crib for the toddler, or prefer very quiet hotels..."
            rows={3}
            className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-white outline-none resize-none focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20 placeholder-white/25 transition-all"
          />
        </div>
      </Section>

      {/* ═════════════ SECTION 4: Locked Routines (Coming Soon) ═════════════ */}
      <Section icon={Clock} title="Locked Routines" subtitle="Hard-locked time blocks the AI must schedule around." className="bg-white/[0.03]">
        <div className="text-center py-12">
          <p className="text-cyan/80 text-lg font-medium tracking-wider uppercase">Coming Soon with Smart Anchors</p>
        </div>
      </Section>

      {/* ═════════════ Floating Save Bar (portaled to body to escape transform) ═════════════ */}
      {createPortal(
        <AnimatePresence>
          {isDirty && (
            <motion.div
              initial={{ opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 40 }}
              transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
              className="fixed bottom-0 left-0 w-full z-50 pointer-events-none flex justify-center pb-8 pt-32 bg-gradient-to-t from-black via-black/80 to-transparent"
            >
              <div className="pointer-events-auto">
                <div className="flex items-center gap-4 rounded-full px-6 py-3">
                  <span className="text-sm text-white/80 text-center pl-2 select-none">
                    You have <span className="text-cyan font-semibold">unsaved</span> changes
                  </span>
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={status === 'saving'}
                    className="ml-2 inline-flex items-center justify-center gap-2 rounded-full bg-cyan text-midnight font-extrabold text-xs px-5 py-2.5 transition-transform duration-300 hover:scale-105 hover:bg-[#80fdf6] hover:shadow-[0_0_15px_rgba(102,252,241,0.4)] cursor-pointer disabled:opacity-50 disabled:scale-100 disabled:cursor-not-allowed"
                  >
                    {status === 'saving' ? (
                      <span className="h-4 w-4 border-2 border-midnight/40 border-t-midnight rounded-full animate-spin" />
                    ) : (
                      <Save size={14} />
                    )}
                    SAVE
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>,
        document.body
      )}
    </div>
  );
}
