import { useRef, useState, useEffect } from 'react';
import { ChevronRight, ChevronLeft, Calendar, Wallet, Activity, User, Users } from 'lucide-react';
import { DraftPlan } from '../../apis/planDraft';
import DestinationPolaroid from './DestinationPolaroid';

interface DraftPlansComponentProps {
  plans: DraftPlan[];
}

const formatDate = (dateObj?: any) => {
  if (!dateObj) return null;
  // Handle string fallback
  if (typeof dateObj === 'string') {
    const d = new Date(dateObj);
    if (isNaN(d.getTime())) return null;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  }
  // Handle dictionary format e.g: {"day": 1, "year": 2026, "month": 6, "timezoneId": "Asia/Kolkata"}
  if (typeof dateObj === 'object' && dateObj.year && dateObj.month && dateObj.day) {
    const d = new Date(dateObj.year, dateObj.month - 1, dateObj.day);
    if (isNaN(d.getTime())) return null;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  }
  return null;
};

export default function DraftPlansComponent({ plans }: DraftPlansComponentProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const cardsRef = useRef<(HTMLDivElement | null)[]>([]);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  // Synchronously update masks, arrows, and card scaling bound 1:1 to exact scroll pixels
  useEffect(() => {
    const updateCarouselUI = () => {
      const isMob = window.innerWidth < 768;
      setIsMobile(isMob);

      const container = scrollRef.current;
      if (!container) return;

      const { scrollLeft, scrollWidth, clientWidth } = container;

      // 1. Update Navigation and Masking states
      setCanScrollLeft(scrollLeft > 5);
      setCanScrollRight(Math.ceil(scrollLeft) + clientWidth < scrollWidth - 5);

      // 2. Compute 60fps Card Scaling based on geometric distance from viewport center
      const viewCenter = scrollLeft + clientWidth / 2;

      // Desktop: 3 cards fully sized. Mobile: 1 card fully sized.
      // This establishes a perfect geometrical radius around the center.
      const safeZone = isMob ? 80 : 580;
      const fadeRange = 300; // Distance to reach maximum visual shrink

      cardsRef.current.forEach((card) => {
        if (!card) return;

        const cardLeft = card.offsetLeft;
        const cardCenter = cardLeft + card.offsetWidth / 2;

        // Absolute distance from exact center of the visible rendering viewport
        const distance = Math.abs(viewCenter - cardCenter);

        let scaleTarget = 1.0;
        let opacityTarget = 1.0;

        if (distance > safeZone) {
          const overflow = distance - safeZone;
          const shrinkRatio = Math.min(1, overflow / fadeRange); // Clamed 0.0 to 1.0
          scaleTarget = 1.0 - (0.15 * shrinkRatio); // Scales strictly between 1.0 and 0.85
          opacityTarget = 1.0 - (0.6 * shrinkRatio); // Fades completely down to 40%
        }

        // Apply raw DOM styles for absolute 0-lag 60fps tracking (bypasses React render tick entirely)
        card.style.transform = `scale(${scaleTarget})`;
        card.style.opacity = opacityTarget.toString();
        card.style.transformOrigin = 'center center';
      });
    };

    // Run perfectly on mount, resize, and scroll
    updateCarouselUI();

    // Enforce immediate calculation layout to prevent 0.1ms render flash where sizes are incorrect
    requestAnimationFrame(updateCarouselUI);

    const container = scrollRef.current;
    if (container) container.addEventListener('scroll', updateCarouselUI, { passive: true });
    window.addEventListener('resize', updateCarouselUI);

    return () => {
      if (container) container.removeEventListener('scroll', updateCarouselUI);
      window.removeEventListener('resize', updateCarouselUI);
    };
  }, [plans]);

  if (!plans || plans.length === 0) return null;

  const scroll = (direction: 'left' | 'right') => {
    if (scrollRef.current) {
      const { current } = scrollRef;
      // Scroll by exactly one card width + gap
      const scrollAmount = direction === 'left' ? -404 : 404;
      current.scrollBy({ left: scrollAmount, behavior: 'smooth' });
    }
  };

  const getMaskStyle = () => {
    const fadeDepth = isMobile ? '40px' : '90px';
    if (canScrollLeft && canScrollRight) {
      return `linear-gradient(to right, transparent, black ${fadeDepth}, black calc(100% - ${fadeDepth}), transparent)`;
    } else if (canScrollLeft) {
      return `linear-gradient(to right, transparent, black ${fadeDepth})`;
    } else if (canScrollRight) {
      return `linear-gradient(to left, transparent, black ${fadeDepth})`;
    }
    return 'none';
  };

  const arrowAnimations = `
    @keyframes slide-left {
      0%, 100% { transform: translateX(0); }
      50% { transform: translateX(-6px); }
    }
    @keyframes slide-right {
      0%, 100% { transform: translateX(0); }
      50% { transform: translateX(6px); }
    }
    .animate-slide-left { animation: slide-left 2s ease-in-out infinite; }
    .animate-slide-right { animation: slide-right 2s ease-in-out infinite; }
  `;

  return (
    <>
      <style>{arrowAnimations}</style>
      <section id="draft-plans" className="relative py-24 sm:py-32 overflow-hidden">

        {/* Title Container bounded to 7xl */}
        <div className="w-full max-w-7xl mx-auto px-6 lg:px-12 xl:px-20">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-white mb-4">
              Your Draft Plans
            </h2>
            <p className="text-sm font-bold text-cyan uppercase tracking-widest">
              {plans.length === 1 ? '1 DRAFT SAVED' : `${plans.length} DRAFTS SAVED`}
            </p>
          </div>
        </div>

        {/* Carousel Container logically decoupled from 7xl max-w to fit full edge-to-edge bleed spacing perfectly */}
        <div className="flex w-full items-center justify-between max-w-[1920px] mx-auto group pl-2 pr-2 sm:pl-8 sm:pr-8">

          {/* Left Navigation Arrow */}
          <button
            onClick={() => scroll('left')}
            className={`hidden md:flex flex-shrink-0 z-20 items-center justify-center text-cyan hover:text-cyan/90 transition-all duration-[700ms] ease-out hover:scale-[1.3] hover:-translate-x-3 active:scale-95 drop-shadow-[0_0_8px_rgba(102,252,241,0.5)] hover:drop-shadow-[0_0_25px_rgba(102,252,241,1)] focus:outline-none group/btn-left ${canScrollLeft ? 'opacity-80 hover:opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}
            aria-label="Scroll left"
          >
            {/* The individual icon shakes when idle by using a custom animation snippet bound to the scroll state */}
            {/* group-hover:!animate-none ensures that bounding idle animation stops cleanly when you physically hover to click it */}
            <ChevronLeft className={`w-12 h-12 transition-transform animate-slide-left group-hover/btn-left:!animate-none`} />
          </button>

          {/* Carousel Track: Unbounded width with dynamic safe centering for 1-100 cards. Flex-1 forces it to naturally fill exact space between the two dynamically positioned arrows! */}
          <div
            className="flex-1 overflow-hidden w-full relative transition-[mask-image] duration-300"
            style={{
              maskImage: getMaskStyle(),
              WebkitMaskImage: getMaskStyle()
            }}
          >
            <div
              ref={scrollRef}
              className="flex gap-6 overflow-x-auto snap-x snap-mandatory pt-4 pb-12 hide-scrollbars scroll-smooth px-4 sm:px-12 pt-12"
              style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
            >
              {/* Native flex layout flow. Dynamic JS padding strictly forces mathematical geometrical centering rather than hoping CSS flexbox gets it right on overflows! */}
              {/* The trailing pseudo-element acts as a mathematical guarantee for Webkit right-padding, forcing explicit layout bounds in the scroll viewer */}
              <div className="flex gap-6 w-max min-w-full after:content-[''] after:w-[1px] after:flex-shrink-0">
                {plans.map((plan, index) => {
                  const isGroup = plan.planning_type?.toLowerCase() === 'squad';
                  const totalAdults = plan.adults || 1;
                  const totalChildren = plan.children || 0;
                  const guestString = totalAdults === 1 && totalChildren === 0 ? '1 Adult' : totalAdults === 1 ? `1 Adult • ${totalChildren} Children` : totalChildren === 0 ? `${totalAdults} Adults` : `${totalAdults} Adults • ${totalChildren} Children`;

                  const start = formatDate(plan.start_date);
                  const end = formatDate(plan.end_date);
                  const dateDisplay = start && end ? `${start} - ${end}` : 'Dates TBD';

                  const originLoc = plan.origin as any;
                  const originCity = originLoc ? (typeof originLoc === 'string' ? originLoc : (originLoc.city || originLoc.state || originLoc.country || 'Unknown Destination')) : 'Unknown Destination';

                  return (
                    <div
                      key={plan.id}
                      ref={(el) => { cardsRef.current[index] = el; }}
                      data-id={plan.id}
                      // We remove transform/opacity from Tailwind transitions to lock the CSS exactly 1:1 with the scroll tracker. They only apply safely on standard DOM boundaries.
                      className="flex-shrink-0 w-[300px] sm:w-[380px] snap-center group/card relative rounded-2xl border border-white/[0.06] bg-carbon/40 p-6 sm:p-8 hover:bg-carbon/80 transition-[background-color,border-color,box-shadow] duration-[400ms] flex flex-col cursor-pointer overflow-hidden hover:border-cyan/40 hover:shadow-[0_0_40px_rgba(102,252,241,0.2)]"
                      onClick={() => window.location.href = `/plan/${plan.id}`}
                    >
                      {/* Background gradient on hover */}
                      <div className="absolute inset-0 bg-gradient-to-br from-cyan/[0.03] to-transparent opacity-0 group-hover/card:opacity-100 transition-opacity duration-500" />

                      <div className="relative z-10 flex flex-col h-full">
                        {/* Polaroid Area */}
                        <DestinationPolaroid destinations={plan.destinations || []} originCity={originCity} />

                        {/* Content below Polaroid */}
                        <div className="flex flex-col flex-1">

                          {/* Badges and Subtitle row */}
                          <div className="flex items-center justify-between mb-4">
                            <span className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider font-semibold px-2.5 py-1 rounded-full border bg-cyan/10 text-cyan border-cyan/20">
                              {isGroup ? <Users size={12} /> : <User size={12} />}
                              {isGroup ? 'Squad' : 'Solo'}
                            </span>

                            <div className="flex flex-col items-end sm:flex-row sm:items-center sm:gap-1.5 text-right">
                              <span className="text-[10px] sm:text-xs text-cyan/90 font-medium">
                                {guestString}
                              </span>
                            </div>
                          </div>

                          {/* Details (Chip UI) */}
                          <div className="flex flex-col gap-3 mb-8">
                            {/* Dates row */}
                            <div className="flex items-center gap-2 text-sm text-white/90 font-medium">
                              <Calendar className="w-4 h-4 text-cyan/80 shrink-0" />
                              <span>{dateDisplay}</span>
                            </div>
                          </div>

                          {/* Footer Action */}
                          <div className="mt-auto flex items-center justify-center border-t border-white/[0.08] pt-5">
                            <span className="uppercase text-sm font-medium text-slate/80 transition-colors group-hover/card:text-cyan">
                              Resume Draft
                            </span>
                            <div className="w-8 h-8 flex items-center justify-center transition-colors">
                              <ChevronRight className="w-4 h-4 text-slate transition-colors group-hover/card:text-cyan" />
                            </div>
                          </div>

                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Right Navigation Arrow */}
          <button
            onClick={() => scroll('right')}
            className={`hidden md:flex flex-shrink-0 z-20 items-center justify-center text-cyan hover:text-cyan/90 transition-all duration-[700ms] ease-out hover:scale-[1.3] hover:translate-x-3 active:scale-95 drop-shadow-[0_0_8px_rgba(102,252,241,0.5)] hover:drop-shadow-[0_0_25px_rgba(102,252,241,1)] focus:outline-none group/btn-right ${canScrollRight ? 'opacity-80 hover:opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}
            aria-label="Scroll right"
          >
            <ChevronRight className={`w-12 h-12 transition-transform animate-slide-right group-hover/btn-right:!animate-none`} />
          </button>
        </div>

      </section>
    </>
  );
}
