import { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../../../api/index';
import { useAuth } from '../../../context/AuthContext';
import { Search, Server } from 'lucide-react';
import { cn } from '../../../utils/tailwind';
import { format, subDays, subWeeks, subMonths, subYears, getISOWeek, getISOWeekYear } from 'date-fns';

const generateBucketOptions = (period: string) => {
  const now = new Date();
  const options = [];

  if (period === 'daily') {
    for (let i = 0; i < 7; i++) {
      const d = subDays(now, i);
      const val = format(d, 'yyyyMMdd');
      const label = format(d, 'MMM d, yyyy');
      options.push({ value: val, label: i === 0 ? `Today (${label})` : label });
    }
  } else if (period === 'weekly') {
    for (let i = 0; i < 4; i++) {
      const d = subWeeks(now, i);
      const week = getISOWeek(d);
      const year = getISOWeekYear(d);
      const val = `${year}W${week.toString().padStart(2, '0')}`;
      options.push({ value: val, label: i === 0 ? `This Week (W${week})` : `${year} W${week}` });
    }
  } else if (period === 'monthly') {
    for (let i = 0; i < 12; i++) {
      const d = subMonths(now, i);
      const val = format(d, 'yyyyMM');
      const label = format(d, 'MMMM yyyy');
      options.push({ value: val, label: i === 0 ? `This Month (${label})` : label });
    }
  } else if (period === 'yearly') {
    for (let i = 0; i < 2; i++) {
      const d = subYears(now, i);
      const val = format(d, 'yyyy');
      options.push({ value: val, label: i === 0 ? `This Year (${val})` : val });
    }
  }
  return options;
};

const getBarColor = (percent: number) => {
  if (percent < 50) return 'bg-cyan';
  if (percent < 80) return 'bg-amber-500';
  return 'bg-red-500';
};

const GlobalUsageCard = ({ config, usageData }: { config: any, usageData: any[] }) => {
  const options = useMemo(() => generateBucketOptions(config.period), [config.period]);
  const [selectedBucket, setSelectedBucket] = useState(options[0]?.value);

  const relevantUsage = useMemo(() => {
    return usageData.filter(u => u.sku === config.sku && u.period_bucket === selectedBucket);
  }, [usageData, config.sku, selectedBucket]);

  const isUnlimited = config.limit === -1;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.2 }}
      className="group relative flex flex-col justify-between overflow-hidden rounded-2xl bg-midnight/40 backdrop-blur-xl p-6 shadow-xl border border-white/10 hover:border-cyan/30 hover:shadow-[0_8px_30px_rgba(102,252,241,0.08)] transition-all duration-300"
    >
      <div>
        <div className="flex items-center justify-between mb-4">
          <span className="inline-flex items-center rounded-md bg-cyan/10 border border-cyan/30 px-2 py-1 text-xs font-medium text-cyan uppercase tracking-wider">
            {config.period}
          </span>
          <select
            value={selectedBucket}
            onChange={(e) => setSelectedBucket(e.target.value)}
            className="text-sm bg-white/[0.03] border border-white/10 rounded-md px-2 py-1 text-white focus:ring-1 focus:ring-cyan focus:border-cyan outline-none transition-all"
          >
            {options.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        <h3 className="text-lg font-semibold leading-tight text-white mb-1">
          {config.sku}
        </h3>
        <div className="flex items-center gap-1.5 text-sm text-white/40 mb-4">
          <Server className="h-3.5 w-3.5" />
          <span>{config.service}</span>
        </div>
      </div>

      <div className="mt-2 space-y-4">
        {(() => {
          const row = relevantUsage[0];
          const usageAmount = row?.usage || 0;
          const percent = isUnlimited ? 0 : Math.min(100, Math.max(0, (usageAmount / config.limit) * 100));
          return (
            <div>
              <div className="flex items-center justify-between text-sm mb-1.5">
                <span className="text-white/40">Consumption</span>
                <span className="font-medium text-white">
                  {isUnlimited ? `${usageAmount.toLocaleString()} / Unlimited` : `${usageAmount.toLocaleString()} / ${config.limit.toLocaleString()}`}
                </span>
              </div>
              <div className="h-2.5 bg-white/10 rounded-full overflow-hidden">
                {!isUnlimited && (
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${percent}%` }}
                    transition={{ duration: 1, ease: "easeOut" }}
                    className={cn("h-full rounded-full shadow-[0_0_10px_rgba(102,252,241,0.5)]", getBarColor(percent))}
                  />
                )}
              </div>
            </div>
          );
        })()}
      </div>
    </motion.div>
  );
};

const UserUsageTable = ({ configs, usageData, search }: { configs: any[], usageData: any[], search: string }) => {
  const [selectedSku, setSelectedSku] = useState(configs[0]?.sku || '');
  const activeConfig = useMemo(() => configs.find(c => c.sku === selectedSku), [configs, selectedSku]);

  const options = useMemo(() => activeConfig ? generateBucketOptions(activeConfig.period) : [], [activeConfig]);
  const [selectedBucket, setSelectedBucket] = useState('');

  useEffect(() => {
    if (options.length > 0 && (!selectedBucket || !options.find(o => o.value === selectedBucket))) {
      setSelectedBucket(options[0].value);
    }
  }, [options, selectedBucket]);

  const relevantUsage = useMemo(() => {
    return usageData
      .filter(u => u.sku === selectedSku && u.period_bucket === selectedBucket)
      .filter(u => u.user_name?.toLowerCase().includes(search.toLowerCase()) || u.user_id.toLowerCase().includes(search.toLowerCase()))
      .sort((a, b) => new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime());
  }, [usageData, selectedSku, selectedBucket, search]);

  if (configs.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-white/40">
        No user-scoped SKUs found.
      </div>
    );
  }

  return (
    <div className="bg-midnight/40 backdrop-blur-xl rounded-2xl shadow-xl border border-white/10 overflow-hidden text-white">
      <div className="p-4 sm:p-6 border-b border-white/10 flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center bg-white/[0.02]">
        <div>
          <h2 className="text-lg font-semibold text-white">User Consumption Table</h2>
          <p className="text-sm text-white/40">Detailed breakdown of quota usage per user.</p>
        </div>
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full sm:w-auto">
          <select
            value={selectedSku}
            onChange={(e) => setSelectedSku(e.target.value)}
            className="w-full sm:w-auto text-sm bg-white/[0.03] border border-white/10 rounded-lg px-3 py-2 text-white focus:ring-1 focus:ring-cyan focus:border-cyan outline-none transition-all"
          >
            {configs.map(c => (
              <option key={c.id} value={c.sku}>{c.sku}</option>
            ))}
          </select>
          <select
            value={selectedBucket}
            onChange={(e) => setSelectedBucket(e.target.value)}
            className="w-full sm:w-auto text-sm bg-white/[0.03] border border-white/10 rounded-lg px-3 py-2 text-white focus:ring-1 focus:ring-cyan focus:border-cyan outline-none transition-all"
          >
            {options.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="overflow-x-auto w-full">
        <table className="min-w-full divide-y divide-white/10">
          <thead className="bg-white/[0.02]">
            <tr>
              <th scope="col" className="py-3.5 pl-4 pr-3 text-left text-xs font-medium text-white/40 uppercase tracking-wider sm:pl-6">User Details</th>
              <th scope="col" className="px-3 py-3.5 text-left text-xs font-medium text-white/40 uppercase tracking-wider">User ID</th>
              <th scope="col" className="px-3 py-3.5 text-left text-xs font-medium text-white/40 uppercase tracking-wider w-1/3">Consumption</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/10 bg-carbon/50">
            {relevantUsage.length === 0 ? (
              <tr>
                <td colSpan={3} className="py-12 text-center text-sm text-white/40">
                  No user usage records found for this period.
                </td>
              </tr>
            ) : (
              relevantUsage.map((row) => {
                const isUnlimited = activeConfig?.limit === -1;
                const limit = activeConfig?.limit || 0;
                const percent = isUnlimited ? 0 : Math.min(100, Math.max(0, (row.usage / limit) * 100));

                return (
                  <motion.tr
                    key={row.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="hover:bg-white/[0.04] transition-colors"
                  >
                    <td className="whitespace-nowrap py-4 pl-4 pr-3 text-sm sm:pl-6">
                      <div className="font-medium text-white">{row.user_name}</div>
                    </td>
                    <td className="whitespace-nowrap px-3 py-4 text-sm font-mono text-white/40">
                      {row.user_id}
                    </td>
                    <td className="whitespace-nowrap px-3 py-4">
                      <div className="flex items-center gap-3">
                        <div className="flex-1 h-2.5 bg-white/10 rounded-full overflow-hidden">
                          {!isUnlimited && (
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${percent}%` }}
                              transition={{ duration: 1, ease: "easeOut" }}
                              className={cn("h-full rounded-full", getBarColor(percent))}
                            />
                          )}
                        </div>
                        <div className="w-24 text-right text-sm font-medium">
                          {isUnlimited ? (
                            <span className="text-white">{row.usage.toLocaleString()} <span className="text-white/40 font-normal">/ Unlimited</span></span>
                          ) : (
                            <span className="text-white">{row.usage.toLocaleString()} <span className="text-white/40 font-normal">/ {limit.toLocaleString()}</span></span>
                          )}
                        </div>
                      </div>
                    </td>
                  </motion.tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default function UsageViewer() {
  const { token } = useAuth();
  const [configs, setConfigs] = useState<any[]>([]);
  const [usage, setUsage] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [scope, setScope] = useState<'global' | 'user'>('global');
  const [search, setSearch] = useState('');

  const loadData = async () => {
    try {
      setLoading(true);
      if (!token) return;
      const [configsData, usageData] = await Promise.all([
        api.admin.fetchConfigs(token),
        api.admin.fetchUsage(token, scope)
      ]);
      const scopeConfigs = configsData.filter((c: any) => c.scope === scope);

      // Sort configs based on the latest updated_at of their corresponding usage records
      scopeConfigs.sort((a: any, b: any) => {
        const aUsage = usageData.filter(u => u.sku === a.sku);
        const bUsage = usageData.filter(u => u.sku === b.sku);
        const aMax = aUsage.length > 0 ? Math.max(...aUsage.map(u => new Date(u.updated_at || 0).getTime())) : 0;
        const bMax = bUsage.length > 0 ? Math.max(...bUsage.map(u => new Date(u.updated_at || 0).getTime())) : 0;
        return bMax - aMax; // descending
      });

      setConfigs(scopeConfigs);
      setUsage(usageData);
    } catch (err) {
      // Do nothing
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [scope]);

  const filteredConfigs = useMemo(() => {
    return configs.filter(c =>
      c.sku.toLowerCase().includes(search.toLowerCase()) ||
      c.service.toLowerCase().includes(search.toLowerCase())
    );
  }, [configs, search]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Usage Viewer</h1>
          <p className="text-sm text-white/40 mt-1">Monitor real-time rate limit consumption by period.</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4 items-center justify-between bg-midnight/40 backdrop-blur-xl p-4 rounded-xl shadow-xl border border-white/10">
        <div className="flex bg-black/20 p-1 rounded-lg w-full sm:w-auto border border-white/5">
          <button
            onClick={() => setScope('global')}
            className={cn(
              "flex-1 sm:flex-none px-6 py-1.5 text-sm font-medium rounded-md transition-colors",
              scope === 'global' ? "bg-white/10 shadow-sm text-white" : "text-white/40 hover:text-white"
            )}
          >
            Global
          </button>
          <button
            onClick={() => setScope('user')}
            className={cn(
              "flex-1 sm:flex-none px-6 py-1.5 text-sm font-medium rounded-md transition-colors",
              scope === 'user' ? "bg-white/10 shadow-sm text-white" : "text-white/40 hover:text-white"
            )}
          >
            User
          </button>
        </div>

        <div className="relative w-full sm:max-w-xs">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search className="h-4 w-4 text-white/40" />
          </div>
          <input
            type="text"
            placeholder={scope === 'global' ? "Search SKUs..." : "Search users..."}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="block w-full pl-10 pr-3 py-2 border border-white/10 rounded-lg bg-carbon/50 text-white text-sm focus:ring-1 focus:ring-cyan focus:border-cyan outline-none transition-all"
          />
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan border-t-transparent"></div>
        </div>
      ) : scope === 'global' ? (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          <AnimatePresence>
            {filteredConfigs.map(config => (
              <GlobalUsageCard key={config.id} config={config} usageData={usage} />
            ))}
          </AnimatePresence>
          {filteredConfigs.length === 0 && (
            <div className="col-span-full py-12 text-center text-sm text-white/40">
              No matching SKUs found for the global scope.
            </div>
          )}
        </div>
      ) : (
        <UserUsageTable configs={configs} usageData={usage} search={search} />
      )}
    </div>
  );
}
