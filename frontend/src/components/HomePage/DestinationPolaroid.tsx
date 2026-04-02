import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../../api';

interface DestinationPolaroidProps {
  destinations: any[];
  originCity?: string;
}

export default function DestinationPolaroid({
  destinations,
  originCity,
}: DestinationPolaroidProps) {
  const [allImages, setAllImages] = useState<string[][]>([]); // One array of URLs per city
  const [cityIndex, setCityIndex] = useState(0);
  const [imageIndex, setImageIndex] = useState(0);
  const [loading, setLoading] = useState(true);

  // Parse destinations to string names
  const destNames = destinations.map((d: any) => {
    if (typeof d === 'string') return d;
    return d.city || d.state || d.country || 'Unknown Destination';
  });

  useEffect(() => {
    let mounted = true;
    const fetchImages = async () => {
      setLoading(true);
      try {
        const fetchedImageSets = await Promise.all(
          destNames.map(async (name) => {
            if (name === 'Unknown Destination') return [];
            // Use the new plural API to get multiple images
            const urls = await api.places.getDestinationImages(name, 10, 1.5);
            return urls && urls.length > 0 ? urls : [];
          })
        );
        if (mounted) {
          setAllImages(fetchedImageSets);
          setLoading(false);

          // Force background pre-loading of all images to the browser cache
          // This eliminates jitter and white flashes when the rotation occurs.
          fetchedImageSets.forEach(set => {
            set.forEach(url => {
              const img = new Image();
              img.src = url;
            });
          });
        }
      } catch (e) {
        if (mounted) setLoading(false);
      }
    };

    if (destNames.length > 0) {
      fetchImages();
    } else {
      setLoading(false);
    }

    return () => { mounted = false; };
  }, [destinations.length]); // Re-fetch only if destinations count changes, to prevent jitter

  const handlePrev = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCityIndex((prev) => (prev - 1 + allImages.length) % allImages.length);
    setImageIndex(0);
  };

  const handleNext = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCityIndex((prev) => (prev + 1) % allImages.length);
    setImageIndex(0);
  };

  const currentCityImages = allImages[cityIndex] || [];
  const currentImage = currentCityImages[imageIndex];
  const currentName = destNames[cityIndex];
  const hasMultipleCities = allImages.length > 1;

  // Auto-rotate logic: Image every 3s, City every 6s
  useEffect(() => {
    if (loading || allImages.length === 0) return;

    let totalTicks = 0;
    const intervalId = window.setInterval(() => {
      totalTicks++;

      const cityImages = allImages[cityIndex] || [];

      // 1. Every 6s (every 2nd tick), swap city
      if (totalTicks % 2 === 0 && allImages.length > 1) {
        setCityIndex(prev => (prev + 1) % allImages.length);
        setImageIndex(0);
      }
      // 2. Every 3s (every tick), swap image within city
      else if (cityImages.length > 1) {
        setImageIndex(prev => (prev + 1) % cityImages.length);
      }
    }, 3000);

    return () => window.clearInterval(intervalId);
  }, [loading, allImages, cityIndex]); // Reset on city change (automatic or manual)

  return (
    <div className="relative w-full h-40 sm:h-48 rounded-xl overflow-hidden mb-6 bg-midnight/60 border border-white/[0.04]">
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
            key={`${cityIndex}-${imageIndex}`}
            src={currentImage}
            alt={currentName}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 1.2, ease: "easeInOut" }}
            className="absolute inset-0 w-full h-full object-cover brightness-[0.75]"
          />
        )}
      </AnimatePresence>

      {/* Gradient Overlay to darken bottom for text */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent pointer-events-none" />

      {/* Origin Overlay */}
      {originCity && originCity !== 'Unknown Destination' && (
        <div className="absolute top-3 left-3 z-10 pointer-events-none">
          <span className="text-white text-xs font-semibold drop-shadow-md">
            From
          </span>
          <br />
          <span className="text-cyan text-s font-semibold drop-shadow-md">
            {originCity}
          </span>
        </div>
      )}

      {/* Destination Name Overlay with Label Animation */}
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
              {currentName}
            </p>
            {allImages.length > 1 && (
              <span className="text-cyan text-[10px] font-bold uppercase tracking-wider opacity-80 drop-shadow-sm block">
                + {allImages.length - 1} more destinations
              </span>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Navigation Arrows (City Level) */}
      {!loading && hasMultipleCities && (
        <>
          <button
            onClick={handlePrev}
            className="absolute left-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-black/40 hover:bg-black/80 backdrop-blur-sm border border-white/10 flex items-center justify-center text-white/80 hover:text-white transition-all cursor-pointer z-10"
          >
            <ChevronLeft size={16} />
          </button>
          <button
            onClick={handleNext}
            className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-black/40 hover:bg-black/80 backdrop-blur-sm border border-white/10 flex items-center justify-center text-white/80 hover:text-white transition-all cursor-pointer z-10"
          >
            <ChevronRight size={16} />
          </button>

          {/* Pagination dots for cities */}
          <div className="absolute top-3 left-0 right-0 flex justify-center gap-1.5 z-10 pointer-events-none">
            {allImages.map((_, i) => (
              <div
                key={i}
                className={`w-1.5 h-1.5 rounded-full transition-all duration-300 ${i === cityIndex ? 'bg-cyan scale-125 shadow-[0_0_8px_rgba(102,252,241,0.6)]' : 'bg-white/30'}`}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
