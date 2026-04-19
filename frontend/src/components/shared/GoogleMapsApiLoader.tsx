import { useEffect, useState } from 'react';
import { APILoader } from '@googlemaps/extended-component-library/react';
import { GOOGLE_MAPS_API_KEY } from '../../apis/config';

declare global {
  interface Window {
    __bonplanGoogleMapsLoaderMounted?: boolean;
  }
}

interface GoogleMapsApiLoaderProps {
  solutionChannel?: string;
}

export default function GoogleMapsApiLoader({
  solutionChannel = 'GMP_BonPlan_global',
}: GoogleMapsApiLoaderProps) {
  const [shouldRender, setShouldRender] = useState(false);

  useEffect(() => {
    const googleReady = Boolean((window as any).google?.maps?.importLibrary);
    if (googleReady) {
      setShouldRender(false);
      return;
    }

    if (window.__bonplanGoogleMapsLoaderMounted) {
      setShouldRender(false);
      return;
    }

    window.__bonplanGoogleMapsLoaderMounted = true;
    setShouldRender(true);

    return () => {
      // Release loader ownership on unmount so a later screen can mount it.
      if (window.__bonplanGoogleMapsLoaderMounted) {
        window.__bonplanGoogleMapsLoaderMounted = false;
      }
    };
  }, []);

  if (!shouldRender) return null;
  return <APILoader apiKey={GOOGLE_MAPS_API_KEY} solutionChannel={solutionChannel} />;
}
