const GOOGLE_AUTH_STATE_KEY = 'bonplan.googleAuth.state';
const GOOGLE_AUTH_ERROR_KEY = 'bonplan.googleAuth.error';
const GOOGLE_AUTH_STATE_TTL_MS = 10 * 60 * 1000;

type RouteState = {
  from?: {
    pathname?: string;
    search?: string;
  };
  submitDraft?: boolean;
};

export type StoredGoogleAuthState = {
  sourcePath: string;
  routeState: RouteState | null;
  createdAt: number;
};

export function storeGoogleAuthState(state: StoredGoogleAuthState) {
  sessionStorage.setItem(GOOGLE_AUTH_STATE_KEY, JSON.stringify(state));
}

export function consumeGoogleAuthState(): StoredGoogleAuthState | null {
  const raw = sessionStorage.getItem(GOOGLE_AUTH_STATE_KEY);
  sessionStorage.removeItem(GOOGLE_AUTH_STATE_KEY);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as StoredGoogleAuthState;
    if (
      typeof parsed.sourcePath !== 'string' ||
      typeof parsed.createdAt !== 'number' ||
      Date.now() - parsed.createdAt > GOOGLE_AUTH_STATE_TTL_MS
    ) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function setGoogleAuthError(message: string) {
  sessionStorage.setItem(GOOGLE_AUTH_ERROR_KEY, message);
}

export function consumeGoogleAuthError(): string {
  const message = sessionStorage.getItem(GOOGLE_AUTH_ERROR_KEY) ?? '';
  sessionStorage.removeItem(GOOGLE_AUTH_ERROR_KEY);
  return message;
}
