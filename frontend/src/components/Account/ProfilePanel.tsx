import { useState, useEffect, useRef } from 'react';
import { Pencil } from 'lucide-react';
import { api } from '../../api';
import { useAuth } from '../../context/AuthContext';
import CountryCodeSelect from '../shared/CountryCodeSelect';

type Status = 'loading' | 'idle' | 'saving' | 'success' | 'error';

type FormData = {
  firstName: string;
  lastName: string;
  email: string;
  countryCode: string;
  phone: string;
  authProvider: string;
};

export default function ProfilePanel() {
  const { token, login } = useAuth();

  const [form, setForm] = useState<FormData>({
    firstName: '',
    lastName: '',
    email: '',
    countryCode: '',
    phone: '',
    authProvider: '',
  });
  const snapshot = useRef<FormData>(form);
  const [editing, setEditing] = useState(false);
  const [status, setStatus] = useState<Status>('loading');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const res = await api.auth.getProfile(token);
        const loaded: FormData = {
          firstName: res.first_name ?? '',
          lastName: res.last_name ?? '',
          email: res.email ?? '',
          countryCode: res.country_code ?? '',
          phone: res.phone ?? '',
          authProvider: res.auth_provider ?? '',
        };
        setForm(loaded);
        snapshot.current = loaded;
        setStatus('idle');
      } catch {
        setStatus('error');
        setMessage('Failed to load profile.');
      }
    })();
  }, [token]);

  useEffect(() => {
    if (!message) return;
    const t = setTimeout(() => { setMessage(''); if (status !== 'idle') setStatus('idle'); }, 3000);
    return () => clearTimeout(t);
  }, [message]);

  const update = (field: string, value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  const handleEdit = () => {
    snapshot.current = { ...form };
    setEditing(true);
    setMessage('');
  };

  const handleCancel = () => {
    setForm(snapshot.current);
    setEditing(false);
    setMessage('');
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !form.firstName.trim() || !form.lastName.trim()) return;
    setStatus('saving');
    setMessage('');
    try {
      const res = await api.auth.updateProfile(
        token,
        form.firstName.trim(),
        form.lastName.trim(),
        form.countryCode || null,
        form.phone.trim() || null,
      );
      const updated = {
        ...form,
        firstName: res.first_name ?? form.firstName,
        lastName: res.last_name ?? form.lastName,
        countryCode: res.country_code ?? form.countryCode,
        phone: res.phone ?? form.phone,
      };
      setForm(updated);
      snapshot.current = updated;
      setEditing(false);
      setStatus('success');
      setMessage(res.message || 'Profile updated.');
      const store = !!localStorage.getItem('token');
      login(token, store, {
        firstName: updated.firstName,
        lastName: updated.lastName,
        email: form.email,
        authProvider: form.authProvider as 'local' | 'google',
      });
    } catch (err: unknown) {
      setStatus('error');
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setMessage(detail || 'Failed to update profile.');
    }
  };

  const inputBase =
    'w-full rounded-xl border px-4 py-2.5 text-sm text-white placeholder-white/20 outline-none transition-all duration-200';
  const inputEditable = `${inputBase} border-white/10 bg-white/[0.03] focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20`;
  const inputReadonly = `${inputBase} border-white/[0.06] bg-transparent cursor-default`;

  if (status === 'loading') {
    return (
      <div className="rounded-2xl border border-white/[0.06] bg-carbon/30 p-8 min-h-[300px] flex items-center justify-center">
        <span className="h-6 w-6 border-2 border-cyan/30 border-t-cyan rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl">
      {message && (
        <div className={`mb-6 rounded-xl px-4 py-3 text-sm ${
          status === 'success' ? 'text-cyan bg-cyan/5 border border-cyan/20' : 'text-red-400 bg-red-400/5 border border-red-400/20'
        }`}>
          {message}
        </div>
      )}

      <form onSubmit={handleSave} className="rounded-2xl border border-white/[0.06] bg-carbon/40 backdrop-blur-sm p-6 sm:p-8 space-y-6">
        {/* Header row: badge + edit button */}
        <div className="flex items-center justify-between">
          <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
            form.authProvider === 'google'
              ? 'bg-blue-400/10 text-blue-400 border border-blue-400/20'
              : 'bg-cyan/10 text-cyan border border-cyan/20'
          }`}>
            <span className={`h-1.5 w-1.5 rounded-full ${form.authProvider === 'google' ? 'bg-blue-400' : 'bg-cyan'}`} />
            {form.authProvider === 'google' ? 'Google Account' : 'Local Account'}
          </span>

          {!editing && (
            <button
              type="button"
              onClick={handleEdit}
              className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs font-medium text-white/60 hover:text-white hover:border-white/20 hover:bg-white/[0.04] transition-all duration-200 cursor-pointer"
            >
              <Pencil size={13} />
              Update Profile
            </button>
          )}
        </div>

        {/* First + Last name */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 gap-4">
          <div>
            <label htmlFor="firstName" className="block text-xs font-medium text-white/40 mb-1.5">
              First name {editing && <span className="text-red-400">*</span>}
            </label>
            <input
              id="firstName"
              type="text"
              required
              readOnly={!editing}
              tabIndex={editing ? 0 : -1}
              value={form.firstName}
              onChange={(e) => update('firstName', e.target.value)}
              placeholder="John"
              className={editing ? inputEditable : inputReadonly}
            />
          </div>
          <div>
            <label htmlFor="lastName" className="block text-xs font-medium text-white/40 mb-1.5">
              Last name {editing && <span className="text-red-400">*</span>}
            </label>
            <input
              id="lastName"
              type="text"
              required
              readOnly={!editing}
              tabIndex={editing ? 0 : -1}
              value={form.lastName}
              onChange={(e) => update('lastName', e.target.value)}
              placeholder="Doe"
              className={editing ? inputEditable : inputReadonly}
            />
          </div>
        </div>

        {/* Email + Phone row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Email (always read-only) */}
          <div>
            <label htmlFor="email" className="block text-xs font-medium text-white/40 mb-1.5">
              Email address
            </label>
            <input
              id="email"
              type="email"
              value={form.email}
              readOnly
              tabIndex={-1}
              className={`${inputReadonly} opacity-50 cursor-not-allowed`}
            />
            <p className="mt-1 text-[11px] text-white/25">Email cannot be changed</p>
          </div>

          {/* Country code + Phone */}
          <div>
            <label className="block text-xs font-medium text-white/40 mb-1.5">
              Phone number
            </label>
            <div className="grid grid-cols-[110px_1fr] gap-2">
              {editing ? (
                <CountryCodeSelect
                  id="countryCode"
                  value={form.countryCode}
                  onChange={(dial) => update('countryCode', dial)}
                />
              ) : (
                <input
                  type="text"
                  readOnly
                  tabIndex={-1}
                  value={form.countryCode || '—'}
                  className={inputReadonly}
                />
              )}
              <input
                id="phone"
                type="tel"
                readOnly={!editing}
                tabIndex={editing ? 0 : -1}
                value={form.phone}
                onChange={(e) => update('phone', e.target.value)}
                placeholder={editing ? '(555) 000-0000' : '—'}
                className={editing ? inputEditable : inputReadonly}
              />
            </div>
          </div>
        </div>

        {/* Action buttons */}
        {editing && (
          <div className="flex items-center gap-3 pt-2">
            <button
              type="submit"
              disabled={status === 'saving' || !form.firstName.trim() || !form.lastName.trim()}
              className="rounded-xl bg-cyan text-midnight font-bold text-sm px-8 py-2.5 hover:shadow-[0_0_25px_rgba(102,252,241,0.3)] transition-all duration-300 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:shadow-none"
            >
              {status === 'saving' ? (
                <span className="inline-flex items-center gap-2">
                  <span className="h-4 w-4 border-2 border-midnight/40 border-t-midnight rounded-full animate-spin" />
                  Saving…
                </span>
              ) : (
                'Save Changes'
              )}
            </button>
            <button
              type="button"
              onClick={handleCancel}
              disabled={status === 'saving'}
              className="rounded-xl border border-white/15 px-6 py-2.5 text-sm font-medium text-white hover:bg-white/[0.06] transition-all cursor-pointer disabled:opacity-40"
            >
              Cancel
            </button>
          </div>
        )}
      </form>
    </div>
  );
}
