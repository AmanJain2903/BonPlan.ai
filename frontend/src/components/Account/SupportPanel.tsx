import { useState, useEffect, useMemo } from 'react';
import { ChevronDown, Send, MessageSquare, HelpCircle, Search, Mail, Clock } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import { api } from '../../api/index';
import { useAuth } from '../../context/AuthContext';

type FAQ = { id: string; question: string; answer: string; order: number };
type Status = 'idle' | 'sending' | 'success' | 'error';

export default function SupportPanel() {
  const { token } = useAuth();

  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [status, setStatus] = useState<Status>('idle');
  const [message, setMessage] = useState('');

  const [faqs, setFaqs] = useState<FAQ[]>([]);
  const [faqSearch, setFaqSearch] = useState('');
  const [openFaq, setOpenFaq] = useState<string | null>(null);

  const filteredFaqs = useMemo(() => {
    const q = faqSearch.trim().toLowerCase();
    if (!q) return faqs;
    return faqs.filter(f =>
      f.question.toLowerCase().includes(q) ||
      f.answer.toLowerCase().includes(q)
    );
  }, [faqs, faqSearch]);

  useEffect(() => {
    api.admin.getPublicFaqs().then(setFaqs).catch(() => {});
  }, []);

  useEffect(() => {
    if (!message) return;
    const t = setTimeout(() => { setMessage(''); if (status !== 'idle') setStatus('idle'); }, 4000);
    return () => clearTimeout(t);
  }, [message]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !subject.trim() || !body.trim()) return;
    setStatus('sending');
    setMessage('');
    try {
      await api.admin.submitTicket(token, subject.trim(), body.trim());
      setStatus('success');
      setMessage('Ticket submitted! We\'ll get back to you soon.');
      setSubject('');
      setBody('');
    } catch (err: unknown) {
      setStatus('error');
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setMessage(detail || 'Failed to submit. Please try again.');
    }
  };

  const inputBase =
    'w-full rounded-xl border px-4 py-2.5 text-base sm:text-sm text-white placeholder-white/20 outline-none transition-all duration-200 border-white/10 bg-white/[0.03] focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20';

  return (
    <div className="max-w-7xl space-y-6">

      {/* ── Contact Support ── */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="rounded-2xl border border-white/[0.06] bg-carbon/40 backdrop-blur-sm overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center gap-3 px-6 sm:px-8 py-5 border-b border-white/[0.05]">
          <div className="h-10 w-10 rounded-xl bg-cyan/10 border border-cyan/15 flex items-center justify-center shrink-0">
            <MessageSquare size={18} className="text-cyan" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white tracking-wide">Contact Support</h3>
            <p className="text-xs text-white/40 mt-0.5">Submit a ticket and we'll get back to you as soon as possible</p>
          </div>
        </div>

        {/* Two-column body */}
        <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr]">
          {/* Left: contact info */}
          <div className="px-8 py-10 border-b lg:border-b-0 lg:border-r border-white/[0.05] bg-white/[0.01] space-y-6">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.12em] text-white/22 mb-4">What to include</p>
              <ul className="space-y-3">
                {[
                  'Clear description of the issue',
                  'Steps to reproduce the problem',
                  'What you expected to happen',
                  'Any error messages you saw',
                ].map(tip => (
                  <li key={tip} className="flex items-start gap-2.5">
                    <span className="mt-0.5 h-4 w-4 rounded-full bg-cyan/10 border border-cyan/15 flex items-center justify-center shrink-0">
                      <span className="h-1.5 w-1.5 rounded-full bg-cyan/50" />
                    </span>
                    <span className="text-xs text-white/35 leading-relaxed">{tip}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="pt-2 space-y-3">
              <div className="flex items-center gap-2.5">
                <Mail size={13} className="text-white/22 shrink-0" />
                <span className="text-xs text-white/30">We reply to every ticket</span>
              </div>
              <div className="flex items-center gap-2.5">
                <Clock size={13} className="text-white/22 shrink-0" />
                <span className="text-xs text-white/30">Typical response within 24–48 hours</span>
              </div>
            </div>
          </div>

          {/* Right: form */}
          <div className="px-6 sm:px-10 py-8">
            {message && (
              <div className={`mb-6 rounded-xl px-4 py-3 text-sm font-medium ${
                status === 'success'
                  ? 'text-cyan bg-cyan/5 border border-cyan/20'
                  : 'text-red-400 bg-red-400/5 border border-red-400/20'
              }`}>
                {message}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="block text-xs font-medium text-white/40 mb-1.5">
                  Subject <span className="text-red-400/70">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  placeholder="Briefly describe your issue"
                  className={inputBase}
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-white/40 mb-1.5">
                  Message <span className="text-red-400/70">*</span>
                </label>
                <textarea
                  required
                  rows={6}
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  placeholder="Describe your issue in detail…"
                  className={`${inputBase} resize-none`}
                />
              </div>

              <button
                type="submit"
                disabled={status === 'sending' || !subject.trim() || !body.trim()}
                className="inline-flex items-center gap-2 rounded-xl bg-cyan text-midnight font-bold text-sm px-7 py-2.5 hover:shadow-[0_0_25px_rgba(102,252,241,0.25)] transition-all duration-300 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:shadow-none"
              >
                {status === 'sending' ? (
                  <>
                    <span className="h-4 w-4 border-2 border-midnight/40 border-t-midnight rounded-full animate-spin" />
                    Sending…
                  </>
                ) : (
                  <>
                    <Send size={14} />
                    Send Message
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      </motion.div>

      {/* ── FAQ ── */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut', delay: 0.08 }}
        className="rounded-2xl border border-white/[0.06] bg-carbon/40 backdrop-blur-sm overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center gap-3 px-6 sm:px-8 py-5 border-b border-white/[0.05]">
          <div className="h-10 w-10 rounded-xl bg-cyan/10 border border-cyan/15 flex items-center justify-center shrink-0">
            <HelpCircle size={18} className="text-cyan" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white tracking-wide">Frequently Asked Questions</h3>
            <p className="text-xs text-white/40 mt-0.5">Answers to common questions about BonPlan.ai</p>
          </div>
        </div>

        <div className="px-6 sm:px-8 py-6">
          {faqs.length === 0 ? (
            <div className="flex flex-col items-center gap-4 py-14">
              <div className="h-14 w-14 rounded-2xl bg-white/[0.03] border border-white/[0.05] flex items-center justify-center">
                <HelpCircle size={24} className="text-white/12" />
              </div>
              <div className="text-center space-y-1">
                <p className="text-sm font-semibold text-white/20">No FAQs yet</p>
                <p className="text-xs text-white/12">Check back soon for answers to common questions.</p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-white/25 pointer-events-none" />
                <input
                  type="text"
                  value={faqSearch}
                  onChange={(e) => { setFaqSearch(e.target.value); setOpenFaq(null); }}
                  placeholder="Search FAQs…"
                  className="w-full rounded-xl border border-white/[0.06] bg-white/[0.02] pl-10 pr-4 py-2.5 text-base sm:text-sm text-white placeholder-white/20 outline-none focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20 transition-all"
                />
              </div>

              {filteredFaqs.length === 0 ? (
                <p className="text-sm text-white/22 py-8 text-center">No FAQs match your search.</p>
              ) : (
                <div className="space-y-2">
                  {filteredFaqs.map((faq) => {
                    const isOpen = openFaq === faq.id;
                    return (
                      <div
                        key={faq.id}
                        className={`rounded-xl border transition-all duration-200 overflow-hidden ${
                          isOpen
                            ? 'border-cyan/[0.14] bg-cyan/[0.025]'
                            : 'border-white/[0.05] bg-white/[0.015] hover:border-white/[0.08]'
                        }`}
                      >
                        <button
                          type="button"
                          onClick={() => setOpenFaq(isOpen ? null : faq.id)}
                          className="w-full flex items-center justify-between px-5 py-4 text-left cursor-pointer gap-4"
                        >
                          <span className={`text-sm font-medium leading-snug transition-colors ${
                            isOpen ? 'text-cyan/85' : 'text-white/70'
                          }`}>
                            {faq.question}
                          </span>
                          <ChevronDown
                            size={15}
                            className={`shrink-0 transition-all duration-200 ${
                              isOpen ? 'rotate-180 text-cyan/50' : 'text-white/25'
                            }`}
                          />
                        </button>
                        <AnimatePresence initial={false}>
                          {isOpen && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              transition={{ duration: 0.22, ease: 'easeOut' }}
                              className="overflow-hidden"
                            >
                              <div className="px-5 pb-5 border-t border-white/[0.05]">
                                <div className="pt-4 text-sm text-white/52 leading-relaxed prose prose-invert prose-sm max-w-none prose-strong:text-white/72 prose-ul:my-1.5 prose-li:my-0.5 prose-p:my-1.5 prose-headings:text-white/65 prose-code:text-cyan/65 prose-code:bg-white/5 prose-code:px-1 prose-code:rounded">
                                  <ReactMarkdown>{faq.answer}</ReactMarkdown>
                                </div>
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}
