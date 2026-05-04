import { useRef, useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { ChevronRight, ChevronLeft } from 'lucide-react';
import { Plan } from '../../apis/plan';
import BoardingPassCard from './BoardingPassCard';
import { usePersonalPlans, useSharedPlans } from '../../hooks/useTripFilters';

interface PersonalPlansComponentProps {
    plans: Plan[];
    variant?: 'personal' | 'shared';
    onDelete: (id: string) => void;
}

export default function PersonalPlansComponent({ plans, variant = 'personal', onDelete }: PersonalPlansComponentProps) {
    const scrollRef = useRef<HTMLDivElement>(null);
    const cardsRef = useRef<(HTMLDivElement | null)[]>([]);
    const [canScrollLeft, setCanScrollLeft] = useState(false);
    const [canScrollRight, setCanScrollRight] = useState(false);
    const [isMobile, setIsMobile] = useState(false);
    const [trackPadding, setTrackPadding] = useState('24px');
    const [isOverflowing, setIsOverflowing] = useState(true);

    const personalPlans = usePersonalPlans(plans);
    const sharedPlans = useSharedPlans(plans);
    const visiblePlans = variant === 'shared' ? sharedPlans : personalPlans;
    const isShared = variant === 'shared';

    // Boarding pass cards are wider: 700px sm / 360px mobile
    const CARD_SM = 700;
    const CARD_MOB = 360;
    const GAP = 24;

    useEffect(() => {
        const handleLayoutEngine = () => {
            if (typeof window === 'undefined') return;
            const w = window.innerWidth;
            const isMob = w < 1240;

            const cardWidth = w >= 640 ? CARD_SM : CARD_MOB;
            const cardsCount = visiblePlans.length;

            const innerTrackWidth = (cardsCount * cardWidth) + (Math.max(0, cardsCount - 1) * GAP) + 1;
            const capacity = isMob ? w : 1240;

            setIsOverflowing(innerTrackWidth > capacity);

            if (isMob) {
                const halfCard = w >= 640 ? CARD_SM / 2 : CARD_MOB / 2;
                setTrackPadding(`calc(50vw - ${halfCard}px)`);
            } else {
                setTrackPadding('24px');
            }
        };

        handleLayoutEngine();
        window.addEventListener('resize', handleLayoutEngine);
        return () => window.removeEventListener('resize', handleLayoutEngine);
    }, [visiblePlans.length]);

    useEffect(() => {
        const updateCarouselUI = () => {
            const isMob = window.innerWidth < 768;
            setIsMobile(isMob);

            const container = scrollRef.current;
            if (!container) return;

            const { scrollLeft, scrollWidth, clientWidth } = container;

            setCanScrollLeft(scrollLeft > 2);
            setCanScrollRight(scrollLeft + clientWidth < scrollWidth - 2);

            const containerLeft = scrollLeft;
            const containerRight = scrollLeft + clientWidth;

            cardsRef.current.forEach((card) => {
                if (!card) return;

                const cardLeft = card.offsetLeft;
                const cardRight = cardLeft + card.offsetWidth;

                const overlapLeft = Math.max(cardLeft, containerLeft);
                const overlapRight = Math.min(cardRight, containerRight);
                const overlapWidth = Math.max(0, overlapRight - overlapLeft);

                const ratio = overlapWidth / card.offsetWidth;

                const scaleTarget = 0.88 + (0.12 * ratio);
                const opacityTarget = 0.4 + (0.6 * ratio);

                card.style.transform = `scale(${scaleTarget})`;
                card.style.opacity = opacityTarget.toString();
                card.style.transformOrigin = 'center center';
            });
        };

        updateCarouselUI();
        requestAnimationFrame(updateCarouselUI);

        const container = scrollRef.current;
        if (container) container.addEventListener('scroll', updateCarouselUI, { passive: true });
        window.addEventListener('resize', updateCarouselUI);

        return () => {
            if (container) container.removeEventListener('scroll', updateCarouselUI);
            window.removeEventListener('resize', updateCarouselUI);
        };
    }, [visiblePlans.length]);

    if (!visiblePlans || visiblePlans.length === 0) return null;

    const scroll = (direction: 'left' | 'right') => {
        if (scrollRef.current) {
            const cardWidth = window.innerWidth >= 640 ? CARD_SM : CARD_MOB;
            const scrollAmount = (direction === 'left' ? -1 : 1) * (cardWidth + GAP);
            scrollRef.current.scrollBy({ left: scrollAmount, behavior: 'smooth' });
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
            <section id={isShared ? 'shared-plans' : 'personal-plans'} className="relative py-24 sm:py-32 overflow-hidden">

                <div className="pointer-events-none absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-px bg-gradient-to-r from-transparent via-cyan/20 to-transparent" />

                <div className="w-full max-w-7xl mx-auto px-6 lg:px-12 xl:px-20">
                    <div className="text-center">
                        <h2 className="text-3xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-white mb-4">
                            {isShared ? 'Shared With You' : 'Your Personal Plans'}
                        </h2>
                        <p className="text-sm font-bold text-cyan uppercase tracking-widest">
                            {isShared
                                ? (visiblePlans.length === 1 ? '1 SHARED ITINERARY' : `${visiblePlans.length} SHARED ITINERARIES`)
                                : (visiblePlans.length === 1 ? '1 PLAN SAVED' : `${visiblePlans.length} PLANS SAVED`)}
                        </p>
                    </div>
                </div>

                <div className="flex w-full items-center justify-between max-w-[1920px] mx-auto group pl-2 pr-2 sm:pl-8 sm:pr-8">

                    <button
                        onClick={() => scroll('left')}
                        className={`hidden md:flex flex-shrink-0 z-20 items-center justify-center text-cyan hover:text-cyan/90 transition-all duration-[700ms] ease-out hover:scale-[1.3] hover:-translate-x-3 active:scale-95 drop-shadow-[0_0_8px_rgba(102,252,241,0.5)] hover:drop-shadow-[0_0_25px_rgba(102,252,241,1)] focus:outline-none group/btn-left ${canScrollLeft ? 'opacity-80 hover:opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}
                        aria-label="Scroll left"
                    >
                        <ChevronLeft className="w-12 h-12 transition-transform animate-slide-left group-hover/btn-left:!animate-none" />
                    </button>

                    <motion.div
                        initial={{ opacity: 0, y: 40, filter: 'blur(4px)', willChange: 'transform, opacity, filter' }}
                        whileInView={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                        viewport={{ once: true, margin: '-100px' }}
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
                            <div
                                className={`flex gap-6 w-max min-w-full transition-[padding] duration-300 ${!isOverflowing ? 'justify-center' : ''} mt-16`}
                                style={isOverflowing ? { paddingLeft: trackPadding } : {}}
                            >
                                {visiblePlans.map((plan, index) => (
                                    <div
                                        key={plan.id}
                                        ref={(el) => { cardsRef.current[index] = el; }}
                                        data-id={plan.id}
                                    >
                                        <BoardingPassCard
                                            plan={plan}
                                            variant={isShared ? 'shared' : 'personal'}
                                            onDelete={onDelete}
                                        />
                                    </div>
                                ))}
                                {isOverflowing && (
                                    <div className="flex-shrink-0" style={{ width: `calc(${trackPadding} - 24px)` }} aria-hidden="true" />
                                )}
                            </div>
                        </div>
                    </motion.div>

                    <button
                        onClick={() => scroll('right')}
                        className={`hidden md:flex flex-shrink-0 z-20 items-center justify-center text-cyan hover:text-cyan/90 transition-all duration-[700ms] ease-out hover:scale-[1.3] hover:translate-x-3 active:scale-95 drop-shadow-[0_0_8px_rgba(102,252,241,0.5)] hover:drop-shadow-[0_0_25px_rgba(102,252,241,1)] focus:outline-none group/btn-right ${canScrollRight ? 'opacity-80 hover:opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}
                        aria-label="Scroll right"
                    >
                        <ChevronRight className="w-12 h-12 transition-transform animate-slide-right group-hover/btn-right:!animate-none" />
                    </button>
                </div>

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
