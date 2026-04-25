// frontend/src/utils/useDynamicMapImpression.ts
//
// React hook that records a single `dynamic_maps` impression with the
// backend rate limiter when a map element mounts, and returns whether
// it's safe to render another one.
//
// Usage:
//   const allowMap = useDynamicMapImpression();
//   return allowMap ? <gmp-map ... /> : <FallbackPlaceholder />;
//
// Why the pre-flight + render decision is bundled together:
// - Google bills the impression the moment <gmp-map> mounts. By gating
//   the render on the pre-flight result, we avoid lighting up a fresh
//   billable map after the quota has flipped to red.
// - The `trackClientSku` call after mount keeps the counter accurate.

import { useEffect, useRef, useState } from 'react';
import { checkSkuQuota, trackClientSku } from './rateLimiter';

export function useDynamicMapImpression(enabled: boolean = true): boolean {
  const [allowed, setAllowed] = useState(true);
  // One impression per hook instance. Guards against React StrictMode's
  // double-invoked effects in dev and parent re-renders that flicker
  // `enabled` true→false→true. Without this we over-count badly.
  const trackedRef = useRef(false);

  useEffect(() => {
    if (!enabled || trackedRef.current) return;
    let cancelled = false;
    (async () => {
      const status = await checkSkuQuota('dynamic_maps');
      if (cancelled || trackedRef.current) return;
      const ok = status.allowed || status.skipped;
      setAllowed(ok);
      if (ok) {
        trackedRef.current = true;
        void trackClientSku('dynamic_maps', 1);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  return allowed;
}
