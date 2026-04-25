// frontend/src/utils/clientLog.ts
//
// Tiny helper for shipping a structured event to the backend's /client-log
// endpoint. Use this *sparingly* — only for things the server cannot observe
// on its own. The canonical case today is the rate limiter blocking a Google
// Maps SDK call client-side: Google bills before the backend ever sees the
// request, so without this helper there's no record on the server that the
// quota was exhausted from the user's POV.
//
// Design rules:
//   1. Fire-and-forget. Never block UX on a logging round-trip.
//   2. Throttled per-event-key so a flickering UI can't spam the backend.
//   3. Swallow every error. A logging failure must never propagate.

import axios from 'axios';
import { API_BASE } from '../apis/config';

const CLIENT_LOG_URL = `${API_BASE}/api/v1/client-log/log`;

// 30s throttle window per (event, sku) pair — covers normal UI re-render
// flicker without losing the signal that a block actually happened.
const THROTTLE_MS = 30_000;
const _lastSentAt = new Map<string, number>();

export type ClientLogLevel = 'info' | 'warning' | 'error';

export interface ClientLogPayload {
  /** Short kebab/snake-case label. Required. */
  event: string;
  /** info | warning | error. Defaults to "warning". */
  level?: ClientLogLevel;
  /** Optional human readable message. */
  message?: string;
  /** Optional SKU this event relates to. */
  sku?: string;
  /** Free-form context (kept small — server caps to 32 keys). */
  context?: Record<string, unknown>;
}

/**
 * Ship a single event to the backend log. Returns immediately; the network
 * call runs in the background.
 */
export function clientLog(payload: ClientLogPayload): void {
  try {
    const key = `${payload.event}:${payload.sku ?? ''}`;
    const now = Date.now();
    const last = _lastSentAt.get(key) ?? 0;
    if (now - last < THROTTLE_MS) return;
    _lastSentAt.set(key, now);

    void axios
      .post(CLIENT_LOG_URL, {
        event: payload.event,
        level: payload.level ?? 'warning',
        message: payload.message,
        sku: payload.sku,
        context: payload.context,
      })
      .catch(() => {
        // Logging failures are deliberately silent.
      });
  } catch {
    // Logging itself must never throw.
  }
}

/**
 * Convenience wrapper for the most common case: "the rate limiter blocked
 * a billable client-side call." Always logged at warning level.
 */
export function logRateLimitBlock(
  sku: string,
  message: string,
  context?: Record<string, unknown>,
): void {
  clientLog({
    event: 'rate_limited',
    level: 'warning',
    sku,
    message,
    context,
  });
}
