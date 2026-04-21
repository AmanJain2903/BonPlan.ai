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
    }

    const savedPos = forceTop ? null : sessionStorage.getItem(`scroll-pos-${location.pathname}`);
    const targetY = savedPos !== null ? parseInt(savedPos, 10) : 0;

    window.scrollTo(0, targetY);

    // For scroll-to-top, the immediate call always succeeds
    if (targetY <= 0) return;

    // For non-zero targets, retry until the browser can actually scroll there.
    // Covers AnimatePresence exit delays + lazy content loading.
    let attempts = 0;
    const intervalId = setInterval(() => {
      window.scrollTo(0, targetY);
      attempts++;
      const reached = Math.abs(window.scrollY - targetY) <= 5;
      if (reached || attempts >= 20) {
        clearInterval(intervalId);
      }
    }, 100);

    return () => clearInterval(intervalId);
  }, [location.pathname]);

  return null;
}
