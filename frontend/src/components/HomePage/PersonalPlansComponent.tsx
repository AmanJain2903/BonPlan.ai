import { useRef, useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { ChevronRight, ChevronLeft, Calendar } from 'lucide-react';
import { Plan } from '../../apis/plan';
import DestinationPolaroid from './DestinationPolaroid';
import { usePersonalPlans } from '../../hooks/useTripFilters';
import { useNavigate } from 'react-router-dom';

interface PersonalPlansComponentProps {
    plans: Plan[];
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

export default function PersonalPlansComponent({ plans }: PersonalPlansComponentProps) {
    const scrollRef = useRef<HTMLDivElement>(null);
    const cardsRef = useRef<(HTMLDivElement | null)[]>([]);
    const [canScrollLeft, setCanScrollLeft] = useState(false);
    const [canScrollRight, setCanScrollRight] = useState(false);
    const [isMobile, setIsMobile] = useState(false);
    const [trackPadding, setTrackPadding] = useState('24px');
    const [isOverflowing, setIsOverflowing] = useState(true);

    const personalPlans = usePersonalPlans(plans);

    const navigate = useNavigate();

    // Layout Engine to perfectly center sparse maps (<3 cards) without `< 0px` clipping heavy overflows
    useEffect(() => {
        const handleLayoutEngine = () => {
            if (typeof window === 'undefined') return;
            const w = window.innerWidth;
            const isMob = w < 1240;

            const cardWidth = w >= 640 ? 380 : 300;
            const gap = 24;
            const cardsCount = personalPlans.length;

            const innerTrackWidth = (cardsCount * cardWidth) + (Math.max(0, cardsCount - 1) * gap) + 1;
            const capacity = isMob ? w : 1240;

            setIsOverflowing(innerTrackWidth > capacity);

            if (isMob) {
                const halfCard = w >= 640 ? 190 : 150;
                setTrackPadding(`calc(50vw - ${halfCard}px)`);
            } else {
                setTrackPadding('24px');
            }
        };

        handleLayoutEngine();
        window.addEventListener('resize', handleLayoutEngine);
        return () => window.removeEventListener('resize', handleLayoutEngine);
    }, [personalPlans.length]);

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

            // 2. Compute 60fps Card Scaling based heavily on genuine rendering viewport overlap intersection!
            const containerLeft = scrollLeft;
            const containerRight = scrollLeft + clientWidth;

            cardsRef.current.forEach((card) => {
                if (!card) return;

                const cardLeft = card.offsetLeft;
                const cardRight = cardLeft + card.offsetWidth;

                // Calculate overlap boundaries physically intersecting exactly what the user can see
                const overlapLeft = Math.max(cardLeft, containerLeft);
                const overlapRight = Math.min(cardRight, containerRight);
                const overlapWidth = Math.max(0, overlapRight - overlapLeft);

                // Native 0.0 to 1.0 overlap percentage representing sheer card availability
                const ratio = overlapWidth / card.offsetWidth;

                // Geometric scale from base 0.85 to strict 1.0 peak
                const scaleTarget = 0.85 + (0.15 * ratio);
                const opacityTarget = 0.4 + (0.6 * ratio);

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
    }, [personalPlans.length]);

    if (!personalPlans || personalPlans.length === 0) return null;

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
            <section id="personal-plans" className="relative py-24 sm:py-32 overflow-hidden">

                {/* Top divider glow */}
                <div className="pointer-events-none absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-px bg-gradient-to-r from-transparent via-cyan/20 to-transparent" />

                {/* Title Container bounded to 7xl */}
                <div className="w-full max-w-7xl mx-auto px-6 lg:px-12 xl:px-20">
                    <div className="text-center">
                        <h2 className="text-3xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-white mb-4">
                            Your Personal Plans
                        </h2>
                        <p className="text-sm font-bold text-cyan uppercase tracking-widest">
                            {personalPlans.length === 1 ? '1 PLAN SAVED' : `${personalPlans.length} PLANS SAVED`}
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

                    {/* Carousel Track: Hardware bounds restricted width completely geometrically forcing arbitrary 4k monitors from rendering illegitimately stretched grids (> 3 main cards). Flex remains 100% symmetrically boxed by justify-between! */}
                    <motion.div
                        initial={{ opacity: 0, y: 40, filter: 'blur(4px)', willChange: 'transform, opacity, filter' }}
                        whileInView={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                        viewport={{ once: true, margin: "-100px" }}
                        transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
                        className="flex-1 overflow-hidden w-full max-w-[1240px] relative transition-[mask-image] duration-300"
                        style={{
                            maskImage: getMaskStyle(),
                            WebkitMaskImage: getMaskStyle()
                        }}
                    >
                        <div
                            ref={scrollRef}
                            className="flex overflow-x-auto snap-x snap-mandatory pt-4 pb-12 hide-scrollbars scroll-smooth"
                            style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
                        >
                            {/* Native flex layout flow. Dynamic JS padding strictly forces mathematical geometrical centering rather than hoping CSS flexbox gets it right on overflows! */}
                            {/* The trailing pseudo-element acts as a mathematical guarantee for Webkit right-padding, forcing explicit layout bounds in the scroll viewer */}
                            <div
                                className={`flex gap-6 w-max min-w-full transition-[padding] duration-300 ${!isOverflowing ? 'justify-center' : ''} mt-16`}
                                style={isOverflowing ? { paddingLeft: trackPadding } : {}}
                            >
                                {personalPlans.map((plan, index) => {
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
                                            // onClick={() => window.location.href = `/plan/${plan.planning_type}/${plan.id}`}
                                            onClick={() => navigate(`/plan/${plan.planning_type}/${plan.id}`)}
                                        >
                                            {/* Background gradient on hover */}
                                            <div className="absolute inset-0 bg-gradient-to-br from-cyan/[0.03] to-transparent opacity-0 group-hover/card:opacity-100 transition-opacity duration-500" />

                                            <div className="relative z-10 flex flex-col h-full">
                                                {/* Polaroid Area (auto-rotates when multiple destinations exist) */}
                                                <DestinationPolaroid
                                                    destinations={plan.destinations || []}
                                                    originCity={originCity}
                                                />

                                                {/* Content below Polaroid */}
                                                <div className="flex flex-col flex-1">

                                                    {/* Badges and Subtitle row */}
                                                    <div className="flex items-center justify-center mb-4">
                                                        <span className="text-[10px] sm:text-xs text-cyan/90 font-medium">
                                                            {guestString}
                                                        </span>
                                                    </div>

                                                    {/* Details (Chip UI) */}
                                                    <div className="flex flex-col gap-3 mb-8 justify-center items-center">
                                                        {/* Dates row */}
                                                        <div className="flex items-center gap-2 text-sm text-white/90 font-medium">
                                                            <Calendar className="w-4 h-4 text-cyan/80 shrink-0" />
                                                            <span>{dateDisplay}</span>
                                                        </div>
                                                    </div>

                                                    {/* Footer Action */}
                                                    <div className="mt-auto flex items-center justify-center border-t border-white/[0.08] pt-5">
                                                        <span className="uppercase text-sm font-medium text-slate/80 transition-colors group-hover/card:text-cyan">
                                                            Resume Plan
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
                                {/* Geometrically secure Safari padding spacer guaranteeing perfectly identically symmetric right offsets globally avoiding padding collapse */}
                                {isOverflowing && (
                                    <div className="flex-shrink-0" style={{ width: `calc(${trackPadding} - 24px)` }} aria-hidden="true" />
                                )}
                            </div>
                        </div>
                    </motion.div>

                    {/* Right Navigation Arrow */}
                    <button
                        onClick={() => scroll('right')}
                        className={`hidden md:flex flex-shrink-0 z-20 items-center justify-center text-cyan hover:text-cyan/90 transition-all duration-[700ms] ease-out hover:scale-[1.3] hover:translate-x-3 active:scale-95 drop-shadow-[0_0_8px_rgba(102,252,241,0.5)] hover:drop-shadow-[0_0_25px_rgba(102,252,241,1)] focus:outline-none group/btn-right ${canScrollRight ? 'opacity-80 hover:opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}
                        aria-label="Scroll right"
                    >
                        <ChevronRight className={`w-12 h-12 transition-transform animate-slide-right group-hover/btn-right:!animate-none`} />
                    </button>
                </div>

                {/* Mobile Swipe Indicator (Fades out seamlessly when hitting scrolling limits) */}
                {isMobile && isOverflowing && (
                    <div className={`md:hidden flex items-center justify-center gap-3 mt-8 transition-opacity duration-700 ${(canScrollLeft || canScrollRight) ? 'opacity-100' : 'opacity-0'}`}>
                        <ChevronLeft size={16} strokeWidth={2.5} className={`text-cyan transition-opacity duration-500 ${canScrollLeft ? 'opacity-100 animate-slide-left' : 'opacity-0'}`} />
                        <span className="text-[11px] uppercase tracking-[0.2em] font-bold text-cyan/70">Swipe</span>
                        <ChevronRight size={16} strokeWidth={2.5} className={`text-cyan transition-opacity duration-500 ${canScrollRight ? 'opacity-100 animate-slide-right' : 'opacity-0'}`} />
                    </div>
                )}

            </section>
        </>
    );
}
