/** Step metadata for the Plan flow.
 *
 *  This file deliberately contains only data – no React components.
 *  `PlanSetup.tsx` is responsible for mapping these step definitions
 *  to concrete step components.
 */

export type PlanOption = {
  id: string;
  title: string;
  description: string;
  helpText?: string;
  choices?: PlanOption[];
};

export type PlanStepMeta = {
  step: number;
  id: string;
  title: string;
  description: string;
  options?: PlanOption[];
  /** Key used by PlanSetup to decide which component to render. */
  componentKey: string;
};

/** Steps that apply to all flows (Solo / Squad, Single / Multi) */
export const PLAN_STEPS: PlanStepMeta[] = [
  {
    step: 1,
    id: 'planning-style',
    title: "Who's planning, {name}?",
    description: "Choose how you'd like to plan your trip - go solo or plan with your group",
    options: [
      {
        id: 'solo',
        title: 'Just Me',
        description: 'Plan your trip solo — full control, your pace, your way',
        helpText:
          'Going with a squad but planning alone? Choose this. You can still share the trip details with your squad later',
      },
      {
        id: 'squad',
        title: 'The Squad',
        description: 'Plan together — everyone gets a say, real-time collaboration',
        helpText:
          'Want a collaborative planning setup? Your squad gets to plan along with you — everyone adds their preferences',
      },
    ],
    componentKey: 'planning-style',
  },
  {
    step: 2,
    id: 'routing-style',
    title: 'What kind of trip are we planning, {name}?',
    description: 'Choose between single and multiple destinations',
    options: [
      {
        id: 'single-hub',
        title: 'Single Hub',
        description: 'One stop, explore around',
      },
      {
        id: 'multi-hop',
        title: 'Multi Hop',
        description: 'Multiple stops, one journey',
      },
    ],
    componentKey: 'routing-style',
  },
  {
    step: 3,
    id: 'source-destination',
    title: "Let's anchor our trip, {name}.",
    description: "Tell us where we're starting and where we're headed",
    options: [],
    componentKey: 'places',
  },
  {
    step: 4,
    id: 'start-end-dates',
    title: "Let's set the timeline, {name}.",
    description: "Tell us when are we traveling",
    options: [],
    componentKey: 'dates',
  },
  {
    step: 5,
    id: 'budget-pacing',
    title: "Let's talk pace and budget, {name}.",
    description: "Tell us your budget and if you want a relaxed getaway or an action-packed adventure",
    options: [
      {
        id: 'pace',
        title: 'Trip Pace',
        description: 'Choose your pace for the trip',
        choices: [
          {
            id: '1',
            title: 'Deep Relax',
            description: 'Slow down and enjoy the journey',
          },
          {
            id: '2',
            title: 'Easygoing',
            description: 'Enjoy the journey at a relaxed pace but don\'t slow down',
          },
          {
            id: '3',
            title: 'Balanced',
            description: 'Enjoy the journey at a moderate pace',
          },
          {
            id: '4',
            title: 'Active Explorer',
            description: 'Actively explore the destination and enjoy the journey',
          },
          {
            id: '5',
            title: 'Action Packed',
            description: 'Explore the destination and enjoy the action-packed experience',
          },
        ],
      },
      {
        id: 'budget',
        title: 'Trip Budget',
        description: 'Choose your budget for the trip',
        choices: [
          {
            id: '1',
            title: 'Shoestring',
            description: 'A budget-friendly trip that won\'t break the bank',
          },
          {
            id: '2',
            title: 'Modest',
            description: 'A budget that allows for a few nice meals and a few drinks',
          },
          {
            id: '3',
            title: 'Comfortable',
            description: 'A comfortable trip to help you relax and enjoy the journey',
          },
          {
            id: '4',
            title: 'Premium',
            description: 'A premium trip to enjoy the destination to the fullest',
          },
          {
            id: '5',
            title: 'Luxury',
            description: 'A luxury trip without thinking about the dollars',
          },
        ],
      }, 
    ],
    componentKey: 'budget-pacing',
  },
  {
    step: 6,
    id: 'conversational-context',
    title: "Let's talk about our trip, {name}.",
    description: "Tell us anything else you want to add to your trip",
    componentKey: 'conversation',
  },
];
