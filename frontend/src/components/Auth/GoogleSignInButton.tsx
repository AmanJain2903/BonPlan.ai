import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { API_BASE, GOOGLE_CLIENT_ID } from '../../apis/config';
import { consumeGoogleAuthError, storeGoogleAuthState } from './googleAuthStorage';

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback?: (response: { credential: string }) => void;
            login_uri?: string;
            ux_mode?: 'popup' | 'redirect';
            click_listener?: () => void;
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
  const location = useLocation();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const pendingError = consumeGoogleAuthError();
    if (pendingError) {
      onError?.(pendingError);
    }

    const render = () => {
      if (!window.google || !containerRef.current) return;

      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        ux_mode: 'redirect',
        login_uri: `${API_BASE}/api/v1/auth/google/redirect`,
        click_listener: () => {
          onLoading?.(true);
          onError?.('');
          storeGoogleAuthState({
            sourcePath: location.pathname,
            routeState: (location.state as { from?: { pathname?: string; search?: string }; submitDraft?: boolean } | null) ?? null,
            createdAt: Date.now(),
          });
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
  }, [location.pathname, location.state, onError, onLoading, text]);

  return (
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
  );
}
