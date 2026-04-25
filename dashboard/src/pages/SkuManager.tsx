import { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Trash2, Edit2, Server, Globe, AlertCircle, Search } from 'lucide-react';
import { fetchConfigs, deleteConfig, createConfig, updateConfig } from '../api';

export default function SkuManager() {
  const [configs, setConfigs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingSku, setEditingSku] = useState<any>(null);
  const [deletingSku, setDeletingSku] = useState<{ sku_id: string, sku: string } | null>(null);
  const [search, setSearch] = useState('');
  const [formData, setFormData] = useState({
    sku: '', service: '', provider: '', description: '', limit: 1000, period: 'monthly', scope: 'global'
  });

  const loadConfigs = async () => {
    try {
      setLoading(true);
      const data = await fetchConfigs();
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
      await deleteConfig(deletingSku);
      setDeletingSku(null);
      loadConfigs();
    }
  };

  const openModal = (config: any = null) => {
    if (config) {
      setEditingSku(config);
      setFormData({
        sku: config.raw_sku,
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
        await updateConfig({ sku_id: editingSku.id, ...formData });
      } else {
        await createConfig(formData);
      }
      setIsModalOpen(false);
      loadConfigs();
    } catch (err) {
      alert('Error saving config.');
      console.error(err);
    }
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
          <h1 className="text-2xl font-bold tracking-tight">SKU Management</h1>
          <p className="text-sm text-[#888888] mt-1">Configure rate limit thresholds for API usage.</p>
        </div>
        <div className="flex flex-col sm:flex-row items-center gap-4 w-full sm:w-auto">
          <div className="relative w-full sm:w-64">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Search className="h-4 w-4 text-[#888888]" />
            </div>
            <input
              type="text"
              placeholder="Search SKUs..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="block w-full pl-10 pr-3 py-2 border border-[#EAEAEA] dark:border-[#333333] rounded-lg bg-transparent text-sm focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>
          <button
            onClick={() => openModal()}
            className="w-full sm:w-auto inline-flex items-center justify-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 transition-colors"
          >
            <Plus className="mr-2 h-4 w-4" />
            Create SKU
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
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
                className="group relative flex flex-col justify-between overflow-hidden rounded-2xl bg-white dark:bg-[#111111] p-6 shadow-[0_2px_8px_rgb(0,0,0,0.04)] ring-1 ring-[#EAEAEA] dark:ring-[#333333] hover:shadow-[0_8px_24px_rgb(0,0,0,0.08)] hover:ring-blue-500/20 transition-all duration-300"
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <span className="inline-flex items-center rounded-md bg-blue-50 dark:bg-blue-500/10 px-2 py-1 text-xs font-medium text-blue-700 dark:text-blue-400 ring-1 ring-inset ring-blue-700/10 dark:ring-blue-400/20 uppercase tracking-wider">
                      {config.period} • {config.scope}
                    </span>
                    <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button onClick={() => openModal(config)} className="p-1.5 text-[#888888] hover:text-blue-600 dark:hover:text-blue-400 transition-colors rounded-md hover:bg-[#F5F5F5] dark:hover:bg-[#1A1A1A]">
                        <Edit2 className="h-4 w-4" />
                      </button>
                      <button onClick={() => setDeletingSku({ sku_id: config.id, sku: config.sku })} className="p-1.5 text-[#888888] hover:text-red-600 dark:hover:text-red-400 transition-colors rounded-md hover:bg-[#F5F5F5] dark:hover:bg-[#1A1A1A]">
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>

                  <h3 className="text-lg font-semibold leading-tight text-[#111111] dark:text-[#EEEEEE] mb-1">
                    {config.sku}
                  </h3>
                  <div className="flex items-center gap-1.5 text-sm text-[#666666] dark:text-[#A0A0A0] mb-4">
                    <Server className="h-3.5 w-3.5" />
                    <span>Service: {config.service}</span>
                  </div>

                  <p className="text-sm text-[#888888] dark:text-[#888888] line-clamp-2 mb-6">
                    {config.description || "No description provided."}
                  </p>
                </div>

                <div className="flex items-center justify-between pt-4 border-t border-[#EAEAEA] dark:border-[#333333]">
                  <div className="flex items-center gap-2">
                    <Globe className="h-4 w-4 text-[#888888]" />
                    <span className="text-sm font-medium text-[#111111] dark:text-[#EEEEEE] capitalize">{config.provider}</span>
                  </div>
                  <div className="text-right">
                    <span className="text-sm text-[#888888]">Limit</span>
                    <div className="font-mono font-medium text-[#111111] dark:text-[#EEEEEE]">
                      {config.limit === -1 ? 'Unlimited' : config.limit.toLocaleString()}
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
          {filteredConfigs.length === 0 && (
            <div className="col-span-full py-12 text-center text-sm text-[#888888]">
              No matching SKUs found.
            </div>
          )}
        </div>
      )}

      {/* Modal - Extremely basic implementation for now, should be extracted to component */}
      <AnimatePresence>
        {isModalOpen && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm" onClick={() => setIsModalOpen(false)} />
            <motion.div initial={{ opacity: 0, y: 10, scale: 0.95 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 10, scale: 0.95 }} className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
              <div className="bg-white dark:bg-[#111111] w-full max-w-md rounded-2xl shadow-xl ring-1 ring-[#EAEAEA] dark:ring-[#333333] pointer-events-auto overflow-hidden">
                <div className="px-6 py-4 border-b border-[#EAEAEA] dark:border-[#333333]">
                  <h2 className="text-lg font-semibold">{editingSku ? 'Edit SKU' : 'Create SKU'}</h2>
                </div>
                <form onSubmit={handleSubmit} className="p-6 space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">SKU Name</label>
                    <input required type="text" value={formData.sku} onChange={e => setFormData({ ...formData, sku: e.target.value })} className="w-full rounded-lg border border-[#EAEAEA] dark:border-[#333333] bg-transparent px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500" placeholder="e.g. Dynamic Maps" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Service Name</label>
                    <input required type="text" value={formData.service} onChange={e => setFormData({ ...formData, service: e.target.value })} className="w-full rounded-lg border border-[#EAEAEA] dark:border-[#333333] bg-transparent px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500" placeholder="e.g. Maps API" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Description</label>
                    <textarea value={formData.description} onChange={e => setFormData({ ...formData, description: e.target.value })} className="w-full rounded-lg border border-[#EAEAEA] dark:border-[#333333] bg-transparent px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500" rows={3}></textarea>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium mb-1">Limit (-1 for unlimited)</label>
                      <input required type="number" value={formData.limit} onChange={e => setFormData({ ...formData, limit: parseInt(e.target.value) })} className="w-full rounded-lg border border-[#EAEAEA] dark:border-[#333333] bg-transparent px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-1">Provider</label>
                      <input required type="text" value={formData.provider} onChange={e => setFormData({ ...formData, provider: e.target.value })} className="w-full rounded-lg border border-[#EAEAEA] dark:border-[#333333] bg-transparent px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500" placeholder="e.g. Google" />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium mb-1">Period</label>
                      <select value={formData.period} onChange={e => setFormData({ ...formData, period: e.target.value })} className="w-full rounded-lg border border-[#EAEAEA] dark:border-[#333333] bg-transparent px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500">
                        <option value="daily">Daily</option>
                        <option value="weekly">Weekly</option>
                        <option value="monthly">Monthly</option>
                        <option value="yearly">Yearly</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-1">Scope</label>
                      <select value={formData.scope} onChange={e => setFormData({ ...formData, scope: e.target.value })} className="w-full rounded-lg border border-[#EAEAEA] dark:border-[#333333] bg-transparent px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500">
                        <option value="global">Global</option>
                        <option value="user">User</option>
                      </select>
                    </div>
                  </div>
                  <div className="pt-4 flex justify-end gap-3">
                    <button type="button" onClick={() => setIsModalOpen(false)} className="px-4 py-2 text-sm font-medium rounded-lg border border-[#EAEAEA] dark:border-[#333333] hover:bg-[#F5F5F5] dark:hover:bg-[#1A1A1A] transition-colors">Cancel</button>
                    <button type="submit" className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-500 transition-colors">Save</button>
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
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm" onClick={() => setDeletingSku({ sku_id: '', sku: '' })} />
            <motion.div initial={{ opacity: 0, y: 10, scale: 0.95 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 10, scale: 0.95 }} className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
              <div className="bg-white dark:bg-[#111111] w-full max-w-sm rounded-2xl shadow-xl ring-1 ring-[#EAEAEA] dark:ring-[#333333] pointer-events-auto overflow-hidden p-6 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-100 dark:bg-red-500/10 mb-4">
                  <AlertCircle className="h-6 w-6 text-red-600 dark:text-red-500" />
                </div>
                <h3 className="text-lg font-semibold text-[#111111] dark:text-[#EEEEEE] mb-2">Delete SKU</h3>
                <p className="text-sm text-[#888888] mb-6">Are you sure you want to delete <span className="font-semibold text-[#111111] dark:text-[#EEEEEE]">{deletingSku.sku}</span>? This action cannot be undone.</p>
                <div className="flex justify-center gap-3">
                  <button onClick={() => setDeletingSku({ sku_id: '', sku: '' })} className="px-4 py-2 text-sm font-medium rounded-lg border border-[#EAEAEA] dark:border-[#333333] hover:bg-[#F5F5F5] dark:hover:bg-[#1A1A1A] transition-colors w-full">Cancel</button>
                  <button onClick={handleDelete} className="px-4 py-2 text-sm font-medium rounded-lg bg-red-600 text-white hover:bg-red-500 transition-colors w-full">Delete</button>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
