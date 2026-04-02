import { useState, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, Check, X as XIcon } from 'lucide-react';
import { motion } from 'framer-motion';
import GoogleSignInButton from './GoogleSignInButton';
import CountryCodeSelect from '../shared/CountryCodeSelect';
import { api } from '../../api';

type Status = 'idle' | 'loading' | 'success' | 'error';

function isValidEmail(email: string) {
  return /^[^@]+@[^@]+\.[^@]+$/.test(email);
}

function getPasswordChecks(pw: string) {
  return [
    { label: 'At least 8 characters', ok: pw.length >= 8 },
    { label: 'One uppercase letter', ok: /[A-Z]/.test(pw) },
    { label: 'One lowercase letter', ok: /[a-z]/.test(pw) },
    { label: 'One number', ok: /[0-9]/.test(pw) },
    { label: 'One special character', ok: /[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(pw) },
  ];
}

export default function Register() {
  const navigate = useNavigate();
  const [googleError, setGoogleError] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [status, setStatus] = useState<Status>('idle');
  const [apiMessage, setApiMessage] = useState('');
  const [form, setForm] = useState({
    firstName: '',
    lastName: '',
    email: '',
    countryCode: '',
    phone: '',
    password: '',
    confirmPassword: '',
  });

  const update = (field: string, value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  const passwordChecks = useMemo(() => getPasswordChecks(form.password), [form.password]);
  const passwordValid = passwordChecks.every((c) => c.ok);
  const emailTouched = form.email.length > 0;
  const emailValid = isValidEmail(form.email);
  const passwordMismatch = form.confirmPassword.length > 0 && form.password !== form.confirmPassword;
  const passwordTouched = form.password.length > 0;

  const canSubmit =
    form.firstName.trim() !== '' &&
    form.lastName.trim() !== '' &&
    emailValid &&
    passwordValid &&
    form.password === form.confirmPassword &&
    status !== 'loading';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;

    setStatus('loading');
    setApiMessage('');
    try {
      const res = await api.auth.register(
        form.firstName.trim(),
        form.lastName.trim(),
        form.email.trim(),
        form.password,
        form.countryCode.trim() || null,
        form.phone.trim() || null,
      );
      setStatus('success');
      setApiMessage(res.message || 'Registration successful!');
      setTimeout(() => navigate('/login'), 4000);
    } catch (err: unknown) {
      setStatus('error');
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setApiMessage(detail || 'Something went wrong. Please try again.');
    }
  };

  const inputClass =
    'w-full rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm text-white placeholder-white/20 outline-none focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20 transition-all duration-200';

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10 sm:py-16">
      <div className="pointer-events-none fixed top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] rounded-full bg-cyan/[0.03] blur-[120px]" />

      <motion.div
        initial={{ opacity: 0, y: 30, filter: 'blur(8px)', willChange: 'transform, opacity, filter' }}
        animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
        transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        className="relative w-full max-w-lg"
      >
        <div className="text-center mb-8">
          <Link to="/" className="inline-flex items-center gap-1.5 text-2xl font-bold text-white mb-4">
            <img src="/logo.png" alt="BonPlan.ai" className="h-15 w-15 object-contain" />
          </Link>
          <h1 className="text-3xl font-bold text-white tracking-tight">
            Create your account at BonPlan<span className="text-cyan">.</span>ai
          </h1>
          <p className="mt-2 text-sm text-slate/60">Start planning smarter trips</p>
        </div>

        {/* Status banner */}
        {(apiMessage || googleError) && (
          <div
            className={`mb-4 rounded-xl py-3 text-sm text-center ${status === 'success' && !googleError
              ? 'text-cyan'
              : 'text-red-400'
              }`}
          >
            {googleError || apiMessage}
          </div>
        )}

        <div className="rounded-2xl border border-white/[0.06] bg-carbon/50 backdrop-blur-sm p-6 sm:p-8">
          <GoogleSignInButton text="signup_with" onError={setGoogleError} />

          <div className="relative my-5">
            <div className="h-px bg-gradient-to-r from-cyan via-white/10 to-cyan" />
            <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 px-4 text-xs text-white">or</span>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {/* First + Last name */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="firstName" className="block text-xs font-medium text-white/40 mb-1.5">
                  First name <span className="text-red-400">*</span>
                </label>
                <input id="firstName" type="text" required value={form.firstName} onChange={(e) => update('firstName', e.target.value)} placeholder="John" className={inputClass} />
              </div>
              <div>
                <label htmlFor="lastName" className="block text-xs font-medium text-white/40 mb-1.5">
                  Last name <span className="text-red-400">*</span>
                </label>
                <input id="lastName" type="text" required value={form.lastName} onChange={(e) => update('lastName', e.target.value)} placeholder="Doe" className={inputClass} />
              </div>
            </div>

            {/* Email */}
            <div>
              <label htmlFor="email" className="block text-xs font-medium text-white/40 mb-1.5">
                Email address <span className="text-red-400">*</span>
              </label>
              <input
                id="email"
                type="email"
                required
                value={form.email}
                onChange={(e) => update('email', e.target.value)}
                placeholder="you@example.com"
                className={`${inputClass} ${emailTouched && !emailValid ? '!border-red-400/50 focus:!border-red-400/70 focus:!ring-red-400/20' : ''}`}
              />
              {emailTouched && !emailValid && (
                <p className="mt-1 text-xs text-red-400/70">Please enter a valid email address</p>
              )}
            </div>

            {/* Country code + Phone */}
            <div className="grid grid-cols-[120px_1fr] gap-3">
              <div>
                <label htmlFor="countryCode" className="block text-xs font-medium text-white/40 mb-1.5">Code</label>
                <CountryCodeSelect id="countryCode" value={form.countryCode} onChange={(dial) => update('countryCode', dial)} />
              </div>
              <div>
                <label htmlFor="phone" className="block text-xs font-medium text-white/40 mb-1.5">Phone number</label>
                <input id="phone" type="tel" value={form.phone} onChange={(e) => update('phone', e.target.value)} placeholder="(555) 000-0000" className={inputClass} />
              </div>
            </div>

            {/* Password + Confirm */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="password" className="block text-xs font-medium text-white/40 mb-1.5">
                  Password <span className="text-red-400">*</span>
                </label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={form.password}
                    onChange={(e) => update('password', e.target.value)}
                    placeholder="Min. 8 chars"
                    className={`${inputClass} pr-10`}
                  />
                  <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-cyan/80 hover:text-cyan transition-colors cursor-pointer">
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
              <div>
                <label htmlFor="confirmPassword" className="block text-xs font-medium text-white/40 mb-1.5">
                  Confirm password <span className="text-red-400">*</span>
                </label>
                <div className="relative">
                  <input
                    id="confirmPassword"
                    type={showConfirm ? 'text' : 'password'}
                    required
                    value={form.confirmPassword}
                    onChange={(e) => update('confirmPassword', e.target.value)}
                    placeholder="Re-enter"
                    className={`w-full rounded-xl border bg-white/[0.03] px-4 py-2.5 pr-10 text-sm text-white placeholder-white/20 outline-none transition-all duration-200 ${passwordMismatch
                      ? 'border-red-400/50 focus:border-red-400/70 focus:ring-1 focus:ring-red-400/20'
                      : 'border-white/10 focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20'
                      }`}
                  />
                  <button type="button" onClick={() => setShowConfirm(!showConfirm)} className="absolute right-3 top-1/2 -translate-y-1/2 text-cyan/80 hover:text-cyan transition-colors cursor-pointer">
                    {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
            </div>
            {passwordMismatch && <p className="-mt-2 text-xs text-red-400/70">Passwords do not match</p>}

            {/* Password strength checklist */}
            {passwordTouched && (
              <div className="-mt-1 flex flex-wrap gap-x-4 gap-y-1">
                {passwordChecks.map((c) => (
                  <span key={c.label} className={`inline-flex items-center gap-1 text-[11px] ${c.ok ? 'text-cyan/70' : 'text-white/25'}`}>
                    {c.ok ? <Check size={11} /> : <XIcon size={11} />}
                    {c.label}
                  </span>
                ))}
              </div>
            )}

            <button
              type="submit"
              disabled={!canSubmit}
              className="w-full rounded-xl bg-cyan text-midnight font-bold text-sm py-3 hover:shadow-[0_0_25px_rgba(102,252,241,0.3)] transition-all duration-300 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:shadow-none"
            >
              {status === 'loading' ? (
                <span className="inline-flex items-center gap-2">
                  <span className="h-4 w-4 border-2 border-midnight/40 border-t-midnight rounded-full animate-spin" />
                  Creating account…
                </span>
              ) : (
                'Create Account'
              )}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-white/30 mt-6">
          Already have an account?{' '}
          <Link to="/login" className="text-cyan hover:text-cyan/80 transition-colors font-medium">Log in</Link>
        </p>
      </motion.div>
    </div>
  );
}
