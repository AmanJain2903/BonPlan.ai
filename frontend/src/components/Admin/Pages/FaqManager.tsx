import { useCallback, useState, useEffect, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { Plus, Trash2, Edit2, HelpCircle, Eye, EyeOff, Search } from 'lucide-react';
import { cn } from '../../../utils/tailwind';
import { api, type FAQ } from '../../../apis/admin';
import { useAuth } from '../../../context/AuthContext';

type FormData = {
  question: string;
  answer: string;
  order: number;
  is_published: boolean;
};

const emptyForm = (): FormData => ({ question: '', answer: '', order: 0, is_published: true });

export default function FaqManager() {
  const { token } = useAuth();
  const [faqs, setFaqs] = useState<FAQ[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingFaq, setEditingFaq] = useState<FAQ | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<FormData>(emptyForm());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setLoading(true);
      setFaqs(await api.adminGetFaqs(token));
    } catch {
      setError('Failed to load FAQs.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const openCreate = () => {
    setEditingFaq(null);
    setFormData(emptyForm());
    setIsModalOpen(true);
  };

  const openEdit = (faq: FAQ) => {
    setEditingFaq(faq);
    setFormData({ question: faq.question, answer: faq.answer, order: faq.order, is_published: faq.is_published });
    setIsModalOpen(true);
  };

  const handleSave = async () => {
    if (!token || !formData.question.trim() || !formData.answer.trim()) return;
    setSaving(true);
    setError('');
    try {
      if (editingFaq) {
        await api.adminUpdateFaq(token, editingFaq.id, formData);
      } else {
        await api.adminCreateFaq(token, formData);
      }
      setIsModalOpen(false);
      await load();
    } catch {
      setError('Save failed. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!token || !deletingId) return;
    try {
      await api.adminDeleteFaq(token, deletingId);
      setDeletingId(null);
      await load();
    } catch {
      setError('Delete failed.');
    }
  };

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return faqs;
    return faqs.filter(f =>
      f.question.toLowerCase().includes(q) ||
      f.answer.toLowerCase().includes(q)
    );
  }, [faqs, search]);

  const inputBase = 'w-full rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm text-white placeholder-white/20 outline-none focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20 transition-all';

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">FAQ Manager</h1>
          <p className="mt-1 text-sm text-white/40">Manage public help content shown across support surfaces.</p>
        </div>
        <button
          onClick={openCreate}
          className="flex-shrink-0 inline-flex items-center gap-2 rounded-xl bg-cyan text-midnight font-bold text-sm px-4 sm:px-5 py-2 hover:shadow-[0_0_20px_rgba(102,252,241,0.25)] transition-all cursor-pointer"
        >
          <Plus size={15} /> <span className="hidden sm:inline">Add FAQ</span><span className="sm:hidden">Add</span>
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-5">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-white/30 pointer-events-none" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search question or answer…"
          className="w-full rounded-xl border border-white/10 bg-white/[0.03] pl-10 pr-4 py-2.5 text-sm text-white placeholder-white/20 outline-none focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20 transition-all"
        />
      </div>

      {error && (
        <div className="mb-4 rounded-xl px-4 py-3 text-sm text-red-400 bg-red-400/5 border border-red-400/20">{error}</div>
      )}

      {/* FAQ list */}
      {loading ? (
        <div className="flex justify-center py-20">
          <span className="h-6 w-6 border-2 border-cyan/30 border-t-cyan rounded-full animate-spin" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl border border-white/[0.06] bg-carbon/30 p-12 flex flex-col items-center gap-3">
          <HelpCircle className="h-10 w-10 text-white/10" />
          <p className="text-white/30 text-sm">{faqs.length === 0 ? 'No FAQs yet. Add one to get started.' : 'No results match your search.'}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((faq) => (
            <div
              key={faq.id}
              className="rounded-2xl border border-white/[0.06] bg-carbon/40 p-4 sm:p-5 flex items-start gap-3"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium', faq.is_published ? 'bg-cyan/10 text-cyan border border-cyan/20' : 'bg-white/5 text-white/40 border border-white/10')}>
                    {faq.is_published ? <Eye size={11} /> : <EyeOff size={11} />}
                    {faq.is_published ? 'Published' : 'Hidden'}
                  </span>
                  <span className="text-xs text-white/30">Order: {faq.order}</span>
                </div>
                <p className="text-sm font-medium text-white mb-1">{faq.question}</p>
                <p className="text-xs text-white/40 line-clamp-2">{faq.answer}</p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <button
                  onClick={() => openEdit(faq)}
                  className="p-2 rounded-lg text-white/40 hover:text-white hover:bg-white/[0.06] transition-all cursor-pointer"
                >
                  <Edit2 size={15} />
                </button>
                <button
                  onClick={() => setDeletingId(faq.id)}
                  className="p-2 rounded-lg text-white/40 hover:text-red-400 hover:bg-red-400/10 transition-all cursor-pointer"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create/Edit Modal */}
      {isModalOpen && createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-[#0d1117] p-6 shadow-2xl">
            <h2 className="text-lg font-bold text-white mb-5">{editingFaq ? 'Edit FAQ' : 'New FAQ'}</h2>

            {error && <p className="mb-3 text-sm text-red-400">{error}</p>}

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-white/40 mb-1.5">Question *</label>
                <input
                  type="text"
                  value={formData.question}
                  onChange={(e) => setFormData(p => ({ ...p, question: e.target.value }))}
                  placeholder="Enter question"
                  className={inputBase}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-white/40 mb-1.5">Answer *</label>
                <textarea
                  rows={4}
                  value={formData.answer}
                  onChange={(e) => setFormData(p => ({ ...p, answer: e.target.value }))}
                  placeholder="Enter answer"
                  className={`${inputBase} resize-none`}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-white/40 mb-1.5">Order</label>
                  <input
                    type="number"
                    value={formData.order}
                    onChange={(e) => setFormData(p => ({ ...p, order: parseInt(e.target.value) || 0 }))}
                    className={inputBase}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-white/40 mb-1.5">Visibility</label>
                  <button
                    type="button"
                    onClick={() => setFormData(p => ({ ...p, is_published: !p.is_published }))}
                    className={cn(
                      'w-full rounded-xl border px-4 py-2.5 text-sm font-medium transition-all cursor-pointer',
                      formData.is_published
                        ? 'border-cyan/20 bg-cyan/10 text-cyan'
                        : 'border-white/10 bg-white/[0.03] text-white/40'
                    )}
                  >
                    {formData.is_published ? 'Published' : 'Hidden'}
                  </button>
                </div>
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={handleSave}
                disabled={saving || !formData.question.trim() || !formData.answer.trim()}
                className="flex-1 rounded-xl bg-cyan text-midnight font-bold text-sm py-2.5 hover:shadow-[0_0_20px_rgba(102,252,241,0.25)] transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {saving ? 'Saving…' : 'Save'}
              </button>
              <button
                onClick={() => { setIsModalOpen(false); setError(''); }}
                className="rounded-xl border border-white/15 px-6 py-2.5 text-sm font-medium text-white hover:bg-white/[0.06] transition-all cursor-pointer"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* Delete Confirm Modal */}
      {deletingId && createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-2xl border border-white/10 bg-[#0d1117] p-6 shadow-2xl">
            <h2 className="text-lg font-bold text-white mb-2">Delete FAQ?</h2>
            <p className="text-sm text-white/50 mb-6">This action cannot be undone.</p>
            <div className="flex gap-3">
              <button
                onClick={handleDelete}
                className="flex-1 rounded-xl bg-red-500 text-white font-bold text-sm py-2.5 hover:bg-red-600 transition-all cursor-pointer"
              >
                Delete
              </button>
              <button
                onClick={() => setDeletingId(null)}
                className="rounded-xl border border-white/15 px-6 py-2.5 text-sm font-medium text-white hover:bg-white/[0.06] transition-all cursor-pointer"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
