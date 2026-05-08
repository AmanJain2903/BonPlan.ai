import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X, Plus, Trash2, Plane, Building2, Car, Map, Utensils, Anchor,
  AlertTriangle, Clock, CalendarDays, DollarSign,
} from 'lucide-react';
import { DateTime } from 'luxon';
import { DayPicker } from 'react-day-picker';
import 'react-day-picker/dist/style.css';
import { SmartAnchor, AnchorEventType, SmartAnchorUserInputs } from '../../apis/plan';
import PlacesAutocomplete from '../shared/PlacesAutocomplete';

/* ── Type config ────────────────────────────────────────────────────────── */

const TYPE_CONFIG: Record<AnchorEventType, { label: string; icon: React.ElementType; color: string }> = {
  FLIGHT:     { label: 'Flight',      icon: Plane,     color: 'text-blue-400' },
  HOTEL:      { label: 'Hotel',       icon: Building2, color: 'text-purple-400' },
  CAR_RENTAL: { label: 'Car Rental',  icon: Car,       color: 'text-amber-400' },
  ACTIVITY:   { label: 'Activity',    icon: Map,       color: 'text-green-400' },
  DINING:     { label: 'Dining',      icon: Utensils,  color: 'text-orange-400' },
  OTHER:      { label: 'Other',       icon: Anchor,    color: 'text-cyan/70' },
};

const ALL_TYPES = Object.keys(TYPE_CONFIG) as AnchorEventType[];
const TIMED_TYPES: AnchorEventType[] = ['ACTIVITY', 'DINING', 'OTHER'];
const DURATION_OPTIONS = [30, 60, 90, 120, 150, 180, 210, 240, 300, 360, 480];

function formatDuration(min: number): string {
  const h = Math.floor(min / 60);
  const m = min % 60;
  if (h === 0) return `${m} min`;
  if (m === 0) return `${h} hr`;
  return `${h} hr ${m} min`;
}

function computeEndTime(startTime: string, durationMinutes: number): string {
  if (!startTime) return '';
  const [h, m] = startTime.split(':').map(Number);
  const total = h * 60 + m + durationMinutes;
  const eh = Math.floor(total / 60) % 24;
  const em = total % 60;
  return `${String(eh).padStart(2, '0')}:${String(em).padStart(2, '0')}`;
}

function newAnchor(type: AnchorEventType = 'FLIGHT'): SmartAnchor {
  return {
    id: crypto.randomUUID(),
    type,
    user_inputs: {},
    details: null,
    prefill_status: 'none',
    duration_minutes: TIMED_TYPES.includes(type) ? 60 : undefined,
  };
}

/* ── Shared input primitives ────────────────────────────────────────────── */

const Field = ({ label, children, required }: { label: string; children: React.ReactNode; required?: boolean }) => (
  <div className="flex flex-col gap-1.5">
    <label className="text-[10px] font-semibold uppercase tracking-widest text-white/45">
      {label}{required && <span className="text-cyan/70 ml-0.5">*</span>}
    </label>
    {children}
  </div>
);

const TextInput = ({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string }) => (
  <input
    type="text"
    value={value}
    onChange={e => onChange(e.target.value)}
    placeholder={placeholder}
    className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white outline-none focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20 placeholder-white/20 transition-all"
  />
);

const NumberInput = ({ value, onChange, placeholder }: { value: number | string; onChange: (v: number | undefined) => void; placeholder?: string }) => (
  <div className="relative">
    <DollarSign className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-white/30 pointer-events-none" />
    <input
      type="number"
      min={0}
      step="0.01"
      value={value === '' || value === undefined ? '' : value}
      onChange={e => onChange(e.target.value === '' ? undefined : parseFloat(e.target.value))}
      placeholder={placeholder ?? '0.00'}
      className="w-full rounded-lg border border-white/10 bg-white/[0.03] pl-7 pr-3 py-2 text-sm text-white outline-none focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20 placeholder-white/20 transition-all [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
    />
  </div>
);

function AnchorDatePicker({ value, onChange, minDate, maxDate, tz }: {
  value: string; onChange: (v: string) => void; minDate?: string; maxDate?: string; tz: string;
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const [popoverStyle, setPopoverStyle] = useState<React.CSSProperties>({});

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (triggerRef.current?.contains(target)) return;
      if (popoverRef.current?.contains(target)) return;
      setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  useEffect(() => {
    if (!open || !triggerRef.current) return;
    const compute = () => {
      const btn = triggerRef.current!.getBoundingClientRect();
      const popW = 310;
      const popH = 330;
      const pad = 8;
      const spaceBelow = window.innerHeight - btn.bottom - pad;
      const spaceAbove = btn.top - pad;
      let top: number;
      if (spaceBelow >= popH) {
        top = btn.bottom + 4;
      } else if (spaceAbove >= popH) {
        top = btn.top - popH - 4;
      } else {
        top = spaceBelow >= spaceAbove ? btn.bottom + 4 : Math.max(pad, btn.top - popH - 4);
      }
      let left = btn.left;
      if (left + popW > window.innerWidth - pad) {
        left = Math.max(pad, window.innerWidth - popW - pad);
      }
      setPopoverStyle({ position: 'fixed', top, left, zIndex: 9999 });
    };
    compute();
    window.addEventListener('scroll', compute, true);
    window.addEventListener('resize', compute);
    return () => {
      window.removeEventListener('scroll', compute, true);
      window.removeEventListener('resize', compute);
    };
  }, [open]);

  const selected = useMemo(() => {
    if (!value) return undefined;
    const dt = DateTime.fromISO(value, { zone: tz });
    return dt.isValid ? new Date(dt.year, dt.month - 1, dt.day) : undefined;
  }, [value, tz]);

  const disabledMatcher = useMemo(() => {
    const minJs = minDate ? (() => { const dt = DateTime.fromISO(minDate, { zone: tz }); return dt.isValid ? new Date(dt.year, dt.month - 1, dt.day) : null; })() : null;
    const maxJs = maxDate ? (() => { const dt = DateTime.fromISO(maxDate, { zone: tz }); return dt.isValid ? new Date(dt.year, dt.month - 1, dt.day) : null; })() : null;
    if (!minJs && !maxJs) return undefined;
    return (day: Date): boolean => {
      if (minJs && day < minJs) return true;
      if (maxJs && day > maxJs) return true;
      return false;
    };
  }, [minDate, maxDate, tz]);

  const defaultMonth = useMemo(() => {
    if (selected) return new Date(selected.getFullYear(), selected.getMonth(), 1);
    if (minDate) {
      const dt = DateTime.fromISO(minDate, { zone: tz });
      if (dt.isValid) return new Date(dt.year, dt.month - 1, 1);
    }
    return new Date();
  }, [selected, minDate, tz]);

  const displayText = value ? DateTime.fromISO(value, { zone: tz }).toFormat('MMM d, yyyy') : '';

  const popover = open ? createPortal(
    <AnimatePresence>
      <motion.div
        ref={popoverRef}
        initial={{ opacity: 0, scale: 0.97 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.97 }}
        transition={{ duration: 0.15 }}
        style={popoverStyle}
        className="rounded-xl border border-white/10 bg-[#0d1017] shadow-[0_12px_40px_rgba(0,0,0,0.6)] p-2"
      >
        <DayPicker
          mode="single"
          selected={selected}
          defaultMonth={defaultMonth}
          onSelect={d => {
            if (d) {
              const iso = DateTime.fromObject({ year: d.getFullYear(), month: d.getMonth() + 1, day: d.getDate() }).toFormat('yyyy-MM-dd');
              onChange(iso);
            }
            setOpen(false);
          }}
          disabled={disabledMatcher}
          className="theme-cyan text-white text-sm m-0"
          modifiersClassNames={{
            selected: 'bg-cyan text-midnight font-bold rounded-lg hover:bg-cyan/90 hover:text-midnight',
            today: 'text-cyan font-bold',
            disabled: 'text-white/15 line-through opacity-60 cursor-not-allowed',
          }}
          styles={{
            caption: { color: 'white', fontWeight: 'bold' },
            head_cell: { color: 'rgba(255,255,255,0.4)', fontWeight: 'normal' },
            cell: { padding: '2px' },
          }}
        />
      </motion.div>
    </AnimatePresence>,
    document.body,
  ) : null;

  return (
    <div ref={containerRef}>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen(o => !o)}
        className={`w-full flex items-center gap-2 rounded-lg border px-3 py-2 text-sm text-left transition-all cursor-pointer ${
          open
            ? 'border-cyan/40 ring-1 ring-cyan/20 bg-white/[0.05]'
            : 'border-white/10 bg-white/[0.03] hover:border-white/20'
        } ${value ? 'text-white' : 'text-white/25'}`}
      >
        <CalendarDays size={13} className="text-white/30 shrink-0" />
        <span className="flex-1 truncate">{displayText || 'Select date…'}</span>
      </button>
      {popover}
    </div>
  );
}

const TimeInput = ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
  <input
    type="time"
    value={value}
    onChange={e => onChange(e.target.value)}
    className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white outline-none focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20 transition-all [color-scheme:dark]"
  />
);

const PlacePicker = ({ value, onChange, placeholder }: {
  value: string;
  onChange: (name: string, placeId?: string, lat?: number, lng?: number) => void;
  placeholder?: string;
}) => (
  <div className="space-y-1">
    {value && (
      <p className="text-[10px] text-white/40 truncate">
        Current: <span className="text-white/55">{value}</span>
      </p>
    )}
    <PlacesAutocomplete
      placeholder={placeholder ?? 'Search for a place'}
      onPlaceChange={p => {
        const parts = [p.city, p.state, p.country].filter(Boolean);
        const display = parts.join(', ') || p.city;
        onChange(display, p.placeId, p.lat, p.lng);
      }}
      className="w-full"
    />
  </div>
);

/* ── Type selector ──────────────────────────────────────────────────────── */

const TypePicker = ({ value, onChange }: { value: AnchorEventType; onChange: (v: AnchorEventType) => void }) => (
  <div className="grid grid-cols-3 gap-2">
    {ALL_TYPES.map(t => {
      const cfg = TYPE_CONFIG[t];
      const Icon = cfg.icon;
      const active = t === value;
      return (
        <button
          key={t}
          type="button"
          onClick={() => onChange(t)}
          className={`flex flex-col items-center gap-1.5 py-3 px-2 rounded-xl border transition-all cursor-pointer ${
            active
              ? 'border-cyan/40 bg-cyan/[0.08] text-cyan shadow-[0_0_12px_rgba(102,252,241,0.15)]'
              : 'border-white/[0.07] bg-white/[0.02] text-white/50 hover:border-white/15 hover:bg-white/[0.04] hover:text-white/70'
          }`}
        >
          <Icon size={16} className={active ? 'text-cyan' : cfg.color} />
          <span className="text-[10px] font-semibold uppercase tracking-wider">{cfg.label}</span>
        </button>
      );
    })}
  </div>
);

/* ── Per-type forms ─────────────────────────────────────────────────────── */

type FormProps = {
  inputs: SmartAnchorUserInputs;
  set: (p: Partial<SmartAnchorUserInputs>) => void;
  tripStart: string;
  tripEnd: string;
  tz: string;
};

const FlightForm = ({ inputs, set, tripStart, tripEnd, tz }: FormProps) => (
  <div className="space-y-3">
    <div className="grid grid-cols-2 gap-3">
      <Field label="Flight Number" required>
        <TextInput value={inputs.flight_number ?? ''} onChange={v => set({ flight_number: v })} placeholder="AF123" />
      </Field>
      <Field label="Airline">
        <TextInput value={inputs.airline ?? ''} onChange={v => set({ airline: v })} placeholder="Air France" />
      </Field>
    </div>
    <Field label="Departure Airport / City" required>
      <PlacePicker value={inputs.departure_airport ?? ''} onChange={(name, placeId, lat, lng) => set({ departure_airport: name, departure_airport_place_id: placeId, departure_airport_lat: lat, departure_airport_lng: lng })} placeholder="Search airport or city…" />
    </Field>
    <Field label="Arrival Airport / City" required>
      <PlacePicker value={inputs.arrival_airport ?? ''} onChange={(name, placeId, lat, lng) => set({ arrival_airport: name, arrival_airport_place_id: placeId, arrival_airport_lat: lat, arrival_airport_lng: lng })} placeholder="Search airport or city…" />
    </Field>
    <Field label="Departure Date" required>
      <AnchorDatePicker value={inputs.departure_date ?? ''} onChange={v => set({ departure_date: v })} minDate={tripStart} maxDate={tripEnd} tz={tz} />
    </Field>
    <div className="grid grid-cols-2 gap-3">
      <Field label="Departure Time">
        <TimeInput value={inputs.departure_time ?? ''} onChange={v => set({ departure_time: v })} />
      </Field>
      <Field label="Arrival Time">
        <TimeInput value={inputs.arrival_time ?? ''} onChange={v => set({ arrival_time: v })} />
      </Field>
    </div>
    <div className="grid grid-cols-2 gap-3">
      <Field label="Cost (USD)">
        <NumberInput value={inputs.cost ?? ''} onChange={v => set({ cost: v })} placeholder="0.00" />
      </Field>
      <Field label="Booking URL">
        <TextInput value={inputs.booking_url ?? ''} onChange={v => set({ booking_url: v })} placeholder="https://…" />
      </Field>
    </div>
    <Field label="Notes">
      <TextInput value={inputs.notes ?? ''} onChange={v => set({ notes: v })} placeholder="Any extra context…" />
    </Field>
  </div>
);

const HotelForm = ({ inputs, set, tripStart, tripEnd, tz }: FormProps) => (
  <div className="space-y-3">
    <Field label="Hotel Name" required>
      <TextInput value={inputs.hotel_name ?? ''} onChange={v => set({ hotel_name: v })} placeholder="Hotel name" />
    </Field>
    <Field label="Location">
      <PlacePicker value={inputs.location ?? ''} onChange={(name, placeId, lat, lng) => set({ location: name, location_place_id: placeId, location_lat: lat, location_lng: lng })} placeholder="Search city or address…" />
    </Field>
    <div className="grid grid-cols-2 gap-3">
      <Field label="Check-in Date" required>
        <AnchorDatePicker value={inputs.checkin_date ?? ''} onChange={v => set({ checkin_date: v })} minDate={tripStart} maxDate={tripEnd} tz={tz} />
      </Field>
      <Field label="Check-out Date" required>
        <AnchorDatePicker value={inputs.checkout_date ?? ''} onChange={v => set({ checkout_date: v })} minDate={inputs.checkin_date || tripStart} maxDate={tripEnd} tz={tz} />
      </Field>
    </div>
    <div className="grid grid-cols-2 gap-3">
      <Field label="Check-in Time">
        <TimeInput value={inputs.checkin_time ?? ''} onChange={v => set({ checkin_time: v })} />
      </Field>
      <Field label="Check-out Time">
        <TimeInput value={inputs.checkout_time ?? ''} onChange={v => set({ checkout_time: v })} />
      </Field>
    </div>
    <div className="grid grid-cols-2 gap-3">
      <Field label="Cost (USD)">
        <NumberInput value={inputs.cost ?? ''} onChange={v => set({ cost: v })} placeholder="0.00" />
      </Field>
      <Field label="Booking URL">
        <TextInput value={inputs.booking_url ?? ''} onChange={v => set({ booking_url: v })} placeholder="https://…" />
      </Field>
    </div>
    <Field label="Notes">
      <TextInput value={inputs.notes ?? ''} onChange={v => set({ notes: v })} placeholder="Any extra context…" />
    </Field>
  </div>
);

const CarForm = ({ inputs, set, tripStart, tripEnd, tz }: FormProps) => (
  <div className="space-y-3">
    <div className="grid grid-cols-2 gap-3">
      <Field label="Rental Company">
        <TextInput value={inputs.company ?? ''} onChange={v => set({ company: v })} placeholder="Hertz, Avis…" />
      </Field>
      <Field label="Car Model">
        <TextInput value={inputs.car_model ?? ''} onChange={v => set({ car_model: v })} placeholder="Toyota Corolla" />
      </Field>
    </div>
    <Field label="Pickup Location" required>
      <PlacePicker value={inputs.pickup_location ?? ''} onChange={(name, placeId, lat, lng) => set({ pickup_location: name, pickup_location_place_id: placeId, pickup_location_lat: lat, pickup_location_lng: lng })} placeholder="Search pickup location…" />
    </Field>
    <div className="grid grid-cols-2 gap-3">
      <Field label="Pickup Date" required>
        <AnchorDatePicker value={inputs.pickup_date ?? ''} onChange={v => set({ pickup_date: v })} minDate={tripStart} maxDate={tripEnd} tz={tz} />
      </Field>
      <Field label="Pickup Time">
        <TimeInput value={inputs.pickup_time ?? ''} onChange={v => set({ pickup_time: v })} />
      </Field>
    </div>
    <Field label="Dropoff Location">
      <PlacePicker value={inputs.dropoff_location ?? ''} onChange={(name, placeId, lat, lng) => set({ dropoff_location: name, dropoff_location_place_id: placeId, dropoff_location_lat: lat, dropoff_location_lng: lng })} placeholder="Same or different location…" />
    </Field>
    <div className="grid grid-cols-2 gap-3">
      <Field label="Dropoff Date" required>
        <AnchorDatePicker value={inputs.dropoff_date ?? ''} onChange={v => set({ dropoff_date: v })} minDate={inputs.pickup_date || tripStart} maxDate={tripEnd} tz={tz} />
      </Field>
      <Field label="Dropoff Time">
        <TimeInput value={inputs.dropoff_time ?? ''} onChange={v => set({ dropoff_time: v })} />
      </Field>
    </div>
    <div className="grid grid-cols-2 gap-3">
      <Field label="Cost (USD)">
        <NumberInput value={inputs.cost ?? ''} onChange={v => set({ cost: v })} placeholder="0.00" />
      </Field>
      <Field label="Booking URL">
        <TextInput value={inputs.booking_url ?? ''} onChange={v => set({ booking_url: v })} placeholder="https://…" />
      </Field>
    </div>
    <Field label="Notes">
      <TextInput value={inputs.notes ?? ''} onChange={v => set({ notes: v })} placeholder="Any extra context…" />
    </Field>
  </div>
);

const PlaceForm = ({ inputs, set, tripStart, tripEnd, tz, nameLabel }: FormProps & { nameLabel: string }) => (
  <div className="space-y-3">
    <Field label={nameLabel} required>
      <TextInput value={inputs.name ?? ''} onChange={v => set({ name: v })} placeholder={`${nameLabel}…`} />
    </Field>
    <Field label="Location">
      <PlacePicker value={inputs.location ?? ''} onChange={(name, placeId, lat, lng) => set({ location: name, location_place_id: placeId, location_lat: lat, location_lng: lng })} placeholder="Search city or address…" />
    </Field>
    <Field label="Date" required>
      <AnchorDatePicker value={inputs.date ?? ''} onChange={v => set({ date: v })} minDate={tripStart} maxDate={tripEnd} tz={tz} />
    </Field>
    <Field label="Cost (USD)">
      <NumberInput value={inputs.cost ?? ''} onChange={v => set({ cost: v })} placeholder="0.00" />
    </Field>
    <Field label="Notes">
      <TextInput value={inputs.notes ?? ''} onChange={v => set({ notes: v })} placeholder="Any extra context…" />
    </Field>
  </div>
);

function InputForm({ anchor, onChange, tripStart, tripEnd, tz }: {
  anchor: SmartAnchor; onChange: (a: SmartAnchor) => void;
  tripStart: string; tripEnd: string; tz: string;
}) {
  const set = useCallback(
    (patch: Partial<SmartAnchorUserInputs>) =>
      onChange({ ...anchor, user_inputs: { ...anchor.user_inputs, ...patch } }),
    [anchor, onChange],
  );
  const fp = { inputs: anchor.user_inputs, set, tripStart, tripEnd, tz };
  if (anchor.type === 'FLIGHT')     return <FlightForm {...fp} />;
  if (anchor.type === 'HOTEL')      return <HotelForm  {...fp} />;
  if (anchor.type === 'CAR_RENTAL') return <CarForm    {...fp} />;
  if (anchor.type === 'ACTIVITY')   return <PlaceForm  {...fp} nameLabel="Activity Name" />;
  if (anchor.type === 'DINING')     return <PlaceForm  {...fp} nameLabel="Restaurant Name" />;
  return                                   <PlaceForm  {...fp} nameLabel="Name" />;
}

/* ── Timing section (ACTIVITY / DINING / OTHER only) ────────────────────── */

function TimingSection({ anchor, onChange }: { anchor: SmartAnchor; onChange: (a: SmartAnchor) => void }) {
  const setStartTime = (v: string) => {
    const updates: Partial<SmartAnchor> = { start_time: v };
    if (anchor.duration_minutes && v) {
      updates.end_time = computeEndTime(v, anchor.duration_minutes);
    }
    onChange({ ...anchor, ...updates });
  };

  const setDuration = (min: number) => {
    const updates: Partial<SmartAnchor> = { duration_minutes: min };
    if (anchor.start_time) updates.end_time = computeEndTime(anchor.start_time, min);
    onChange({ ...anchor, ...updates });
  };

  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.015] p-3.5 space-y-3">
      <div className="flex items-center gap-1.5">
        <Clock size={11} className="text-white/35" />
        <span className="text-[10px] font-bold uppercase tracking-widest text-white/35">Timing</span>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Start Time">
          <TimeInput value={anchor.start_time ?? ''} onChange={setStartTime} />
        </Field>
        <Field label="End Time">
          <TimeInput value={anchor.end_time ?? ''} onChange={v => onChange({ ...anchor, end_time: v })} />
        </Field>
      </div>
      <Field label="Duration">
        <select
          value={anchor.duration_minutes ?? 60}
          onChange={e => setDuration(Number(e.target.value))}
          className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white outline-none focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20 transition-all cursor-pointer"
        >
          {DURATION_OPTIONS.map(m => (
            <option key={m} value={m} className="bg-[#0a0d12]">{formatDuration(m)}</option>
          ))}
        </select>
      </Field>
    </div>
  );
}

/* ── Saved anchor compact row ───────────────────────────────────────────── */

function fmtDate(dt?: string): string {
  if (!dt) return '';
  try {
    const d = DateTime.fromISO(dt);
    if (d.isValid) return d.toFormat('MMM d, yyyy');
    return dt;
  } catch { return dt; }
}

function anchorTitle(anchor: SmartAnchor): string {
  const { type: t, user_inputs: u } = anchor;
  if (t === 'FLIGHT')     return [u.airline, u.flight_number].filter(Boolean).join(' · ') || 'Flight';
  if (t === 'HOTEL')      return u.hotel_name || 'Hotel';
  if (t === 'CAR_RENTAL') return u.company || 'Car Rental';
  if (t === 'ACTIVITY')   return u.name || 'Activity';
  if (t === 'DINING')     return u.name || 'Restaurant';
  return u.name || 'Other';
}

function anchorSubtitle(anchor: SmartAnchor): string {
  const { type: t, user_inputs: u, start_time, end_time } = anchor;
  const timeStr = start_time && end_time ? `${start_time} – ${end_time}` : start_time ?? '';
  let base = '';
  if (t === 'FLIGHT') {
    const from = u.departure_airport || '';
    const to   = u.arrival_airport   || '';
    const date = u.departure_date ? fmtDate(u.departure_date) : '';
    base = [from && to ? `${from} → ${to}` : null, date].filter(Boolean).join(' · ');
  } else if (t === 'HOTEL') {
    const dates = [u.checkin_date ? fmtDate(u.checkin_date) : '', u.checkout_date ? fmtDate(u.checkout_date) : ''].filter(Boolean).join(' → ');
    base = [u.location, dates].filter(Boolean).join(' · ');
  } else if (t === 'CAR_RENTAL') {
    base = [u.pickup_location, u.pickup_date ? fmtDate(u.pickup_date) : ''].filter(Boolean).join(' · ');
  } else {
    base = [u.location, u.date ? fmtDate(u.date) : ''].filter(Boolean).join(' · ');
  }
  return [base, timeStr].filter(Boolean).join(' · ');
}

interface SavedAnchorRowProps {
  anchor: SmartAnchor;
  number: number;
  onDelete: () => void;
  confirmingDelete: boolean;
  onAskDelete: () => void;
  onCancelDelete: () => void;
}

function SavedAnchorRow({ anchor, number, onDelete, confirmingDelete, onAskDelete, onCancelDelete }: SavedAnchorRowProps) {
  const cfg   = TYPE_CONFIG[anchor.type];
  const Icon  = cfg.icon;
  const title = anchorTitle(anchor);
  const sub   = anchorSubtitle(anchor);

  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] overflow-hidden">
      <div className="flex items-center gap-3 p-3">
        <div className="h-9 w-9 rounded-lg bg-white/[0.04] border border-white/[0.08] flex items-center justify-center shrink-0">
          <Icon size={15} className={cfg.color} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[9px] font-bold uppercase tracking-widest text-white/25">#{number}</span>
            <p className="text-sm font-semibold text-white truncate">{title}</p>
          </div>
          <p className="text-xs text-white/35 truncate mt-0.5">{cfg.label}{sub ? ` · ${sub}` : ''}</p>
        </div>
        <button
          type="button"
          onClick={onAskDelete}
          className="p-2 rounded-lg text-white/30 hover:text-red-400 hover:bg-red-400/10 transition-all cursor-pointer shrink-0"
        >
          <Trash2 size={13} />
        </button>
      </div>

      <AnimatePresence>
        {confirmingDelete && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-3 pt-0 flex items-center gap-3 border-t border-red-500/15 bg-red-500/[0.04]">
              <AlertTriangle size={12} className="text-red-400/70 shrink-0" />
              <p className="text-xs text-red-400/80 flex-1">Remove this saved anchor?</p>
              <button type="button" onClick={onCancelDelete} className="text-[11px] text-white/40 hover:text-white px-2 py-1 rounded cursor-pointer transition-colors">Keep</button>
              <button type="button" onClick={onDelete} className="text-[11px] text-red-400 hover:text-red-300 font-semibold px-2 py-1 rounded cursor-pointer transition-colors">Remove</button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ── Draft anchor form ──────────────────────────────────────────────────── */

interface TripContext {
  start_date: string;
  end_date: string;
  destinations: string[];
  adults: number;
  children: number;
  timezoneId: string;
}

interface DraftAnchorFormProps {
  anchor: SmartAnchor;
  number: number;
  onChange: (a: SmartAnchor) => void;
  onDelete: () => void;
  tripContext: TripContext;
}

function DraftAnchorForm({ anchor, number, onChange, onDelete, tripContext }: DraftAnchorFormProps) {
  const handleTypeChange = (t: AnchorEventType) => {
    const isTimed = TIMED_TYPES.includes(t);
    onChange({
      ...anchor,
      type: t,
      user_inputs: {},
      details: null,
      prefill_status: 'none',
      start_time: isTimed ? anchor.start_time : undefined,
      end_time: isTimed ? anchor.end_time : undefined,
      duration_minutes: isTimed ? 60 : undefined,
    });
  };

  return (
    <div className="rounded-xl border border-cyan/20 bg-cyan/[0.025] overflow-hidden">
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <div className="flex items-center gap-2">
          <span className="text-[9px] font-bold uppercase tracking-widest text-cyan/40">Smart Anchor</span>
          <span className="text-xs font-bold text-cyan/60">#{number}</span>
        </div>
        <button
          type="button"
          onClick={onDelete}
          className="p-1.5 rounded-lg text-white/30 hover:text-red-400 hover:bg-red-400/10 transition-all cursor-pointer"
        >
          <Trash2 size={13} />
        </button>
      </div>

      <div className="px-4 pb-4 space-y-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-white/40 mb-2">Type</p>
          <TypePicker value={anchor.type} onChange={handleTypeChange} />
        </div>

        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-white/40 mb-2">Details</p>
          <InputForm anchor={anchor} onChange={onChange} tripStart={tripContext.start_date} tripEnd={tripContext.end_date} tz={tripContext.timezoneId || DateTime.local().zoneName} />
        </div>

        {TIMED_TYPES.includes(anchor.type) && (
          <TimingSection anchor={anchor} onChange={onChange} />
        )}
      </div>
    </div>
  );
}

/* ── Main modal ─────────────────────────────────────────────────────────── */

interface SmartAnchorsModalProps {
  savedAnchors: SmartAnchor[];
  drafts: SmartAnchor[];
  setDrafts: React.Dispatch<React.SetStateAction<SmartAnchor[]>>;
  saving: boolean;
  tripContext: TripContext;
  onSave: (anchors: SmartAnchor[]) => Promise<void>;
  onClose: () => void;
}

export default function SmartAnchorsModal({
  savedAnchors,
  drafts,
  setDrafts,
  saving,
  tripContext,
  onSave,
  onClose,
}: SmartAnchorsModalProps) {
  const [deletedSavedIds, setDeletedSavedIds] = useState<Set<string>>(new Set());
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const lastAddedIdRef = useRef<string | null>(null);
  const draftRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const bodyRef = useRef<HTMLDivElement>(null);

  const visibleSaved = savedAnchors.filter(a => !deletedSavedIds.has(a.id));
  const totalCount = visibleSaved.length + drafts.length;

  useEffect(() => {
    if (!lastAddedIdRef.current) return;
    const id = lastAddedIdRef.current;
    lastAddedIdRef.current = null;
    setTimeout(() => {
      const el = draftRefs.current[id];
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 50);
  }, [drafts.length]);

  const handleAddAnchor = () => {
    const anchor = newAnchor();
    lastAddedIdRef.current = anchor.id;
    setDrafts(prev => [...prev, anchor]);
  };

  const handleDeleteSaved = (id: string) => {
    setDeletedSavedIds(prev => new Set([...prev, id]));
    setConfirmDeleteId(null);
  };

  const handleDeleteDraft = (id: string) => {
    setDrafts(prev => prev.filter(d => d.id !== id));
  };

  const handleDraftChange = useCallback((updated: SmartAnchor) => {
    setDrafts(prev => prev.map(d => d.id === updated.id ? updated : d));
  }, [setDrafts]);

  const handleSaveAll = async () => {
    const allAnchors = [...visibleSaved, ...drafts];
    await onSave(allAnchors);
  };

  const noChanges = drafts.length === 0 && visibleSaved.length === savedAnchors.length && deletedSavedIds.size === 0;

  return createPortal(
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        <div
          className="absolute inset-0 bg-black/70 backdrop-blur-sm"
          onClick={() => { if (!saving) onClose(); }}
        />
        <motion.div
          initial={{ opacity: 0, y: 24, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 24, scale: 0.97 }}
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
          className="relative w-full max-w-lg max-h-[92vh] flex flex-col rounded-2xl border border-white/[0.08] bg-[#0a0d12] shadow-[0_30px_80px_rgba(0,0,0,0.7)] overflow-hidden"
        >
          {/* Header */}
          <div className="flex items-center gap-3 px-6 py-5 border-b border-white/[0.06] shrink-0">
            <div className="h-9 w-9 rounded-xl bg-cyan/10 border border-cyan/15 flex items-center justify-center text-cyan">
              <Anchor size={17} />
            </div>
            <div className="flex-1">
              <h2 className="text-base font-bold text-white">Smart Anchors</h2>
              <p className="text-xs text-white/40 mt-0.5">
                {totalCount > 0 ? `${totalCount} anchor${totalCount !== 1 ? 's' : ''}` : 'Lock in pre-booked events — AI plans around them.'}
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="p-2 rounded-xl text-white/40 hover:text-white hover:bg-white/5 transition-all cursor-pointer disabled:opacity-30"
            >
              <X size={18} />
            </button>
          </div>

          {/* Body */}
          <div ref={bodyRef} className="flex-1 overflow-y-auto px-6 py-5 space-y-2 scrollbar-hide">
            {visibleSaved.length > 0 && (
              <div className="space-y-2">
                {visibleSaved.map((anchor, idx) => (
                  <SavedAnchorRow
                    key={anchor.id}
                    anchor={anchor}
                    number={idx + 1}
                    confirmingDelete={confirmDeleteId === anchor.id}
                    onAskDelete={() => setConfirmDeleteId(confirmDeleteId === anchor.id ? null : anchor.id)}
                    onCancelDelete={() => setConfirmDeleteId(null)}
                    onDelete={() => handleDeleteSaved(anchor.id)}
                  />
                ))}
              </div>
            )}

            {drafts.length > 0 && (
              <div className="space-y-3 pt-1">
                {visibleSaved.length > 0 && (
                  <div className="flex items-center gap-2 py-1">
                    <div className="flex-1 h-px bg-white/[0.06]" />
                    <span className="text-[10px] font-bold uppercase tracking-widest text-white/25">New</span>
                    <div className="flex-1 h-px bg-white/[0.06]" />
                  </div>
                )}
                {drafts.map((draft, idx) => (
                  <div
                    key={draft.id}
                    ref={el => { draftRefs.current[draft.id] = el; }}
                  >
                    <DraftAnchorForm
                      anchor={draft}
                      number={visibleSaved.length + idx + 1}
                      onChange={handleDraftChange}
                      onDelete={() => handleDeleteDraft(draft.id)}
                      tripContext={tripContext}
                    />
                  </div>
                ))}
              </div>
            )}

            {totalCount === 0 && (
              <div className="text-center py-10">
                <div className="h-14 w-14 rounded-2xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mx-auto mb-4">
                  <Anchor size={24} className="text-white/20" />
                </div>
                <p className="text-sm font-semibold text-white/50">No anchors yet</p>
                <p className="text-xs text-white/25 mt-1.5 max-w-xs mx-auto">
                  Add pre-booked flights, hotels, or reservations. AI will plan the rest of each day around them.
                </p>
              </div>
            )}

            <button
              type="button"
              onClick={handleAddAnchor}
              className="w-full flex items-center justify-center gap-2 rounded-xl border border-dashed border-white/15 py-3 text-sm text-white/40 hover:border-cyan/30 hover:text-cyan/70 hover:bg-cyan/[0.03] transition-all cursor-pointer mt-1"
            >
              <Plus size={14} />
              {totalCount === 0 ? 'Add Anchor' : 'Add Another Anchor'}
            </button>
          </div>

          {/* Footer */}
          <div className="shrink-0 flex gap-3 px-6 py-4 border-t border-white/[0.06]">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="flex-1 rounded-xl border border-white/10 bg-white/[0.03] py-2.5 text-sm text-white/60 hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSaveAll}
              disabled={saving || noChanges}
              className="flex-1 rounded-xl bg-cyan text-midnight font-bold text-sm py-2.5 hover:bg-[#80fdf6] transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {saving ? (
                <>
                  <span className="h-4 w-4 border-2 border-midnight/30 border-t-midnight rounded-full animate-spin" />
                  Saving…
                </>
              ) : 'Save All'}
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>,
    document.body,
  );
}
