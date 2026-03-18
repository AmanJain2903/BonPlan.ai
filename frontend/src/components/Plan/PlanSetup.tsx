import { useEffect, useState, useMemo } from 'react';
import { Navigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useTrip } from '../../context/TripContext';

// Plan Configurations
import { COMMON_PLAN_STEPS, SOLO_SINGLE_HUB_STEPS } from './Plan';

// Import your Step Components
import { Step1PlanningStyle } from './StepComponents/Step1';
import { Step2RoutingStyle } from './StepComponents/Step2';
import { SoloSingleStep3Places } from './StepComponents/Solo-Single/Step3';
import { SoloSingleStep4Dates } from './StepComponents/Solo-Single/Step4';
import { SoloSingleStep5BudgetPacing } from './StepComponents/Solo-Single/Step5';
import { SoloSingleStep6Conversation } from './StepComponents/Solo-Single/Step6';

export default function PlanSetup() {
  const { isLoggedIn, user } = useAuth();
  const { trip, setTrip, updateTripData } = useTrip();
  
  const [hoveredTip, setHoveredTip] = useState<string | null>(null);

  const activeSteps = useMemo(() => {
    let steps = [...COMMON_PLAN_STEPS];
    
    if (trip.planningStyle === 'solo' && trip.routingStyle === 'single-hub') {
      steps = [...steps, ...SOLO_SINGLE_HUB_STEPS];
    }
    return steps;
  }, [trip.planningStyle, trip.routingStyle]);

  const [currentStepIndex, setCurrentStepIndex] = useState(() => {
    const stepString = sessionStorage.getItem('bonplan.planStepIndex');
    const n = stepString ? Number(stepString) : NaN;
    if (!Number.isFinite(n) || n < 0) return 0;
    // Don't let them jump ahead if they haven't picked a planning style
    if (!trip.planningStyle) return 0; 
    // Prevent out-of-bounds if steps change dynamically
    return Math.min(n, activeSteps.length - 1);
  });

  // Ensure index stays in bounds if activeSteps shrinks (e.g., user goes back and changes a core setting)
  useEffect(() => {
    if (currentStepIndex >= activeSteps.length) {
      setCurrentStepIndex(Math.max(0, activeSteps.length - 1));
    }
  }, [activeSteps.length, currentStepIndex]);

  // Persist step position
  useEffect(() => {
    sessionStorage.setItem('bonplan.planStepIndex', String(currentStepIndex));
  }, [currentStepIndex]);


  if (!isLoggedIn) return <Navigate to="/login" replace />;

  const name = user?.firstName?.trim() || '';
  
  // Get the Metadata for the current step!
  const currentStepMeta = activeSteps[currentStepIndex];

  // --- Core Engine Functions ---
  const handleNext = () => {
    setCurrentStepIndex((prev) => prev + 1);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    console.log('trip', trip);
  };

  const handleBack = () => {
    setCurrentStepIndex((prev) => Math.max(0, prev - 1));
  };

  // The Component Mapper
  // This reads the 'componentKey' from Plan.ts and returns the right UI
  const renderStepContent = () => {
    switch (currentStepMeta.componentKey) {
      case 'planning-style':
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
      case 'solo-single-places':
        return <SoloSingleStep3Places onNext={handleNext} />;
      case 'solo-single-dates':
        return (
          <SoloSingleStep4Dates
            tripData={trip.tripData}
            updateTripData={updateTripData}
            onNext={handleNext}
          />
        );
      case 'solo-single-budget-pacing':
        return (
          <SoloSingleStep5BudgetPacing
            tripData={trip.tripData}
            updateTripData={updateTripData}
            onNext={handleNext}
          />
        );
      case 'solo-single-conversation':
        return (
          <SoloSingleStep6Conversation
            tripData={trip.tripData}
            updateTripData={updateTripData}
            onNext={handleNext}
          />
        );
      default:
        return <div className="text-white">Unknown Step Configuration</div>;
    }
  };

  return (
    <div className="min-h-screen relative overflow-hidden pt-[24px] pb-[24px]">

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
        <div className="w-full max-w-4xl flex flex-col items-center text-center mb-12">
          <div className="h-6 flex items-center justify-center animate-[fade-in_300ms_ease-out]">
            <span className="text-s font-bold tracking-widest text-white/75 uppercase">
              Step {currentStepMeta.step}
            </span>
          </div>

          <div className="mt-3 min-h-[3.25rem] sm:min-h-[4rem] lg:min-h-[4.5rem] flex items-center justify-center w-full">
            <h1
              key={currentStepMeta.id} // Forces animation to re-run on step change
              className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-white tracking-tight animate-[fade-in_400ms_ease-out]"
            >
              {/* This magically splits "Where are we going, {name}?" and styles the name! */}
              {currentStepMeta.title.split('{name}').map((part, i, arr) =>
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
              {currentStepMeta.description}
            </p>
          </div>
        </div>

        {/* Dynamic Component Rendering */}
        {renderStepContent()}

      </div>
    </div>
  );
}