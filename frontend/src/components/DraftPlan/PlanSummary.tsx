import { useState, useMemo, useEffect } from 'react';
import {
  ClipboardCheck, Calendar, MapPin, Wallet, Gauge, Users, Route, Plus, Minus, X,
  Sparkles, User, Sun, ExternalLink, PlaneTakeoff
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { DateTime } from 'luxon';
import type { TripDraft } from '../../context/TripContext';
import { useAuth } from '../../context/AuthContext';
import {
  DEFAULT_PREFERENCES,
  ACTIVITY_INTERESTS,
  DINING_STYLES,
  ACCOMMODATION_STYLES,
  TRAVEL_TO_OPTIONS,
  TRAVEL_AROUND_OPTIONS,
  ACCESSIBILITY_OPTIONS,
  LIFESTYLE_TOGGLES,
  TripPreferences
} from '../../data/preferences';

type PlanDraftProps = {
  trip: TripDraft;
  name: string;
  onDraft: (adults?: number, children?: number) => void;
};

const paceLabels: Record<string, string> = {
  '1': 'Deep Relax', '2': 'Easygoing', '3': 'Balanced', '4': 'Active Explorer', '5': 'Action Packed',
};

const budgetLabels: Record<string, string> = {
  '1': 'Shoestring', '2': 'Modest', '3': 'Comfortable', '4': 'Premium', '5': 'Luxury',
};

const formatDate = (d: any) => {
  if (!d || !d.month || !d.year) return 'Not set';
  return DateTime.fromObject({ year: d.year, month: d.month, day: d.day }).toLocaleString(DateTime.DATE_MED);
};

export function PlanSummary({ trip, name, onDraft }: PlanDraftProps) {
  const { user } = useAuth();
  const [showModal, setShowModal] = useState(false);
  const [showPrefsModal, setShowPrefsModal] = useState(false);
  const [adults, setAdults] = useState(1);
  const [children, setChildren] = useState(0);

  // Disable background scroll when modal is open
  useEffect(() => {
    if (showModal || showPrefsModal) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [showModal, showPrefsModal]);

  const basePreferences = useMemo(() => (user?.preferences || DEFAULT_PREFERENCES) as TripPreferences, [user]);
  const currentPrefs = useMemo(() => trip.tripData?.preferences || basePreferences, [trip.tripData?.preferences, basePreferences]);

  const origin = trip.tripData?.origin?.city || 'Origin';
  const dests = trip.tripData?.destinations?.map((d: any) => d.city) || [];
  const allNodes = [origin, ...dests];

  return (
    <>
      <div className="w-full max-w-4xl flex flex-col items-center text-center mb-6 -mt-10">
        <div className="mt-3 min-h-[3.25rem] sm:min-h-[4rem] lg:min-h-[4.5rem] flex items-center justify-center w-full">
          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-white tracking-tight animate-[fade-in_400ms_ease-out]">
            {name ? (
              <>Let's review our choices, <span className="text-cyan">{name}</span>.</>
            ) : (
              <>Let's review our choices.</>
            )}
          </h1>
        </div>
        <div className="mt-3 h-5 flex items-center justify-center">
          <p className="text-white/40 text-sm animate-[fade-in_500ms_ease-out]">
            Here is a summary of all your trip preferences
          </p>
        </div>
      </div>

      <div className="w-full max-w-5xl animate-[fade-in_400ms_ease-out] pb-24">
        <div className="group relative rounded-2xl border border-white/[0.08] bg-carbon/40 backdrop-blur-sm p-8 overflow-hidden">
          <div className="pointer-events-none absolute -inset-24 opacity-0 group-hover:opacity-100 transition-opacity duration-300 blur-3xl">
            <div
              className="absolute inset-0"
              style={{
                background: 'radial-gradient(circle at 50% 50%, rgba(102,252,241,0.20), transparent 58%)',
              }}
            />
          </div>

          <div className="relative mb-6 flex items-center gap-3 border-b border-white/10 pb-4">
            <div className="h-10 w-10 rounded-xl bg-cyan/10 border border-cyan/15 flex items-center justify-center">
              <ClipboardCheck size={18} className="text-cyan" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white transition-colors duration-300 group-hover:text-cyan">Your Trip Summary</h2>
              <p className="text-xs text-white/50">Everything looks good? Let's draft your BonPlan.</p>
            </div>
          </div>

          <div className="relative space-y-4 text-sm">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="flex items-center justify-between p-4 rounded-xl bg-white/[0.03] border border-white/[0.05] transition-colors hover:bg-white/[0.05]">
                <div className="flex items-center gap-3 text-white/70">
                  <Users size={16} />
                  <span>Planning Style</span>
                </div>
                <span className="font-semibold text-cyan capitalize">{trip.planningStyle || 'Not set'}</span>
              </div>
              <div className="flex items-center justify-between p-4 rounded-xl bg-white/[0.03] border border-white/[0.05] transition-colors hover:bg-white/[0.05]">
                <div className="flex items-center gap-3 text-white/70">
                  <Route size={16} />
                  <span>Routing Style</span>
                </div>
                <span className="font-semibold text-cyan">
                  {trip.routingStyle === 'single-hub' ? 'Single Hub' : trip.routingStyle === 'multi-hop' ? 'Multi Hop' : 'Not set'}
                </span>
              </div>
            </div>

            <div className="p-4 sm:p-6 rounded-xl bg-white/[0.03] border border-white/[0.05] space-y-4 transition-colors hover:bg-white/[0.05]">
              <div className="flex items-center gap-3 text-white/70 mb-2">
                <MapPin size={16} />
                <span>Journey Outline</span>
              </div>

              <div className="relative w-full bg-black/20 rounded-xl py-5">
                <div
                    className="overflow-x-auto scrollbar-hide px-4"
                    style={{
                        maskImage: 'linear-gradient(to right, transparent, black 20px, black calc(100% - 20px), transparent)',
                        WebkitMaskImage: 'linear-gradient(to right, transparent, black 20px, black calc(100% - 20px), transparent)'
                    }}
                >
                    <div className="relative min-w-max px-4">
                        {allNodes.length > 1 && (
                        <div className="absolute top-[0.65rem] left-[10%] right-[10%] h-[2px] bg-cyan/40 overflow-hidden rounded-full z-0" />
                        )}

                        <div className="relative flex items-center justify-center gap-4 sm:gap-8 z-10">
                        {allNodes.map((node, i) => (
                            <div key={i} className="flex flex-col items-center gap-2 w-20 sm:w-28 shrink-0">
                            <div className="h-6 w-6 bg-carbon rounded-full border-2 border-cyan flex items-center justify-center shrink-0">
                                {i === 0 ? (
                                <PlaneTakeoff size={12} className="text-cyan" />
                                ) : (
                                <MapPin size={12} className="text-cyan" />
                                )}
                            </div>
                            <span className="text-cyan font-bold text-[11px] sm:text-[13px] text-center leading-tight [text-shadow:0_0_10px_rgba(102,252,241,0.2)] break-words w-full">
                                {node}
                            </span>
                            </div>
                        ))}
                        </div>
                    </div>
                </div>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 sm:gap-0 p-4 rounded-xl bg-white/[0.03] border border-white/[0.05] transition-colors hover:bg-white/[0.05]">
              <div className="flex items-center gap-3 text-white/70">
                <Calendar size={16} className="shrink-0" />
                <span>Dates</span>
              </div>
              <span className="font-semibold text-cyan tracking-wide text-sm pl-7 sm:pl-0 sm:text-right">
                {formatDate(trip.tripData?.startDate)} — {formatDate(trip.tripData?.endDate)}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="flex items-center justify-between p-4 rounded-xl bg-white/[0.03] border border-white/[0.05] transition-colors hover:bg-white/[0.05]">
                <div className="flex items-center gap-3 text-white/70">
                  <Gauge size={16} />
                  <span>Pace</span>
                </div>
                <span className="font-semibold text-cyan">{trip.tripData?.pace ? paceLabels[trip.tripData.pace] : 'Not set'}</span>
              </div>
              <div className="flex items-center justify-between p-4 rounded-xl bg-white/[0.03] border border-white/[0.05] transition-colors hover:bg-white/[0.05]">
                <div className="flex items-center gap-3 text-white/70">
                  <Wallet size={16} />
                  <span>Budget</span>
                </div>
                <span className="font-semibold text-cyan">{trip.tripData?.budget ? budgetLabels[trip.tripData.budget] : 'Not set'}</span>
              </div>
            </div>

            {/* Trip Preferences Section */}
            <div className="flex items-center justify-between p-4 rounded-xl bg-white/[0.03] border border-white/[0.05] transition-colors hover:bg-white/[0.05]">
              <div className="flex items-center gap-3 text-white/70">
                <Sparkles size={16} />
                <span>Trip Preferences</span>
                <button
                  onClick={() => setShowPrefsModal(true)}
                  className="flex items-center gap-1.5 rounded-lg text-cyan hover:scale-125 transition-all cursor-pointer"
                >
                  <ExternalLink size={13} />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <AnimatePresence>
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 40 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          className="fixed bottom-0 left-0 w-full z-40 pointer-events-none flex justify-center pb-8 pt-32 bg-gradient-to-t from-black via-black/80 to-transparent"
        >
          <div className="pointer-events-auto">
            <div className="flex items-center gap-4 rounded-full px-6 py-3">
              <span className="text-sm text-white/70 text-center">
                Looks good?
              </span>
              <button
                onClick={() => setShowModal(true)}
                className="ml-2 inline-flex items-center justify-center rounded-full bg-cyan text-midnight font-extrabold text-xs px-4 py-2 transition-transform duration-300 hover:scale-[1.02] hover:bg-[#80fdf6] shadow-[0_0_15px_rgba(102,252,241,0.4)] cursor-pointer overflow-hidden"
              >
                YES
              </button>
            </div>
          </div>
        </motion.div>
      </AnimatePresence>
      <div className="h-16 shrink-0" aria-hidden />

      {/* Full Preferences Modal (Read-Only) */}
      <AnimatePresence>
        {showPrefsModal && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setShowPrefsModal(false)}
              className="absolute inset-0 backdrop-blur-md"
            />

            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="relative w-full max-w-3xl max-h-[75vh] overflow-hidden rounded-2xl border border-white/[0.06] bg-carbon/40 backdrop-blur-xl flex flex-col"
            >
              {/* Header */}
              <div className="p-6 flex items-center justify-between border-b border-white/5">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-xl bg-cyan/10 border border-cyan/15 flex items-center justify-center text-cyan">
                    <Sparkles size={20} />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-white tracking-wide">Trip Preferences</h3>
                    <p className="text-xs text-white/40">Your chosen preferences for this trip.</p>
                  </div>
                </div>
                <button
                  onClick={() => setShowPrefsModal(false)}
                  className="h-10 w-10 rounded-full hover:bg-white/5 flex items-center justify-center text-white/40 hover:text-cyan/80 hover:scale-125 transition-colors cursor-pointer"
                >
                  <X size={20} />
                </button>
              </div>

              {/* Content */}
              <div className="flex-1 overflow-y-auto p-6 space-y-8 scrollbar-hide">
                {/* Section Wrapper Helper */}
                {[
                  {
                    icon: Sparkles,
                    title: "Vibe & Rhythm",
                    fields: [
                      { label: "Rhythm", value: currentPrefs.schedule_rhythm.replace('_', ' '), icon: Sun },
                      { label: "Interests", value: currentPrefs.activity_interests.map(v => ACTIVITY_INTERESTS.find(o => o.value === v)?.label || v).join(', ') }
                    ]
                  },
                  {
                    icon: MapPin,
                    title: "Logistics",
                    fields: [
                      { label: "Getting There", value: TRAVEL_TO_OPTIONS.find(o => o.value === currentPrefs.travel_preferences?.travel_to_destination)?.label || 'Any' },
                      { label: "Moving Around", value: TRAVEL_AROUND_OPTIONS.find(o => o.value === currentPrefs.travel_preferences?.travel_around_destination)?.label || 'Any' },
                      { label: "Basecamp", value: ACCOMMODATION_STYLES.find(o => o.value === currentPrefs.accommodation_style)?.label || 'Any' },
                      { label: "Dining", value: DINING_STYLES.find(o => o.value === currentPrefs.dining_style)?.label || 'Any' },
                    ]
                  },
                  {
                    icon: User,
                    title: "Requirements",
                    fields: [
                      { label: "Dietary", value: currentPrefs.dietary_restrictions.length > 0 ? currentPrefs.dietary_restrictions.join(', ') : 'None' },
                      { label: "Accessibility", value: ACCESSIBILITY_OPTIONS.find(o => o.value === currentPrefs.accessibility_preferences)?.label || 'Standard' }
                    ]
                  }
                ].map((sec, i) => (
                  <div key={i} className="space-y-4">
                    <div className="flex items-center gap-2 border-b border-white/5 pb-2">
                      <sec.icon size={14} className="text-cyan/50" />
                      <h4 className="text-[10px] font-bold text-white/40 uppercase tracking-widest">{sec.title}</h4>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {sec.fields.map((f, j) => (
                        <div key={j} className="p-3.5 rounded-xl border border-white/[0.06] bg-white/[0.02] space-y-1">
                          <span className="text-[10px] text-white/40 font-medium uppercase">{f.label}</span>
                          <p className="text-sm text-cyan font-semibold capitalize text-justify">{f.value || 'Not set'}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}

                {/* Lifestyle Toggles */}
                <div className="space-y-4">
                  <div className="flex items-center gap-2 border-b border-white/5 pb-2">
                    <User size={14} className="text-cyan/50" />
                    <h4 className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Lifestyle Preferences</h4>
                  </div>
                  <div className="relative w-full">
                    <div
                      className="flex gap-2 overflow-x-auto scrollbar-hide px-4 py-1"
                      style={{
                        maskImage: 'linear-gradient(to right, transparent, black 24px, black calc(100% - 24px), transparent)',
                        WebkitMaskImage: 'linear-gradient(to right, transparent, black 24px, black calc(100% - 24px), transparent)'
                      }}
                    >
                      {LIFESTYLE_TOGGLES.map(t => (
                        <div
                          key={t.key}
                          className={`px-4 py-2 rounded-full text-xs font-semibold border transition-all shrink-0 whitespace-nowrap ${currentPrefs.other_preferences?.[t.key]
                            ? 'border-cyan/40 bg-cyan/10 text-cyan shadow-[0_0_12px_rgba(102,252,241,0.1)]'
                            : 'border-white/10 bg-white/[0.03] text-white/30 opacity-60'
                            }`}
                        >
                          {t.label}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Additional Notes */}
                {currentPrefs.other_preferences?.additional_notes && (
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 border-b border-white/5 pb-2">
                      <ClipboardCheck size={14} className="text-cyan/50" />
                      <h4 className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Additional Notes</h4>
                    </div>
                    <div className="p-4 rounded-xl border border-white/[0.06] bg-white/[0.02]">
                      <p className="text-xs text-white/70 italic leading-relaxed">
                        "{currentPrefs.other_preferences.additional_notes}"
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="fixed bottom-0 left-0 w-full z-50 pointer-events-none flex justify-center pb-8 pt-24 bg-gradient-to-t from-carbon via-carbon/80 to-transparent">
              </div>
              <div className="h-18 shrink-0" aria-hidden />
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {showModal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center backdrop-blur-sm animate-[fade-in_200ms_ease-out]">
          <div className="relative w-[90%] max-w-sm rounded-2xl border border-white/[0.08] bg-carbon/40 p-6 shadow-2xl animate-[zoom-in_200ms_ease-out]">
            <button
              onClick={() => setShowModal(false)}
              className="absolute right-4 top-4 text-white/40 hover:text-white/80 transition-colors"
            >
              <X size={20} />
            </button>
            <h3 className="text-xl font-bold text-white mb-2">Who's joining?</h3>
            <p className="text-sm text-white/50 mb-6">Let's dial in your guest count.</p>

            <div className="space-y-4 mb-8">
              {/* Adults */}
              <div className="flex items-center justify-between p-3 rounded-xl bg-white/[0.03] border border-white/[0.05]">
                <span className="font-semibold text-white/80">Adults</span>
                <div className="flex items-center gap-4">
                  <button onClick={() => setAdults(Math.max(1, adults - 1))} className="h-8 w-8 rounded-full bg-white/5 flex items-center justify-center hover:bg-white/10 transition">
                    <Minus size={14} className="text-white" />
                  </button>
                  <span className="w-4 text-center text-white font-bold">{adults}</span>
                  <button onClick={() => setAdults(adults + 1)} className="h-8 w-8 rounded-full bg-cyan/10 flex items-center justify-center hover:bg-cyan/20 transition">
                    <Plus size={14} className="text-cyan" />
                  </button>
                </div>
              </div>

              {/* Children */}
              <div className="flex items-center justify-between p-3 rounded-xl bg-white/[0.03] border border-white/[0.05]">
                <div className="flex flex-col">
                  <span className="font-semibold text-white/80">Children</span>
                  <span className="text-[10px] text-white/40">Under 12</span>
                </div>
                <div className="flex items-center gap-4">
                  <button onClick={() => setChildren(Math.max(0, children - 1))} className="h-8 w-8 rounded-full bg-white/5 flex items-center justify-center hover:bg-white/10 transition">
                    <Minus size={14} className="text-white" />
                  </button>
                  <span className="w-4 text-center text-white font-bold">{children}</span>
                  <button onClick={() => setChildren(children + 1)} className="h-8 w-8 rounded-full bg-cyan/10 flex items-center justify-center hover:bg-cyan/20 transition">
                    <Plus size={14} className="text-cyan" />
                  </button>
                </div>
              </div>
            </div>

            <button
              onClick={() => {
                setShowModal(false);
                onDraft(adults, children);
              }}
              className="w-full inline-flex items-center justify-center rounded-xl bg-cyan text-midnight font-extrabold text-sm px-6 py-4 transition-all duration-300 hover:scale-[1.02] hover:bg-[#80fdf6] shadow-[0_0_20px_rgba(102,252,241,0.2)] hover:shadow-[0_0_30px_rgba(102,252,241,0.6)] cursor-pointer"
            >
              DRAFT BON PLAN
            </button>
          </div>
        </div>
      )}
    </>
  );
}
