import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { motion } from 'framer-motion';
import { useAuth } from '../../context/AuthContext';
import { useTrip } from '../../context/TripContext';

// Plan Configurations
import { PLAN_STEPS as activeSteps } from './Plan';

// Import your Step Components
import { Step1PlanningStyle } from './StepComponents/Step1.tsx';
import { Step2RoutingStyle } from './StepComponents/Step2.tsx';
import { Step3Places } from './StepComponents/Step3.tsx';
import { Step4Dates } from './StepComponents/Step4.tsx';
import { Step5BudgetPacing } from './StepComponents/Step5.tsx';
import { Step6TripPreferences } from './StepComponents/Step6.tsx';
import { PlanSummary } from './PlanSummary.tsx';

// API
import { api } from '../../api';

export default function PlanSetup() {
  const { isLoggedIn, user, token } = useAuth();
  const { trip, setTrip, updateTripData } = useTrip();
  const navigate = useNavigate();

  const [hoveredTip, setHoveredTip] = useState<string | null>(null);

  const [currentStepIndex, setCurrentStepIndex] = useState(() => {
    const stepString = sessionStorage.getItem('bonplan.planStepIndex');
    const n = stepString ? Number(stepString) : NaN;
    if (!Number.isFinite(n) || n < 0) return 0;
    // Don't let them jump ahead if they haven't picked a planning style
    if (!trip.planningStyle) return 0;
    // Prevent out-of-bounds if steps change dynamically
    return Math.min(n, activeSteps.length - 1);
  });

  // Persist step position
  useEffect(() => {
    sessionStorage.setItem('bonplan.planStepIndex', String(currentStepIndex));
  }, [currentStepIndex]);

  const commitCurrentStepRef = useRef<null | (() => void)>(null);

  // Clear any previously registered commit when step changes.
  useEffect(() => {
    commitCurrentStepRef.current = null;
  }, [currentStepIndex]);

  // Removed isLoggedIn check to allow unauthenticated users to draft plans

  const name = user?.firstName?.trim() || '';

  // Get the Metadata for the current step!
  const isSummary = currentStepIndex >= activeSteps.length;
  const currentStepMeta = isSummary ? null : activeSteps[currentStepIndex];

  let displayTitle = currentStepMeta?.title || '';
  let displayDescription = currentStepMeta?.description || '';

  if (!name && currentStepMeta) {
    displayTitle = displayTitle.replace(/,\s*\{name\}/g, '').replace(/\{name\}/g, '');
    if (currentStepMeta.id === 'trip-preferences') {
      displayTitle = "Let's set some preferences.";
      displayDescription = "Tell us what you'd like to do on the trip";
    }
  }

  // --- Core Engine Functions ---
  const handleNext = () => {
    setCurrentStepIndex((prev) => prev + 1);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    console.log('trip', trip);
  };

  const handleBack = () => {
    // Commit whatever the current step has in-progress (same as YES, but without navigation)
    commitCurrentStepRef.current?.();
    setCurrentStepIndex((prev) => Math.max(0, prev - 1));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // The Component Mapper
  const renderStepContent = () => {
    if (isSummary) {
      return (
        <PlanSummary
          trip={trip}
          name={name}
          onDraft={async (adults, children) => {
            if (adults !== undefined && children !== undefined) {
              updateTripData({ adults, children });
            }
            if (token) {
              try {
                const response = await api.plan.draftPlan(token, {
                  planningStyle: trip.planningStyle,
                  routingStyle: trip.routingStyle,
                  tripData: { ...trip.tripData, adults, children },
                });
                const tripId = response.trip_id;
                navigate(`/plan/${trip.planningStyle}/${tripId}`, { replace: true });
              } catch (e) {
                console.error('Failed to draft plan API call', e);
                navigate('/', { replace: true });
              }
            } else {
              navigate('/register', { state: { submitDraft: true } });
            }
          }}
        />
      );
    }

    switch (currentStepMeta?.componentKey) {
      case 'planning-style':
        commitCurrentStepRef.current = null;
        return (
          <Step1PlanningStyle
            hoveredTip={hoveredTip}
            planningStyle={trip.planningStyle}
            onTipChange={setHoveredTip}
            onSelect={(val) => {
              setTrip({ planningStyle: val as 'solo' | 'squad' });
              handleNext();
            }}
          />
        );
      case 'routing-style':
        commitCurrentStepRef.current = null;
        return (
          <Step2RoutingStyle
            planningStyle={trip.planningStyle}
            onSelect={(val) => {
              setTrip({ routingStyle: val as 'single-hub' | 'multi-hop' });
              // Also initialize the core tripData draft here!
              // updateTripData({ type: val === 'single-hub' ? 'solo-single' : 'multi-hop' }); 
              handleNext();
            }}
          />
        );
      case 'places':
        return (
          <Step3Places
            onNext={handleNext}
            registerCommit={(fn) => {
              commitCurrentStepRef.current = fn;
            }}
          />
        );
      case 'dates':
        return (
          <Step4Dates
            tripData={trip.tripData}
            updateTripData={updateTripData}
            onNext={handleNext}
            registerCommit={(fn) => {
              commitCurrentStepRef.current = fn;
            }}
          />
        );
      case 'budget-pacing':
        return (
          <Step5BudgetPacing
            tripData={trip.tripData}
            updateTripData={updateTripData}
            onNext={handleNext}
            registerCommit={(fn) => {
              commitCurrentStepRef.current = fn;
            }}
          />
        );
      case 'preferences':
        return (
          <Step6TripPreferences
            tripData={trip.tripData}
            updateTripData={updateTripData}
            onNext={handleNext}
            registerCommit={(fn) => {
              commitCurrentStepRef.current = fn;
            }}
          />
        );
      default:
        return <div className="text-white">Unknown Step Configuration</div>;
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, filter: 'blur(8px)', transition: { duration: 0.3 } }}
      className="min-h-screen relative overflow-hidden pt-[24px] pb-[24px]"
    >

      {/* Back button */}
      {currentStepIndex > 0 && (
        <button
          onClick={handleBack}
          className="absolute top-[94px] z-20 left-6 lg:left-12 xl:left-20 inline-flex items-center gap-1.5 text-sm font-medium text-cyan hover:text-cyan/70 transition-colors cursor-pointer animate-[fade-in_300ms_ease-out]"
        >
          <ArrowLeft size={16} />
          Back
        </button>
      )}

      {/* Main content */}
      <div className="relative z-10 flex flex-col items-center justify-start min-h-screen pt-[120px] px-6">

        {/* Fixed header block driven completely by Plan.ts */}
        {!isSummary && currentStepMeta && (
          <div className="w-full max-w-4xl flex flex-col items-center text-center mb-6">
            <div className="h-6 flex items-center justify-center animate-[fade-in_300ms_ease-out]">
              <span className="text-s font-bold tracking-widest text-white/75 uppercase">
                Step {currentStepMeta.step}
              </span>
            </div>

            {/* Current Trip Setting - PlanningStyle RoutingStyle */}
            {currentStepIndex >= 2 && (
              <div className="flex items-center justify-center w-full">
                {/* Use a 3-column grid so the dot stays perfectly centered */}
                <h5 className="grid grid-cols-[1fr_auto_1fr] items-center justify-items-center gap-3 text-lg sm:text-xl lg:text-2xl font-bold tracking-tight animate-[fade-in_400ms_ease-out] w-full">

                  {/* First half of the gradient text */}
                  <span className="justify-self-end bg-gradient-to-r from-cyan via-[#80fdf6] to-cyan/80 bg-clip-text text-transparent whitespace-nowrap">
                    {trip.planningStyle === 'solo' ? 'Solo Planning' : 'Group Planning'}
                  </span>

                  {/* The perfectly centered geometric dot */}
                  <div className="h-1.5 w-1.5 shrink-0 rounded-full bg-cyan/50 shadow-[0_0_8px_rgba(102,252,241,0.6)]" />

                  {/* Second half of the gradient text */}
                  <span className="justify-self-start bg-gradient-to-r from-cyan/80 via-cyan to-[#80fdf6] bg-clip-text text-transparent whitespace-nowrap">
                    {trip.routingStyle === 'single-hub' ? 'Single Hub' : 'Multi Hop'}
                  </span>

                </h5>
              </div>
            )}

            <div className="mt-3 min-h-[3.25rem] sm:min-h-[4rem] lg:min-h-[4.5rem] flex items-center justify-center w-full">
              <h1
                key={currentStepMeta.id} // Forces animation to re-run on step change
                className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-white tracking-tight animate-[fade-in_400ms_ease-out]"
              >
                {/* This magically splits "Where are we going, {name}?" and styles the name! */}
                {displayTitle.split('{name}').map((part, i, arr) =>
                  i < arr.length - 1 ? (
                    <span key={i}>
                      {part}
                      {name && <span className="text-cyan">{name}</span>}
                    </span>
                  ) : (
                    <span key={i}>{part}</span>
                  )
                )}
              </h1>
            </div>

            <div className="mt-3 h-5 flex items-center justify-center">
              <p className="text-white/40 text-sm animate-[fade-in_500ms_ease-out]" key={`desc-${currentStepMeta.id}`}>
                {displayDescription}
              </p>
            </div>
          </div>
        )}

        {/* Dynamic Component Rendering */}
        {renderStepContent()}

      </div>
    </motion.div>
  );
}