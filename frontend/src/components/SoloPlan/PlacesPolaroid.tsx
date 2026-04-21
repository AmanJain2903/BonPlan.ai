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
}

interface PlaceEntry {
  placeId: string;
  placeName: string;
}

export default function PlacesPolaroid({ day, variant = 'card' }: PlacesPolaroidProps) {
  const [allImages, setAllImages] = useState<string[][]>([]); // One array of URLs per place
  const [placeIndex, setPlaceIndex] = useState(0);
  const [imageIndices, setImageIndices] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const filteredPlacesRef = useRef<PlaceEntry[]>([]);

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

  const isImageTooDarkOrTooLight = (url: string, darkThreshold = 40, lightThreshold = 200): Promise<boolean> => {
    return new Promise((resolve) => {
      const img = new Image();
      img.crossOrigin = "anonymous"; // CRITICAL for Google/External URLs
      img.src = url;

      img.onload = () => {
        const canvas = document.createElement("canvas");
        const ctx = canvas.getContext("2d");
        if (!ctx) return resolve(false);

        // Draw a tiny version (10x10) to save processing power
        canvas.width = 10;
        canvas.height = 10;
        ctx.drawImage(img, 0, 0, 10, 10);

        const imageData = ctx.getImageData(0, 0, 10, 10).data;
        let totalLuminance = 0;

        for (let i = 0; i < imageData.length; i += 4) {
          const r = imageData[i];
          const g = imageData[i + 1];
          const b = imageData[i + 2];
          // Relative Luminance formula
          totalLuminance += (0.2126 * r + 0.7152 * g + 0.0722 * b);
        }

        const avgLuminance = totalLuminance / (imageData.length / 4);
        resolve(avgLuminance < darkThreshold || avgLuminance > lightThreshold);
      };

      img.onerror = () => resolve(false); // Skip filtering if image fails to load
    });
  };

  useEffect(() => {
    let mounted = true;
    const fetchImages = async () => {
      setLoading(true);
      try {
        const rawImageSets = await Promise.all(
          places.map(async (place) => {
            const urls = await api.places.getDestinationImagesByPlaceId(place.placeId, 10, 1.5);
            // Filter out fallback placeholder images
            const validUrls = (urls || []).filter((url) => url && url !== FALLBACK_IMAGE);
            // Async filter: check brightness for each image in parallel
            const brightnessChecks = await Promise.all(
              validUrls.map((url) => isImageTooDarkOrTooLight(url))
            );
            return validUrls.filter((_, i) => !brightnessChecks[i]);
          })
        );

        if (mounted) {
          // Only keep places that have at least one real image
          const validIndices = rawImageSets
            .map((set, i) => (set.length > 0 ? i : -1))
            .filter((i) => i >= 0);
          const filteredImages = validIndices.map((i) => rawImageSets[i]);
          // Also filter the places list to stay in sync
          const filteredPlaces = validIndices.map((i) => places[i]);

          setAllImages(filteredImages);
          setImageIndices(new Array(filteredImages.length).fill(0));
          setPlaceIndex(0);
          setLoading(false);
          // Update the places ref so names stay in sync
          filteredPlacesRef.current = filteredPlaces;

          // Pre-load all images into browser cache
          filteredImages.forEach((set) => {
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

    if (places.length > 0) {
      fetchImages();
    } else {
      setLoading(false);
      setAllImages([]);
      setImageIndices([]);
    }

    return () => { mounted = false; };
  }, [placeIdsKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // Derived state
  const currentPlaceImages = allImages[placeIndex] || [];
  const currentImageIndex = imageIndices[placeIndex] || 0;
  const currentImage = currentPlaceImages[currentImageIndex];
  const currentName = filteredPlacesRef.current[placeIndex]?.placeName || '';

  // Auto-rotate: image every 3s, place every 6s
  useEffect(() => {
    if (loading || allImages.length === 0) return;

    let totalTicks = 0;
    const intervalId = window.setInterval(() => {
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
    }, 3000);

    return () => window.clearInterval(intervalId);
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
