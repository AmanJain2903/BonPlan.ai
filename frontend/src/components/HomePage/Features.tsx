import {
  Lock,
  RefreshCw,
  Map,
  Crosshair,
  Users,
  MessageSquare,
  Radio,
  SlidersHorizontal,
} from 'lucide-react';
import type { ComponentType } from 'react';
import type { LucideProps } from 'lucide-react';
import {
  AnchorsVisual,
  ShuffleVisual,
  SwapVisual,
  PacingVisual,
  MultiplayerVisual,
  ConversationalVisual,
  MapVisual,
  ConciergeVisual,
} from './FeatureVisuals';

const features: {
  icon: ComponentType<LucideProps>;
  title: string;
  description: string;
  Visual: ComponentType;
}[] = [
  {
    icon: Lock,
    title: 'Unbreakable Smart Anchors',
    description:
      'Feed the AI your pre-booked flights, non-refundable dinner reservations, or scheduled tours. BonPlan locks these anchors in place as immutable constraints — the AI is strictly prohibited from modifying or deleting them. It intelligently routes the rest of your trip around them, ensuring zero logistical conflicts and accounting for real-world friction like transit, baggage claim, and check-in times.',
    Visual: AnchorsVisual,
  },
  {
    icon: RefreshCw,
    title: 'Dynamic Auto-Shuffling',
    description:
      'Travel plans change. Using an intuitive drag-and-drop timeline, extend, move, or remove any activity and the AI will instantly reshuffle the rest of the day to make the new schedule fit. The time changes are cascaded to subsequent events, transit buffers are recalculated, and the ripple effect is halted right before it collides with any Smart Anchor — prompting you to compress or drop the lowest-priority event.',
    Visual: ShuffleVisual,
  },
  {
    icon: Crosshair,
    title: 'Surgical Activity Swaps',
    description:
      "Don't like a specific museum suggestion? Highlight that single activity and ask the AI to swap it out for a food tour. The agentic loop isolates that exact time window, checks the geographical distance to surrounding events, queries external APIs for a replacement that fits the precise temporal and spatial boundaries, and patches it in — leaving the rest of your meticulously planned day completely untouched.",
    Visual: SwapVisual,
  },
  {
    icon: SlidersHorizontal,
    title: 'Customized Pacing',
    description:
      'Whether you want an aggressively efficient sightseeing blitz, a relaxed vacation with long coffee breaks, or a mix of both — set your Pacing Preference and the AI adapts. It directly controls the minimum rest intervals injected between scheduled events, optimizing travel routes and activity density to match your exact desired rhythm. From "Action-Packed" to "Leisurely," every itinerary feels personally calibrated.',
    Visual: PacingVisual,
  },
  {
    icon: Users,
    title: 'Multiplayer Collaborative Mode',
    description:
      'Planning a group trip is no longer a headache of endless group chat messages and conflicting opinions. Generate a shareable link, invite friends or family to the live canvas, and let them vote on AI-generated activities. The itinerary dynamically updates based on group consensus. Assign Owner, Editor, or Viewer roles so nobody accidentally drags and wrecks the timeline — and even create Split Events for subgroups who want to do different things at the same time.',
    Visual: MultiplayerVisual,
  },
  {
    icon: MessageSquare,
    title: 'Conversational Context',
    description:
      'Speak to BonPlan exactly how you would speak to a human travel agent. Just describe your vibe — "I\'m going to Tokyo for 5 days, I know nothing, make it a mix of big tourist spots and chill evenings" — and the AI tailors the recommendations to perfectly match the context. No forms, no dropdowns. Your words shape the entire itinerary, including dietary restrictions, accessibility needs, and budget constraints.',
    Visual: ConversationalVisual,
  },
  {
    icon: Map,
    title: 'Real-World Grounded',
    description:
      'An AI is only as smart as the reality it understands. BonPlan is directly wired into Google Maps, Google Places, and live travel databases. Every recommendation is verified for exact walking, driving, and transit times. Every restaurant is checked for real operating hours. Every landmark is confirmed open on the day you plan to visit. No hallucinations, no "confidently wrong" suggestions — just schedules that are physically executable.',
    Visual: MapVisual,
  },
  {
    icon: Radio,
    title: 'Real-Time Travel Concierge',
    description:
      "BonPlan doesn't stop working when the itinerary is finalized. Throughout your journey, the agent acts as your live companion — providing a morning summary of today's schedule and weather, real-time traffic routing to your next stop, and instant contingency plans for last-minute disruptions. If your Smart Anchor flight is suddenly delayed by 3 hours, the concierge sends a push notification offering to automatically compress your day to absorb the lost time.",
    Visual: ConciergeVisual,
  },
];

export default function Features() {
  return (
    <section id="features" className="relative px-6 lg:px-12 xl:px-20 py-24 sm:py-32">
      {/* Top divider glow */}
      <div className="pointer-events-none absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-px bg-gradient-to-r from-transparent via-cyan/20 to-transparent" />

      <div className="w-full max-w-7xl mx-auto">
        {/* Section header */}
        <div className="text-center mb-20">
          <h1 className="text-4xl sm:text-6xl lg:text-7xl font-bold tracking-tight text-white">
            How it works
          </h1>
          <p className="text-s font-semibold tracking-widest uppercase text-cyan mb-4">
            Built on Smart Anchors
          </p>
        </div>

        {/* Feature list */}
        <div>
          {features.map((feature, i) => {
            const isEven = i % 2 === 0;

            return (
              <div key={feature.title}>
                {/* Divider line */}
                {i > 0 && (
                  <div className="h-px bg-gradient-to-r from-white/10 via-cyan to-white/10" />
                )}

                <div className="group py-12 sm:py-16 lg:py-20">
                  {/* Two-column layout: text + visual, alternating sides */}
                  <div className={`flex flex-col lg:flex-row items-center gap-10 lg:gap-16 ${!isEven ? 'lg:flex-row-reverse' : ''}`}>
                    {/* Text side */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-4 mb-5">
                        <div className="flex items-center justify-center w-12 h-12 rounded-lg bg-cyan/[0.08] border border-cyan/15 group-hover:border-cyan/30 group-hover:bg-cyan/[0.12] transition-all duration-300">
                          <feature.icon size={18} className="text-cyan" />
                        </div>
                        <h3 className="text-2xl sm:text-3xl font-semibold text-white tracking-tight group-hover:text-cyan transition-colors duration-300">
                          {feature.title}
                        </h3>
                      </div>
                      <p className="pl-16 text-base sm:text-lg leading-[1.75] text-slate/75 group-hover:text-slate/70 transition-colors duration-300">
                        {feature.description}
                      </p>
                    </div>

                    {/* Visual side */}
                    <div className="w-full lg:w-[340px] xl:w-[400px] shrink-0 rounded-2xl border border-white/[0.06] bg-carbon/40 p-6">
                      <feature.Visual />
                    </div>
                  </div>
                </div>
              </div>
            );
          })}

          {/* Bottom divider */}
          <div className="h-px bg-gradient-to-r from-transparent via-white/[0.07] to-transparent" />
        </div>
      </div>
    </section>
  );
}
