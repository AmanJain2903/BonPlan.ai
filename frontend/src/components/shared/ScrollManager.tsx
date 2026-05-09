import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

export default function ScrollManager() {
  const location = useLocation();

  useEffect(() => {
    if ('scrollRestoration' in window.history) {
      window.history.scrollRestoration = 'manual';
    }
  }, []);

  useEffect(() => {
    if (location.pathname.includes('/privacy') || location.pathname.includes('/terms')) {
      sessionStorage.removeItem('force-scroll-top');
      sessionStorage.removeItem(`scroll-pos-${location.pathname}`);
      window.scrollTo({ top: 0, behavior: 'instant' });
    }
  }, [location.pathname]);

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
    const resetHorizontalScroll = () => {
      window.scrollTo({ left: 0, top: window.scrollY, behavior: 'auto' });
      document.documentElement.scrollLeft = 0;
      document.body.scrollLeft = 0;
    };

    const forceTop = sessionStorage.getItem('force-scroll-top');
    if (forceTop) {
      sessionStorage.removeItem('force-scroll-top');
      sessionStorage.removeItem(`scroll-pos-${location.pathname}`);
    }

    const savedPos = forceTop ? null : sessionStorage.getItem(`scroll-pos-${location.pathname}`);
    const targetY = savedPos !== null ? parseInt(savedPos, 10) : 0;

    window.scrollTo({ left: 0, top: targetY, behavior: 'auto' });
    resetHorizontalScroll();

    // For scroll-to-top, the immediate call always succeeds
    if (targetY <= 0) {
      const rafId = requestAnimationFrame(resetHorizontalScroll);
      return () => cancelAnimationFrame(rafId);
    }

    // For non-zero targets, retry until the browser can actually scroll there.
    // Covers AnimatePresence exit delays + lazy content loading.
    let attempts = 0;
    const intervalId = setInterval(() => {
      window.scrollTo({ left: 0, top: targetY, behavior: 'auto' });
      resetHorizontalScroll();
      attempts++;
      const reached = Math.abs(window.scrollY - targetY) <= 5;
      if (reached || attempts >= 20) {
        clearInterval(intervalId);
      }
    }, 100);

    const rafId = requestAnimationFrame(resetHorizontalScroll);
    return () => {
      clearInterval(intervalId);
      cancelAnimationFrame(rafId);
    };
  }, [location.pathname]);

  return null;
}
