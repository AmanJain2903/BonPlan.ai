import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Mail } from 'lucide-react';
import { motion } from 'framer-motion';
import { api } from '../../api';

type Status = 'idle' | 'loading' | 'success' | 'error';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState<Status>('idle');
  const [message, setMessage] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setStatus('loading');
    setMessage('');
    try {
      const res = await api.auth.forgotPassword(email.trim());
      setStatus('success');
      setMessage(res.message || 'If an account with that email exists, a reset link has been sent.');
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
    <div className="min-h-screen flex items-center justify-center px-4 py-12 sm:py-24">
      <div className="pointer-events-none fixed top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] rounded-full bg-cyan/[0.03] blur-[120px]" />

      <motion.div 
        initial={{ opacity: 0, y: 30, filter: 'blur(8px)', willChange: 'transform, opacity, filter' }}
        animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
        transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        className="relative w-full max-w-md"
      >
        <div className="text-center mb-10">
          <Link to="/" className="inline-flex items-center gap-1.5 text-2xl font-bold text-white mb-6">
            <img src="/logo.png" alt="BonPlan.ai" className="h-15 w-15 object-contain" />
          </Link>
          <h1 className="text-3xl font-bold text-white tracking-tight">
            Reset your password
          </h1>
          <p className="mt-2 text-sm text-slate/60">
            Enter your email and we'll send you a link to reset your password
          </p>
        </div>

        {message && (
          <div className={`mb-4 rounded-xl px-4 py-3 text-sm text-center ${status === 'success'
            ? 'text-cyan bg-cyan/5 border border-cyan/20'
            : 'text-red-400 bg-red-400/5 border border-red-400/20'
            }`}>
            {message}
          </div>
        )}

        {status === 'success' ? (
          <div className="rounded-2xl border border-white/[0.06] bg-carbon/50 backdrop-blur-sm p-8 text-center">
            <div className="mx-auto mb-5 h-14 w-14 rounded-full bg-cyan/10 flex items-center justify-center">
              <Mail size={24} className="text-cyan" />
            </div>
            <p className="text-sm text-white/50 mb-6">
              Check your inbox for a password reset link. The link expires in 15 minutes.
            </p>
          </div>
        ) : (
          <div className="rounded-2xl border border-white/[0.06] bg-carbon/50 backdrop-blur-sm p-8">
            <form onSubmit={handleSubmit} className="flex flex-col gap-5">
              <div>
                <label htmlFor="email" className="block text-xs font-medium text-white/40 mb-2">
                  Email address <span className="text-red-400">*</span>
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-white placeholder-white/20 outline-none focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20 transition-all duration-200"
                />
              </div>

              <button
                type="submit"
                disabled={status === 'loading'}
                className="w-full rounded-xl bg-cyan text-midnight font-bold text-sm py-3.5 hover:shadow-[0_0_25px_rgba(102,252,241,0.3)] transition-all duration-300 cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {status === 'loading' ? (
                  <span className="inline-flex items-center gap-2">
                    <span className="h-4 w-4 border-2 border-midnight/40 border-t-midnight rounded-full animate-spin" />
                    Sending…
                  </span>
                ) : (
                  'Send Reset Link'
                )}
              </button>
            </form>
          </div>
        )}

        <p className="text-center text-xs text-white/30 mt-8">
          <Link to="/login" className="inline-flex items-center gap-1 text-cyan hover:text-cyan/80 transition-colors font-medium">
            <ArrowLeft size={12} />
            Back to login
          </Link>
        </p>
      </motion.div>
    </div>
  );
}
