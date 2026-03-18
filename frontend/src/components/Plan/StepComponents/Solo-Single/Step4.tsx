import { useEffect, useMemo, useState } from 'react';
import { CalendarPlus, CalendarCheck } from 'lucide-react';
import { DayPicker } from 'react-day-picker';
import type { SoloSingleTripData, TripDate } from '../../../../context/TripContext';
import { api } from '../../../../apis/utils';
import { DateTime } from 'luxon';

// Optional: if you haven't imported the base styles in your global css
import 'react-day-picker/dist/style.css'; 

type SoloSingleStep4Props = {
  tripData: SoloSingleTripData | null;
  updateTripData: (patch: Partial<SoloSingleTripData>) => void;
  onNext: () => void;
};

// --- 1. Solo Theme (All Cyan) ---
const THEME = {
  iconBg: 'bg-cyan/10 border-cyan/15',
  iconColor: 'text-cyan',
  hoverTitle: 'group-hover:text-cyan',
  glowColor: 'rgba(102,252,241,0.20)',
};

// --- 2. Reusable Inline Calendar Card ---
type DateCardProps = {
  title: string;
  subtitle: string;
  Icon: any;
  gradientPos: string;
  inputValue: string;
  onChange: (val: string) => void;
  minDateJs?: Date;
  animDelay?: string;
  rangeStartIso?: string;
  rangeEndIso?: string;
  rangeMode?: 'start' | 'end';
};

const DateCard = ({
  title,
  subtitle,
  Icon,
  gradientPos,
  inputValue,
  onChange,
  minDateJs,
  rangeStartIso,
  rangeEndIso,
  rangeMode,
}: DateCardProps) => {
  
  // Convert YYYY-MM-DD to a local JS Date at midnight (date-only, no timezone drift)
  const selectedDate = useMemo(() => {
    if (!inputValue) return undefined;
    const dt = DateTime.fromISO(inputValue);
    return new Date(dt.year, dt.month - 1, dt.day);
  }, [inputValue]);

  const rangeStart = useMemo(() => {
    if (!rangeStartIso) return undefined;
    const dt = DateTime.fromISO(rangeStartIso);
    return new Date(dt.year, dt.month - 1, dt.day);
  }, [rangeStartIso]);

  const rangeEnd = useMemo(() => {
    if (!rangeEndIso) return undefined;
    const dt = DateTime.fromISO(rangeEndIso);
    return new Date(dt.year, dt.month - 1, dt.day);
  }, [rangeEndIso]);

  const inBetweenModifier = useMemo(() => {
    if (!rangeStart || !rangeEnd || !rangeMode) return undefined;

    const startTime = rangeStart.getTime();
    const endTime = rangeEnd.getTime();
    if (endTime <= startTime) return undefined;

    if (rangeMode === 'start') {
      // Start calendar: highlight (start + 1) .. end (inclusive)
      const from = new Date(startTime);
      from.setDate(from.getDate() + 1);
      return (date: Date) => date >= from && date <= rangeEnd;
    }

    // End calendar: highlight start .. (end - 1) (inclusive)
    const to = new Date(endTime);
    to.setDate(to.getDate() - 1);
    return (date: Date) => date >= rangeStart && date <= to;
  }, [rangeEnd, rangeMode, rangeStart]);

  return (
    <div className="group relative rounded-2xl border border-white/[0.08] bg-carbon/40 backdrop-blur-sm p-8 flex flex-col overflow-hidden">
      {/* Background Glow */}
      <div className="pointer-events-none absolute -inset-24 opacity-0 group-hover:opacity-100 transition-opacity duration-300 blur-3xl">
        <div
          className="absolute inset-0"
          style={{ background: `radial-gradient(circle at ${gradientPos}, ${THEME.glowColor}, transparent 58%)` }}
        />
      </div>

      {/* Header */}
      <div className="flex items-center gap-3 mb-3">
        <div className={`h-11 w-11 rounded-xl flex items-center justify-center border ${THEME.iconBg}`}>
          <Icon size={18} className={THEME.iconColor} />
        </div>
        <div className="min-w-0">
          <h2 className={`text-lg font-bold text-white transition-colors ${THEME.hoverTitle}`}>
            {title}
          </h2>
          <p className="text-xs text-white/35">
            {subtitle}
          </p>
        </div>
      </div>

      {/* Inline React Day Picker */}
      <div className="flex-1 flex justify-center items-start bg-white/[0.01] rounded-xl border border-white/[0.04] p-4">
        <DayPicker
          mode="single"
          selected={selectedDate}
          onSelect={(d) => {
            if (d) {
              // Treat the picked day as date-only (local calendar day)
              const iso = DateTime.fromObject(
                { year: d.getFullYear(), month: d.getMonth() + 1, day: d.getDate() },
              ).toFormat('yyyy-MM-dd');
              onChange(iso);
            }
          }}
          disabled={minDateJs ? { before: minDateJs } : undefined}
          modifiers={
            inBetweenModifier
              ? {
                  inBetween: inBetweenModifier,
                }
              : undefined
          }
          // Tailwind formatting for the calendar
          className="theme-cyan text-white text-sm m-0"
          modifiersClassNames={{
            selected: 'bg-cyan text-midnight font-bold rounded-lg hover:bg-cyan/90 hover:text-midnight',
            today: 'text-cyan font-bold',
            disabled: 'text-white/15 line-through opacity-60 cursor-not-allowed',
            inBetween: 'bg-cyan/10 text-white/85 rounded-lg',
          }}
          styles={{
            caption: { color: 'white', fontWeight: 'bold' },
            head_cell: { color: 'rgba(255,255,255,0.4)', fontWeight: 'normal' },
            cell: { padding: '2px' },
          }}
        />
      </div>
    </div>
  );
};

// --- 3. Main Step 4 Component ---
export function SoloSingleStep4Dates({ tripData, updateTripData, onNext }: SoloSingleStep4Props) {
  const origin = tripData?.origin ?? null;

  const [timezoneId, setTimezoneId] = useState<string | null>(
     null,
  );

  const [startInput, setStartInput] = useState<string>(() => {
    const d = tripData?.startDate;
    return d && d.year && d.month && d.day
      ? DateTime.fromObject({ year: d.year, month: d.month, day: d.day }).toISODate() ?? ''
      : '';
  });

  const [endInput, setEndInput] = useState<string>(() => {
    const d = tripData?.endDate;
    return d && d.year && d.month && d.day
      ? DateTime.fromObject({ year: d.year, month: d.month, day: d.day }).toISODate() ?? ''
      : '';
  });

  useEffect(() => {
    if (!origin?.lat || !origin?.lng) return;

    let cancelled = false;

    api
      .getTimezoneId(origin.lat, origin.lng)
      .then((res) => {
        if (cancelled) return;
        setTimezoneId(res.timezoneId);

        const patch: Partial<SoloSingleTripData> = {};
        const baseDate: TripDate = {
          day: null,
          month: null,
          year: null,
          timezoneId: res.timezoneId,
        };

        patch.startDate = tripData?.startDate
          ? { ...tripData.startDate, timezoneId: res.timezoneId }
          : baseDate;
        patch.endDate = tripData?.endDate
          ? { ...tripData.endDate, timezoneId: res.timezoneId }
          : baseDate;

        updateTripData(patch);
      })
      .catch(() => {
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [origin?.lat, origin?.lng]);

  const effectiveZone = timezoneId || DateTime.local().zoneName;

  // DayPicker uses local JS Dates. We must convert zone-aware "today" into a date-only local JS Date.
  const minDateJs = useMemo(() => {
    const dt = DateTime.now().setZone(effectiveZone).startOf('day');
    return new Date(dt.year, dt.month - 1, dt.day);
  }, [effectiveZone]);

  // End date can't be before the selected start date.
  const endMinDateJs = useMemo(() => {
    if (!startInput) return minDateJs;
    const s = DateTime.fromISO(startInput, { zone: effectiveZone }).startOf('day');
    const startJs = new Date(s.year, s.month - 1, s.day);
    return startJs > minDateJs ? startJs : minDateJs;
  }, [effectiveZone, minDateJs, startInput]);

  // If start date moves forward beyond end date, clear end date.
  useEffect(() => {
    if (!startInput || !endInput) return;
    const s = DateTime.fromISO(startInput, { zone: effectiveZone }).startOf('day');
    const e = DateTime.fromISO(endInput, { zone: effectiveZone }).startOf('day');
    if (e < s) setEndInput('');
    if (s < DateTime.now().startOf('day')){
      setStartInput('');
      setEndInput('');
    }
  }, [effectiveZone, startInput, endInput]);

  const canConfirm = startInput !== '' && endInput !== '';

  const handleConfirm = () => {
    if (!canConfirm) return;

    const start = DateTime.fromISO(startInput, { zone: effectiveZone });
    const end = DateTime.fromISO(endInput, { zone: effectiveZone });

    updateTripData({
      startDate: { year: start.year, month: start.month, day: start.day, timezoneId: effectiveZone },
      endDate: { year: end.year, month: end.month, day: end.day, timezoneId: effectiveZone },
    });

    onNext();
  };

  const prettyStart = startInput ? DateTime.fromISO(startInput, { zone: effectiveZone }).toLocaleString(DateTime.DATE_MED) : '';
  const prettyEnd = endInput ? DateTime.fromISO(endInput, { zone: effectiveZone }).toLocaleString(DateTime.DATE_MED) : '';

  return (
    <>
    <div className={`w-full max-w-5xl animate-[fade-in_400ms_ease-out] ${canConfirm ? 'pb-24' : ''}`}>
      <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
        {/* Start Date */}
        <DateCard
          title="When do we kick things off?"
          subtitle="Your trip start date"
          Icon={CalendarPlus}
          gradientPos="30% 20%"
          inputValue={startInput}
          onChange={setStartInput}
          minDateJs={minDateJs}
          rangeStartIso={startInput && endInput ? startInput : undefined}
          rangeEndIso={startInput && endInput ? endInput : undefined}
          rangeMode="start"
        />

        {/* End Date */}
        <DateCard
          title="When does this chapter wrap?"
          subtitle="The day you head back"
          Icon={CalendarCheck}
          gradientPos="70% 20%"
          inputValue={endInput}
          onChange={setEndInput}
          minDateJs={endMinDateJs}
          animDelay="0.3s" // Offsets the wiggle animation slightly for a natural feel!
          rangeStartIso={startInput && endInput ? startInput : undefined}
          rangeEndIso={startInput && endInput ? endInput : undefined}
          rangeMode="end"
        />
      </div>
      </div>

      {/* Sticky Yes button at bottom of viewport */}
      {canConfirm && (
        // 1. Taller gradient (pt-32) creates a perfectly smooth fade with no harsh lines
        <div className="fixed bottom-0 left-0 w-full z-50 pointer-events-none flex justify-center pb-8 pt-32 bg-gradient-to-t from-black via-black/80 to-transparent">
          
          <div className="pointer-events-auto">
            <div className="flex items-center gap-4 rounded-full px-6 py-3">
              <span className="text-sm text-white/80 text-center pl-2 select-none">
                Are we travelling from{' '}
                <span className="text-cyan font-semibold">{prettyStart}</span>{' '}
                to{' '}
                <span className="text-cyan font-semibold">{prettyEnd}</span>?
              </span>
              <button
                type="button"
                onClick={handleConfirm}
                className="ml-2 inline-flex items-center justify-center rounded-full bg-cyan text-midnight font-extrabold text-xs px-4 py-2 transition-transform duration-300 hover:scale-105 hover:bg-[#80fdf6] hover:shadow-[0_0_15px_rgba(102,252,241,0.4)] cursor-pointer"
              >
                YES
              </button>
            </div>
          </div>
        </div>
      )}
      {canConfirm && <div className="h-16 shrink-0" aria-hidden />}
    </>
  );
}