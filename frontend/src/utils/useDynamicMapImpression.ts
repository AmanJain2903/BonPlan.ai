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

import { useEffect, useState } from 'react';
import { checkSkuQuota, trackClientSku } from './rateLimiter';

export function useDynamicMapImpression(enabled: boolean = true): boolean {
  // Default to allowing render until we know otherwise — better to flash
  // an extra map than to leave the UI blank during a slow status read.
  const [allowed, setAllowed] = useState(true);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    (async () => {
      const status = await checkSkuQuota('dynamic_maps');
      if (cancelled) return;
      const ok = status.allowed || status.skipped;
      setAllowed(ok);
      if (ok) {
        // Bill the mount once we've decided to render.
        void trackClientSku('dynamic_maps', 1);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  return allowed;
}
