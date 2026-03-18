import { useState } from 'react';
import { MapPin, PlaneTakeoff, Navigation } from 'lucide-react';
import { useTrip } from '../../../../context/TripContext';
import { GOOGLE_MAPS_API_KEY } from '../../../../apis/config';
import { APILoader, PlacePicker } from '@googlemaps/extended-component-library/react';

type Step3Props = {
  onNext?: () => void;
};

// --- 1. Reusable Google Place Parser ---
const parseGooglePlace = (e: any, onUpdate: (data: any) => void) => {
  const place = e.target?.value;
  
  if (place && place.location) {
    const lat = place.location.lat();
    const lng = place.location.lng();
    const name = place.displayName;
  
    let city = '';
    let state = '';
    let country = '';
    if (place.addressComponents) {
      place.addressComponents.forEach((component: any) => {
        const types = component.types;

        if (types.includes('locality') || types.includes('postal_town')) {
          city = component.longText;
        }
        if (types.includes('administrative_area_level_1')) {
          state = component.shortText; 
        }
        if (types.includes('country')) {
          country = component.longText;
        }
      });
    }
    
    if (!city) {
      city = name;
    }

    onUpdate({ city, state, country, lat, lng });
  }
};

// --- 2. Reusable Location Card Component ---
type LocationCardProps = {
  title: string;
  subtitle: string;
  Icon: any;
  gradientPos: string;
  inputValue: any;
  onPlaceChange: (val: any) => void;
  showMap: boolean;
  animCondition: boolean;
  animKey: string;
  animName: string;
  onAnimEnd: () => void;
};

const LocationCard = ({
  title, subtitle, Icon, gradientPos, inputValue, onPlaceChange, showMap,
  animCondition, animKey, animName, onAnimEnd
}: LocationCardProps) => (
  <div className="group relative rounded-2xl border border-white/[0.08] bg-carbon/40 backdrop-blur-sm p-8 overflow-hidden">
    {/* Background Glow */}
    <div className="pointer-events-none absolute -inset-24 opacity-0 group-hover:opacity-100 transition-opacity duration-300 blur-3xl">
      <div
        className="absolute inset-0"
        style={{ background: `radial-gradient(circle at ${gradientPos}, rgba(102,252,241,0.20), rgba(102,252,241,0) 58%)` }}
      />
    </div>

    {/* Header */}
    <div className="flex items-center gap-3 mb-3">
      <div className="h-11 w-11 rounded-xl bg-cyan/10 border border-cyan/15 flex items-center justify-center">
        <Icon size={18} className="text-cyan" />
      </div>
      <div className="min-w-0">
        <h2 className="text-lg font-bold text-white group-hover:text-cyan transition-colors">
          {title}
        </h2>
        <p className="text-xs text-white/35">
          {subtitle}
        </p>
      </div>
    </div>

    {/* Alternating Plane Animation */}
    <div className="relative mt-3 mb-5 h-16 rounded-xl border border-white/[0.06] bg-white/[0.02] overflow-hidden">
      <div className="absolute inset-0">
        <div className="absolute bottom-4 h-0.5 w-[100%] bg-gradient-to-r from-cyan/0 via-cyan/25 to-cyan/0" />
        <div className="absolute bottom-4 h-0.5 w-[100%] bg-gradient-to-r from-transparent via-white/10 to-transparent" />
        <div className="absolute right-0 top-0 h-full w-24 bg-gradient-to-l from-white/[0.02] to-transparent" />
      </div>
      {animCondition && (
        <PlaneTakeoff
          key={animKey}
          size={18}
          onAnimationEnd={onAnimEnd}
          className="absolute left-10 bottom-10 text-cyan/80 opacity-0"
          style={{ animation: `${animName} 2.8s ease-in-out 1`, animationFillMode: 'both' }}
        />
      )}
    </div>

    {/* Mini Map (Renders when BOTH fields are selected globally) */}
    {showMap && inputValue?.lat != null && inputValue?.lng != null && (
      <div className="relative mb-4 h-[170px] rounded-xl border border-white/[0.06] bg-white/[0.02] overflow-hidden">
        <gmp-map
          center={`${inputValue.lat},${inputValue.lng}`}
          zoom="11"
          map-id="DEMO_MAP_ID"
          style={{ height: '100%', width: '100%' }}
        >
          <gmp-advanced-marker
            position={`${inputValue.lat},${inputValue.lng}`}
            title={inputValue.city}
          />
        </gmp-map>
        <div className="pointer-events-none absolute inset-0 ring-1 ring-white/[0.06]" />
      </div>
    )}

    {/* Google Place Picker */}
    <div className="relative placepicker-shell">
      <PlacePicker
        placeholder="Search for a city or airport"
        className="w-full"
        onPlaceChange={(e: any) => parseGooglePlace(e, onPlaceChange)}
      />
    </div>
  </div>
);


// --- 3. Main Step 3 Component ---
export function SoloSingleStep3Places({ onNext }: Step3Props) {
  const { trip, updateTripData } = useTrip();
  
  const [originInput, setOriginInput] = useState(() => trip.tripData?.origin);
  const [destinationInput, setDestinationInput] = useState(() => trip.tripData?.destination);
  const [lastRunAnimation, setLastRunAnimation] = useState('Landing');
  const [animTick, setAnimTick] = useState(0);

  // Map only shows if both fields have been selected
  const canContinue = Boolean(originInput && destinationInput);

  return (
    <>
      <APILoader 
        apiKey={GOOGLE_MAPS_API_KEY} 
        solutionChannel="GMP_GE_placepicker_v2" 
      />

      <div className="w-full max-w-5xl grid grid-cols-1 md:grid-cols-2 gap-8 animate-[fade-in_400ms_ease-out]">
        
        {/* Origin Card */}
        <LocationCard
          title="Where are we starting from?"
          subtitle="Our base location will be set here"
          Icon={Navigation}
          gradientPos="30% 20%"
          inputValue={originInput}
          onPlaceChange={setOriginInput}
          showMap={canContinue}
          animCondition={lastRunAnimation === 'Landing'}
          animKey={`takeoff-${animTick}`}
          animName="plane-takeoff"
          onAnimEnd={() => {
            setLastRunAnimation('Takeoff');
            setAnimTick((t) => t + 1);
          }}
        />

        {/* Destination Card */}
        <LocationCard
          title="What’s our destination?"
          subtitle="Our destination will be set here"
          Icon={MapPin}
          gradientPos="70% 20%"
          inputValue={destinationInput}
          onPlaceChange={setDestinationInput}
          showMap={canContinue}
          animCondition={lastRunAnimation === 'Takeoff'}
          animKey={`landing-${animTick}`}
          animName="plane-landing"
          onAnimEnd={() => {
            setLastRunAnimation('Landing');
            setAnimTick((t) => t + 1);
          }}
        />

      </div>

      {/* Sticky Yes button at bottom of viewport */}
      {canContinue && (
        // 1. Taller gradient (pt-32) creates a perfectly smooth fade with no harsh lines
        <div className="fixed bottom-0 left-0 w-full z-50 pointer-events-none flex justify-center pb-8 pt-32 bg-gradient-to-t from-black via-black/80 to-transparent">
          
          <div className="pointer-events-auto">
            <div className="flex items-center gap-4 rounded-full px-6 py-3">
              <span className="text-sm text-white/80 text-center pl-2 select-none">
                Are we going from{' '}
                <span className="text-cyan font-semibold">{originInput?.city}</span>{' '}
                to{' '}
                <span className="text-cyan font-semibold">{destinationInput?.city}</span>?
              </span>
              <button
                type="button"
                onClick={() => {
                  updateTripData({
                    type: 'solo-single',
                    origin: originInput,
                    destination: destinationInput,
                  });
                  if (onNext) onNext();
                }}
                className="ml-2 inline-flex items-center justify-center rounded-full bg-cyan text-midnight font-extrabold text-xs px-4 py-2 transition-transform duration-300 hover:scale-105 hover:bg-[#80fdf6] hover:shadow-[0_0_15px_rgba(102,252,241,0.4)] cursor-pointer"
              >
                YES
              </button>
            </div>
          </div>
        </div>
      )}
      {canContinue && <div className="h-16 shrink-0" aria-hidden />}
    </>
  );
}