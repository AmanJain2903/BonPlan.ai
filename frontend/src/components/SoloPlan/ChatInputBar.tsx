import { useMemo, useRef, useState, useEffect, type KeyboardEvent } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Square, Clock, ChevronUp, X, Check } from 'lucide-react';
import { EVENT_ICON, EVENT_LABEL, eventIdentityKey } from './constants';
import type { ChatMode, ItineraryDay, AttachedEventRef } from './types';

const SINGLE_LINE_INPUT_HEIGHT = 44;

interface ChatInputBarProps {
  isGenerating: boolean;
  chatMode: ChatMode;
  chatInput: string;
  setChatInput: (val: string) => void;
  itineraryDays: ItineraryDay[];
  selectedEvents: AttachedEventRef[];
  setSelectedEvents: (events: AttachedEventRef[]) => void;
  onSend: () => void;
  onStop: () => void;
  elapsedSeconds: number;
  errorType?: 'stopped' | 'error' | null;
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export default function ChatInputBar({
  isGenerating,
  chatMode,
  chatInput,
  setChatInput,
  itineraryDays,
  selectedEvents,
  setSelectedEvents,
  onSend,
  onStop,
  elapsedSeconds,
  errorType,
}: ChatInputBarProps) {
  const isEditingMode = chatMode === 'editing';
  const [isPickerOpen, setIsPickerOpen] = useState(false);
  const [activeDayIndex, setActiveDayIndex] = useState(0);
  const [activeEventIndex, setActiveEventIndex] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const dayRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const eventRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const pickerDays = useMemo(() => {
    return itineraryDays
      .map((day) => ({
        dayNumber: day.dayNumber,
        label: day.title?.trim() ? day.title : `Day ${day.dayNumber}`,
        events: (day.events || [])
          .filter((event: any) => typeof event?.day_number === 'number' && typeof event?.event_number === 'number')
          .map((event: any) => ({
            day_number: event.day_number as number,
            event_number: event.event_number as number,
            event_id: typeof event.event_id === 'string' ? event.event_id : undefined,
            event_type: String(event.event_type || ''),
            title: getEventMainTitle(event),
          })),
      }))
      .filter((day) => day.events.length > 0);
  }, [itineraryDays]);

  const selectedKeySet = useMemo(
    () => new Set(selectedEvents.map((event) => event.event_id ? `id:${event.event_id}` : `${event.day_number}-${event.event_number}`)),
    [selectedEvents],
  );

  const selectedEventDisplay = useMemo(() => {
    const lookup = new Map<string, { title: string; event_type: string }>();
    for (const day of pickerDays) {
      for (const event of day.events) {
        lookup.set(event.event_id ? `id:${event.event_id}` : `${event.day_number}-${event.event_number}`, {
          title: event.title,
          event_type: event.event_type,
        });
      }
    }
    return selectedEvents
      .map((selected) => {
        const meta = lookup.get(`${selected.day_number}-${selected.event_number}`);
        const byId = selected.event_id ? lookup.get(`id:${selected.event_id}`) : null;
        const resolved = byId || meta;
        if (!resolved) return null;
        return {
          ...selected,
          title: resolved.title,
          event_type: resolved.event_type,
        };
      })
      .filter((item): item is NonNullable<typeof item> => item != null);
  }, [pickerDays, selectedEvents]);

  const activeDay = pickerDays[activeDayIndex];
  const activeEvents = activeDay?.events || [];
  const activeEvent = activeEvents[activeEventIndex];

  const toggleEventSelection = (event: { day_number: number; event_number: number; event_id?: string }) => {
    const key = event.event_id ? `id:${event.event_id}` : `${event.day_number}-${event.event_number}`;
    if (selectedKeySet.has(key)) {
      setSelectedEvents(
        selectedEvents.filter(
          (selected) =>
            eventIdentityKey(selected) !== eventIdentityKey(event),
        ),
      );
      return;
    }
    setSelectedEvents([
      ...selectedEvents,
      { day_number: event.day_number, event_number: event.event_number, event_id: event.event_id },
    ]);
  };

  useEffect(() => {
    if (!isPickerOpen) return;
    if (pickerDays.length === 0) {
      setActiveDayIndex(0);
      setActiveEventIndex(0);
      return;
    }
    if (activeDayIndex >= pickerDays.length) setActiveDayIndex(0);
    const eventsForDay = pickerDays[Math.min(activeDayIndex, pickerDays.length - 1)]?.events || [];
    if (eventsForDay.length === 0) setActiveEventIndex(0);
    if (activeEventIndex >= eventsForDay.length) setActiveEventIndex(0);
  }, [isPickerOpen, pickerDays, activeDayIndex, activeEventIndex]);

  useEffect(() => {
    if (!isPickerOpen) return;
    dayRefs.current[activeDayIndex]?.scrollIntoView({
      behavior: 'smooth',
      block: 'nearest',
      inline: 'nearest',
    });
  }, [isPickerOpen, activeDayIndex]);

  useEffect(() => {
    if (!isPickerOpen) return;
    eventRefs.current[activeEventIndex]?.scrollIntoView({
      behavior: 'smooth',
      block: 'nearest',
      inline: 'nearest',
    });
  }, [isPickerOpen, activeEventIndex, activeDayIndex]);

  useEffect(() => {
    const target = textareaRef.current;
    if (!target) return;
    target.style.height = 'auto';
    if (!chatInput.trim()) {
      target.style.height = `${SINGLE_LINE_INPUT_HEIGHT}px`;
      return;
    }
    target.style.height = `${Math.max(SINGLE_LINE_INPUT_HEIGHT, Math.min(target.scrollHeight, 120))}px`;
  }, [chatInput, isEditingMode]);

  const openPicker = () => {
    if (!isEditingMode || pickerDays.length === 0) return;
    setIsPickerOpen(true);
  };

  const handlePickerKeyboard = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === '@' && isEditingMode) {
      e.preventDefault();
      openPicker();
      return;
    }

    if (
      isPickerOpen &&
      e.key.length === 1 &&
      e.key !== '@' &&
      !e.ctrlKey &&
      !e.metaKey &&
      !e.altKey
    ) {
      setIsPickerOpen(false);
    }

    if (!isPickerOpen || !isEditingMode) return;

    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      setActiveDayIndex((prev) => Math.max(0, prev - 1));
      setActiveEventIndex(0);
      return;
    }
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      setActiveDayIndex((prev) => Math.min(pickerDays.length - 1, prev + 1));
      setActiveEventIndex(0);
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveEventIndex((prev) => Math.max(0, prev - 1));
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveEventIndex((prev) => Math.min(activeEvents.length - 1, prev + 1));
      return;
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (activeEvent) toggleEventSelection(activeEvent);
      return;
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      setIsPickerOpen(false);
    }
  };

  const handleSend = () => {
    if (!isEditingMode || !chatInput.trim() || isGenerating) return;
    setIsPickerOpen(false);
    const target = textareaRef.current;
    if (target) {
      target.style.height = `${SINGLE_LINE_INPUT_HEIGHT}px`;
    }
    onSend();
  };

  return (
    <div className="w-full shrink-0 px-3 pb-2 sm:px-6 sm:pb-3 relative items-center flex flex-col">
      <AnimatePresence>
        {isGenerating && !errorType && (
          <motion.div
            layout
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            className={`${isEditingMode ? 'absolute -top-9' : 'absolute bottom-5'} flex items-center gap-3 z-20`}
          >
            <div className="flex items-center gap-1.5 px-3 py-2 bg-black/40 backdrop-blur-md border border-white/10 rounded-full text-[10px] font-bold uppercase tracking-widest text-white/50">
              <Clock className="w-3 h-3 text-cyan/60" />
              <span className="font-mono">{formatElapsed(elapsedSeconds)}</span>
            </div>

            <button
              onClick={onStop}
              className="flex items-center gap-2 px-4 py-2 bg-black/40 backdrop-blur-md border border-white/10 rounded-full text-[10px] font-bold uppercase tracking-widest text-white/60 hover:text-white hover:border-red-500/30 hover:bg-red-500/5 transition-all group"
            >
              <Square className="w-3 h-3 text-red-500 group-hover:scale-110 transition-transform fill-red-500/20" />
              <span>Stop Generation</span>
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.div
        initial={false}
        animate={{
          opacity: isEditingMode ? 1 : 0,
          y: isEditingMode ? 0 : 20,
          pointerEvents: isEditingMode ? 'auto' : 'none'
        }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        className="w-full max-w-3xl mx-auto"
      >
        {selectedEventDisplay.length > 0 && (
          <div className="w-full mb-2 flex flex-wrap gap-2">
            {selectedEventDisplay.map((event) => {
              const key = event.event_id ? `id:${event.event_id}` : `${event.day_number}-${event.event_number}`;
              const Icon = (EVENT_ICON as Record<string, any>)[event.event_type] || EVENT_ICON.DEFAULT;
              return (
                <button
                  key={key}
                  onClick={() =>
                    setSelectedEvents(
                      selectedEvents.filter(
                        (selected) =>
                          eventIdentityKey(selected) !== eventIdentityKey(event),
                      ),
                    )
                  }
                  className="inline-flex items-center gap-1.5 max-w-full px-2.5 py-1 rounded-full bg-cyan/12 border border-cyan/35 text-cyan text-[11px]"
                >
                  <Icon className="w-3 h-3 shrink-0" />
                  <span className="truncate max-w-[220px]">{event.title}</span>
                  <X className="w-3 h-3 shrink-0" />
                </button>
              );
            })}
          </div>
        )}

        <motion.div layout className="relative group w-full">
          <div
            className={`absolute -inset-0.5 rounded-2xl blur transition-all duration-300 ${
              isPickerOpen
                ? 'bg-gradient-to-r from-cyan/30 to-blue/30 opacity-35'
                : 'bg-gradient-to-r from-cyan/20 to-blue/20 opacity-15 group-hover:opacity-30'
            }`}
          />
          <div className="relative overflow-hidden bg-black/60 backdrop-blur-xl border border-white/12 rounded-2xl shadow-2xl focus-within:border-cyan/50 transition-all duration-300">
            <button
              onClick={() => setIsPickerOpen((prev) => !prev)}
              disabled={!isEditingMode || pickerDays.length === 0}
              className="w-full h-8 px-4 text-white/70 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-all flex items-center justify-between border-b border-white/10"
            >
              <span className="text-[11px] sm:text-xs font-medium truncate">Tag along any specific events</span>
              <ChevronUp className={`w-3.5 h-3.5 shrink-0 transition-transform ${isPickerOpen ? 'rotate-180' : ''}`} />
            </button>

            <AnimatePresence initial={false}>
              {isPickerOpen && (
                <motion.div
                  key="event-picker"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.24, ease: 'easeOut' }}
                  className="overflow-hidden border-b border-white/10"
                >
                  <motion.div
                    initial={{ y: -8 }}
                    animate={{ y: 0 }}
                    exit={{ y: -8 }}
                    transition={{ duration: 0.2, ease: 'easeOut' }}
                    className="w-full bg-black/25 p-3"
                  >
                    {pickerDays.length === 0 ? (
                      <div className="text-xs text-white/45 px-1 py-2">No events available.</div>
                    ) : (
                      <>
                        <div className="overflow-x-auto scrollbar-hide">
                          <div className="flex items-center gap-2 w-max min-w-full pb-2">
                            {pickerDays.map((day, index) => (
                              <button
                                key={day.dayNumber}
                                ref={(node) => {
                                  dayRefs.current[index] = node;
                                }}
                                onClick={() => {
                                  setActiveDayIndex(index);
                                  setActiveEventIndex(0);
                                }}
                                className={`shrink-0 px-3 py-1.5 rounded-full text-xs border transition-all ${
                                  index === activeDayIndex
                                    ? 'border-cyan/60 bg-cyan/15 text-cyan'
                                    : 'border-white/10 bg-white/[0.02] text-white/60 hover:text-white/85'
                                }`}
                              >
                                {day.label}
                              </button>
                            ))}
                          </div>
                        </div>

                        <div className="max-h-48 overflow-y-auto scrollbar-hide mt-1 pr-1">
                          <div className="flex flex-col gap-1.5">
                            {activeEvents.map((event, index) => {
                              const key = event.event_id ? `id:${event.event_id}` : `${event.day_number}-${event.event_number}`;
                              const Icon = (EVENT_ICON as Record<string, any>)[event.event_type] || EVENT_ICON.DEFAULT;
                              const isSelected = selectedKeySet.has(key);
                              const isActive = index === activeEventIndex;
                              return (
                                <button
                                  key={key}
                                  ref={(node) => {
                                    eventRefs.current[index] = node;
                                  }}
                                  onClick={() => toggleEventSelection(event)}
                                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-left border transition-all ${
                                    isActive
                                      ? 'border-cyan/60 bg-cyan/12'
                                      : 'border-white/10 bg-white/[0.02] hover:border-white/20'
                                  }`}
                                >
                                  <Icon className="w-3.5 h-3.5 text-cyan shrink-0" />
                                  <span className="text-xs text-white/85 truncate flex-1">{event.title}</span>
                                  <span className="text-[10px] uppercase tracking-wider text-white/35">
                                    {EVENT_LABEL[event.event_type] || event.event_type}
                                  </span>
                                  {isSelected && <Check className="w-3.5 h-3.5 text-cyan shrink-0" />}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      </>
                    )}
                  </motion.div>
                </motion.div>
              )}
            </AnimatePresence>

            <div className="flex items-center p-1.5 px-4">
              <textarea
                ref={textareaRef}
                value={chatInput}
                onChange={(e) => {
                  if (isPickerOpen && e.target.value.trim().length > 0 && !e.target.value.endsWith('@')) {
                    setIsPickerOpen(false);
                  }
                  setChatInput(e.target.value);
                }}
                onKeyDown={(e) => {
                  handlePickerKeyboard(e);
                  if (e.defaultPrevented) return;
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement;
                  target.style.height = 'auto';
                  target.style.height = `${Math.max(SINGLE_LINE_INPUT_HEIGHT, Math.min(target.scrollHeight, 120))}px`;
                }}
                disabled={!isEditingMode}
                placeholder="Want to make edits?"
                className="w-full bg-transparent border-none text-white text-sm focus:outline-none focus:ring-0 py-2.5 resize-none overflow-y-auto scrollbar-hide disabled:opacity-30 disabled:cursor-not-allowed placeholder:text-white/40"
                rows={1}
                style={{ minHeight: `${SINGLE_LINE_INPUT_HEIGHT}px`, maxHeight: '120px' }}
              />
              <button
                onClick={handleSend}
                disabled={!isEditingMode || !chatInput.trim() || isGenerating}
                className="shrink-0 ml-2 p-2 rounded-xl bg-cyan/90 text-black disabled:opacity-20 disabled:cursor-not-allowed hover:bg-cyan hover:scale-110 active:scale-90 transition-all"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </div>
  );
}

function getEventMainTitle(event: any): string {
  if (!event) return 'Untitled event';

  switch (event.event_type) {
    case 'ACTIVITY':
    case 'DINING':
      return event.place_details?.event_name || event.place_details?.place_name || 'Untitled place';
    case 'OTHER':
      return event.other_details?.event_name || event.other_details?.place_name || 'Untitled event';
    case 'HOTEL_CHECKIN':
      return event.hotel_checkin_details?.hotel_name || 'Hotel check-in';
    case 'HOTEL_CHECKOUT':
      return event.hotel_checkout_details?.hotel_name || 'Hotel check-out';
    case 'FLIGHT_TAKEOFF': {
      const airline = event.flight_takeoff_details?.airline || 'Flight';
      const number = event.flight_takeoff_details?.flight_number;
      return number ? `${airline} ${number}` : airline;
    }
    case 'FLIGHT_LAND': {
      const airline = event.flight_land_details?.airline || 'Flight';
      const number = event.flight_land_details?.flight_number;
      return number ? `${airline} ${number}` : airline;
    }
    case 'CAR_PICKUP': {
      const vehicle = event.car_pickup_details?.vehicle?.vehicle_name;
      const company = event.car_pickup_details?.rental_company_name;
      if (vehicle && company) return `Pickup ${vehicle} from ${company}`;
      if (company) return `Pickup from ${company}`;
      return 'Car pickup';
    }
    case 'CAR_DROPOFF': {
      const company = event.car_dropoff_details?.rental_company_name;
      if (company) return `Dropoff at ${company}`;
      return 'Car dropoff';
    }
    case 'COMMUTE': {
      const mode = String(event.commute_details?.travel_mode || 'COMMUTE').toLowerCase();
      return `${mode.charAt(0).toUpperCase()}${mode.slice(1)} commute`;
    }
    default:
      return EVENT_LABEL[event.event_type] || 'Untitled event';
  }
}
