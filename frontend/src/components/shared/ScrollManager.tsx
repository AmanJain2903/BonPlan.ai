import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

export default function ScrollManager() {
  const location = useLocation();

  useEffect(() => {
    if ('scrollRestoration' in window.history) {
      window.history.scrollRestoration = 'manual';
    }
  }, []);

  // Save scroll position
  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout>;
    const handleScroll = () => {
      if (timeoutId) clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        sessionStorage.setItem(`scroll-pos-${location.pathname}`, window.scrollY.toString());
      }, 100);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', handleScroll);
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [location.pathname]);

  // Restore position
  useEffect(() => {
    const forceTop = sessionStorage.getItem('force-scroll-top');
    if (forceTop) {
      sessionStorage.removeItem('force-scroll-top');
      sessionStorage.removeItem(`scroll-pos-${location.pathname}`);
      window.scrollTo(0, 0);
      // Delayed fallback in case of structural mounts taking time
      const t = setTimeout(() => window.scrollTo(0, 0), 100);
      return () => clearTimeout(t);
    }

    const savedPos = sessionStorage.getItem(`scroll-pos-${location.pathname}`);
    const restore = () => {
      if (savedPos !== null) {
        window.scrollTo(0, parseInt(savedPos, 10));
      } else {
        window.scrollTo(0, 0);
      }
    };

    restore();
    // Re-trigger scroll to fight layout shifts caused by AnimatePresence or lazy images
    const t1 = setTimeout(restore, 100);
    const t2 = setTimeout(restore, 350);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [location.pathname]);

  return null;
}
