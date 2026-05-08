import { useCallback, useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Activity,
  BarChart3,
  CalendarDays,
  Clock,
  Gauge,
  Globe2,
  RefreshCw,
  Sparkles,
  Ticket,
  TrendingUp,
  Users,
  Image,
} from 'lucide-react';
import { api } from '../../../api/index';
import type { AdminAnalyticsOverview } from '../../../apis/admin';
import { useAuth } from '../../../context/AuthContext';
import { cn } from '../../../utils/tailwind';

const formatNumber = (value?: number) => (value ?? 0).toLocaleString();
const formatPercent = (value?: number) => `${(value ?? 0).toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
const formatMoney = (value?: number) => (value ?? 0).toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });

const titleize = (value: string) => value.replace(/_/g, ' ').replace(/\b\w/g, letter => letter.toUpperCase());

function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
  tone = 'cyan',
}: {
  label: string;
  value: string;
  detail: string;
  icon: React.ElementType;
  tone?: 'cyan' | 'green' | 'amber' | 'rose';
}) {
  const toneClasses = {
    cyan: 'border-cyan/20 bg-cyan/10 text-cyan',
    green: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300',
    amber: 'border-amber-400/20 bg-amber-400/10 text-amber-300',
    rose: 'border-rose-400/20 bg-rose-400/10 text-rose-300',
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-white/10 bg-midnight/40 p-5 shadow-xl backdrop-blur-xl"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wider text-white/40">{label}</p>
          <p className="mt-2 text-3xl font-bold tracking-tight text-white">{value}</p>
        </div>
        <div className={cn('flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border', toneClasses[tone])}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
      <p className="mt-4 text-sm text-white/45">{detail}</p>
    </motion.div>
  );
}

function BreakdownList({
  title,
  items,
  empty = 'No data for this filter.',
}: {
  title: string;
  items: { label: string; value: number }[];
  empty?: string;
}) {
  const max = Math.max(...items.map(item => item.value), 1);

  return (
    <motion.div
      whileHover={{ y: -4, scale: 1.015 }}
      transition={{ duration: 0.18, ease: 'easeOut' }}
      className="relative z-0 flex h-80 min-h-0 flex-col rounded-2xl border border-white/10 bg-midnight/40 p-5 shadow-xl backdrop-blur-xl transition-[border-color,box-shadow] duration-200 hover:z-20 hover:border-cyan/30 hover:shadow-[0_10px_34px_rgba(102,252,241,0.12)]"
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="truncate text-base font-semibold text-white">{title}</h2>
        <span className="shrink-0 rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-xs text-white/40">
          {formatNumber(items.length)}
        </span>
      </div>
      <div className="mt-5 min-h-0 flex-1 space-y-4 overflow-y-auto pr-1 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-white/20">
        {items.length === 0 ? (
          <div className="flex h-full items-center justify-center text-center text-sm text-white/40">{empty}</div>
        ) : items.map(item => (
          <div key={item.label} className="space-y-2">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="truncate text-white/70">{titleize(item.label)}</span>
              <span className="font-medium text-white">{formatNumber(item.value)}</span>
            </div>
            <div className="h-2 rounded-full bg-white/10">
              <div
                className="h-full rounded-full bg-cyan shadow-[0_0_12px_rgba(102,252,241,0.35)]"
                style={{ width: `${Math.max(4, (item.value / max) * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

export default function AnalyticsDashboard() {
  const { token } = useAuth();
  const [data, setData] = useState<AdminAnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadData = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError('');
    try {
      const overview = await api.admin.fetchAnalyticsOverview(token, {
        days: 0,
        planning_type: 'all',
        status: 'all',
        auth_provider: 'all',
      });
      setData(overview);
    } catch {
      setError('Analytics could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadData();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadData]);

  const breakdowns = useMemo(() => {
    if (!data) return null;
    const toItems = (record: Record<string, number>) => Object.entries(record)
      .filter(([, value]) => value > 0)
      .sort((a, b) => b[1] - a[1])
      .map(([label, value]) => ({ label, value }));
    return {
      statuses: toItems(data.breakdowns.statuses),
      planning: toItems(data.breakdowns.planning_types),
      auth: toItems(data.breakdowns.auth_providers),
      budgets: toItems(data.breakdowns.budgets),
      paces: toItems(data.breakdowns.paces),
    };
  }, [data]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Analytics</h1>
          <p className="mt-1 text-sm text-white/40">Track users, drafts, generated itineraries, conversion, collaboration, and support health.</p>
        </div>
        <button
          onClick={loadData}
          disabled={loading}
          className="inline-flex w-full items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] px-4 py-2 text-sm font-medium text-white/80 transition-all hover:border-cyan/40 hover:text-white disabled:opacity-50 sm:w-auto"
        >
          <RefreshCw className={cn('mr-2 h-4 w-4', loading && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-400/20 bg-rose-400/10 px-4 py-3 text-sm text-rose-200">{error}</div>
      )}

      {loading && !data ? (
        <div className="flex justify-center py-16">
          <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-cyan border-t-transparent" />
        </div>
      ) : data && breakdowns ? (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Total Users" value={formatNumber(data.summary.total_users)} detail={`${formatNumber(data.summary.google_users)} Google users, ${formatPercent(data.summary.verification_rate)} verified`} icon={Users} />
            <MetricCard label="Generated Trips" value={formatNumber(data.summary.generated_trips)} detail={`${formatPercent(data.summary.conversion_rate)} draft to generated conversion`} icon={Sparkles} tone="green" />
            <MetricCard label="Remaining Drafts" value={formatNumber(data.summary.remaining_drafts)} detail={`${formatPercent(data.summary.draft_rate)} of tracked trips still in draft`} icon={Clock} tone="amber" />
            <MetricCard label="Avg Trip Length" value={`${formatNumber(data.summary.average_days_per_trip)} days`} detail={`${formatMoney(data.summary.average_trip_cost)} avg generated itinerary cost`} icon={CalendarDays} />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Total Itineraries" value={formatNumber(data.summary.total_itineraries)} detail={`${formatNumber(data.summary.generated_itineraries)} generated itinerary rows`} icon={BarChart3} />
            <MetricCard label="Google User Share" value={formatPercent(data.summary.google_user_rate)} detail={`${formatNumber(data.summary.local_users)} local users in this view`} icon={Globe2} />
            <MetricCard label="Shared Trips" value={formatNumber(data.collaboration.shared_trips)} detail={`${formatNumber(data.collaboration.pending_invites)} pending invitations`} icon={Activity} tone="green" />
            <MetricCard label="Support Queue" value={formatNumber(data.operations.open_tickets)} detail={`${formatNumber(data.operations.unacknowledged_tickets)} unacknowledged tickets`} icon={Ticket} tone={data.operations.open_tickets > 0 ? 'rose' : 'cyan'} />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"> 
            <MetricCard label="Avg Party Size" value={formatNumber(data.summary.average_party_size)} detail={`${formatNumber(data.summary.average_party_size)} travelers per itinerary`} icon={Gauge} />
            <MetricCard label="Avg Events per Itinerary" value={formatNumber(data.summary.average_events_per_itinerary)} detail={`${formatNumber(data.summary.average_events_per_itinerary)} average events per itinerary`} icon={TrendingUp} />
            <MetricCard label="API Cache Entries" value={formatNumber(data.operations.api_cache_entries)} detail={`${formatNumber(data.operations.api_cache_entries)} entries in API cache`} icon={Activity} />
            <MetricCard label="Photo Cache Entries" value={formatNumber(data.operations.photo_cache_entries)} detail={`${formatNumber(data.operations.photo_cache_entries)} entries in photo cache`} icon={Image} />
          </div>

          <div className="h-px w-full bg-white/10 mt-12 mb-12" />

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <BreakdownList title="Trip Status" items={breakdowns.statuses} />
            <BreakdownList title="Planning Type" items={breakdowns.planning} />
            <BreakdownList title="Auth Provider" items={breakdowns.auth} />
            <BreakdownList title="Budgets" items={breakdowns.budgets} />
            <BreakdownList title="Pace" items={breakdowns.paces} />
            <BreakdownList title="Top Destinations" items={data.breakdowns.top_destinations.map(item => ({ label: item.name, value: item.count }))} />
          </div>
        </>
      ) : null}
    </div>
  );
}
