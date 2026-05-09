import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Trash2, ChevronRight, Loader2, Calendar, Users } from 'lucide-react';
import { Plan } from '../../apis/plan';
import { api } from '../../api';
import { useNavigate } from 'react-router-dom';
import { generationManager } from '../SoloPlan/generationManager';

interface DraftCardProps {
  plan: Plan;
  onDelete: (id: string) => void;
}

const formatDate = (dateObj?: any): string | null => {
  if (!dateObj) return null;
  let d: Date;
  if (typeof dateObj === 'string') {
    d = new Date(dateObj);
  } else if (typeof dateObj === 'object' && dateObj.year && dateObj.month && dateObj.day) {
    d = new Date(dateObj.year, dateObj.month - 1, dateObj.day);
  } else {
    return null;
  }
  if (isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
};

export default function DraftCard({ plan, onDelete }: DraftCardProps) {
  const navigate = useNavigate();

  const [allImages, setAllImages] = useState<string[]>([]);
  const [imageIndex, setImageIndex] = useState(0);
  const [imgLoading, setImgLoading] = useState(true);
  const tickOffsetRef = useRef(Math.floor(Math.random() * 2000));

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  const [isGenerating, setIsGenerating] = useState(
    () => generationManager.getSession(plan.id)?.isActive ?? false
  );

  useEffect(() => {
    return generationManager.subscribe(plan.id, (session) => {
      setIsGenerating(session.isActive);
    });
  }, [plan.id]);

  // Parse origin
  const originLoc = plan.origin as any;
  const originCity = originLoc
    ? (typeof originLoc === 'string' ? originLoc : (originLoc.city || originLoc.state || originLoc.country || ''))
    : '';

  // Parse all destinations
  const destArray = plan.destinations || [];
  const allDestCities = destArray.map((d: any) => {
    if (typeof d === 'string') return d;
    return d.city || d.state || d.country || '';
  }).filter(Boolean) as string[];

  // Guests
  const totalAdults = plan.adults || 1;
  const totalChildren = plan.children || 0;
  const guestString = totalAdults === 1 && totalChildren === 0
    ? '1 Adult'
    : totalAdults === 1
      ? `1 Adult · ${totalChildren} Children`
      : totalChildren === 0
        ? `${totalAdults} Adults`
        : `${totalAdults} Adults · ${totalChildren} Children`;

  // Dates
  const start = formatDate(plan.start_date);
  const end = formatDate(plan.end_date);
  const dateDisplay = start && end ? `${start} – ${end}` : 'Dates TBD';

  // Fetch images for all destinations
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
      const detail = err?.response?.data?.detail || err?.message || 'Could not delete draft.';
      setDeleteError(typeof detail === 'string' ? detail : JSON.stringify(detail));
      setDeleting(false);
    }
  };

  const currentImage = allImages[imageIndex];

  return (
    <>
      <div
        className="flex-shrink-0 w-[min(300px,calc(100dvw-32px))] sm:w-[500px] min-h-[230px] sm:min-h-[240px] snap-center group/card relative rounded-2xl border border-white/[0.07] bg-carbon/30 hover:bg-carbon/60 transition-[background-color,border-color,box-shadow] duration-[400ms] cursor-pointer overflow-hidden hover:border-cyan/35 hover:shadow-[0_0_50px_rgba(102,252,241,0.15)]"
        onClick={() => navigate(`/plan/${plan.planning_type}/${plan.id}`)}
      >
        {/* Background rotating image */}
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
          <div className="absolute inset-0 bg-gradient-to-r from-midnight/80 via-midnight/55 to-midnight/80" />
        </div>

        {/* Hover glow */}
        <div className="absolute inset-0 bg-gradient-to-br from-cyan/[0.04] to-transparent opacity-0 group-hover/card:opacity-100 transition-opacity duration-500 z-[1] pointer-events-none" />

        {/* Content */}
        <div className="relative z-10 flex flex-col justify-between h-full min-h-[170px] sm:min-h-[185px] p-5 sm:p-6">

          {/* Top row: label + delete */}
          <div className="flex items-center justify-between mb-6">
            {isGenerating ? (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-cyan/10 border border-cyan/20">
                <motion.span
                  className="w-1.5 h-1.5 rounded-full bg-cyan"
                  animate={{ opacity: [1, 0.3, 1], scale: [1, 0.7, 1] }}
                  transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
                />
                <span className="text-[9px] font-bold uppercase tracking-[0.2em] text-cyan/80 select-none">Generating</span>
              </div>
            ) : (
              <span className="text-[9px] font-bold uppercase tracking-[0.22em] text-white/20 select-none">
                BonPlan · Draft
              </span>
            )}
            <button
              onClick={(e) => { e.stopPropagation(); setShowDeleteModal(true); }}
              className="w-7 h-7 flex items-center justify-center rounded-full border border-red-500/15 bg-red-500/5 text-red-400/35 hover:text-red-400 hover:border-red-400/35 hover:bg-red-400/10 transition-all duration-200 opacity-0 group-hover/card:opacity-100"
              title="Delete draft"
            >
              <Trash2 className="w-3 h-3" />
            </button>
          </div>

          {/* Destinations */}
          <div className="mb-6 min-w-0">
            <div className="flex flex-wrap gap-1.5 mb-1">
              {allDestCities.slice(0, 3).map((city, i) => (
                <span key={i} className="text-sm sm:text-base font-bold text-white truncate max-w-[160px]">
                  {city.split(',')[0]}{i < Math.min(allDestCities.length, 3) - 1 && <span className="text-white/25 mx-1">·</span>}
                </span>
              ))}
              {allDestCities.length > 3 && (
                <span className="text-xs text-cyan/50 font-semibold self-center">+{allDestCities.length - 3} more</span>
              )}
            </div>
            {originCity && (
              <span className="text-[10px] sm:text-xs text-white/35">
                From {originCity.split(',')[0]}
              </span>
            )}
          </div>

          {/* Footer: dates + guests + CTA */}
          <div className="flex items-center justify-between mt-auto">
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1.5 text-[10px] sm:text-xs text-white/50 mb-2">
                <Calendar className="w-3 h-3 text-white/25 flex-shrink-0" />
                <span>{dateDisplay}</span>
              </div>
              <div className="flex items-center gap-1.5 text-[10px] sm:text-xs text-white/50">
                <Users className="w-3 h-3 text-white/25 flex-shrink-0" />
                <span>{guestString}</span>
              </div>
            </div>

            <div className="flex items-center gap-1 text-white/50 group-hover/card:text-cyan transition-colors duration-300 mt-8">
              <span className="text-[12px] uppercase tracking-widest font-bold">{isGenerating ? 'Generating...' : plan.has_events ? 'Resume' : 'Start'}</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </div>
          </div>
        </div>
      </div>

      {/* Delete Modal */}
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
                  <h3 className="text-white font-semibold text-base mb-1">Delete this draft?</h3>
                  <p className="text-white/50 text-sm leading-relaxed">
                    Permanently deletes the draft plan. Cannot be undone.
                  </p>
                </div>
              </div>
              {deleteError && (
                <p className="text-red-400 text-xs mb-4 bg-red-400/5 border border-red-400/20 rounded-lg px-3 py-2">
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
                  {deleting ? 'Deleting…' : 'Delete Draft'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
