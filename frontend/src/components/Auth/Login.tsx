import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Eye, EyeOff } from 'lucide-react';
import { motion } from 'framer-motion';
import GoogleSignInButton from './GoogleSignInButton';
import WelcomePreferencesModal from './WelcomePreferencesModal';
import { api } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { useTrip } from '../../context/TripContext';

type Status = 'idle' | 'loading' | 'error';

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const { trip, resetTrip } = useTrip();
  const [showPassword, setShowPassword] = useState(false);
  const [status, setStatus] = useState<Status>('idle');
  const [apiMessage, setApiMessage] = useState('');
  const [googleError, setGoogleError] = useState('');
  const [form, setForm] = useState({ email: '', password: '', remember: false });
  const [showWelcome, setShowWelcome] = useState(false);

  const update = (field: string, value: string | boolean) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus('loading');
    setApiMessage('');
    try {
      const res = await api.auth.login(form.email.trim(), form.password);
      if (res.token) {
        const isAdmin = res.is_admin ?? false;
        login(res.token, form.remember, {
          firstName: res.first_name ?? '',
          lastName: res.last_name ?? '',
          email: res.email ?? '',
          authProvider: 'local',
          preferences: res.preferences,
          isAdmin,
        });

        const fromPath = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname;
        const next = fromPath && fromPath.startsWith('/admin') && isAdmin ? fromPath : '/';

        const submitDraft = (location.state as any)?.submitDraft;
        
        if (submitDraft && trip.planningStyle && trip.tripData) {
          try {
            const draftRes = await api.plan.draftPlan(res.token, {
              planningStyle: trip.planningStyle,
              routingStyle: trip.routingStyle,
              tripData: trip.tripData,
            });
            resetTrip();
            navigate(`/plan/${trip.planningStyle}/${draftRes.trip_id}`, { replace: true });
          } catch (err) {
            console.error('Failed to submit draft post-login', err);
            navigate(next, { replace: true });
          }
        } else if (res.is_new_user) {
          setShowWelcome(true);
        } else {
          navigate(next);
        }
      }
    } catch (err: unknown) {
      setStatus('error');
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setApiMessage(detail || 'Something went wrong. Please try again.');
    }
  };

  return (
    <>
      <div className="min-h-screen flex items-center justify-center px-4 py-12 sm:py-24">
        {/* Ambient glow */}
        <div className="pointer-events-none fixed top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] rounded-full bg-cyan/[0.03] blur-[120px]" />

        <motion.div
          initial={{ opacity: 0, y: 30, filter: 'blur(8px)', willChange: 'transform, opacity, filter' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="relative w-full max-w-md"
        >
          {/* Header */}
          <div className="text-center mb-10">
            <Link to="/" className="inline-flex items-center gap-1.5 text-2xl font-bold text-white mb-6">
              <img src="/logo.png" alt="BonPlan.ai" className="h-15 w-15 object-contain" />
            </Link>
            <h1 className="text-3xl font-bold text-white tracking-tight">
              Welcome back to BonPlan<span className="text-cyan">.</span>ai
            </h1>
            <p className="mt-2 text-sm text-slate/60">Log in to access your trips</p>
          </div>

          {/* Error banner */}
          {(apiMessage || googleError) && (
            <div className="mb-4 rounded-xl px-4 py-3 text-sm text-red-400 text-center">
              {apiMessage || googleError}
            </div>
          )}

          <div className="rounded-2xl border border-white/[0.06] bg-carbon/50 backdrop-blur-sm p-8">
            <GoogleSignInButton text="continue_with" onError={setGoogleError} />

            <div className="relative my-7">
              <div className="h-px bg-gradient-to-r from-cyan via-white/10 to-cyan" />
              <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 px-4 text-xs text-white">or</span>
            </div>

            <form onSubmit={handleSubmit} className="flex flex-col gap-5">
              <div>
                <label htmlFor="email" className="block text-xs font-medium text-white/40 mb-2">
                  Email address <span className="text-red-400">*</span>
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  value={form.email}
                  onChange={(e) => update('email', e.target.value)}
                  placeholder="you@example.com"
                  className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-white placeholder-white/20 outline-none focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20 transition-all duration-200"
                />
              </div>

              <div>
                <label htmlFor="password" className="block text-xs font-medium text-white/40 mb-2">
                  Password <span className="text-red-400">*</span>
                </label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={form.password}
                    onChange={(e) => update('password', e.target.value)}
                    placeholder="Enter your password"
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
              </div>

              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.remember}
                    onChange={(e) => update('remember', e.target.checked)}
                    className="h-4 w-4 rounded border-white/20 bg-white/[0.03] accent-cyan cursor-pointer"
                  />
                  <span className="text-xs text-white/40">Remember me</span>
                </label>
                <Link to="/forgot-password" className="text-xs text-cyan/70 hover:text-cyan transition-colors font-medium">
                  Forgot password?
                </Link>
              </div>

              <button
                type="submit"
                disabled={status === 'loading'}
                className="w-full rounded-xl bg-cyan text-midnight font-bold text-sm py-3.5 hover:shadow-[0_0_25px_rgba(102,252,241,0.3)] transition-all duration-300 cursor-pointer mt-1 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {status === 'loading' ? (
                  <span className="inline-flex items-center gap-2">
                    <span className="h-4 w-4 border-2 border-midnight/40 border-t-midnight rounded-full animate-spin" />
                    Logging in…
                  </span>
                ) : (
                  'Log In'
                )}
              </button>
            </form>
          </div>

          <p className="text-center text-xs text-white/30 mt-8">
            Don't have an account?{' '}
            <Link to="/register" className="text-cyan hover:text-cyan/80 transition-colors font-medium">Sign up</Link>
          </p>
        </motion.div>
      </div>

      <WelcomePreferencesModal
        open={showWelcome}
        onSetup={() => { setShowWelcome(false); navigate('/account/preferences?from=welcome'); }}
        onSkip={() => { setShowWelcome(false); navigate('/'); }}
      />
    </>
  );
}
