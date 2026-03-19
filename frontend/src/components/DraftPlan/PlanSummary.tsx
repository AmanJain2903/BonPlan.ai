import { useState } from 'react';
import { ClipboardCheck, Calendar, MapPin, Wallet, Gauge, MessageSquare, Users, Route, Plus, Minus, X } from 'lucide-react';
import { DateTime } from 'luxon';
import type { TripDraft } from '../../context/TripContext';

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
  const [showModal, setShowModal] = useState(false);
  const [adults, setAdults] = useState(1);
  const [children, setChildren] = useState(0);

  const origin = trip.tripData?.origin?.city || 'Origin';
  const dests = trip.tripData?.destinations?.map((d: any) => d.city) || [];
  const allNodes = [origin, ...dests];

  return (
    <>
      <div className="w-full max-w-4xl flex flex-col items-center text-center mb-6 -mt-10">
        <div className="mt-3 min-h-[3.25rem] sm:min-h-[4rem] lg:min-h-[4.5rem] flex items-center justify-center w-full">
          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-white tracking-tight animate-[fade-in_400ms_ease-out]">
            Let's review our choices, <span className="text-cyan">{name}</span>.
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

            <div className="p-6 rounded-xl bg-white/[0.03] border border-white/[0.05] space-y-4 transition-colors hover:bg-white/[0.05]">
              <div className="flex items-center gap-3 text-white/70 mb-2">
                <MapPin size={16} />
                <span>Journey Outline</span>
              </div>

              <div className="relative w-full bg-black/20 rounded-xl px-2 py-6">
                {allNodes.length > 1 && (
                  <div className="absolute top-[2.1rem] left-[3.5rem] right-[3.5rem] h-[2px] bg-cyan/40 overflow-hidden rounded-full z-0" />
                )}

                <div className="relative flex justify-between z-10 space-x-2">
                  {allNodes.map((node, i) => (
                    <div key={i} className="flex flex-col items-center gap-3 w-28 mx-auto">
                      <div className="h-5 w-5 rounded-full bg-midnight border-2 border-cyan shadow-[0_0_12px_rgba(102,252,241,0.5)] flex items-center justify-center shrink-0">
                        {i === 0 || i === allNodes.length - 1 ? (
                          <div className="h-2 w-2 rounded-full bg-cyan shadow-[0_0_8px_rgba(102,252,241,1)]" />
                        ) : (
                          <div className="h-1.5 w-1.5 rounded-full bg-cyan/70" />
                        )}
                      </div>
                      <span className="text-cyan font-bold text-[13px] text-center leading-tight [text-shadow:0_0_10px_rgba(102,252,241,0.2)]">
                        {node}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between p-4 rounded-xl bg-white/[0.03] border border-white/[0.05] transition-colors hover:bg-white/[0.05]">
              <div className="flex items-center gap-3 text-white/70">
                <Calendar size={16} />
                <span>Dates</span>
              </div>
              <span className="font-semibold text-cyan tracking-wide">
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

            {trip.tripData?.conversationalContext && (
              <div className="p-4 rounded-xl bg-white/[0.03] border border-white/[0.05] transition-colors hover:bg-white/[0.05]">
                <div className="flex items-center gap-3 text-white/70 mb-3">
                  <MessageSquare size={16} />
                  <span>Additional Context</span>
                </div>
                <p className="text-cyan/90 leading-relaxed italic border-l-2 border-cyan/30 pl-3">
                  "{trip.tripData.conversationalContext}"
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="fixed bottom-0 left-0 w-full z-40 pointer-events-none flex justify-center pb-8 pt-32 bg-gradient-to-t from-black via-black/80 to-transparent">
        <div className="pointer-events-auto">
          <div className="flex items-center gap-4 rounded-full px-6 py-3">
            <span className="text-sm text-white/70 text-center">
              Looks good?
            </span>
            <button
              onClick={() => setShowModal(true)}
              className="ml-2 inline-flex items-center justify-center rounded-full bg-cyan text-midnight font-extrabold text-xs px-4 py-2 transition-transform duration-300 hover:scale-105 hover:bg-[#80fdf6] shadow-[0_0_15px_rgba(102,252,241,0.4)] cursor-pointer"
            >
              YES
            </button>
          </div>
        </div>
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center backdrop-blur-sm animate-[fade-in_200ms_ease-out]">
          <div className="relative w-[90%] max-w-sm rounded-2xl border border-white/10 bg-carbon/80 p-6 shadow-2xl animate-[zoom-in_200ms_ease-out]">
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
