import { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useOutletContext } from 'react-router-dom';
import { Plus, Trash2, Edit2, Server, Globe, AlertCircle, Search, Menu } from 'lucide-react';
import { cn } from '../../../utils/tailwind';
import { api } from '../../../api/index';

export default function SkuManager() {
  const { setSidebarOpen } = useOutletContext<{ setSidebarOpen: (v: boolean) => void }>();
  const [configs, setConfigs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingSku, setEditingSku] = useState<any>(null);
  const [deletingSku, setDeletingSku] = useState<{ sku_id: string, sku: string }>({ sku_id: '', sku: '' });
  const [search, setSearch] = useState('');
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());
  const [formData, setFormData] = useState({
    sku: '', service: '', provider: '', description: '', limit: 1000, period: 'monthly', scope: 'global'
  });

  const loadConfigs = async () => {
    try {
      setLoading(true);
      const data = await api.admin.fetchConfigs();
      setConfigs(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConfigs();
  }, []);

  const handleDelete = async () => {
    if ((deletingSku.sku_id && deletingSku.sku_id !== '') || (deletingSku.sku && deletingSku.sku !== '')) {
      await api.admin.deleteConfig(deletingSku);
      setDeletingSku({ sku_id: '', sku: '' });
      loadConfigs();
    }
  };

  const openModal = (config: any = { sku_id: '', sku: '' }) => {
    if (config && (config.sku_id !== '' || config.sku !== '')) {
      setEditingSku(config);
      setFormData({
        sku: config.sku,
        service: config.service,
        provider: config.provider,
        description: config.description,
        limit: config.limit,
        period: config.period,
        scope: config.scope
      });
    } else {
      setEditingSku(null);
      setFormData({ sku: '', service: '', provider: '', description: '', limit: 1000, period: 'monthly', scope: 'global' });
    }
    setIsModalOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingSku) {
        await api.admin.updateConfig({ sku_id: editingSku.id, ...formData });
      } else {
        await api.admin.createConfig(formData);
      }
      setIsModalOpen(false);
      loadConfigs();
    } catch (err) {
      alert('Error saving config.');
      console.error(err);
    }
  };

  const toggleExpand = (id: string) => {
    setExpandedCards(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const filteredConfigs = useMemo(() => {
    if (!search) return configs;
    const s = search.toLowerCase();
    return configs.filter(c =>
      c.sku.toLowerCase().includes(s) ||
      c.service.toLowerCase().includes(s) ||
      c.provider.toLowerCase().includes(s) ||
      (c.description && c.description.toLowerCase().includes(s)) ||
      c.period.toLowerCase().includes(s) ||
      c.scope.toLowerCase().includes(s)
    );
  }, [configs, search]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <div className="flex items-center gap-3">
            <button onClick={() => setSidebarOpen(true)} className="md:hidden text-white/70 hover:text-white transition-colors">
              <Menu className="h-6 w-6" />
            </button>
            <h1 className="text-2xl font-bold tracking-tight text-white">SKU Management</h1>
          </div>
          <p className="text-sm text-white/40 mt-1 sm:ml-9">Configure rate limit thresholds for API usage.</p>
        </div>
        <div className="flex flex-col sm:flex-row items-center gap-4 w-full sm:w-auto">
          <div className="relative w-full sm:w-64">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Search className="h-4 w-4 text-white/40" />
            </div>
            <input
              type="text"
              placeholder="Search SKUs..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="block w-full pl-10 pr-3 py-2 border border-white/10 rounded-lg bg-carbon/50 text-white text-sm focus:ring-1 focus:ring-cyan focus:border-cyan outline-none transition-all"
            />
          </div>
          <button
            onClick={() => openModal()}
            className="w-full sm:w-auto inline-flex items-center justify-center rounded-lg bg-cyan px-4 py-2 text-sm font-semibold text-midnight hover:shadow-[0_0_20px_rgba(102,252,241,0.35)] transition-all"
          >
            <Plus className="mr-2 h-4 w-4" />
            Create SKU
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan border-t-transparent"></div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          <AnimatePresence>
            {filteredConfigs.map((config) => (
              <motion.div
                key={config.id}
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
                      {config.period} • {config.scope}
                    </span>
                    <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button onClick={() => openModal(config)} className="p-1.5 text-white/40 hover:text-cyan transition-colors rounded-md hover:bg-white/[0.06]">
                        <Edit2 className="h-4 w-4" />
                      </button>
                      <button onClick={() => setDeletingSku({ sku_id: config.id, sku: config.sku })} className="p-1.5 text-white/40 hover:text-red-400 transition-colors rounded-md hover:bg-white/[0.06]">
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>

                  <h3 className="text-lg font-semibold leading-tight text-white mb-1">
                    {config.sku}
                  </h3>
                  <div className="flex items-center gap-1.5 text-sm text-white/40 mb-4">
                    <Server className="h-3.5 w-3.5" />
                    <span>Service: {config.service}</span>
                  </div>

                  <div className="mb-6">
                    <p className={cn("text-sm text-white/40 transition-all duration-300", expandedCards.has(config.id) ? "" : "line-clamp-2")}>
                      {config.description || "No description provided."}
                    </p>
                    {config.description && config.description.length > 80 && (
                      <button
                        onClick={() => toggleExpand(config.id)}
                        className="text-xs font-medium text-cyan hover:text-cyan/80 mt-1 focus:outline-none"
                      >
                        {expandedCards.has(config.id) ? "Show less" : "Read more"}
                      </button>
                    )}
                  </div>
                </div>

                <div className="flex items-center justify-between pt-4 border-t border-white/10">
                  <div className="flex items-center gap-2">
                    <Globe className="h-4 w-4 text-white/40" />
                    <span className="text-sm font-medium text-white capitalize">{config.provider}</span>
                  </div>
                  <div className="text-right">
                    <span className="text-sm text-white/40 block leading-none mb-1">Limit</span>
                    <div className="font-mono font-medium text-white leading-none">
                      {config.limit === -1 ? 'Unlimited' : config.limit.toLocaleString()}
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
          {filteredConfigs.length === 0 && (
            <div className="col-span-full py-12 text-center text-sm text-white/40">
              No matching SKUs found.
            </div>
          )}
        </div>
      )}

      <AnimatePresence>
        {isModalOpen && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" onClick={() => setIsModalOpen(false)} />
            <motion.div initial={{ opacity: 0, y: 10, scale: 0.95 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 10, scale: 0.95 }} className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
              <div className="bg-midnight/70 backdrop-blur-2xl border border-white/10 w-full max-w-md rounded-2xl shadow-2xl pointer-events-auto overflow-hidden text-white">
                <div className="px-6 py-4 border-b border-white/10">
                  <h2 className="text-lg font-semibold">{editingSku ? 'Edit SKU' : 'Create SKU'}</h2>
                </div>
                <form onSubmit={handleSubmit} className="p-6 space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-white/70 mb-1">SKU Name</label>
                    <input required type="text" value={formData.sku} onChange={e => setFormData({ ...formData, sku: e.target.value })} className="w-full rounded-lg border border-white/10 bg-transparent px-3 py-2 text-sm text-white focus:ring-1 focus:ring-cyan focus:border-cyan outline-none transition-all" placeholder="e.g. Dynamic Maps" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-white/70 mb-1">Service Name</label>
                    <input required type="text" value={formData.service} onChange={e => setFormData({ ...formData, service: e.target.value })} className="w-full rounded-lg border border-white/10 bg-transparent px-3 py-2 text-sm text-white focus:ring-1 focus:ring-cyan focus:border-cyan outline-none transition-all" placeholder="e.g. Maps API" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-white/70 mb-1">Description</label>
                    <textarea value={formData.description} onChange={e => setFormData({ ...formData, description: e.target.value })} className="w-full rounded-lg border border-white/10 bg-transparent px-3 py-2 text-sm text-white focus:ring-1 focus:ring-cyan focus:border-cyan outline-none transition-all" rows={3}></textarea>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-white/70 mb-1">Limit (-1 for unlim.)</label>
                      <input required type="number" value={formData.limit} onChange={e => setFormData({ ...formData, limit: parseInt(e.target.value) })} className="w-full rounded-lg border border-white/10 bg-transparent px-3 py-2 text-sm text-white focus:ring-1 focus:ring-cyan focus:border-cyan outline-none transition-all" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-white/70 mb-1">Provider</label>
                      <input required type="text" value={formData.provider} onChange={e => setFormData({ ...formData, provider: e.target.value })} className="w-full rounded-lg border border-white/10 bg-transparent px-3 py-2 text-sm text-white focus:ring-1 focus:ring-cyan focus:border-cyan outline-none transition-all" placeholder="e.g. Google" />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-white/70 mb-1">Period</label>
                      <select value={formData.period} onChange={e => setFormData({ ...formData, period: e.target.value })} className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white focus:ring-1 focus:ring-cyan focus:border-cyan outline-none transition-all">
                        <option value="daily">Daily</option>
                        <option value="weekly">Weekly</option>
                        <option value="monthly">Monthly</option>
                        <option value="yearly">Yearly</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-white/70 mb-1">Scope</label>
                      <select value={formData.scope} onChange={e => setFormData({ ...formData, scope: e.target.value })} className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white focus:ring-1 focus:ring-cyan focus:border-cyan outline-none transition-all">
                        <option value="global">Global</option>
                        <option value="user">User</option>
                      </select>
                    </div>
                  </div>
                  <div className="pt-4 flex justify-end gap-3">
                    <button type="button" onClick={() => setIsModalOpen(false)} className="px-4 py-2 text-sm font-medium rounded-lg border border-white/20 text-white hover:bg-white/[0.06] transition-colors">Cancel</button>
                    <button type="submit" className="px-4 py-2 text-sm font-medium rounded-lg bg-cyan text-midnight hover:shadow-[0_0_15px_rgba(102,252,241,0.3)] transition-all">Save</button>
                  </div>
                </form>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {deletingSku && ((deletingSku.sku && deletingSku.sku !== '') || (deletingSku.sku_id && deletingSku.sku_id !== '')) && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" onClick={() => setDeletingSku({ sku_id: '', sku: '' })} />
            <motion.div initial={{ opacity: 0, y: 10, scale: 0.95 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 10, scale: 0.95 }} className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
              <div className="bg-midnight/70 backdrop-blur-2xl border border-white/10 w-full max-w-sm rounded-2xl shadow-2xl pointer-events-auto overflow-hidden p-6 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-400/10 border border-red-400/20 mb-4">
                  <AlertCircle className="h-6 w-6 text-red-400" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">Delete SKU</h3>
                <p className="text-sm text-white/40 mb-6">Are you sure you want to delete <span className="font-semibold text-white">{deletingSku.sku}</span>? This action cannot be undone.</p>
                <div className="flex justify-center gap-3">
                  <button onClick={() => setDeletingSku({ sku_id: '', sku: '' })} className="px-4 py-2 text-sm font-medium rounded-lg border border-white/20 text-white hover:bg-white/[0.06] transition-colors w-full">Cancel</button>
                  <button onClick={handleDelete} className="px-4 py-2 text-sm font-medium rounded-lg bg-red-400/10 border border-red-400/30 text-red-400 hover:bg-red-400/20 transition-colors w-full">Delete</button>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
