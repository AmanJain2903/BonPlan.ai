import { useEffect, useRef, useState, type ReactNode } from 'react';
import { MapPin, PlaneTakeoff, Navigation, X } from 'lucide-react';
import { useTrip, type Place } from '../../../context/TripContext';
import { GOOGLE_MAPS_API_KEY } from '../../../apis/config';
import { APILoader, PlacePicker } from '@googlemaps/extended-component-library/react';

// Route building blocks (used for multi-hop connected lines)
import '@googlemaps/extended-component-library/route_building_blocks/route_data_provider.js';
import '@googlemaps/extended-component-library/route_building_blocks/route_polyline.js';

type Step3Props = {
  onNext?: () => void;
  registerCommit?: (fn: () => void) => void;
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
  belowMap?: ReactNode;
  placePickerRef?: any; // <-- NEW
  placePickerKey?: number; // <-- NEW: used to force-remount and clear PlacePicker input
};

const LocationCard = ({
  title, subtitle, Icon, gradientPos, inputValue, onPlaceChange, showMap,
  animCondition, animKey, animName, onAnimEnd, belowMap, placePickerRef, placePickerKey // <-- NEW
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

    {belowMap}

    {/* Google Place Picker */}
    <div className="relative placepicker-shell">
      <PlacePicker
        ref={placePickerRef} 
        key={placePickerKey}
        placeholder="Search for a city or airport"
        className="w-full"
        onPlaceChange={(e: any) => parseGooglePlace(e, onPlaceChange)}
      />
    </div>
  </div>
);

function Step3SingleHub({ onNext, registerCommit }: Step3Props) {
  const { trip, updateTripData } = useTrip();

  const [originInput, setOriginInput] = useState<Place | null>(() => trip.tripData?.origin ?? null);
  const [destinationsInput, setDestinationsInput] = useState<Place[]>(
    () => trip.tripData?.destinations ?? [],
  );

  const [lastRunAnimation, setLastRunAnimation] = useState('Landing');
  const [animTick, setAnimTick] = useState(0);

  // Single-hub UI uses only the first selected destination for display,
  // but we preserve the full list in local state (so switching modes doesn't drop choices).
  const destinationInput = destinationsInput[0] ?? null;
  const canContinue = Boolean(originInput && destinationInput);

  useEffect(() => {
    registerCommit?.(() => {
      if (!canContinue) return;
      updateTripData({
        origin: originInput,
        destinations: destinationsInput.length > 0 ? destinationsInput : null,
      });
    });
  }, [canContinue, destinationsInput, originInput, registerCommit, updateTripData]);

  return (
    <>
      <APILoader apiKey={GOOGLE_MAPS_API_KEY} solutionChannel="GMP_GE_placepicker_v2" />

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
          onPlaceChange={(val: Place) => setDestinationsInput([val])}
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
        <div className="fixed bottom-0 left-0 w-full z-50 pointer-events-none flex justify-center pb-8 pt-32 bg-gradient-to-t from-black via-black/80 to-transparent">
          <div className="pointer-events-auto">
            <div className="flex items-center gap-4 rounded-full px-6 py-3">
              <span className="text-sm text-white/80 text-center pl-2 select-none">
                Are we going from{' '}
                <span className="text-cyan font-semibold">{originInput?.city}</span> to{' '}
                <span className="text-cyan font-semibold">{destinationInput?.city}</span>?
              </span>
              <button
                type="button"
                onClick={() => {
                  updateTripData({
                    origin: originInput,
                    destinations: destinationInput ? [destinationInput] : null,
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

function Step3MultiHop({ onNext, registerCommit }: Step3Props) {
  const { trip, updateTripData } = useTrip();

  const [originInput, setOriginInput] = useState<Place | null>(() => trip.tripData?.origin ?? null);
  const [destinationsInput, setDestinationsInput] = useState<Place[]>(
    () => trip.tripData?.destinations ?? [],
  );

  // Use the exact same animation state logic as SingleHub
  const [lastRunAnimation, setLastRunAnimation] = useState('Landing');
  const [animTick, setAnimTick] = useState(0);

  const mapRef = useRef<any>(null);
  const destPickerRef = useRef<any>(null); // To bind ref if needed
  const [destPickerKey, setDestPickerKey] = useState(0);

  const canContinue = Boolean(originInput && destinationsInput.length > 0);

  useEffect(() => {
    registerCommit?.(() => {
      if (!canContinue) return;
      updateTripData({
        origin: originInput,
        destinations: destinationsInput,
      });
    });
  }, [canContinue, destinationsInput, originInput, registerCommit, updateTripData]);


  const addStop = (place: Place) => {
    setDestinationsInput((prev) => {
      const exists = prev.some(
        (p) =>
          p.lat != null &&
          p.lng != null &&
          place.lat != null &&
          place.lng != null &&
          Math.abs(p.lat - place.lat) < 1e-6 &&
          Math.abs(p.lng - place.lng) < 1e-6,
      );
      if (exists) return prev;
      return [...prev, place];
    });
    // Force-remount the PlacePicker so the textbox is cleared after selection.
    setDestPickerKey((k) => k + 1);
  };

  const removeStop = (index: number) => {
    setDestinationsInput((prev) => prev.filter((_, i) => i !== index));
  };

  // Scale map to perfectly frame only the destination markers
  useEffect(() => {
    const pts = destinationsInput.filter(
      (p): p is Place => p != null && p.lat != null && p.lng != null,
    );

    if (pts.length === 0) return;

    const el = mapRef.current as any;
    const innerMap = el?.innerMap ?? el;

    if (pts.length === 1) {
      // If only 1 destination, zoom to it cleanly like SingleHub
      innerMap?.panTo?.({ lat: pts[0].lat, lng: pts[0].lng });
      innerMap?.setZoom?.(11);
      return;
    }

    const googleObj = (window as any).google;
    const maps = googleObj?.maps;
    if (!maps?.LatLngBounds) return;

    const bounds = new maps.LatLngBounds();
    pts.forEach((p) => bounds.extend({ lat: p.lat as number, lng: p.lng as number }));

    innerMap?.fitBounds?.(bounds);
  }, [destinationsInput]);

  return (
    <>
      <APILoader apiKey={GOOGLE_MAPS_API_KEY} solutionChannel="GMP_GE_placepicker_v2" />

      <div className={`w-full max-w-5xl grid grid-cols-1 md:grid-cols-2 gap-8 animate-[fade-in_400ms_ease-out] ${canContinue ? 'pb-24' : ''}`}>
        
        {/* --- SOURCE CARD --- */}
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
          belowMap={
            originInput && destinationsInput.length > 0 ? (
              <div className="flex justify-center mb-4">
                <div className="inline-flex items-center gap-2 rounded-full border border-cyan/20 bg-cyan/10 px-3 py-2 text-xs text-white/85">
                  <span className="font-semibold text-cyan">{originInput.city}</span>
                </div>
              </div>
            ) : null
          }
        />

        {/* --- DESTINATION CARD --- */}
        <LocationCard
          title="What all locations are we covering?"
          subtitle="Our stops will be set here"
          Icon={MapPin}
          gradientPos="70% 20%"
          placePickerRef={destPickerRef} // Binds the ref for auto-clearing
          placePickerKey={destPickerKey} // Forces PlacePicker remount so textbox clears
          inputValue={null} // By passing null, we prevent LocationCard's default single map
          onPlaceChange={addStop}
          showMap={false} // Prevent default map
          animCondition={lastRunAnimation === 'Takeoff'}
          animKey={`landing-${animTick}`}
          animName="plane-landing"
          onAnimEnd={() => {
            setLastRunAnimation('Landing');
            setAnimTick((t) => t + 1);
          }}
          belowMap={
            <>
              {/* Custom Multi-Map (Same 170px height as SingleHub) */}
              {canContinue && destinationsInput.length > 0 && (
                <div className="relative mb-4 h-[170px] rounded-xl border border-white/[0.06] bg-white/[0.02] overflow-hidden">
                  <gmp-map
                    ref={mapRef}
                    center={`${destinationsInput[0].lat},${destinationsInput[0].lng}`}
                    zoom="11"
                    map-id="DEMO_MAP_ID"
                    style={{ height: '100%', width: '100%' }}
                  >
                    {/* ONLY iterate destinations. No lines. No source pin. */}
                    {destinationsInput.map((s, idx) =>
                      s.lat != null && s.lng != null ? (
                        <gmp-advanced-marker
                          key={`${s.lat}-${s.lng}-${idx}`}
                          position={`${s.lat},${s.lng}`}
                          title={s.city ?? `Stop ${idx + 1}`}
                        />
                      ) : null,
                    )}
                  </gmp-map>
                  <div className="pointer-events-none absolute inset-0 ring-1 ring-white/[0.06]" />
                </div>
              )}

              {/* Pills */}
              {destinationsInput.length > 0 && (
                <div className="w-full relative [mask-image:linear-gradient(to_right,transparent,black_5%,black_95%,transparent)]">
                  <div className="w-full overflow-x-auto scrollbar-hide">
                    {/* Center pills when they don't overflow, still scroll when they do */}
                    <div className="flex justify-center px-4 pb-3">
                      <div className="flex flex-nowrap gap-2 min-w-max">
                        {destinationsInput.map((stop, idx) => (
                          <button
                            key={`${stop.lat ?? 'x'}-${stop.lng ?? 'y'}-${idx}`}
                            type="button"
                            onClick={() => removeStop(idx)}
                            className="inline-flex items-center gap-2 whitespace-nowrap rounded-full border border-cyan/20 bg-cyan/10 px-3 py-2 text-xs text-white/85 hover:bg-cyan/15 transition-colors cursor-pointer"
                          >
                            <span className="font-semibold text-cyan">{stop.city}</span>
                            <X size={14} className="text-cyan" />
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </>
          }
        />
      </div>

      {/* Sticky Yes button at bottom of viewport */}
      {canContinue && (
        <div className="fixed bottom-0 left-0 w-full z-50 pointer-events-none flex justify-center pb-8 pt-32 bg-gradient-to-t from-black via-black/80 to-transparent">
          <div className="pointer-events-auto">
            <div className="flex items-center gap-4 rounded-full px-6 py-3">
              <span className="text-sm text-white/80 text-center pl-2 select-none">
                Are we starting this trip from{' '}
                <span className="text-cyan font-semibold">{originInput?.city}</span> to a total of{' '}
                <span className="text-cyan font-semibold">{destinationsInput.length}</span> destinations?
              </span>
              <button
                type="button"
                onClick={() => {
                  updateTripData({
                    origin: originInput,
                    destinations: destinationsInput,
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

// --- 3. Main Step 3 Component ---
export function Step3Places({ onNext, registerCommit }: Step3Props) {
  const { trip } = useTrip();
  if (trip.routingStyle === 'multi-hop') {
    return <Step3MultiHop onNext={onNext} registerCommit={registerCommit} />;
  }
  return <Step3SingleHub onNext={onNext} registerCommit={registerCommit} />;
}