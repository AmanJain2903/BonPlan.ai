// frontend/src/utils/rateLimiter.ts
//
// Client-side bridge to the backend's surgical SKU rate limiter.
//
// Why this exists:
// - The Google Maps JS SDK (Dynamic Maps, Directions, Place Picker
//   autocomplete) bills client-side. The backend never sees those calls
//   directly, so it can't decrement counters from the request path alone.
// - To still enforce a quota we mirror every client-side billable event
//   to the backend via /api/v1/rate-limiting/track-client-sku, which
//   atomically increments the same Redis-backed counters that the MCP
//   tools and backend endpoints share.
// - Pre-flight checks (`checkSkuQuota`) read the counter without
//   incrementing — used to gate expensive renders (map mounts) so we
//   stop showing maps once the monthly cap is exhausted.
//
// Soft enforcement caveat:
//   Google has *already billed* the impression by the time we record it.
//   What this lets us do is *prevent the next* render once we know the
//   quota is exhausted. Treat 429s as "stop rendering further maps",
//   not "undo the last call".

import axios, { AxiosError } from 'axios';
import { API_BASE } from '../apis/config';

const TRACK_URL = `${API_BASE}/api/v1/rate-limiting/track-client-sku`;
const STATUS_URL = (sku: string) =>
  `${API_BASE}/api/v1/rate-limiting/status/${encodeURIComponent(sku)}`;

export type ClientSku = string;

export type SkuStatus = {
  allowed: boolean;
  limit: number;
  current: number;
  remaining: number;
  retry_after_seconds: number;
  /**
   * True when the limiter chose not to enforce — unlimited SKU, missing
   * config, or Redis unreachable. Treat the same as `allowed: true` for
   * UX decisions but skip caching aggressively (state may change).
   */
  skipped: boolean;
};

const DEFAULTS: SkuStatus = {
  allowed: true,
  limit: -1,
  current: 0,
  remaining: -1,
  retry_after_seconds: 0,
  skipped: true,
};

// ─── Pre-flight cache ─────────────────────────────────────────
//
// Status reads hit Redis but they still cost a round trip. For UX-gating
// we only need approximate freshness — a 30s TTL is plenty. Inside that
// window every render reuses the last reading.
const STATUS_CACHE_TTL_MS = 30_000;
const statusCache = new Map<string, { value: SkuStatus; at: number }>();

function readCachedStatus(sku: ClientSku): SkuStatus | null {
  const entry = statusCache.get(sku);
  if (!entry) return null;
  if (Date.now() - entry.at > STATUS_CACHE_TTL_MS) {
    statusCache.delete(sku);
    return null;
  }
  return entry.value;
}

function writeCachedStatus(sku: ClientSku, value: SkuStatus): void {
  statusCache.set(sku, { value, at: Date.now() });
}

function invalidateCachedStatus(sku: ClientSku): void {
  statusCache.delete(sku);
}

// ─── Public API ───────────────────────────────────────────────

/**
 * Pre-flight: read the current quota state for a SKU without incrementing.
 *
 * Use this to gate expensive client-side calls (map mounts, route
 * fetches). Returns DEFAULTS (allowed=true) if the backend is unreachable
 * — we'd rather render the map than block the whole UI on a transient
 * network blip.
 */
export async function checkSkuQuota(sku: ClientSku): Promise<SkuStatus> {
  const cached = readCachedStatus(sku);
  if (cached) return cached;

  try {
    const { data } = await axios.get(STATUS_URL(sku));
    const value: SkuStatus = {
      allowed: Boolean(data.allowed),
      limit: Number(data.limit ?? -1),
      current: Number(data.current ?? 0),
      remaining: Number(data.remaining ?? -1),
      retry_after_seconds: Number(data.retry_after_seconds ?? 0),
      skipped: Boolean(data.skipped),
    };
    writeCachedStatus(sku, value);
    return value;
  } catch (err) {
    return DEFAULTS;
  }
}

/**
 * Record `count` units of usage against `sku`. Resolves to the post-write
 * status. On HTTP 429 the response is `{ allowed: false, ... }` — callers
 * should treat that as "don't issue the *next* call".
 *
 * Errors from the network layer are swallowed and resolve to DEFAULTS so
 * a backend hiccup never blocks a user-visible action — the next status
 * read will reconcile.
 */
export async function trackClientSku(
  sku: ClientSku,
  count: number = 1,
): Promise<SkuStatus> {
  // Bust the pre-flight cache so subsequent checks see the increment.
  invalidateCachedStatus(sku);

  try {
    const { data } = await axios.post(TRACK_URL, { sku, count });
    return {
      allowed: true,
      limit: -1, // track-client-sku doesn't echo the limit
      current: Number(data.current ?? 0),
      remaining: Number(data.remaining ?? -1),
      retry_after_seconds: 0,
      skipped: Boolean(data.skipped),
    };
  } catch (err) {
    const ax = err as AxiosError<any>;
    if (ax.response?.status === 429) {
      const detail = ax.response.data?.detail ?? {};
      return {
        allowed: false,
        limit: Number(detail.limit ?? 0),
        current: Number(detail.current ?? 0),
        remaining: 0,
        retry_after_seconds: Number(detail.retry_after_seconds ?? 60),
        skipped: false,
      };
    }
    return DEFAULTS;
  }
}

/**
 * Combined helper for the common pattern: "before doing X, check quota;
 * if allowed, do X and increment; if not, run a fallback".
 *
 * The increment fires after the action so that an action which throws
 * doesn't burn quota.
 */
export async function withSkuBudget<T>(
  sku: ClientSku,
  action: () => Promise<T> | T,
  fallback: () => Promise<T> | T,
): Promise<T> {
  const status = await checkSkuQuota(sku);
  if (!status.allowed && !status.skipped) {
    return await fallback();
  }
  const result = await action();
  // Fire-and-forget — UX shouldn't wait on the tracking write.
  void trackClientSku(sku, 1);
  return result;
}
