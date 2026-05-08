import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { api as planApi } from '../../apis/plan';
import { useAuth } from '../../context/AuthContext';

type Status = 'loading' | 'error';

export default function ShareInvite() {
  const navigate = useNavigate();
  const location = useLocation();
  const { isLoggedIn, token } = useAuth();
  const [status, setStatus] = useState<Status>('loading');
  const [message, setMessage] = useState('Accepting invitation...');

  const inviteToken = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return params.get('token') || '';
  }, [location.search]);
  const inviteAction = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return params.get('action') || 'accept';
  }, [location.search]);

  useEffect(() => {
    if (!inviteToken) {
      setStatus('error');
      setMessage('This invitation link is missing its token.');
      return;
    }
    setMessage(inviteAction === 'elevate' ? 'Approving access request...' : 'Accepting invitation...');

    if (!isLoggedIn) {
      navigate('/login', {
        replace: true,
        state: { from: { pathname: location.pathname, search: location.search } },
      });
      return;
    }

    const accept = async () => {
      try {
        const authToken = token || localStorage.getItem('token') || sessionStorage.getItem('token') || '';
        const res = inviteAction === 'elevate'
          ? await planApi.elevateTripAccess(authToken, inviteToken)
          : await planApi.acceptTripInvitation(authToken, inviteToken);
        if (res.trip_id) {
          navigate(`/plan/${res.planning_type || 'solo'}/${res.trip_id}`, { replace: true });
          return;
        }
        setStatus('error');
        setMessage(res.message || (inviteAction === 'elevate' ? 'The access request could not be approved.' : 'The invitation could not be accepted.'));
      } catch (err: unknown) {
        const detail =
          err && typeof err === 'object' && 'response' in err
            ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
            : undefined;
        setStatus('error');
        setMessage(detail || (inviteAction === 'elevate' ? 'The access request could not be approved.' : 'The invitation could not be accepted.'));
      }
    };

    accept();
  }, [inviteAction, inviteToken, isLoggedIn, location.pathname, location.search, navigate, token]);

  return (
    <div className="min-h-[100svh] flex items-center justify-start sm:justify-center px-4 pt-24 pb-12 sm:py-24">
      <motion.div
        initial={{ opacity: 0, y: 20, filter: 'blur(6px)' }}
        animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-md rounded-2xl border border-white/[0.06] bg-carbon/50 backdrop-blur-sm p-8 text-center"
      >
        <img src="/logo.png" alt="BonPlan.ai" className="h-14 w-14 object-contain mx-auto mb-5" />
        <h1 className="text-2xl font-bold text-white mb-3">
          {inviteAction === 'elevate' ? 'Access Request' : 'Trip Invitation'}
        </h1>
        <p className={status === 'error' ? 'text-sm text-red-400' : 'text-sm text-white/60'}>
          {message}
        </p>
        {status === 'loading' && (
          <div className="mt-6 mx-auto h-8 w-8 rounded-full border-2 border-cyan/30 border-t-cyan animate-spin" />
        )}
        {status === 'error' && (
          <div className="mt-6 flex items-center justify-center gap-3">
            <Link
              to="/login"
              state={{ from: { pathname: location.pathname, search: location.search } }}
              className="rounded-xl border border-cyan/30 px-4 py-2 text-sm font-semibold text-cyan hover:bg-cyan/10 transition-colors"
            >
              Log In
            </Link>
            <Link
              to="/register"
              state={{ from: { pathname: location.pathname, search: location.search } }}
              className="rounded-xl bg-cyan px-4 py-2 text-sm font-bold text-midnight hover:shadow-[0_0_20px_rgba(102,252,241,0.25)] transition-all"
            >
              Sign Up
            </Link>
          </div>
        )}
      </motion.div>
    </div>
  );
}
