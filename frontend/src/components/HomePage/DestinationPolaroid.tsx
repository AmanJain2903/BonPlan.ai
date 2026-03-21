import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { api } from '../../api';

interface DestinationPolaroidProps {
  destinations: any[];
  originCity?: string;
}

export default function DestinationPolaroid({ destinations, originCity }: DestinationPolaroidProps) {
  const [images, setImages] = useState<string[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [imageLoaded, setImageLoaded] = useState(false);

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
        const fetchedImages = await Promise.all(
          destNames.map(async (name) => {
            if (name === 'Unknown Destination') return '';
            const url = await api.places.getDestinationImage(name);
            return url;
          })
        );
        if (mounted) {
          setImages(fetchedImages.map(url => url || '')); // Handle fallbacks upstream
          setLoading(false);
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
  }, [destinations]); // Note: re-fetches if destination array ref changes, which is okay on page load

  useEffect(() => {
    setImageLoaded(false);
  }, [currentIndex, images]);

  const handlePrev = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCurrentIndex((prev) => (prev - 1 + images.length) % images.length);
  };

  const handleNext = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCurrentIndex((prev) => (prev + 1) % images.length);
  };

  const currentImage = images[currentIndex];
  const currentName = destNames[currentIndex];
  const hasMultiple = images.length > 1;

  return (
    <div className="relative w-full h-40 sm:h-48 rounded-xl overflow-hidden mb-6 bg-midnight/60 border border-white/[0.04]">
      {/* Skeleton / Loading */}
      {(loading || (currentImage && !imageLoaded)) && (
        <div className="absolute inset-0 flex items-center justify-center bg-carbon/50 z-0">
          <div className="w-6 h-6 border-2 border-cyan/50 border-t-cyan rounded-full animate-spin" />
        </div>
      )}

      {/* Image */}
      {!loading && currentImage && (
        <img
          src={currentImage}
          alt={currentName}
          onLoad={() => setImageLoaded(true)}
          onError={() => setImageLoaded(true)}
          className={`absolute inset-0 w-full h-full object-cover brightness-[0.6] transition-opacity duration-300 ${imageLoaded ? 'opacity-100' : 'opacity-0'}`}
        />
      )}

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

      {/* Destination Name Overlay */}
      <div className="absolute bottom-4 left-4 right-4 text-center pointer-events-none">
        <p className="text-white font-bold text-lg sm:text-xl tracking-wide drop-shadow-md truncate transition-colors group-hover/card:text-cyan">
          {currentName}
        </p>
        {
          hasMultiple && (
            <span className="text-cyan text-xs font-semibold drop-shadow-md">
              +{images.length - 1} more
            </span>
          )
        }
      </div>

      {/* Navigation Arrows */}
      {!loading && hasMultiple && (
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

          {/* Pagination dots for polaroid aesthetics */}
          <div className="absolute top-3 left-0 right-0 flex justify-center gap-1.5 z-10 pointer-events-none">
            {images.map((_, i) => (
              <div
                key={i}
                className={`w-1.5 h-1.5 rounded-full transition-all duration-300 ${i === currentIndex ? 'bg-white scale-125' : 'bg-white/30'}`}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
