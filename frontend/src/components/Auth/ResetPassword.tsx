import { useState, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Eye, EyeOff, Check, X as XIcon, ShieldCheck } from 'lucide-react';
import { api } from '../../api';

type Status = 'idle' | 'loading' | 'success' | 'error';

function getPasswordChecks(pw: string) {
  return [
    { label: 'At least 8 characters', ok: pw.length >= 8 },
    { label: 'One uppercase letter', ok: /[A-Z]/.test(pw) },
    { label: 'One lowercase letter', ok: /[a-z]/.test(pw) },
    { label: 'One number', ok: /[0-9]/.test(pw) },
    { label: 'One special character', ok: /[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(pw) },
  ];
}

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') ?? '';

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [status, setStatus] = useState<Status>('idle');
  const [message, setMessage] = useState('');

  const checks = useMemo(() => getPasswordChecks(password), [password]);
  const valid = checks.every((c) => c.ok);
  const mismatch = confirm.length > 0 && password !== confirm;
  const touched = password.length > 0;
  const canSubmit = valid && password === confirm && status !== 'loading';

  if (!token) {
    return (
      <div className="min-h-screen bg-midnight flex items-center justify-center px-4">
        <div className="text-center">
          <p className="text-red-400 text-sm mb-4">Invalid or missing reset link.</p>
          <Link to="/forgot-password" className="text-cyan text-sm hover:text-cyan/80 transition-colors font-medium">
            Request a new link
          </Link>
        </div>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setStatus('loading');
    setMessage('');
    try {
      const res = await api.auth.resetPassword(token, password);
      setStatus('success');
      setMessage(res.message || 'Password has been reset successfully.');
    } catch (err: unknown) {
      setStatus('error');
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setMessage(detail || 'Something went wrong. Please try again.');
    }
  };

  return (
    <div className="min-h-screen bg-midnight flex items-center justify-center px-4 py-12 sm:py-24">
      <div className="pointer-events-none fixed top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] rounded-full bg-cyan/[0.03] blur-[120px]" />

      <div className="relative w-full max-w-md">
        <div className="text-center mb-10">
          <Link to="/" className="inline-flex items-center gap-1.5 text-2xl font-bold text-white mb-6">
            <img src="/logo.png" alt="BonPlan.ai" className="h-15 w-15 object-contain" />
          </Link>
          <h1 className="text-3xl font-bold text-white tracking-tight">
            Set new password
          </h1>
          <p className="mt-2 text-sm text-slate/60">
            Choose a strong password for your account
          </p>
        </div>

        {message && status === 'error' && (
          <div className="mb-4 rounded-xl border border-red-400/20 bg-red-400/5 px-4 py-3 text-sm text-red-400 text-center">
            {message}
          </div>
        )}

        {status === 'success' ? (
          <div className="rounded-2xl border border-white/[0.06] bg-carbon/50 backdrop-blur-sm p-8 text-center">
            <div className="mx-auto mb-5 h-14 w-14 rounded-full bg-cyan/10 flex items-center justify-center">
              <ShieldCheck size={24} className="text-cyan" />
            </div>
            <p className="text-sm text-cyan font-medium mb-2">{message}</p>
            <p className="text-sm text-white/50 mb-6">
              You can now log in with your new password.
            </p>
            <Link
              to="/login"
              className="inline-flex items-center gap-2 rounded-xl bg-cyan text-midnight font-bold text-sm px-6 py-3 hover:shadow-[0_0_25px_rgba(102,252,241,0.3)] transition-all duration-300"
            >
              Go to Login
            </Link>
          </div>
        ) : (
          <div className="rounded-2xl border border-white/[0.06] bg-carbon/50 backdrop-blur-sm p-8">
            <form onSubmit={handleSubmit} className="flex flex-col gap-5">
              {/* New password */}
              <div>
                <label htmlFor="password" className="block text-xs font-medium text-white/40 mb-2">
                  New password <span className="text-red-400">*</span>
                </label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter new password"
                    className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 pr-11 text-sm text-white placeholder-white/20 outline-none focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20 transition-all duration-200"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-cyan/80 hover:text-cyan transition-colors cursor-pointer"
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
                {touched && (
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
                    {checks.map((c) => (
                      <span key={c.label} className={`inline-flex items-center gap-1 text-[11px] ${c.ok ? 'text-cyan/70' : 'text-white/25'}`}>
                        {c.ok ? <Check size={11} /> : <XIcon size={11} />}
                        {c.label}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Confirm password */}
              <div>
                <label htmlFor="confirm" className="block text-xs font-medium text-white/40 mb-2">
                  Confirm password <span className="text-red-400">*</span>
                </label>
                <div className="relative">
                  <input
                    id="confirm"
                    type={showConfirm ? 'text' : 'password'}
                    required
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    placeholder="Re-enter new password"
                    className={`w-full rounded-xl border bg-white/[0.03] px-4 py-3 pr-11 text-sm text-white placeholder-white/20 outline-none transition-all duration-200 ${mismatch
                        ? 'border-red-400/50 focus:border-red-400/70 focus:ring-1 focus:ring-red-400/20'
                        : 'border-white/10 focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20'
                      }`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirm(!showConfirm)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-cyan/80 hover:text-cyan transition-colors cursor-pointer"
                  >
                    {showConfirm ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
                {mismatch && <p className="mt-1 text-xs text-red-400/70">Passwords do not match</p>}
              </div>

              <button
                type="submit"
                disabled={!canSubmit}
                className="w-full rounded-xl bg-cyan text-midnight font-bold text-sm py-3.5 hover:shadow-[0_0_25px_rgba(102,252,241,0.3)] transition-all duration-300 cursor-pointer mt-1 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:shadow-none"
              >
                {status === 'loading' ? (
                  <span className="inline-flex items-center gap-2">
                    <span className="h-4 w-4 border-2 border-midnight/40 border-t-midnight rounded-full animate-spin" />
                    Resetting…
                  </span>
                ) : (
                  'Reset Password'
                )}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
