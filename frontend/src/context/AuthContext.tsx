import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

type UserInfo = {
  firstName: string;
  lastName: string;
  email: string;
  authProvider?: 'local' | 'google';
  preferences?: any;
};

type AuthState = {
  token: string | null;
  user: UserInfo | null;
  isLoggedIn: boolean;
  login: (token: string, remember: boolean, user?: Partial<UserInfo>) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthState>({
  token: null,
  user: null,
  isLoggedIn: false,
  login: () => {},
  logout: () => {},
});

const USER_KEY = 'user';

function loadUser(): UserInfo | null {
  const raw = localStorage.getItem(USER_KEY) ?? sessionStorage.getItem(USER_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem('token') ?? sessionStorage.getItem('token'),
  );
  const [user, setUser] = useState<UserInfo | null>(loadUser);

  const login = useCallback((newToken: string, remember: boolean, info?: Partial<UserInfo>) => {
    setToken(newToken);
    const userInfo: UserInfo = {
      firstName: info?.firstName ?? '',
      lastName: info?.lastName ?? '',
      email: info?.email ?? '',
      authProvider: info?.authProvider,
      preferences: info?.preferences,
    };
    setUser(userInfo);
    const store = remember ? localStorage : sessionStorage;
    const clear = remember ? sessionStorage : localStorage;
    store.setItem('token', newToken);
    store.setItem(USER_KEY, JSON.stringify(userInfo));
    clear.removeItem('token');
    clear.removeItem(USER_KEY);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    for (const s of [localStorage, sessionStorage]) {
      s.removeItem('token');
      s.removeItem(USER_KEY);
    }
    // remove all the scroll positions
    Object.keys(sessionStorage).forEach(key => {
      if (key.startsWith('scroll-pos-')) {
        sessionStorage.removeItem(key); // Delete it!
      }
    });
  }, []);

  return (
    <AuthContext.Provider value={{ token, user, isLoggedIn: !!token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
