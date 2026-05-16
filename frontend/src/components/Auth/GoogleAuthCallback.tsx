import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { useTrip } from '../../context/TripContext';
import WelcomePreferencesModal from './WelcomePreferencesModal';
import { consumeGoogleAuthState, setGoogleAuthError, type StoredGoogleAuthState } from './googleAuthStorage';

export default function GoogleAuthCallback() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const { trip, resetTrip } = useTrip();
  const pendingStateRef = useRef<StoredGoogleAuthState | null>(null);
  const startedRef = useRef(false);
  const [showWelcome, setShowWelcome] = useState(false);

  useEffect(() => {
    if (startedRef.current) {
      return;
    }
    startedRef.current = true;

    // Consume once here (not in useRef init) so React Strict Mode's double-mount
    // doesn't empty sessionStorage before the real run.
    pendingStateRef.current = consumeGoogleAuthState();

    const redirectBackToAuth = (errorMessage: string) => {
      const pendingState = pendingStateRef.current;
      setGoogleAuthError(errorMessage);
      navigate(pendingState?.sourcePath === '/register' ? '/register' : '/login', {
        replace: true,
        state: pendingState?.routeState ?? undefined,
      });
    };

    const finalizeGoogleLogin = async () => {
      const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ''));
      const error = hashParams.get('error');
      const exchangeToken = hashParams.get('exchange_token');

      if (window.location.hash) {
        window.history.replaceState(null, '', window.location.pathname);
      }

      if (error) {
        redirectBackToAuth(error);
        return;
      }

      if (!exchangeToken) {
        redirectBackToAuth('Google sign-in failed. Please try again.');
        return;
      }

      try {
        const res = await api.auth.completeGoogleLogin(exchangeToken);
        if (!res.token) {
          throw new Error('Missing app token after Google sign-in.');
        }

        const isAdmin = res.is_admin ?? false;
        login(res.token, true, {
          firstName: res.first_name ?? '',
          lastName: res.last_name ?? '',
          email: res.email ?? '',
          authProvider: 'google',
          preferences: res.preferences,
          isAdmin,
        });

        const routeState = pendingStateRef.current?.routeState;
        const from = routeState?.from;
        const fromPath = from?.pathname;
        const fromSearch = from?.search || '';
        const isInviteRedirect = fromPath === '/share-invite';
        const next =
          fromPath && fromPath.startsWith('/admin')
            ? (isAdmin ? `${fromPath}${fromSearch}` : '/')
            : (fromPath && fromPath !== '/login' && fromPath !== '/register' ? `${fromPath}${fromSearch}` : '/');

        // Check both route state (set by click_listener) and the sessionStorage flag
        // (set in PlanSetup before redirect). The flag is the reliable fallback when
        // click_listener doesn't fire or Strict Mode consumed the route state early.
        const hasPendingDraft = sessionStorage.getItem('bonplan.pendingDraft') === 'true';
        sessionStorage.removeItem('bonplan.pendingDraft');

        if ((routeState?.submitDraft || hasPendingDraft) && trip.planningStyle && trip.tripData) {
          try {
            const draftRes = await api.plan.draftPlan(res.token, {
              planningStyle: trip.planningStyle,
              routingStyle: trip.routingStyle,
              tripData: trip.tripData,
            });
            resetTrip();
            navigate(`/plan/${trip.planningStyle}/${draftRes.trip_id}`, { replace: true });
            return;
          } catch {
            navigate(next, { replace: true });
            return;
          }
        }

        if (res.is_new_user && !isInviteRedirect) {
          setShowWelcome(true);
          return;
        }

        navigate(next, { replace: true });
      } catch (err: unknown) {
        const detail =
          err && typeof err === 'object' && 'response' in err
            ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
            : undefined;
        redirectBackToAuth(detail || 'Google sign-in failed. Please try again.');
      }
    };

    void finalizeGoogleLogin();
  }, [login, navigate, resetTrip, trip.planningStyle, trip.routingStyle, trip.tripData]);

  return (
    <>
      <div className="min-h-[100svh] flex items-center justify-start sm:justify-center px-4 pt-24 pb-12 sm:py-24">
        <div className="pointer-events-none fixed top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] rounded-full bg-cyan/[0.03] blur-[120px]" />

        <motion.div
          initial={{ opacity: 0, y: 30, filter: 'blur(8px)', willChange: 'transform, opacity, filter' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="relative w-full max-w-md"
        >
          <div className="text-center mb-10">
            <img src="/logo.png" alt="BonPlan.ai" className="mx-auto h-15 w-15 object-contain mb-6" />
            <h1 className="text-3xl font-bold text-white tracking-tight">
              BonPlan<span className="text-cyan">.</span>ai
            </h1>
          </div>

          <div className="rounded-2xl border border-white/[0.06] bg-carbon/50 backdrop-blur-sm p-8 text-center">
            <div className="mx-auto mb-6 h-10 w-10 border-2 border-cyan/40 border-t-cyan rounded-full animate-spin" />
            <p className="text-white/70">Completing Google sign-in…</p>
          </div>
        </motion.div>
      </div>

      <WelcomePreferencesModal
        open={showWelcome}
        onSetup={() => {
          setShowWelcome(false);
          navigate('/account/preferences?from=welcome', { replace: true });
        }}
        onSkip={() => {
          setShowWelcome(false);
          navigate('/', { replace: true });
        }}
      />
    </>
  );
}
