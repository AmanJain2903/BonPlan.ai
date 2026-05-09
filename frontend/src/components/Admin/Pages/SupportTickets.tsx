import { useCallback, useState, useEffect, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { Ticket, CheckCircle, Clock, Send, ChevronDown, ChevronUp, MailCheck, Search } from 'lucide-react';
import { cn } from '../../../utils/tailwind';
import { api, type SupportTicket } from '../../../apis/admin';
import { useAuth } from '../../../context/AuthContext';

type FilterStatus = 'ALL' | 'OPEN' | 'RESOLVED';

export default function SupportTickets() {
  const { token } = useAuth();
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterStatus>('ALL');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [replyTicket, setReplyTicket] = useState<SupportTicket | null>(null);
  const [replyMessage, setReplyMessage] = useState('');
  const [replying, setReplying] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [acknowledgingId, setAcknowledgingId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setLoading(true);
      const status = filter === 'ALL' ? undefined : filter;
      setTickets(await api.adminGetTickets(token, status));
    } catch {
      setError('Failed to load tickets.');
    } finally {
      setLoading(false);
    }
  }, [filter, token]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    if (!successMsg) return;
    const t = setTimeout(() => setSuccessMsg(''), 3500);
    return () => clearTimeout(t);
  }, [successMsg]);

  const toggleStatus = async (ticket: SupportTicket) => {
    if (!token) return;
    const newStatus = ticket.status === 'OPEN' ? 'RESOLVED' : 'OPEN';
    setUpdatingId(ticket.id);
    setError('');
    try {
      await api.adminUpdateTicketStatus(token, ticket.id, newStatus);
      if (newStatus === 'RESOLVED') setSuccessMsg('Ticket resolved. Resolution email sent to user.');
      await load();
    } catch {
      setError('Failed to update status.');
    } finally {
      setUpdatingId(null);
    }
  };

  const handleAcknowledge = async (ticket: SupportTicket) => {
    if (!token) return;
    setAcknowledgingId(ticket.id);
    setError('');
    try {
      await api.adminAcknowledgeTicket(token, ticket.id);
      setTickets(prev => prev.map(t => t.id === ticket.id ? { ...t, acknowledged: true } : t));
      setSuccessMsg(`Acknowledgement sent to ${ticket.user_email}.`);
    } catch {
      setError('Failed to send acknowledgement.');
    } finally {
      setAcknowledgingId(null);
    }
  };

  const handleReply = async () => {
    if (!token || !replyTicket || !replyMessage.trim()) return;
    setReplying(true);
    setError('');
    try {
      await api.adminReplyToTicket(token, replyTicket.id, replyMessage.trim());
      setSuccessMsg('Reply sent successfully.');
      setReplyTicket(null);
      setReplyMessage('');
    } catch {
      setError('Failed to send reply.');
    } finally {
      setReplying(false);
    }
  };

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return tickets;
    return tickets.filter(t =>
      t.subject.toLowerCase().includes(q) ||
      t.body.toLowerCase().includes(q) ||
      t.user_email.toLowerCase().includes(q) ||
      (t.user_id ?? '').toLowerCase().includes(q)
    );
  }, [tickets, search]);

  const fmt = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Support Tickets</h1>
          <p className="mt-1 text-sm text-white/40">Review, acknowledge, resolve, and reply to user support requests.</p>
        </div>

        {/* Filter tabs */}
        <div className="flex items-center gap-1 rounded-xl border border-white/10 bg-white/[0.03] p-1 self-start sm:self-auto">
          {(['ALL', 'OPEN', 'RESOLVED'] as FilterStatus[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                'rounded-lg px-3 py-1.5 text-xs font-medium transition-all cursor-pointer',
                filter === f ? 'bg-white/[0.08] text-white' : 'text-white/40 hover:text-white'
              )}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Search */}
      <div className="relative mb-5">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-white/30 pointer-events-none" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search subject, body, email, or user ID…"
          className="w-full rounded-xl border border-white/10 bg-white/[0.03] pl-10 pr-4 py-2.5 text-sm text-white placeholder-white/20 outline-none focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20 transition-all"
        />
      </div>

      {error && (
        <div className="mb-4 rounded-xl px-4 py-3 text-sm text-red-400 bg-red-400/5 border border-red-400/20">{error}</div>
      )}
      {successMsg && (
        <div className="mb-4 rounded-xl px-4 py-3 text-sm text-cyan bg-cyan/5 border border-cyan/20">{successMsg}</div>
      )}

      {loading ? (
        <div className="flex justify-center py-20">
          <span className="h-6 w-6 border-2 border-cyan/30 border-t-cyan rounded-full animate-spin" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl border border-white/[0.06] bg-carbon/30 p-12 flex flex-col items-center gap-3">
          <Ticket className="h-10 w-10 text-white/10" />
          <p className="text-white/30 text-sm">{tickets.length === 0 ? 'No tickets found.' : 'No results match your search.'}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((ticket) => {
            const isExpanded = expandedId === ticket.id;
            const isUpdating = updatingId === ticket.id;
            return (
              <div
                key={ticket.id}
                className="rounded-2xl border border-white/[0.06] bg-carbon/40 overflow-hidden"
              >
                {/* Ticket header row */}
                <div
                  className="flex flex-col sm:flex-row sm:items-start gap-3 p-4 sm:p-5 cursor-pointer hover:bg-white/[0.02] transition-colors"
                  onClick={() => setExpandedId(isExpanded ? null : ticket.id)}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                      <span className={cn(
                        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
                        ticket.status === 'OPEN'
                          ? 'bg-amber-400/10 text-amber-400 border border-amber-400/20'
                          : 'bg-cyan/10 text-cyan border border-cyan/20'
                      )}>
                        {ticket.status === 'OPEN' ? <Clock size={11} /> : <CheckCircle size={11} />}
                        {ticket.status}
                      </span>
                      <span className="text-xs text-white/30 truncate max-w-[160px] sm:max-w-none">{ticket.user_email}</span>
                      <span className="text-xs text-white/20 hidden sm:inline">{fmt(ticket.created_at)}</span>
                    </div>
                    <p className="text-sm font-medium text-white truncate">{ticket.subject}</p>
                    <p className="text-xs text-white/20 sm:hidden mt-0.5">{fmt(ticket.created_at)}</p>
                  </div>

                  <div className="flex items-center gap-1.5 flex-wrap shrink-0">
                    {!ticket.acknowledged && (
                      <button
                        onClick={(e) => { e.stopPropagation(); handleAcknowledge(ticket); }}
                        disabled={acknowledgingId === ticket.id}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-2.5 py-1.5 text-xs text-white/60 hover:text-white hover:border-white/20 hover:bg-white/[0.04] transition-all cursor-pointer disabled:opacity-40"
                      >
                        <MailCheck size={12} />
                        <span className="hidden sm:inline">{acknowledgingId === ticket.id ? '…' : 'Acknowledge'}</span>
                        <span className="sm:hidden">{acknowledgingId === ticket.id ? '…' : 'Ack'}</span>
                      </button>
                    )}
                    <button
                      onClick={(e) => { e.stopPropagation(); setReplyTicket(ticket); }}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-2.5 py-1.5 text-xs text-white/60 hover:text-white hover:border-white/20 hover:bg-white/[0.04] transition-all cursor-pointer"
                    >
                      <Send size={12} /> Reply
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); toggleStatus(ticket); }}
                      disabled={isUpdating}
                      className={cn(
                        'inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-all cursor-pointer disabled:opacity-40',
                        ticket.status === 'OPEN'
                          ? 'border-cyan/20 bg-cyan/10 text-cyan hover:bg-cyan/20'
                          : 'border-white/10 text-white/40 hover:text-white hover:border-white/20 hover:bg-white/[0.04]'
                      )}
                    >
                      {isUpdating ? '…' : ticket.status === 'OPEN' ? 'Resolve' : 'Reopen'}
                    </button>
                    <div className="p-1.5 text-white/30 pointer-events-none">
                      {isExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                    </div>
                  </div>
                </div>

                {/* Expanded body */}
                {isExpanded && (
                  <div className="px-5 pb-5 border-t border-white/[0.04]">
                    <p className="pt-4 text-sm text-white/60 leading-relaxed whitespace-pre-wrap">{ticket.body}</p>
                    <p className="mt-3 text-xs text-white/20">ID: {ticket.id}</p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Reply Modal */}
      {replyTicket && createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-[#0d1117] p-6 shadow-2xl">
            <h2 className="text-lg font-bold text-white mb-1">Reply to Ticket</h2>
            <p className="text-xs text-white/40 mb-5">To: {replyTicket.user_email} — {replyTicket.subject}</p>

            {error && <p className="mb-3 text-sm text-red-400">{error}</p>}

            <textarea
              rows={6}
              value={replyMessage}
              onChange={(e) => setReplyMessage(e.target.value)}
              placeholder="Type your reply…"
              className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm text-white placeholder-white/20 outline-none focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20 transition-all resize-none"
            />

            <div className="flex gap-3 mt-4">
              <button
                onClick={handleReply}
                disabled={replying || !replyMessage.trim()}
                className="flex-1 inline-flex items-center justify-center gap-2 rounded-xl bg-cyan text-midnight font-bold text-sm py-2.5 hover:shadow-[0_0_20px_rgba(102,252,241,0.25)] transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {replying ? (
                  <>
                    <span className="h-4 w-4 border-2 border-midnight/40 border-t-midnight rounded-full animate-spin" />
                    Sending…
                  </>
                ) : (
                  <><Send size={14} /> Send Reply</>
                )}
              </button>
              <button
                onClick={() => { setReplyTicket(null); setReplyMessage(''); setError(''); }}
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
