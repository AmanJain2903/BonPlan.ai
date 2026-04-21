import { useState, useMemo, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, EyeOff, Check, X as XIcon, Trash2, Lock } from 'lucide-react';
import { api } from '../../api';
import { useAuth } from '../../context/AuthContext';

function getPasswordChecks(pw: string) {
  return [
    { label: 'At least 8 characters', ok: pw.length >= 8 },
    { label: 'One uppercase letter', ok: /[A-Z]/.test(pw) },
    { label: 'One lowercase letter', ok: /[a-z]/.test(pw) },
    { label: 'One number', ok: /[0-9]/.test(pw) },
    { label: 'One special character', ok: /[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(pw) },
  ];
}

export default function SettingsPanel() {
  const { token, user, logout } = useAuth();
  const navigate = useNavigate();
  const isGoogle = user?.authProvider === 'google';

  // Change password state
  const [pwForm, setPwForm] = useState({ current: '', newPw: '', confirm: '' });
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [pwStatus, setPwStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [pwMessage, setPwMessage] = useState('');

  useEffect(() => {
    if (!pwMessage) return;
    const timer = setTimeout(() => {
      setPwMessage('');
      setPwStatus('idle');
    }, 3000);
    return () => clearTimeout(timer);
  }, [pwMessage]);

  // Delete account state
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const passwordChecks = useMemo(() => getPasswordChecks(pwForm.newPw), [pwForm.newPw]);
  const passwordValid = passwordChecks.every((c) => c.ok);
  const passwordMismatch = pwForm.confirm.length > 0 && pwForm.newPw !== pwForm.confirm;
  const newTouched = pwForm.newPw.length > 0;

  const canSubmitPw =
    pwForm.current.length > 0 &&
    passwordValid &&
    pwForm.newPw === pwForm.confirm &&
    pwStatus !== 'loading';

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmitPw || !token) return;
    setPwStatus('loading');
    setPwMessage('');
    try {
      const res = await api.auth.changePassword(token, pwForm.current, pwForm.newPw);
      setPwStatus('success');
      setPwMessage(res.message || 'Password changed successfully.');
      setPwForm({ current: '', newPw: '', confirm: '' });
    } catch (err: unknown) {
      setPwStatus('error');
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setPwMessage(detail || 'Failed to change password.');
    }
  };

  const handleDeleteAccount = async () => {
    if (!token) return;
    setDeleting(true);
    try {
      await api.auth.deleteUser(token);
      setConfirmDelete(false);
      logout();
      navigate('/');
    } catch {
      setDeleting(false);
    }
  };

  const inputClass =
    'w-full rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm text-white placeholder-white/20 outline-none focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20 transition-all duration-200';

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-stretch max-w-7xl">
      {/* Change Password */}
      <section className={`flex flex-col ${isGoogle ? 'pointer-events-none select-none' : ''}`}>
        <div className="flex items-center gap-3 mb-6">
          <div className="h-9 w-9 rounded-lg bg-cyan/10 flex items-center justify-center">
            <Lock size={18} className="text-cyan" />
          </div>
          <div>
            <h2 className="text-lg font-extrabold text-white">Change Password</h2>
            <p className="text-xs text-white/75">
              {isGoogle
                ? 'Password management is handled by Google for your account'
                : 'Update your password to keep your account secure'}
            </p>
          </div>
        </div>

        {isGoogle && (
          <div className="flex-1 rounded-2xl border border-white/[0.06] p-6 flex items-center justify-center min-h-[200px] bg-carbon/40 backdrop-blur-sm">
            <p className="text-sm text-white/30 text-center">
              You signed in with Google. Password change is not available.
            </p>
          </div>
        )}

        {!isGoogle && pwMessage && (
          <div className={`mb-5 rounded-xl px-4 py-3 text-sm ${pwStatus === 'success' ? 'text-cyan' : 'text-red-400'}`}>
            {pwMessage}
          </div>
        )}

        {!isGoogle && <form onSubmit={handleChangePassword} className="flex-1 rounded-2xl border border-white/[0.06] p-6 space-y-5 bg-carbon/40 backdrop-blur-sm">
          {/* Current password */}
          <div>
            <label className="block text-xs font-medium text-white/40 mb-1.5">Current password</label>
            <div className="relative">
              <input
                type={showCurrent ? 'text' : 'password'}
                value={pwForm.current}
                onChange={(e) => setPwForm((f) => ({ ...f, current: e.target.value }))}
                placeholder="Enter current password"
                className={`${inputClass} pr-10`}
              />
              <button type="button" onClick={() => setShowCurrent(!showCurrent)} className="absolute right-3 top-1/2 -translate-y-1/2 text-cyan/80 hover:text-cyan transition-colors cursor-pointer">
                {showCurrent ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* New password */}
          <div>
            <label className="block text-xs font-medium text-white/40 mb-1.5">New password</label>
            <div className="relative">
              <input
                type={showNew ? 'text' : 'password'}
                value={pwForm.newPw}
                onChange={(e) => setPwForm((f) => ({ ...f, newPw: e.target.value }))}
                placeholder="Enter new password"
                className={`${inputClass} pr-10`}
              />
              <button type="button" onClick={() => setShowNew(!showNew)} className="absolute right-3 top-1/2 -translate-y-1/2 text-cyan/80 hover:text-cyan transition-colors cursor-pointer">
                {showNew ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {newTouched && (
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
                {passwordChecks.map((c) => (
                  <span key={c.label} className={`inline-flex items-center gap-1 text-[11px] ${c.ok ? 'text-cyan/70' : 'text-white/25'}`}>
                    {c.ok ? <Check size={11} /> : <XIcon size={11} />}
                    {c.label}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Confirm new password */}
          <div>
            <label className="block text-xs font-medium text-white/40 mb-1.5">Confirm new password</label>
            <div className="relative">
              <input
                type={showConfirm ? 'text' : 'password'}
                value={pwForm.confirm}
                onChange={(e) => setPwForm((f) => ({ ...f, confirm: e.target.value }))}
                placeholder="Re-enter new password"
                className={`w-full rounded-xl border bg-white/[0.03] px-4 py-2.5 pr-10 text-sm text-white placeholder-white/20 outline-none transition-all duration-200 ${passwordMismatch
                  ? 'border-red-400/50 focus:border-red-400/70 focus:ring-1 focus:ring-red-400/20'
                  : 'border-white/10 focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20'
                  }`}
              />
              <button type="button" onClick={() => setShowConfirm(!showConfirm)} className="absolute right-3 top-1/2 -translate-y-1/2 text-cyan/80 hover:text-cyan transition-colors cursor-pointer">
                {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {passwordMismatch && <p className="mt-1 text-xs text-red-400/70">Passwords do not match</p>}
          </div>

          <button
            type="submit"
            disabled={!canSubmitPw}
            className="rounded-xl bg-cyan text-midnight font-bold text-sm px-6 py-2.5 hover:shadow-[0_0_25px_rgba(102,252,241,0.3)] transition-all duration-300 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:shadow-none"
          >
            {pwStatus === 'loading' ? (
              <span className="inline-flex items-center gap-2">
                <span className="h-4 w-4 border-2 border-midnight/40 border-t-midnight rounded-full animate-spin" />
                Updating…
              </span>
            ) : (
              'Update Password'
            )}
          </button>
        </form>}
      </section>

      {/* Delete Account */}
      <section className="flex flex-col">
        <div className="flex items-center gap-3 mb-6">
          <div className="h-9 w-9 rounded-lg bg-red-400/10 flex items-center justify-center">
            <Trash2 size={18} className="text-red-400" />
          </div>
          <div>
            <h2 className="text-lg font-extrabold text-white">Delete Account</h2>
            <p className="text-xs text-white/75">Permanently remove your account and all associated data</p>
          </div>
        </div>

        <div className="flex-1 rounded-2xl border border-white/[0.06] bg-carbon/40 backdrop-blur-sm p-6">
          <p className="text-sm text-white/50 mb-5">
            Once you delete your account, all your trips, preferences, and personal data will be permanently erased. This action cannot be undone.
          </p>

          {!confirmDelete ? (
            <button
              onClick={() => setConfirmDelete(true)}
              className="rounded-xl border border-red-400/30 bg-red-400/5 px-5 py-2.5 text-sm font-medium text-red-400 hover:bg-red-400/10 hover:border-red-400/50 transition-all duration-200 cursor-pointer"
            >
              Delete my account
            </button>
          ) : (
            <div className="space-y-4">
              <p className="text-sm font-medium text-red-400">Are you sure? This cannot be undone.</p>
              <div className="flex gap-3">
                <button
                  onClick={() => { setConfirmDelete(false); setDeleting(false); }}
                  className="rounded-xl border border-white/15 px-5 py-2.5 text-sm font-medium text-white hover:bg-white/[0.06] transition-all cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDeleteAccount}
                  disabled={deleting}
                  className="rounded-xl bg-red-500 px-5 py-2.5 text-sm font-bold text-white hover:bg-red-600 transition-all cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {deleting ? (
                    <span className="inline-flex items-center gap-2">
                      <span className="h-3.5 w-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                      Deleting…
                    </span>
                  ) : (
                    'Yes, delete my account'
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
