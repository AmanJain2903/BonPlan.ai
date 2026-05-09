import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import {
  Check,
  Copy,
  Download,
  Link as LinkIcon,
  Loader2,
  PencilLine,
  Share2,
  Trash2,
  UserPlus,
} from 'lucide-react';
import { api } from '../../apis/plan';
import type { Plan, ShareAccessRole, TripMemberAccess, UserSummary } from '../../apis/plan';
import { useAuth } from '../../context/AuthContext';

interface TripShareMenuProps {
  tripId: string;
  plan: Plan;
}

type Feedback = { type: 'success' | 'error'; text: string } | null;

const roleLabels: Record<string, string> = {
  owner: 'Owner',
  shared_editor: 'Editor',
  shared_viewer: 'Viewer',
  group_member: 'Member',
};

function displayName(person: Pick<UserSummary, 'first_name' | 'last_name' | 'email'>) {
  const name = `${person.first_name || ''} ${person.last_name || ''}`.trim();
  return name || person.email || 'Pending user';
}

function initialsFor(person: Pick<UserSummary, 'first_name' | 'last_name' | 'email'>) {
  const initials = `${person.first_name?.[0] || ''}${person.last_name?.[0] || ''}`.toUpperCase();
  if (initials) return initials;
  return (person.email?.[0] || '?').toUpperCase();
}

function ownerAsMember(owner?: UserSummary): TripMemberAccess | null {
  if (!owner?.email) return null;
  return {
    id: 'owner',
    role: 'owner',
    invitation_status: 'accepted',
    accepted: true,
    is_owner: true,
    first_name: owner.first_name || '',
    last_name: owner.last_name || '',
    email: owner.email,
  };
}

async function extractErrorDetail(err: unknown, fallback: string): Promise<string> {
  const response =
    err && typeof err === 'object' && 'response' in err
      ? (err as { response?: { data?: unknown } }).response
      : undefined;
  const data = response?.data;

  if (data instanceof Blob) {
    try {
      const text = await data.text();
      const parsed = JSON.parse(text) as { detail?: string; message?: string };
      return parsed.detail || parsed.message || fallback;
    } catch {
      return fallback;
    }
  }

  if (data && typeof data === 'object') {
    const detail = (data as { detail?: string; message?: string }).detail;
    const message = (data as { detail?: string; message?: string }).message;
    return detail || message || fallback;
  }

  return fallback;
}

export default function TripShareMenu({ tripId, plan }: TripShareMenuProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [members, setMembers] = useState<TripMemberAccess[]>([]);
  const [loadingMembers, setLoadingMembers] = useState(false);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<ShareAccessRole>('shared_viewer');
  const [submitting, setSubmitting] = useState(false);
  const [creatingLink, setCreatingLink] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [requestingEdit, setRequestingEdit] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [createdLink, setCreatedLink] = useState('');
  const [memberToRemove, setMemberToRemove] = useState<TripMemberAccess | null>(null);

  const currentRole = plan.role;
  const canInvite = currentRole === 'owner' || currentRole === 'shared_editor';
  const canRequestEdit = currentRole === 'shared_viewer';
  const canRemove = currentRole === 'owner';
  const ownerMember = useMemo(() => ownerAsMember(plan.owner), [plan.owner]);

  const loadMembers = useCallback(async () => {
    const token = localStorage.getItem('token') || sessionStorage.getItem('token');
    if (!token) return;
    setLoadingMembers(true);
    try {
      const res = await api.getTripMembers(token, tripId);
      setMembers(res.members || []);
    } catch {
      setFeedback({ type: 'error', text: 'Could not load shared access.' });
    } finally {
      setLoadingMembers(false);
    }
  }, [tripId]);

  useEffect(() => {
    if (!open) return;
    loadMembers();
  }, [loadMembers, open]);

  useEffect(() => {
    if (!open) return;

    const close = () => setOpen(false);
    const isInsideMenu = (target: EventTarget | null) =>
      target instanceof Node && rootRef.current?.contains(target);
    const onPointerDown = (event: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        close();
      }
    };
    const onOutsideScroll = (event: Event) => {
      if (!isInsideMenu(event.target)) {
        close();
      }
    };

    document.addEventListener('pointerdown', onPointerDown);
    window.addEventListener('scroll', onOutsideScroll, true);
    window.addEventListener('wheel', onOutsideScroll, { passive: true });
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      window.removeEventListener('scroll', onOutsideScroll, true);
      window.removeEventListener('wheel', onOutsideScroll);
    };
  }, [open]);

  const visibleMembers = useMemo(() => {
    const combined = [...members];
    if (ownerMember && !combined.some((member) => member.role === 'owner')) {
      combined.unshift(ownerMember);
    }

    if (currentRole === 'shared_viewer') {
      const currentUserEmail = user?.email?.toLowerCase() || '';
      return combined.filter((member) => {
        const memberEmail = member.email?.toLowerCase() || '';
        return member.role === 'owner' || (currentUserEmail !== '' && memberEmail === currentUserEmail);
      });
    }
    return combined;
  }, [currentRole, members, ownerMember, user?.email]);

  const handleInvite = async (event: FormEvent) => {
    event.preventDefault();
    const token = localStorage.getItem('token') || sessionStorage.getItem('token');
    if (!token || !email.trim()) return;
    setSubmitting(true);
    setFeedback(null);
    try {
      const res = await api.shareTrip(token, tripId, { email: email.trim(), role });
      setFeedback({ type: 'success', text: res.message || 'Invitation sent.' });
      setEmail('');
      setInviteOpen(false);
      await loadMembers();
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setFeedback({ type: 'error', text: detail || 'Could not send the invitation.' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateLink = async () => {
    const token = localStorage.getItem('token') || sessionStorage.getItem('token');
    if (!token) return;
    setCreatingLink(true);
    setFeedback(null);
    setCreatedLink('');
    try {
      const res = await api.createShareLink(token, tripId, { role });
      if (res.url) {
        setCreatedLink(res.url);
        const label = role === 'shared_editor' ? 'Editor' : 'Viewer';
        try {
          await navigator.clipboard?.writeText(res.url);
          setFeedback({ type: 'success', text: `${label} link copied.` });
        } catch {
          setFeedback({ type: 'success', text: `${label} link created.` });
        }
      }
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setFeedback({ type: 'error', text: detail || 'Could not create a share link.' });
    } finally {
      setCreatingLink(false);
    }
  };

  const handleDownloadPdf = async () => {
    const token = localStorage.getItem('token') || sessionStorage.getItem('token');
    if (!token) return;
    setDownloadingPdf(true);
    setFeedback(null);
    try {
      const { blob, filename } = await api.downloadTripItineraryPdf(token, tripId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setFeedback({ type: 'success', text: 'Itinerary PDF downloaded.' });
    } catch (err: unknown) {
      setFeedback({
        type: 'error',
        text: await extractErrorDetail(err, 'Could not download the itinerary PDF.'),
      });
    } finally {
      setDownloadingPdf(false);
    }
  };

  const handleRemoveConfirmed = async () => {
    const token = localStorage.getItem('token') || sessionStorage.getItem('token');
    if (!token || !memberToRemove || memberToRemove.is_owner) return;
    setFeedback(null);
    try {
      await api.removeTripMember(token, tripId, memberToRemove.id);
      setFeedback({ type: 'success', text: 'Access removed.' });
      setMemberToRemove(null);
      await loadMembers();
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setFeedback({ type: 'error', text: detail || 'Could not remove access.' });
    }
  };

  const handleRequestEditAccess = async () => {
    const token = localStorage.getItem('token') || sessionStorage.getItem('token');
    if (!token) return;
    setRequestingEdit(true);
    setFeedback(null);
    try {
      const res = await api.requestEditAccess(token, tripId);
      setFeedback({ type: 'success', text: res.message || 'Request sent to the owner.' });
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setFeedback({ type: 'error', text: detail || 'Could not request editing access.' });
    } finally {
      setRequestingEdit(false);
    }
  };

  return (
    <div ref={rootRef} className="flex items-center gap-2">
      <button
        onClick={() => {
          setOpen((value) => !value);
          setFeedback(null);
          setCreatedLink('');
          setMemberToRemove(null);
        }}
        className={`h-10 w-10 shrink-0 rounded-full border backdrop-blur-md flex items-center justify-center transition-all ${open
          ? 'border-cyan/40 bg-cyan text-midnight shadow-[0_0_18px_rgba(102,252,241,0.25)]'
          : 'border-white/10 bg-black/60 text-cyan hover:border-cyan/40 hover:bg-cyan/10'
          }`}
        title="Share itinerary"
        aria-label="Share itinerary"
      >
        <Share2 className="h-4 w-4" />
      </button>

      {open && (
        <div className="absolute right-0 top-12 z-[80] w-[min(92vw,380px)] overflow-hidden rounded-2xl border border-white/10 bg-carbon/95 shadow-2xl backdrop-blur-xl flex flex-col max-h-[min(80vh,560px)]">
          <div className="border-b border-white/5 px-4 py-3 shrink-0">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-bold text-white">Shared Access</h3>
                <p className="text-[11px] text-white/40">
                  {roleLabels[currentRole] || 'Member'}
                </p>
              </div>
              {loadingMembers && <Loader2 className="h-4 w-4 animate-spin text-cyan" />}
            </div>
          </div>

          <div className="max-h-[240px] overflow-y-auto px-3 py-3 chat-scrollbar shrink-0">
            {visibleMembers.length === 0 ? (
              <div className="rounded-xl border border-white/5 bg-black/20 px-3 py-4 text-center text-xs text-white/40">
                No shared access yet.
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {visibleMembers.map((member) => {
                  const memberEmail = member.email?.toLowerCase() || '';
                  const currentUserEmail = user?.email?.toLowerCase() || '';
                  const isCurrentUser = memberEmail !== '' && memberEmail === currentUserEmail;
                  const isOwner = member.role === 'owner' || member.is_owner;
                  const rowClass = isCurrentUser
                    ? 'border-cyan/30 bg-cyan/[0.08]'
                    : isOwner
                      ? 'border-amber-300/25 bg-amber-300/[0.06]'
                      : 'border-transparent hover:bg-white/[0.04]';

                  return (
                    <div key={member.id} className={`flex items-center gap-3 rounded-xl border px-2 py-2 transition-colors ${rowClass}`}>
                      <div className={`h-9 w-9 shrink-0 rounded-full border flex items-center justify-center text-xs font-bold ${isOwner ? 'bg-amber-300/10 border-amber-300/30 text-amber-200' : 'bg-cyan/15 border-cyan/20 text-cyan'}`}>
                        {initialsFor(member)}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <p className="truncate text-sm font-semibold text-white">{displayName(member)}</p>
                          {isCurrentUser && (
                            <span className="shrink-0 rounded-full border border-cyan/25 bg-cyan/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-cyan">
                              You
                            </span>
                          )}
                          {isOwner && (
                            <span className="shrink-0 rounded-full border border-amber-300/25 bg-amber-300/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-amber-200">
                              Owner
                            </span>
                          )}
                          {!isOwner && (
                            <span className="shrink-0 rounded-full border border-white/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-white/45">
                              {roleLabels[member.role] || 'Member'}
                            </span>
                          )}
                        </div>
                        <p className="truncate text-xs text-white/35">{member.email || 'Invitation link'}</p>
                      </div>
                      <div className="flex shrink-0 items-center gap-1.5">
                        <span
                          className={`h-2 w-2 rounded-full ${member.accepted ? 'bg-cyan' : 'bg-amber-300'}`}
                          title={member.accepted ? 'Accepted' : 'Pending'}
                        />
                        {canRemove && !member.is_owner && (
                          <button
                            onClick={() => setMemberToRemove(member)}
                            className="rounded-lg p-1.5 text-white/30 hover:bg-red-400/10 hover:text-red-400 transition-colors"
                            title="Remove access"
                            aria-label="Remove access"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="border-t border-white/5 px-4 py-3 shrink-0 overflow-y-auto">
            {canInvite ? (
              <>
                <div className="mb-3">
                  <div className="mb-1.5 text-[10px] font-bold uppercase tracking-[0.16em] text-white/35">Access Mode</div>
                  <div className="grid grid-cols-2 gap-2 rounded-xl border border-white/10 bg-black/30 p-1">
                    <button
                      type="button"
                      onClick={() => setRole('shared_viewer')}
                      className={`rounded-lg px-3 py-2 text-xs font-bold uppercase tracking-wide transition-colors ${role === 'shared_viewer' ? 'bg-cyan text-midnight' : 'text-white/45 hover:text-white'}`}
                    >
                      Viewing
                    </button>
                    <button
                      type="button"
                      onClick={() => setRole('shared_editor')}
                      className={`rounded-lg px-3 py-2 text-xs font-bold uppercase tracking-wide transition-colors ${role === 'shared_editor' ? 'bg-cyan text-midnight' : 'text-white/45 hover:text-white'}`}
                    >
                      Editing
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <button
                    onClick={() => setInviteOpen((value) => !value)}
                    className="flex h-10 items-center justify-center rounded-xl border border-white/10 text-cyan hover:border-cyan/35 hover:bg-cyan/10 transition-colors"
                    title="Invite by email"
                    aria-label="Invite by email"
                  >
                    <UserPlus className="h-4 w-4" />
                  </button>
                  <button
                    onClick={handleDownloadPdf}
                    disabled={downloadingPdf}
                    className="flex h-10 items-center justify-center rounded-xl border border-white/10 text-cyan hover:border-cyan/35 hover:bg-cyan/10 transition-colors disabled:opacity-50"
                    title="Download itinerary PDF"
                    aria-label="Download itinerary PDF"
                  >
                    {downloadingPdf ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                  </button>
                  <button
                    onClick={handleCreateLink}
                    disabled={creatingLink}
                    className="flex h-10 items-center justify-center rounded-xl border border-white/10 text-cyan hover:border-cyan/35 hover:bg-cyan/10 transition-colors disabled:opacity-50"
                    title="Create viewer link"
                    aria-label="Create viewer link"
                  >
                    {creatingLink ? <Loader2 className="h-4 w-4 animate-spin" /> : <LinkIcon className="h-4 w-4" />}
                  </button>
                </div>

                {inviteOpen && (
                  <form onSubmit={handleInvite} className="mt-3 flex flex-col gap-3">
                    <input
                      type="email"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      placeholder="name@example.com"
                      className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2.5 text-base sm:text-sm text-white placeholder-white/25 outline-none focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20"
                      required
                    />
                    <button
                      type="submit"
                      disabled={submitting || !email.trim()}
                      className="flex h-10 items-center justify-center gap-2 rounded-xl bg-cyan px-3 text-sm font-bold text-midnight transition-all hover:shadow-[0_0_20px_rgba(102,252,241,0.25)] disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                      Share
                    </button>
                  </form>
                )}
              </>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                {canRequestEdit && (
                  <button
                    onClick={handleRequestEditAccess}
                    disabled={requestingEdit}
                    className="flex h-10 items-center justify-center gap-2 rounded-xl border border-white/10 text-cyan hover:border-cyan/35 hover:bg-cyan/10 transition-colors disabled:opacity-50"
                    title="Request editing access"
                    aria-label="Request editing access"
                  >
                    {requestingEdit ? <Loader2 className="h-4 w-4 animate-spin" /> : <PencilLine className="h-4 w-4" />}
                    <span className="text-xs font-bold uppercase tracking-wide">Ask to Edit</span>
                  </button>
                )}
                <button
                  onClick={handleDownloadPdf}
                  disabled={downloadingPdf}
                  className="flex h-10 items-center justify-center rounded-xl border border-white/10 text-cyan hover:border-cyan/35 hover:bg-cyan/10 transition-colors disabled:opacity-50"
                  title="Download itinerary PDF"
                  aria-label="Download itinerary PDF"
                >
                  {downloadingPdf ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                </button>
              </div>
            )}

            {feedback && (
              <p className={`mt-3 text-xs ${feedback.type === 'error' ? 'text-red-400' : 'text-cyan'}`}>
                {feedback.text}
              </p>
            )}
            {createdLink && (
              <button
                onClick={() => navigator.clipboard?.writeText(createdLink)}
                className="mt-2 flex w-full items-center gap-2 rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-left text-[11px] text-white/45 hover:text-white/70 transition-colors"
                title="Copy link"
              >
                <Copy className="h-3.5 w-3.5 shrink-0 text-cyan" />
                <span className="truncate">{createdLink}</span>
              </button>
            )}
          </div>

          {memberToRemove && (
            <div className="absolute inset-0 z-[90] flex items-center justify-center bg-black/70 px-4 backdrop-blur-sm">
              <div className="w-full rounded-2xl border border-white/10 bg-carbon p-5 shadow-2xl">
                <h4 className="text-sm font-bold text-white">Remove Access?</h4>
                <p className="mt-2 text-xs leading-relaxed text-white/50">
                  {displayName(memberToRemove)} will lose access to this itinerary immediately.
                </p>
                <div className="mt-5 grid grid-cols-2 gap-2">
                  <button
                    onClick={() => setMemberToRemove(null)}
                    className="rounded-xl border border-white/10 px-3 py-2 text-xs font-bold uppercase tracking-wide text-white/60 hover:bg-white/[0.05] hover:text-white transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleRemoveConfirmed}
                    className="rounded-xl bg-red-400 px-3 py-2 text-xs font-bold uppercase tracking-wide text-midnight hover:bg-red-300 transition-colors"
                  >
                    Remove
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
