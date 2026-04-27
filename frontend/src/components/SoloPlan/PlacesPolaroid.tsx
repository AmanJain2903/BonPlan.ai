import { ItineraryDay } from './types';
import { useEffect, useState, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../../api';
import { FALLBACK_IMAGE } from '../../apis/config';

interface PlacesPolaroidProps {
  day: ItineraryDay;
  /**
   * "card"       – used inside DayCard: shows place name overlay, nav arrows, gradient.
   * "background" – used inside ExpandedFrame: just rotating images, no text, low opacity + blur.
   */
  variant?: 'card' | 'background';
  destinations?: string[];
}

interface PlaceEntry {
  placeId: string;
  placeName: string;
}

export default function PlacesPolaroid({ day, variant = 'card', destinations = [] }: PlacesPolaroidProps) {
  const [allImages, setAllImages] = useState<string[][]>([]); // One array of URLs per place
  const [placeIndex, setPlaceIndex] = useState(0);
  const [imageIndices, setImageIndices] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const filteredNamesRef = useRef<string[]>([]);
  // Stable per-instance random phase offset so cards don't all tick in sync
  const tickOffsetRef = useRef(Math.floor(Math.random() * 1500));

  // Extract unique places (by place_id) from qualifying events.
  // DINING/ACTIVITY store data in event.place_details; OTHER in event.other_details.
  const places: PlaceEntry[] = useMemo(() => {
    const seen = new Set<string>();
    const result: PlaceEntry[] = [];
    for (const event of day.events) {
      let details: any = null;
      if (['DINING', 'ACTIVITY'].includes(event.event_type)) {
        details = event.place_details;
      } else if (event.event_type === 'OTHER') {
        details = event.other_details;
      }
      if (details?.place_id && !seen.has(details.place_id)) {
        seen.add(details.place_id);
        result.push({
          placeId: details.place_id,
          placeName: details.place_name || details.event_name || 'Interesting Place',
        });
      }
    }
    return result;
  }, [day.events]);

  // Stable string key — only re-fetch when the actual set of place IDs changes
  const placeIdsKey = useMemo(() => places.map((p) => p.placeId).join(','), [places]);
  const destinationsKey = useMemo(() => destinations.join(','), [destinations]);

  useEffect(() => {
    let mounted = true;
    const fetchImages = async () => {
      setLoading(true);
      try {
        let finalImages: string[][] = [];
        let finalNames: string[] = [];

        if (places.length > 0) {
          const rawImageSets = await Promise.all(
            places.map(async (place) => {
              const urls = await api.places.getDestinationImagesByPlaceId(place.placeId, 2, 1.5);
              // Filter out fallback placeholder images
              const validUrls = (urls || []).filter((url) => url && url !== FALLBACK_IMAGE);
              return validUrls;
            })
          );

          const validIndices = rawImageSets
            .map((set, i) => (set.length > 0 ? i : -1))
            .filter((i) => i >= 0);
          finalImages = validIndices.map((i) => rawImageSets[i]);
          finalNames = validIndices.map((i) => places[i].placeName);
        }

        // Fallback to destinations if no place images were found
        if (finalImages.length === 0 && destinations && destinations.length > 0) {
          const destNames = destinations.map((d: any) => {
            if (typeof d === 'string') return d;
            const destName = (d.city ? `${d.city}` : "") + (d.state ? `, ${d.state}` : "") + (d.country ? `, ${d.country}` : "");
            return destName || 'Unknown Destination';
          });

          const rawImageSets = await Promise.all(
            destNames.map(async (name) => {
              if (name === 'Unknown Destination') return [];
              const urls = await api.places.getDestinationImagesByName(name, 2, 1.5);
              return urls.length > 0 ? urls : [];
            })
          );

          const validIndices = rawImageSets
            .map((set, i) => (set.length > 0 ? i : -1))
            .filter((i) => i >= 0);
          finalImages = validIndices.map((i) => rawImageSets[i]);
          finalNames = validIndices.map((i) => destNames[i]);
        }

        if (mounted) {
          setAllImages(finalImages);
          setImageIndices(new Array(finalImages.length).fill(0));
          setPlaceIndex(0);
          setLoading(false);
          filteredNamesRef.current = finalNames;

          finalImages.forEach((set) => {
            set.forEach((url) => {
              const img = new Image();
              img.src = url;
            });
          });
        }
      } catch (e) {
        if (mounted) setLoading(false);
      }
    };

    fetchImages();

    return () => { mounted = false; };
  }, [placeIdsKey, destinationsKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // Derived state
  const currentPlaceImages = allImages[placeIndex] || [];
  const currentImageIndex = imageIndices[placeIndex] || 0;
  const currentImage = currentPlaceImages[currentImageIndex];
  const currentName = filteredNamesRef.current[placeIndex] || '';

  // Auto-rotate: image every 1.5s, place every 3s
  // tickOffsetRef staggers each card's phase so they don't all tick in sync.
  useEffect(() => {
    if (loading || allImages.length === 0) return;

    let totalTicks = 0;
    let intervalId: number;

    const startInterval = () => {
      intervalId = window.setInterval(() => {
        totalTicks++;

        const placeImages = allImages[placeIndex] || [];

        // Every 6s (every 2nd tick) swap place
        if (totalTicks % 2 === 0 && allImages.length > 1) {
          setImageIndices((prev) => {
            const next = [...prev];
            if (placeImages.length > 1) {
              next[placeIndex] = (next[placeIndex] + 1) % placeImages.length;
            }
            return next;
          });
          setPlaceIndex((prev) => (prev + 1) % allImages.length);
        }
        // Every 3s (every tick) swap image within same place
        else if (placeImages.length > 1) {
          setImageIndices((prev) => {
            const next = [...prev];
            next[placeIndex] = (next[placeIndex] + 1) % placeImages.length;
            return next;
          });
        }
      }, 1500);
    };

    const timeoutId = window.setTimeout(startInterval, tickOffsetRef.current);

    return () => {
      window.clearTimeout(timeoutId);
      if (intervalId) window.clearInterval(intervalId);
    };
  }, [loading, allImages, placeIndex]);

  // ── Background variant: just the rotating image, no overlays ──────────
  if (variant === 'background') {
    const hasImages = !loading && allImages.length > 0 && currentImage;

    return (
      <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden">
        <AnimatePresence initial={false}>
          {hasImages && (
            <motion.img
              key={`${placeIndex}-${currentImageIndex}`}
              src={currentImage}
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.50 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 2, ease: 'easeInOut' }}
              className="absolute inset-0 w-full h-full object-cover blur-xs scale-110"
            />
          )}
        </AnimatePresence>
        {/* Dark overlay — only render when images are present */}
        <AnimatePresence>
          {hasImages && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 1.5, ease: 'easeInOut' }}
              className="absolute inset-0 bg-gradient-to-b from-black/70 via-black/50 to-black/70"
            />
          )}
        </AnimatePresence>
      </div>
    );
  }

  // ── Card variant: full polaroid with name overlay and navigation ──────
  return (
    <div className="relative w-full aspect-3/2 rounded-xl overflow-hidden mb-6 bg-midnight/60 border border-white/[0.04]">
      {/* Skeleton / Initial Loading Only */}
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-carbon/50 z-10">
          <div className="w-6 h-6 border-2 border-cyan/50 border-t-cyan rounded-full animate-spin" />
        </div>
      )}

      {/* Image with Cross-fade Animation */}
      <AnimatePresence initial={false}>
        {!loading && currentImage && (
          <motion.img
            key={`${placeIndex}-${currentImageIndex}`}
            src={currentImage}
            alt={currentName}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 1.2, ease: 'easeInOut' }}
            className="absolute inset-0 w-full h-full object-cover brightness-[0.75]"
          />
        )}
      </AnimatePresence>

      {/* Gradient Overlay */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent pointer-events-none" />

      {/* Place Name Overlay */}
      <div className="absolute bottom-4 left-4 right-4 text-center pointer-events-none overflow-hidden h-14 flex flex-col justify-end">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentName}
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -20, opacity: 0 }}
            transition={{ duration: 0.4 }}
          >
            <p className="text-white font-bold text-lg sm:text-xl tracking-wide drop-shadow-md truncate group-hover/card:text-cyan transition-colors">
              {currentName.split(',')[0]}
            </p>
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
