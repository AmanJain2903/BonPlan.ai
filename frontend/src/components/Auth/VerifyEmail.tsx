import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { api } from '../../api';

type Status = 'idle' | 'loading' | 'success' | 'error';

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const [status, setStatus] = useState<Status>(token ? 'loading' : 'error');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!token) {
      setMessage('Invalid verification link. No token provided.');
      setStatus('error');
      return;
    }
    const verify = async () => {
      try {
        const response = await api.auth.verifyEmail(token);
        setStatus('success');
        setMessage(response.message || 'Email verified successfully.');
      } catch (err: unknown) {
        setStatus('error');
        const detail =
          err && typeof err === 'object' && 'response' in err &&
            typeof (err as { response?: { data?: { detail?: string } } }).response?.data?.detail === 'string'
            ? (err as { response: { data: { detail: string } } }).response.data.detail
            : 'Could not reach the server. Please try again.';
        setMessage(detail);
      }
    };
    verify();
  }, [token]);

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 sm:py-24">
      <div className="pointer-events-none fixed top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] rounded-full bg-cyan/[0.03] blur-[120px]" />
      <motion.div
        initial={{ opacity: 0, y: 30, filter: 'blur(8px)', willChange: 'transform, opacity, filter' }}
        animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
        transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        className="relative w-full max-w-md text-center"
      >
        <Link to="/" className="inline-flex items-center gap-1.5 text-2xl font-bold text-white mb-8">
          <img src="/logo.png" alt="BonPlan.ai" className="h-15 w-15 object-contain" />
        </Link>
        <h1 className="text-3xl font-bold text-white tracking-tight mb-4">BonPlan<span className="text-cyan">.</span>ai</h1>
        <div className="rounded-2xl border border-white/[0.06] bg-carbon/50 backdrop-blur-sm p-8">
          {status === 'loading' && (
            <>
              <div className="mx-auto w-10 h-10 border-2 border-cyan/40 border-t-cyan rounded-full animate-spin mb-6" />
              <p className="text-white/70">Verifying your email…</p>
            </>
          )}
          {(status === 'success' || message === 'Email already verified.') && (
            <>
              <div className="mx-auto w-12 h-12 rounded-full bg-cyan/20 flex items-center justify-center mb-6">
                <svg className="w-6 h-6 text-cyan" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-white mb-2">Email verified</h2>
              <p className="text-slate/70 mb-6">{message}</p>
              <Link
                to="/login"
                className="inline-block rounded-xl bg-cyan text-midnight font-bold text-sm py-3 px-6 hover:shadow-[0_0_25px_rgba(102,252,241,0.3)] transition-all"
              >
                Log in
              </Link>
            </>
          )}
          {status === 'error' && message !== 'Email already verified.' && (
            <>
              <div className="mx-auto w-12 h-12 rounded-full bg-red-400/20 flex items-center justify-center mb-6">
                <svg className="w-6 h-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-white mb-2">Verification failed</h2>
              <p className="text-slate/70 mb-6">{message}</p>
              <Link
                to="/login"
                className="text-cyan hover:text-cyan/80 font-medium text-sm"
              >
                Back to login
              </Link>
            </>
          )}
        </div>
      </motion.div>
    </div>
  );
}
