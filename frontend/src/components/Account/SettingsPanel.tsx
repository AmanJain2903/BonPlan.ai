import { useState, useMemo, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, EyeOff, Check, X as XIcon, Trash2, Lock, Shield, AlertTriangle } from 'lucide-react';
import { motion } from 'framer-motion';
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

  const [pwForm, setPwForm] = useState({ current: '', newPw: '', confirm: '' });
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [pwStatus, setPwStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [pwMessage, setPwMessage] = useState('');

  useEffect(() => {
    if (!pwMessage) return;
    const timer = setTimeout(() => { setPwMessage(''); setPwStatus('idle'); }, 3000);
    return () => clearTimeout(timer);
  }, [pwMessage]);

  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const passwordChecks = useMemo(() => getPasswordChecks(pwForm.newPw), [pwForm.newPw]);
  const passwordValid = passwordChecks.every((c) => c.ok);
  const passwordMismatch = pwForm.confirm.length > 0 && pwForm.newPw !== pwForm.confirm;
  const newTouched = pwForm.newPw.length > 0;
  const strengthCount = passwordChecks.filter(c => c.ok).length;

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

  const strengthPct = newTouched ? Math.round((strengthCount / passwordChecks.length) * 100) : 0;
  const strengthColor =
    strengthCount <= 1 ? 'bg-red-500' :
    strengthCount <= 2 ? 'bg-orange-400' :
    strengthCount <= 3 ? 'bg-yellow-400' :
    strengthCount <= 4 ? 'bg-cyan/70' : 'bg-cyan';
  const strengthLabel =
    !newTouched ? '' :
    strengthCount <= 1 ? 'Very weak' :
    strengthCount <= 2 ? 'Weak' :
    strengthCount <= 3 ? 'Fair' :
    strengthCount <= 4 ? 'Good' : 'Strong';

  return (
    <div className="max-w-7xl space-y-6">

      {/* ── Change Password ── */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className={`rounded-2xl border border-white/[0.06] bg-carbon/40 backdrop-blur-sm overflow-hidden ${isGoogle ? 'pointer-events-none select-none' : ''}`}
      >
        {/* Section header */}
        <div className="flex items-center gap-3 px-6 sm:px-8 py-5 border-b border-white/[0.05]">
          <div className={`h-10 w-10 rounded-xl flex items-center justify-center shrink-0 border ${
            isGoogle ? 'bg-white/[0.03] border-white/[0.06]' : 'bg-cyan/10 border-cyan/15'
          }`}>
            <Lock size={18} className={isGoogle ? 'text-white/20' : 'text-cyan'} />
          </div>
          <div>
            <h3 className="text-base font-bold text-white tracking-wide">Change Password</h3>
            <p className="text-xs text-white/40 mt-0.5">
              {isGoogle
                ? 'Password management is handled by Google for your account'
                : 'Update your password regularly to keep your account secure'}
            </p>
          </div>
        </div>

        {isGoogle ? (
          <div className="flex flex-col items-center justify-center gap-4 py-16 px-8">
            <div className="h-14 w-14 rounded-2xl bg-white/[0.03] border border-white/[0.05] flex items-center justify-center">
              <Shield size={24} className="text-white/12" />
            </div>
            <div className="text-center space-y-1.5">
              <p className="text-sm font-semibold text-white/25">Managed by Google</p>
              <p className="text-xs text-white/15 max-w-xs">
                You signed in with Google. To change your password, visit your Google account settings.
              </p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr]">
            {/* Left: description */}
            <div className="px-8 py-10 border-b lg:border-b-0 lg:border-r border-white/[0.05] bg-white/[0.01] space-y-5">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.12em] text-white/22 mb-3">Tips for a strong password</p>
                <ul className="space-y-2.5">
                  {[
                    'Mix uppercase & lowercase letters',
                    'Include numbers and symbols',
                    'Avoid personal info like birthdays',
                    'Use a unique password for each site',
                  ].map(tip => (
                    <li key={tip} className="flex items-start gap-2.5">
                      <span className="mt-0.5 h-4 w-4 rounded-full bg-cyan/10 border border-cyan/15 flex items-center justify-center shrink-0">
                        <Check size={10} className="text-cyan/60" strokeWidth={2.5} />
                      </span>
                      <span className="text-xs text-white/35 leading-relaxed">{tip}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Right: form */}
            <div className="px-6 sm:px-10 py-8">
              {pwMessage && (
                <div className={`mb-6 rounded-xl px-4 py-2.5 text-xs font-medium ${
                  pwStatus === 'success'
                    ? 'text-cyan bg-cyan/5 border border-cyan/20'
                    : 'text-red-400 bg-red-400/5 border border-red-400/20'
                }`}>
                  {pwMessage}
                </div>
              )}

              <form onSubmit={handleChangePassword} className="space-y-5">
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
                    <button type="button" onClick={() => setShowCurrent(!showCurrent)} className="absolute right-3 top-1/2 -translate-y-1/2 text-white/25 hover:text-cyan transition-colors cursor-pointer">
                      {showCurrent ? <EyeOff size={15} /> : <Eye size={15} />}
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
                    <button type="button" onClick={() => setShowNew(!showNew)} className="absolute right-3 top-1/2 -translate-y-1/2 text-white/25 hover:text-cyan transition-colors cursor-pointer">
                      {showNew ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>

                  {newTouched && (
                    <div className="mt-2.5 space-y-2">
                      <div className="flex items-center gap-3">
                        <div className="flex-1 h-1 rounded-full bg-white/[0.06] overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-300 ${strengthColor}`}
                            style={{ width: `${strengthPct}%` }}
                          />
                        </div>
                        <span className="text-[10px] font-semibold text-white/28 shrink-0 w-14 text-right">{strengthLabel}</span>
                      </div>
                      <div className="flex flex-wrap gap-x-3 gap-y-1">
                        {passwordChecks.map((c) => (
                          <span key={c.label} className={`inline-flex items-center gap-1 text-[10px] font-medium ${c.ok ? 'text-cyan/65' : 'text-white/18'}`}>
                            {c.ok ? <Check size={10} strokeWidth={2.5} /> : <XIcon size={10} strokeWidth={2.5} />}
                            {c.label}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Confirm */}
                <div>
                  <label className="block text-xs font-medium text-white/40 mb-1.5">Confirm new password</label>
                  <div className="relative">
                    <input
                      type={showConfirm ? 'text' : 'password'}
                      value={pwForm.confirm}
                      onChange={(e) => setPwForm((f) => ({ ...f, confirm: e.target.value }))}
                      placeholder="Re-enter new password"
                      className={`w-full rounded-xl border bg-white/[0.03] px-4 py-2.5 pr-10 text-sm text-white placeholder-white/20 outline-none transition-all duration-200 ${
                        passwordMismatch
                          ? 'border-red-400/50 focus:border-red-400/70 focus:ring-1 focus:ring-red-400/20'
                          : 'border-white/10 focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20'
                      }`}
                    />
                    <button type="button" onClick={() => setShowConfirm(!showConfirm)} className="absolute right-3 top-1/2 -translate-y-1/2 text-white/25 hover:text-cyan transition-colors cursor-pointer">
                      {showConfirm ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                  {passwordMismatch && <p className="mt-1.5 text-[11px] text-red-400/70">Passwords do not match</p>}
                </div>

                <button
                  type="submit"
                  disabled={!canSubmitPw}
                  className="rounded-xl bg-cyan text-midnight font-bold text-sm px-8 py-2.5 hover:shadow-[0_0_25px_rgba(102,252,241,0.25)] transition-all duration-300 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:shadow-none"
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
              </form>
            </div>
          </div>
        )}
      </motion.div>

      {/* ── Danger Zone ── */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut', delay: 0.08 }}
        className="rounded-2xl border border-red-500/[0.14] bg-red-500/[0.02] backdrop-blur-sm overflow-hidden"
      >
        {/* Section header */}
        <div className="flex items-center gap-3 px-6 sm:px-8 py-5 border-b border-red-500/[0.08]">
          <div className="h-10 w-10 rounded-xl bg-red-400/[0.08] border border-red-400/15 flex items-center justify-center shrink-0">
            <Trash2 size={18} className="text-red-400/80" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white tracking-wide">Danger Zone</h3>
            <p className="text-xs text-white/40 mt-0.5">Irreversible actions that permanently affect your account</p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr]">
          {/* Left: warning description */}
          <div className="px-8 py-10 border-b lg:border-b-0 lg:border-r border-red-500/[0.07] bg-red-500/[0.01] space-y-4">
            <div className="flex items-center gap-2.5">
              <AlertTriangle size={14} className="text-red-400/60 shrink-0" />
              <p className="text-xs font-bold uppercase tracking-[0.12em] text-red-400/50">Permanent action</p>
            </div>
            <p className="text-xs text-white/35 leading-relaxed">
              Deleting your account will permanently erase all your trips, preferences, and personal data. This cannot be recovered or reversed.
            </p>
            <p className="text-xs text-white/22 leading-relaxed">
              If you're having trouble with the app, consider contacting support before taking this step.
            </p>
          </div>

          {/* Right: action */}
          <div className="px-6 sm:px-10 py-10 flex flex-col justify-center">
            {!confirmDelete ? (
              <div className="space-y-3">
                <p className="text-sm font-semibold text-white/60">Delete Account</p>
                <p className="text-xs text-white/30">Once deleted, your account and all its data are gone permanently.</p>
                <button
                  onClick={() => setConfirmDelete(true)}
                  className="mt-2 rounded-xl border border-red-400/20 bg-red-400/[0.04] px-5 py-2.5 text-sm font-semibold text-red-400/70 hover:text-red-400 hover:bg-red-400/[0.09] hover:border-red-400/35 transition-all duration-200 cursor-pointer"
                >
                  Delete my account
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <p className="text-sm font-bold text-red-400">Are you absolutely sure?</p>
                <p className="text-xs text-white/35">This action is permanent and cannot be undone.</p>
                <div className="flex gap-3">
                  <button
                    onClick={() => { setConfirmDelete(false); setDeleting(false); }}
                    className="flex-1 rounded-xl border border-white/10 py-2.5 text-sm font-medium text-white/55 hover:text-white hover:bg-white/[0.05] transition-all cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleDeleteAccount}
                    disabled={deleting}
                    className="flex-1 rounded-xl bg-red-500 py-2.5 text-sm font-bold text-white hover:bg-red-600 transition-all cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    {deleting ? (
                      <span className="inline-flex items-center justify-center gap-2">
                        <span className="h-3.5 w-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                        Deleting…
                      </span>
                    ) : (
                      'Yes, delete forever'
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  );
}
