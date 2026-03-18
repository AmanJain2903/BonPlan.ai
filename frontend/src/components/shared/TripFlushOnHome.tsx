import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useTrip } from '../../context/TripContext';

export default function TripFlushOnHome() {
  const { pathname } = useLocation();
  const { resetTrip } = useTrip();

  useEffect(() => {
    if (pathname === '/') resetTrip();
  }, [pathname, resetTrip]);

  return null;
}

