import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Trash2, Download, ChevronRight, Loader2, Plane, Users, Eye, Pencil, Radio, CheckCircle } from 'lucide-react';
import { Plan } from '../../apis/plan';
import { api } from '../../api';
import { useNavigate } from 'react-router-dom';

interface BoardingPassCardProps {
  plan: Plan;
  variant?: 'personal' | 'shared';
  onDelete: (id: string) => void;
}

const formatShortDate = (dateObj?: any): string => {
  if (!dateObj) return '—';
  let d: Date;
  if (typeof dateObj === 'string') {
    d = new Date(dateObj);
  } else if (typeof dateObj === 'object' && dateObj.year && dateObj.month && dateObj.day) {
    d = new Date(dateObj.year, dateObj.month - 1, dateObj.day);
  } else {
    return '—';
  }
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
};

// Initials-style code: multi-word → initials ("New York" → "NY"), single word → first 3 chars
const cityCode = (name: string): string => {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return '???';
  if (words.length === 1) return words[0].replace(/[^a-zA-Z]/g, '').substring(0, 3).toUpperCase();
  return words.map(w => w.replace(/[^a-zA-Z]/g, '')[0] || '').join('').substring(0, 3).toUpperCase() || '???';
};

// Inclusive day count: Jun 16 → Jun 20 = 5 days
const computeDays = (start: any, end: any): number | null => {
  const parse = (obj: any): Date | null => {
    if (!obj) return null;
    if (typeof obj === 'string') return new Date(obj);
    if (obj.year && obj.month && obj.day) return new Date(obj.year, obj.month - 1, obj.day);
    return null;
  };
  const s = parse(start);
  const e = parse(end);
  if (!s || !e || isNaN(s.getTime()) || isNaN(e.getTime())) return null;
  return Math.max(1, Math.round((e.getTime() - s.getTime()) / (1000 * 60 * 60 * 24)) + 1);
};

const formatCost = (cost: number | null | undefined): string | null => {
  if (cost == null) return null;
  if (cost >= 1000) return `$ ${(cost / 1000).toFixed(1)}k`;
  return `$ ${Math.round(cost)}`;
};

export default function BoardingPassCard({ plan, variant = 'personal', onDelete }: BoardingPassCardProps) {
  const navigate = useNavigate();
  const isShared = variant === 'shared';
  const isEditor = plan.role === 'shared_editor';

  const [allImages, setAllImages] = useState<string[]>([]);
  const [imageIndex, setImageIndex] = useState(0);
  const [imgLoading, setImgLoading] = useState(true);
  const tickOffsetRef = useRef(Math.floor(Math.random() * 2000));

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const [downloading, setDownloading] = useState(false);

  // Parse origin
  const originLoc = plan.origin as any;
  const originCity = originLoc
    ? (typeof originLoc === 'string' ? originLoc : (originLoc.city || originLoc.state || originLoc.country || 'Origin'))
    : 'Origin';

  // Parse all destinations
  const destArray = plan.destinations || [];
  const allDestCities = destArray.map((d: any) => {
    if (typeof d === 'string') return d;
    return d.city || d.state || d.country || '';
  }).filter(Boolean) as string[];

  const primaryDest = allDestCities[0] || 'Destination';
  const isMultiCity = allDestCities.length > 1;

  // Pax string
  const totalAdults = plan.adults || 1;
  const totalChildren = plan.children || 0;
  const paxString = totalAdults === 1 && totalChildren === 0
    ? '1 Adult'
    : totalChildren === 0
      ? `${totalAdults} Adults`
      : `${totalAdults} + ${totalChildren} Pax`;

  const duration = computeDays(plan.start_date, plan.end_date);
  const startStr = formatShortDate(plan.start_date);
  const endStr = formatShortDate(plan.end_date);
  const costStr = formatCost(plan.cost);
  const tripTitle = plan.itinerary_title?.trim() || '';

  const ownerName = plan.owner
    ? `${plan.owner.first_name || ''} ${plan.owner.last_name || ''}`.trim() || plan.owner.email
    : '';

  // Fetch images for ALL destinations, flatten into single rotation pool
  const destCitiesKey = allDestCities.join(',');
  useEffect(() => {
    let mounted = true;
    const fetchImages = async () => {
      setImgLoading(true);
      try {
        const names = allDestCities.filter(c => c && c !== 'Destination');
        if (names.length === 0) { setImgLoading(false); return; }
        const results = await Promise.all(
          names.map(name => api.places.getDestinationImagesByName(name, 2, 1.5))
        );
        if (mounted) {
          const flat = results.flat().filter(Boolean);
          setAllImages(flat);
          setImageIndex(0);
          setImgLoading(false);
          flat.forEach(url => { const img = new Image(); img.src = url; });
        }
      } catch {
        if (mounted) setImgLoading(false);
      }
    };
    fetchImages();
    return () => { mounted = false; };
  }, [destCitiesKey]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (imgLoading || allImages.length <= 1) return;
    let id: number;
    const start = () => { id = window.setInterval(() => setImageIndex(p => (p + 1) % allImages.length), 3500); };
    const t = window.setTimeout(start, tickOffsetRef.current);
    return () => { window.clearTimeout(t); if (id) window.clearInterval(id); };
  }, [imgLoading, allImages.length]);

  const handleDelete = async () => {
    const token = localStorage.getItem('token') || sessionStorage.getItem('token');
    if (!token) return;
    setDeleting(true);
    setDeleteError('');
    try {
      await api.plan.deletePlan(token, plan.id);
      onDelete(plan.id);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Could not delete trip.';
      setDeleteError(typeof detail === 'string' ? detail : JSON.stringify(detail));
      setDeleting(false);
    }
  };

  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const token = localStorage.getItem('token') || sessionStorage.getItem('token');
    if (!token || downloading) return;
    setDownloading(true);
    try {
      const { blob, filename } = await api.plan.downloadTripItineraryPdf(token, plan.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      // silently fail
    } finally {
      setDownloading(false);
    }
  };

  const currentImage = allImages[imageIndex];

  return (
    <>
      {/* ── Boarding Pass Card ─────────────────────────────────────── */}
      <div
        className="flex-shrink-0 w-[min(360px,calc(100dvw-32px))] sm:w-[700px] min-h-[320px] sm:min-h-[340px] snap-center group/card relative rounded-2xl border border-white/[0.07] bg-carbon/30 hover:bg-carbon/60 transition-[background-color,border-color,box-shadow] duration-[400ms] cursor-pointer overflow-hidden hover:border-cyan/35 hover:shadow-[0_0_50px_rgba(102,252,241,0.15)]"
        onClick={() => navigate(`/plan/${plan.planning_type}/${plan.id}`)}
      >
        {/* Background rotating image — lighter overlay so image shows through */}
        <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
          <AnimatePresence initial={false}>
            {!imgLoading && currentImage && (
              <motion.img
                key={imageIndex}
                src={currentImage}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 2.5, ease: 'easeInOut' }}
                className="absolute inset-0 w-full h-full object-cover blur-[2px] scale-105"
              />
            )}
          </AnimatePresence>
          {/* Lighter gradient so image is visible */}
          <div className="absolute inset-0 bg-gradient-to-r from-midnight/80 via-midnight/55 to-midnight/80" />
        </div>

        {/* Hover accent glow */}
        <div className="absolute inset-0 bg-gradient-to-br from-cyan/[0.04] to-transparent opacity-0 group-hover/card:opacity-100 transition-opacity duration-500 z-[1] pointer-events-none" />

        {/* ── Content layout ─────────────────────────────────── */}
        <div className="relative z-10 flex h-full min-h-[320px] sm:min-h-[340px]">

          {/* ── Left main section ───────────────────────────── */}
          <div className="flex-1 flex flex-col p-5 sm:p-6 min-w-0">

            {/* Header row: brand + status/role badges */}
            <div className="flex items-start justify-between gap-3 mb-4 sm:mb-5 min-w-0">
              <span className="min-w-0 truncate pt-1 text-[9px] font-bold uppercase tracking-[0.22em] text-white/20 select-none">
                {`BonPlan · ${isShared ? 'Shared' : 'Personal'} Pass`}
              </span>
              <div className="flex max-w-[54%] flex-shrink-0 flex-wrap items-center justify-end gap-1.5 sm:max-w-none">
                {plan.status === 'current' && (
                  <span className="inline-flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full border border-emerald-400/40 bg-emerald-400/10 text-emerald-400">
                    <Radio className="w-2.5 h-2.5" />
                    Live
                  </span>
                )}
                {plan.status === 'completed' && (
                  <span className="inline-flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full border border-white/15 bg-white/5 text-white/35">
                    <CheckCircle className="w-2.5 h-2.5" />
                    Done
                  </span>
                )}
                {isShared && (
                  <span className={`inline-flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full border ${
                    isEditor
                      ? 'border-cyan/35 bg-cyan/10 text-cyan'
                      : 'border-white/12 bg-white/5 text-white/45'
                  }`}>
                    {isEditor ? <Pencil className="w-2.5 h-2.5" /> : <Eye className="w-2.5 h-2.5" />}
                    {isEditor ? 'Editor' : 'Viewer'}
                  </span>
                )}
              </div>
            </div>

            {tripTitle && (
              <div className="mb-6 sm:mb-7 min-w-0 max-w-full">
                <div className="mb-1.5 flex items-center gap-2">
                  <span className="h-px w-5 flex-shrink-0 bg-cyan/35" />
                  <span className="text-[8px] font-bold uppercase tracking-[0.24em] text-cyan/45">Trip</span>
                </div>
                <h3
                  className="line-clamp-2 max-w-full break-words text-lg font-black leading-[1.08] tracking-tight text-white/95 [overflow-wrap:anywhere] sm:text-2xl"
                  title={tripTitle}
                >
                  {tripTitle}
                </h3>
              </div>
            )}

            {/* Route: FROM ──✈── TO */}
            <div className="flex items-center gap-3 sm:gap-4 mb-6 sm:mb-7">
              {/* Origin */}
              <div className="flex flex-col min-w-0">
                <span className="text-3xl sm:text-4xl font-black text-white tracking-widest leading-none font-mono">
                  {cityCode(originCity)}
                </span>
                <span className="text-[10px] sm:text-xs text-white/40 truncate max-w-[90px] sm:max-w-[130px] mt-1">
                  {originCity.split(',')[0]}
                </span>
              </div>

              {/* Route line + plane */}
              <div className="flex-1 flex flex-col items-center gap-1 min-w-0">
                <div className="w-full flex items-center gap-1.5">
                  <div className="h-px flex-1 bg-gradient-to-r from-white/10 to-cyan/25" />
                  <Plane className="w-4 h-4 sm:w-5 sm:h-5 text-cyan/50 flex-shrink-0" />
                  <div className="h-px flex-1 bg-gradient-to-r from-cyan/25 to-white/10" />
                </div>
                {/* Multi-city route pills below the line */}
                {isMultiCity && (
                  <div className="flex items-center gap-1 flex-wrap justify-center max-w-full">
                    {allDestCities.slice(0, 3).map((city, i) => (
                      <span key={i} className="text-[8px] text-white/30 border border-white/[0.07] px-1.5 py-0.5 rounded-full truncate max-w-[70px]">
                        {city.split(',')[0]}
                      </span>
                    ))}
                    {allDestCities.length > 3 && (
                      <span className="text-[8px] text-cyan/35">+{allDestCities.length - 3}</span>
                    )}
                  </div>
                )}
              </div>

              {/* Destination(s) */}
              <div className="flex flex-col items-end min-w-0">
                <span className="text-3xl sm:text-4xl font-black text-white tracking-widest leading-none font-mono">
                  {isMultiCity ? 'MUL' : cityCode(primaryDest)}
                </span>
                <span className="text-[10px] sm:text-xs text-white/40 truncate max-w-[90px] sm:max-w-[130px] mt-1 text-right">
                  {isMultiCity
                    ? `${allDestCities.length} destinations`
                    : primaryDest.split(',')[0]}
                </span>
              </div>
            </div>

            {/* Info strip: dates + duration + cost */}
            <div className="flex items-center gap-3 sm:gap-4 mb-6 sm:mb-7 flex-wrap">
              <div className="flex items-center gap-2 text-xs sm:text-sm text-white/55 font-medium">
                <span>{startStr}</span>
                <span className="text-white/20 text-[10px]">→</span>
                <span>{endStr}</span>
              </div>
              {duration && (
                <span className="text-[10px] sm:text-xs font-semibold text-white/35 border border-white/[0.07] px-2 py-0.5 rounded-full">
                  {duration} days
                </span>
              )}
              {costStr && (
                <span className="inline-flex items-center gap-1 text-[10px] sm:text-xs font-semibold text-cyan/60 border border-cyan/15 bg-cyan/5 px-2 py-0.5 rounded-full">
                  {costStr} est.
                </span>
              )}
            </div>

            {/* Footer: pace/budget pills + action buttons */}
            <div className="mt-auto flex items-center justify-between gap-3 min-w-0">
              <div className="flex min-w-0 items-center gap-1.5 flex-wrap">
                {plan.budget && (
                  <span className="max-w-[130px] truncate text-[9px] uppercase tracking-wider text-white/25 border border-white/[0.07] px-2 py-0.5 rounded-full sm:max-w-[180px]">
                    {plan.budget}
                  </span>
                )}
                {plan.pace && (
                  <span className="max-w-[130px] truncate text-[9px] uppercase tracking-wider text-white/25 border border-white/[0.07] px-2 py-0.5 rounded-full sm:max-w-[180px]">
                    {plan.pace}
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                <button
                  onClick={handleDownload}
                  disabled={downloading}
                  className="w-8 h-8 flex items-center justify-center rounded-full border border-cyan/20 bg-cyan/5 text-cyan/50 hover:text-cyan hover:border-cyan/40 hover:bg-cyan/10 transition-all duration-200"
                  title="Download PDF"
                >
                  {downloading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); setShowDeleteModal(true); }}
                  className="w-8 h-8 flex items-center justify-center rounded-full border border-red-500/15 bg-red-500/5 text-red-400/40 hover:text-red-400 hover:border-red-400/35 hover:bg-red-400/10 transition-all duration-200"
                  title="Delete trip"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>

          {/* ── Perforation (desktop only) ──────────────────── */}
          <div className="hidden sm:flex flex-col items-center py-5 flex-shrink-0 pointer-events-none">
            <div className="w-px h-full border-l border-dashed border-white/[0.10]" />
          </div>

          {/* ── Right stub (desktop only) ───────────────────── */}
          <div className="hidden sm:flex w-[155px] flex-col justify-between py-6 px-4 pl-3 flex-shrink-0">
            {/* Destination block */}
            <div className="min-w-0">
              <div className="text-[8px] uppercase tracking-[0.2em] text-white/20 mb-1">
                {isMultiCity ? 'Destinations' : 'To'}
              </div>
              {isMultiCity ? (
                <div className="space-y-0.5">
                  {allDestCities.slice(0, 3).map((city, i) => (
                    <div key={i} className="text-xs font-semibold text-white truncate leading-tight">
                      {city.split(',')[0]}
                    </div>
                  ))}
                  {allDestCities.length > 3 && (
                    <div className="text-[9px] text-white/50">+{allDestCities.length - 3} more</div>
                  )}
                </div>
              ) : (
                <div className="text-sm font-bold text-white leading-tight truncate">
                  {primaryDest.split(',')[0]}
                </div>
              )}
              {isShared && ownerName && (
                <div className="text-[9px] text-white/25 mt-1.5 truncate">by {ownerName}</div>
              )}
            </div>

            {/* Passengers */}
            <div>
              <div className="text-[8px] uppercase tracking-[0.2em] text-white/20 mb-0.5">Passengers</div>
              <div className="flex items-center gap-1 text-xs font-semibold text-white/55 leading-tight">
                <Users className="w-3 h-3 text-white/25 flex-shrink-0" />
                {paxString}
              </div>
            </div>

            {/* Duration */}
            {duration && (
              <div>
                <div className="text-[8px] uppercase tracking-[0.2em] text-white/20 mb-0.5">Duration</div>
                <div className="text-xs font-semibold text-white/55">{duration} Days</div>
              </div>
            )}

            {/* Open CTA */}
            <div className="flex items-center justify-end gap-1 text-white/50 group-hover/card:text-cyan transition-colors duration-300">
              <span className="text-[12px] uppercase tracking-widest font-bold">Open</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </div>
          </div>

        </div>
      </div>

      {/* ── Delete Modal ──────────────────────────────────────────── */}
      <AnimatePresence>
        {showDeleteModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm"
            onClick={(e) => { e.stopPropagation(); if (!deleting) { setShowDeleteModal(false); setDeleteError(''); } }}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 8 }}
              transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
              className="w-full max-w-sm mx-4 rounded-2xl bg-carbon border border-white/[0.08] p-6 shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-start gap-3 mb-5">
                <div className="w-10 h-10 rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Trash2 className="w-5 h-5 text-red-400" />
                </div>
                <div>
                  <h3 className="text-white font-semibold text-base mb-1">Delete this trip?</h3>
                  <p className="text-white/50 text-sm leading-relaxed">
                    Permanently deletes the trip and all itinerary data. Cannot be undone.
                  </p>
                </div>
              </div>
              {deleteError && (
                <p className="text-red-400 text-xs mb-8 bg-red-400/5 border border-red-400/20 rounded-lg px-3 py-2">
                  {deleteError}
                </p>
              )}
              <div className="flex gap-3">
                <button
                  onClick={() => { setShowDeleteModal(false); setDeleteError(''); }}
                  disabled={deleting}
                  className="flex-1 py-2.5 rounded-xl border border-white/10 text-white/60 hover:text-white hover:border-white/20 transition-all text-sm font-medium"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDelete}
                  disabled={deleting}
                  className="flex-1 py-2.5 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 hover:border-red-500/50 transition-all text-sm font-semibold disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {deleting && <Loader2 className="w-4 h-4 animate-spin" />}
                  {deleting ? 'Deleting…' : 'Delete Trip'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
