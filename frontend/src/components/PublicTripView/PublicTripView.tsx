import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Calendar, MapPin, Users, DollarSign, Clock } from 'lucide-react';
import { api, PublicPlanData } from '../../apis/plan';
import SEOHead from '../shared/SEOHead';
import { renderSubCardForEvent } from '../SoloPlan/subcards';

function formatDate(d: any): string {
  if (!d) return '';
  if (typeof d === 'string') return d;
  if (d.month && d.day && d.year) return `${d.month}/${d.day}/${d.year}`;
  return '';
}

function buildDescription(plan: PublicPlanData): string {
  const dests = plan.destinations?.join(', ') || plan.origin || 'an amazing destination';
  const days = plan.days ? `${plan.days}-day ` : '';
  const who = plan.adults > 1 ? `group of ${plan.adults}` : 'solo traveler';
  const budget = plan.budget ? ` on a ${plan.budget.toLowerCase()} budget` : '';
  const events = plan.events?.filter(
    (e: any) => !['START', 'END', 'COMMUTE'].includes(e.event_type)
  ).length || 0;
  const highlights = events > 0 ? ` Includes ${events} activities, dining, and more.` : '';
  return `Explore this AI-generated ${days}itinerary to ${dests} for a ${who}${budget}.${highlights} Planned by BonPlan.ai.`.slice(0, 160);
}

function buildJsonLd(plan: PublicPlanData, url: string): object {
  const activities = plan.events
    ?.filter((e: any) => e.event_type === 'ACTIVITY' || e.event_type === 'DINING')
    .map((e: any) => ({
      '@type': e.event_type === 'DINING' ? 'FoodEstablishment' : 'TouristAttraction',
      name: e.place_details?.name || e.other_details?.title || 'Activity',
      description: e.place_details?.description || e.other_details?.description || '',
    }));

  return {
    '@context': 'https://schema.org',
    '@type': 'TouristTrip',
    name: plan.title || `Trip to ${plan.destinations?.join(' & ')}`,
    description: buildDescription(plan),
    url,
    touristType: plan.planning_type === 'solo' ? 'Solo traveler' : 'Group',
    itinerary: activities?.slice(0, 10) || [],
    offers: plan.cost
      ? { '@type': 'Offer', price: plan.cost, priceCurrency: 'USD' }
      : undefined,
  };
}

function groupByDay(events: any[]): [string, { date: string; events: any[] }][] {
  const map = new Map<string, { date: string; events: any[] }>();
  for (const e of events) {
    if (e.event_type === 'START' || e.event_type === 'END') continue;
    const key = e.day_title || 'Other';
    if (!map.has(key)) map.set(key, { date: e.date || '', events: [] });
    map.get(key)!.events.push(e);
  }
  return Array.from(map.entries());
}

// No-op since public view has no interactive map
const noop = () => {};

export default function PublicTripView() {
  const { tripId } = useParams<{ tripId: string }>();
  const [plan, setPlan] = useState<PublicPlanData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!tripId) return;
    api.getPublicPlan(tripId)
      .then((res) => {
        if (res.status_code === 200 && res.plan) setPlan(res.plan);
        else setError(res.message || 'Itinerary not found.');
      })
      .catch(() => setError('Failed to load itinerary.'))
      .finally(() => setLoading(false));
  }, [tripId]);

  if (loading) {
    return (
      <div className="relative z-10 min-h-screen flex items-center justify-center">
        <div className="w-7 h-7 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !plan) {
    return (
      <>
        <SEOHead title="Itinerary Not Found" noIndex />
        <div className="relative z-10 min-h-screen flex flex-col items-center justify-center gap-4 text-white/60">
          <p className="text-lg">{error || 'Itinerary not found.'}</p>
          <Link to="/" className="text-cyan-400 hover:underline text-sm">← BonPlan.ai</Link>
        </div>
      </>
    );
  }

  const destinations = plan.destinations?.join(' & ') || plan.origin || 'Unknown Destination';
  const pageTitle = plan.title || `${plan.days ? `${plan.days}-Day ` : ''}Trip to ${destinations}`;
  const description = buildDescription(plan);
  const jsonLd = buildJsonLd(plan, `https://bonplanai.com/trip/${tripId}`);
  const dayGroups = groupByDay(plan.events || []);
  const ownerName = plan.owner?.first_name
    ? `${plan.owner.first_name} ${plan.owner.last_name}`.trim()
    : 'a BonPlan.ai user';

  return (
    <>
      <SEOHead title={pageTitle} description={description} url={`/trip/${tripId}`} type="article" jsonLd={jsonLd} />

      {/* z-10 lifts above z-0 BlurBackground while keeping the map/blur visible */}
      <div className="relative z-10 min-h-screen">

        {/* Hero — compact on mobile */}
        <div className="max-w-3xl mx-auto px-4 sm:px-6 pt-16 sm:pt-24 pb-6 sm:pb-10">
          <br />

          <h1 className="text-xl sm:text-3xl font-bold text-white leading-tight mb-3 sm:mb-4">
            {pageTitle}
          </h1>

          {/* Stat chips */}
          <div className="flex flex-wrap gap-1.5 sm:gap-2">
            {plan.destinations?.length > 0 && (
              <span className="inline-flex items-center gap-1 sm:gap-1.5 px-2.5 sm:px-3 py-1 rounded-full bg-black/40 border border-white/10 text-[11px] sm:text-xs text-white/60">
                <MapPin size={10} className="text-cyan-400 shrink-0" /> {destinations}
              </span>
            )}
            {plan.days && (
              <span className="inline-flex items-center gap-1 sm:gap-1.5 px-2.5 sm:px-3 py-1 rounded-full bg-black/40 border border-white/10 text-[11px] sm:text-xs text-white/60">
                <Clock size={10} className="text-cyan-400 shrink-0" /> {plan.days} days
              </span>
            )}
            {(plan.start_date || plan.end_date) && (
              <span className="inline-flex items-center gap-1 sm:gap-1.5 px-2.5 sm:px-3 py-1 rounded-full bg-black/40 border border-white/10 text-[11px] sm:text-xs text-white/60">
                <Calendar size={10} className="text-cyan-400 shrink-0" />
                {formatDate(plan.start_date)}{plan.end_date ? ` – ${formatDate(plan.end_date)}` : ''}
              </span>
            )}
            {plan.adults > 0 && (
              <span className="inline-flex items-center gap-1 sm:gap-1.5 px-2.5 sm:px-3 py-1 rounded-full bg-black/40 border border-white/10 text-[11px] sm:text-xs text-white/60">
                <Users size={10} className="text-cyan-400 shrink-0" />
                {plan.adults} adult{plan.adults > 1 ? 's' : ''}
                {plan.children > 0 ? `, ${plan.children} child${plan.children > 1 ? 'ren' : ''}` : ''}
              </span>
            )}
            {plan.cost != null && plan.cost > 0 && (
              <span className="inline-flex items-center gap-1 sm:gap-1.5 px-2.5 sm:px-3 py-1 rounded-full bg-black/40 border border-white/10 text-[11px] sm:text-xs text-white/60">
                <DollarSign size={10} className="text-cyan-400 shrink-0" /> ~${plan.cost.toLocaleString()}
              </span>
            )}
          </div>
        </div>

        {/* Day sections */}
        <div className="max-w-3xl mx-auto px-4 sm:px-6 pb-12 space-y-6 sm:space-y-8">
          {dayGroups.map(([dayTitle, { date, events }]) => (
            <section key={dayTitle} className="rounded-2xl border border-cyan/20 bg-black/10 shadow-2xl overflow-hidden">
              {/* Day header */}
              <div className="flex items-center gap-3 px-4 py-3 border-b border-white/[0.08]">
                <h2 className="text-base sm:text-lg font-bold text-white/90">{dayTitle}</h2>
                {date && date !== 'Start' && date !== 'End' && (
                  <span className="flex items-center gap-1.5 text-cyan/70 bg-cyan/10 px-2.5 py-1 rounded-full shrink-0">
                    <Calendar className="w-3 h-3 shrink-0" />
                    <span className="text-[10px] font-semibold uppercase tracking-wider">{date}</span>
                  </span>
                )}
              </div>

              {/* Events */}
              <div className="flex flex-col gap-3 p-3">
                {events.map((event, i) => (
                  <div key={event.id || `${dayTitle}-${i}`}>
                    {renderSubCardForEvent(event, { onViewOnMap: noop })}
                  </div>
                ))}
              </div>
            </section>
          ))}

          {/* Tips */}
          {plan.tips?.length > 0 && (
            <section>
              <h2 className="text-lg font-bold text-white/90 mb-3">Travel Tips</h2>
              <div className="rounded-2xl border border-white/10 bg-black/10 shadow-2xl px-4 py-3 space-y-2.5">
                {plan.tips.map((tip, i) => (
                  <div key={i} className="flex gap-3 text-sm text-white/60 leading-relaxed">
                    <span className="text-cyan-400/60 shrink-0 mt-0.5 text-xs">→</span>
                    {tip}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* CTA */}
          <section className="rounded-2xl border border-cyan/20 bg-black/10 shadow-2xl overflow-hidden">
            <div className="px-6 py-8 text-center">
              <p className="text-white/40 text-[10px] uppercase tracking-widest mb-2">Powered by AI</p>
              <p className="text-white font-semibold text-base sm:text-lg mb-1">Plan your next adventure</p>
              <p className="text-white/50 text-sm mb-5">BonPlan.ai builds personalized itineraries in minutes.</p>
              <Link to="/"
                className="inline-flex items-center gap-2 px-6 py-2.5 rounded-full text-sm font-semibold text-midnight hover:opacity-90 transition-opacity"
                style={{ backgroundColor: 'var(--color-cyan)' }}>
                Start Planning Free →
              </Link>
            </div>
          </section>

          <p className="text-center text-white/20 text-xs pb-4">
            Created by {ownerName} · Generated by BonPlan.ai
          </p>
        </div>
      </div>
    </>
  );
}
