import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { GOOGLE_CLIENT_ID } from '../../apis/config';
import WelcomePreferencesModal from './WelcomePreferencesModal';

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential: string }) => void;
            auto_select?: boolean;
          }) => void;
          renderButton: (
            parent: HTMLElement,
            options: {
              theme?: string;
              size?: string;
              text?: string;
              shape?: string;
              width?: number;
              locale?: string;
            },
          ) => void;
        };
      };
    };
  }
}

type Props = {
  text?: 'signin_with' | 'signup_with' | 'continue_with';
  onError?: (message: string) => void;
  onLoading?: (loading: boolean) => void;
};

export default function GoogleSignInButton({ text = 'continue_with', onError, onLoading }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { login } = useAuth();
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [showWelcome, setShowWelcome] = useState(false);

  useEffect(() => {
    const render = () => {
      if (!window.google || !containerRef.current) return;

      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: async (response: { credential: string }) => {
          onLoading?.(true);
          onError?.('');
          try {
            const res = await api.auth.googleLogin(response.credential);
            if (res.token) {
              login(res.token, true, {
                firstName: res.first_name ?? '',
                lastName: res.last_name ?? '',
                email: res.email ?? '',
                authProvider: 'google',
                preferences: res.preferences,
              });

              // Show welcome modal only for first-time registrations (server-driven)
              if (res.is_new_user) {
                setShowWelcome(true);
              } else {
                navigate('/');
              }
            }
          } catch (err: unknown) {
            const detail =
              err && typeof err === 'object' && 'response' in err
                ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
                : undefined;
            onError?.(detail || 'Google sign-in failed. Please try again.');
          } finally {
            onLoading?.(false);
          }
        },
      });

      window.google.accounts.id.renderButton(containerRef.current, {
        theme: 'outline',
        size: 'large',
        text,
        shape: 'circle',
        width: containerRef.current.offsetWidth,
      });

      setReady(true);
    };

    if (window.google) {
      render();
    } else {
      const interval = setInterval(() => {
        if (window.google) {
          clearInterval(interval);
          render();
        }
      }, 100);
      return () => clearInterval(interval);
    }
  }, []);

  return (
    <>
      <div className="w-full">
        <div
          ref={containerRef}
          className={`w-full flex items-center justify-center rounded-xl overflow-hidden transition-opacity duration-300 ${ready ? 'opacity-100' : 'opacity-0'}`}
          style={{ minHeight: 44 }}
        />
        {!ready && (
          <div className="w-full flex items-center justify-center gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm font-medium text-white/40">
            <span className="h-4 w-4 border-2 border-white/20 border-t-white/50 rounded-full animate-spin" />
            Loading Google Sign-In…
          </div>
        )}
      </div>

      <WelcomePreferencesModal
        open={showWelcome}
        onSetup={() => { setShowWelcome(false); navigate('/account/preferences?from=welcome'); }}
        onSkip={() => { setShowWelcome(false); navigate('/'); }}
      />
    </>
  );
}

