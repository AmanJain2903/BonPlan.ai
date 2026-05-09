import { useState, useEffect, useRef } from 'react';
import { Pencil, User, Mail, Phone } from 'lucide-react';
import { motion } from 'framer-motion';
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

  const handleEdit = () => { snapshot.current = { ...form }; setEditing(true); setMessage(''); };
  const handleCancel = () => { setForm(snapshot.current); setEditing(false); setMessage(''); };

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

  const initials = `${form.firstName?.[0] ?? ''}${form.lastName?.[0] ?? ''}`.toUpperCase();

  const inputBase = 'w-full rounded-xl border px-4 py-2.5 text-base sm:text-sm outline-none transition-all duration-200';
  const inputEditable = `${inputBase} border-white/10 bg-white/[0.03] text-white placeholder-white/20 focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20`;
  const inputReadonly = `${inputBase} border-transparent bg-transparent text-white/60 cursor-default px-0`;

  if (status === 'loading') {
    return (
      <div className="max-w-7xl rounded-2xl border border-white/[0.06] bg-carbon/40 backdrop-blur-sm p-8 min-h-[300px] flex items-center justify-center">
        <span className="h-6 w-6 border-2 border-cyan/30 border-t-cyan rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-7xl space-y-5">
      {message && (
        <div className={`rounded-xl px-4 py-3 text-sm font-medium ${
          status === 'success'
            ? 'text-cyan bg-cyan/5 border border-cyan/20'
            : 'text-red-400 bg-red-400/5 border border-red-400/20'
        }`}>
          {message}
        </div>
      )}

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="rounded-2xl border border-white/[0.06] bg-carbon/40 backdrop-blur-sm overflow-hidden"
      >
        {/* Card header */}
        <div className="flex flex-col items-stretch gap-4 px-6 sm:flex-row sm:items-center sm:justify-between sm:px-8 py-5 border-b border-white/[0.05]">
          <div className="flex min-w-0 items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-cyan/10 border border-cyan/15 flex items-center justify-center shrink-0">
              <User size={18} className="text-cyan" />
            </div>
            <div className="min-w-0">
              <h3 className="text-base font-bold text-white tracking-wide">Personal Information</h3>
              <p className="text-xs text-white/40 mt-0.5">Your name, email address, and contact details</p>
            </div>
          </div>
          {!editing && (
            <button
              type="button"
              onClick={handleEdit}
              className="inline-flex w-full shrink-0 items-center justify-center gap-2 rounded-xl border border-white/10 px-4 py-2 text-xs font-semibold text-white/45 hover:text-white hover:border-white/20 hover:bg-white/[0.04] transition-all duration-200 cursor-pointer sm:w-auto"
            >
              <Pencil size={12} />
              Edit Profile
            </button>
          )}
        </div>

        {/* Two-column body */}
        <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr]">
          {/* Left: Identity panel */}
          <div className="flex flex-col items-center justify-center gap-5 px-8 py-10 border-b lg:border-b-0 lg:border-r border-white/[0.05] bg-white/[0.01]">
            <div className="h-20 w-20 rounded-2xl bg-gradient-to-br from-cyan/35 via-cyan/15 to-cyan/5 border border-cyan/20 flex items-center justify-center text-2xl font-bold text-cyan shrink-0">
              {initials || <User size={28} className="text-cyan/50" />}
            </div>
            <div className="text-center space-y-1">
              <p className="text-base font-bold text-white leading-tight">
                {`${form.firstName} ${form.lastName}`.trim() || 'Your Name'}
              </p>
              <p className="text-xs text-white/35 break-all">{form.email}</p>
            </div>
            <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold border ${
              form.authProvider === 'google'
                ? 'bg-blue-400/10 text-blue-400 border-blue-400/20'
                : 'bg-cyan/10 text-cyan border-cyan/20'
            }`}>
              <span className={`h-1.5 w-1.5 rounded-full ${form.authProvider === 'google' ? 'bg-blue-400' : 'bg-cyan'}`} />
              {form.authProvider === 'google' ? 'Google Account' : 'Local Account'}
            </span>
          </div>

          {/* Right: Form fields */}
          <form onSubmit={handleSave} className="px-6 sm:px-10 py-8 space-y-7">
            {/* Personal info */}
            <div>
              <div className="flex items-center gap-2 mb-4">
                <User size={12} className="text-white/22" />
                <p className="text-[10px] font-bold uppercase tracking-[0.13em] text-white/22">Name</p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="firstName" className="block text-xs font-medium text-white/40 mb-1.5">
                    First name{editing && <span className="text-red-400/70 ml-0.5">*</span>}
                  </label>
                  <input
                    id="firstName"
                    type="text"
                    required
                    readOnly={!editing}
                    tabIndex={editing ? 0 : -1}
                    value={form.firstName}
                    onChange={(e) => update('firstName', e.target.value)}
                    placeholder={editing ? 'John' : '—'}
                    className={editing ? inputEditable : inputReadonly}
                  />
                </div>
                <div>
                  <label htmlFor="lastName" className="block text-xs font-medium text-white/40 mb-1.5">
                    Last name{editing && <span className="text-red-400/70 ml-0.5">*</span>}
                  </label>
                  <input
                    id="lastName"
                    type="text"
                    required
                    readOnly={!editing}
                    tabIndex={editing ? 0 : -1}
                    value={form.lastName}
                    onChange={(e) => update('lastName', e.target.value)}
                    placeholder={editing ? 'Doe' : '—'}
                    className={editing ? inputEditable : inputReadonly}
                  />
                </div>
              </div>
            </div>

            <div className="h-px bg-white/[0.04]" />

            {/* Contact */}
            <div>
              <div className="flex items-center gap-2 mb-4">
                <Mail size={12} className="text-white/22" />
                <p className="text-[10px] font-bold uppercase tracking-[0.13em] text-white/22">Contact</p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
                    className={`${inputReadonly} opacity-35 cursor-not-allowed`}
                  />
                  <p className="mt-1.5 text-[10px] text-white/18">Cannot be changed</p>
                </div>

                <div>
                  <label className="block text-xs font-medium text-white/40 mb-1.5">
                    <Phone size={11} className="inline mr-1 opacity-60" />
                    Phone number
                  </label>
                  <div className="grid grid-cols-[100px_1fr] gap-2">
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
            </div>

            {/* Action buttons */}
            {editing && (
              <div className="flex items-center gap-3 pt-2 border-t border-white/[0.05]">
                <button
                  type="submit"
                  disabled={status === 'saving' || !form.firstName.trim() || !form.lastName.trim()}
                  className="inline-flex items-center gap-2 rounded-xl bg-cyan text-midnight font-bold text-sm px-7 py-2.5 hover:shadow-[0_0_25px_rgba(102,252,241,0.25)] transition-all duration-300 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:shadow-none"
                >
                  {status === 'saving' ? (
                    <>
                      <span className="h-4 w-4 border-2 border-midnight/40 border-t-midnight rounded-full animate-spin" />
                      Saving…
                    </>
                  ) : (
                    'Save Changes'
                  )}
                </button>
                <button
                  type="button"
                  onClick={handleCancel}
                  disabled={status === 'saving'}
                  className="rounded-xl border border-white/10 px-6 py-2.5 text-sm font-medium text-white/55 hover:text-white hover:bg-white/[0.05] hover:border-white/18 transition-all cursor-pointer disabled:opacity-40"
                >
                  Cancel
                </button>
              </div>
            )}
          </form>
        </div>
      </motion.div>
    </div>
  );
}
