import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { Car, Footprints, Bike, Train, Plane, Loader2, Play, Square } from 'lucide-react';
import { ItineraryDay } from './types';
import {
  EVENT_ACCENT,
  EVENT_LABEL,
  coordinatesForEvent,
  eventKey,
} from './constants';
import { GOOGLE_MAPS_MAP_ID } from '../../apis/config';
import { checkSkuQuota, trackClientSku } from '../../utils/rateLimiter';

// ─── Types ────────────────────────────────────────────────────

interface DayMapViewBodyProps {
  day: ItineraryDay;
  allDays: ItineraryDay[];
  highlightedEventKey?: string | null;
  onNavigateToDay?: (dayNumber: number) => void;
  isGenerating?: boolean;
}

interface EventPin {
  key: string;
  event_type: string;
  lat: number;
  lng: number;
  label: string;
  faded: boolean;
  order: number;
  contextDayNumber?: number;
  contextTag?: string;
}

interface CommuteLine {
  key: string;
  travel_mode: string;
  origin: { lat: number; lng: number };
  destination: { lat: number; lng: number };
  order: number;
}

/** A flight path drawn as a geodesic arc on the map. */
interface FlightRoute {
  key: string;
  departure: { lat: number; lng: number };
  arrival: { lat: number; lng: number };
  label: string;
}

/** A single step in the animated day tour. */
interface TourStep {
  type: 'pause' | 'travel';
  startTime: number; // cumulative ms from tour start
  duration: number;
  // pause fields
  lat?: number;
  lng?: number;
  label?: string;
  zoom?: number;
  isFaded?: boolean; // true for context (prev/next day) stops
  // travel fields
  path?: { lat: number; lng: number }[];
  travelMode?: string;
}

// ─── Coordinate Helpers ───────────────────────────────────────

type AnyCoords =
  | { latitude?: number; longitude?: number; lat?: number; lng?: number }
  | null
  | undefined;

function toLatLng(coords: AnyCoords): { lat: number; lng: number } | null {
  if (!coords) return null;
  const lat = typeof coords.latitude === 'number' ? coords.latitude : coords.lat;
  const lng = typeof coords.longitude === 'number' ? coords.longitude : coords.lng;
  return typeof lat === 'number' && typeof lng === 'number' ? { lat, lng } : null;
}

function haversineKm(
  a: { lat: number; lng: number },
  b: { lat: number; lng: number },
): number {
  const R = 6371;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLng = ((b.lng - a.lng) * Math.PI) / 180;
  const sLat = Math.sin(dLat / 2);
  const sLng = Math.sin(dLng / 2);
  const h =
    sLat * sLat +
    Math.cos((a.lat * Math.PI) / 180) *
    Math.cos((b.lat * Math.PI) / 180) *
    sLng * sLng;
  return R * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
}

/**
 * Interpolate a position along a polyline path given progress 0→1.
 * Returns the lat/lng at the given fraction of the total path distance.
 */
function interpolateAlongPath(
  path: { lat: number; lng: number }[],
  progress: number,
): { lat: number; lng: number } {
  if (path.length === 0) return { lat: 0, lng: 0 };
  if (path.length === 1 || progress <= 0) return path[0];
  if (progress >= 1) return path[path.length - 1];

  // Cumulative distances
  const dists = [0];
  for (let i = 1; i < path.length; i++) {
    dists.push(dists[i - 1] + haversineKm(path[i - 1], path[i]));
  }
  const total = dists[dists.length - 1];
  if (total === 0) return path[0];

  const target = progress * total;
  for (let i = 1; i < path.length; i++) {
    if (dists[i] >= target) {
      const seg = (target - dists[i - 1]) / (dists[i] - dists[i - 1]);
      return {
        lat: path[i - 1].lat + (path[i].lat - path[i - 1].lat) * seg,
        lng: path[i - 1].lng + (path[i].lng - path[i - 1].lng) * seg,
      };
    }
  }
  return path[path.length - 1];
}

// ─── Mode Colors (darkened for visibility) ────────────────────

const MODE_COLOR: Record<string, string> = {
  DRIVE: '#0891b2',
  WALK: '#059669',
  TRANSIT: '#d97706',
  BICYCLE: '#a855f7',
  TWO_WHEELER: '#e11d48',
  FLIGHT: '#6366f1',
  None: '#00d0f0ff',
};

// ─── Marker Icon SVG Builder ──────────────────────────────────

const EVENT_GLYPH_PATH: Record<string, string> = {
  FLIGHT_TAKEOFF:
    'M6.36 17.4 4 17l-2-4 1.1-.55a2 2 0 0 1 1.8 0l.17.1a2 2 0 0 0 1.8 0L8 12 5 6l.9-.45a2 2 0 0 1 2.09.2l4.02 3a2 2 0 0 0 2.1.2l4.19-2.06a2.41 2.41 0 0 1 1.73-.17L21 7a1.4 1.4 0 0 1 .87 1.99l-.38.76c-.23.46-.6.84-1.07 1.08L7.58 17.2a2 2 0 0 1-1.22.18Z',
  FLIGHT_LAND:
    'M3.77 10.77 2 9l2-4.5 1.1.55c.55.28.9.84.9 1.45s.35 1.17.9 1.45L8 8.5l3-6 1.05.53a2 2 0 0 1 1.09 1.52l.72 5.4a2 2 0 0 0 1.09 1.52l4.4 2.2c.42.22.78.55 1.01.96l.6 1.03c.49.88-.06 1.98-1.06 2.1l-1.18.15c-.47.06-.95-.02-1.37-.24L4.29 11.15a2 2 0 0 1-.52-.38Z',
  HOTEL_CHECKIN:
    'M2 20v-8a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v8 M4 10V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v4 M12 4v6 M2 18h20',
  HOTEL_CHECKOUT:
    'M2 4v16 M2 8h18a2 2 0 0 1 2 2v10 M2 17h20 M6 8v9',
  CAR_PICKUP:
    'M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2 M5 17a2 2 0 1 0 4 0 2 2 0 1 0-4 0 M9 17h6 M15 17a2 2 0 1 0 4 0 2 2 0 1 0-4 0',
  CAR_DROPOFF:
    'M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2 M5 17a2 2 0 1 0 4 0 2 2 0 1 0-4 0 M9 17h6 M15 17a2 2 0 1 0 4 0 2 2 0 1 0-4 0',
  DINING:
    'M12 16H4a2 2 0 1 1 0-4h16a2 2 0 1 1 0 4h-4.25 M5 12a2 2 0 0 1-2-2 9 7 0 0 1 18 0 2 2 0 0 1-2 2 M5 16a2 2 0 0 0-2 2 3 3 0 0 0 3 3h12a3 3 0 0 0 3-3 2 2 0 0 0-2-2q0 0 0 0 M6.67 12 12.8 16.6a2 2 0 0 0 2.8-.4l3.15-4.2',
  ACTIVITY:
    'M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0 M9 10a3 3 0 1 0 6 0 3 3 0 1 0-6 0',
  OTHER:
    'M12 17v5 M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z',
  DEFAULT:
    'M12 17v5 M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z',
};

function makePinDataUri(
  color: string,
  type: string,
  opts: { faded?: boolean; highlighted?: boolean; order?: number; contextTag?: string },
): { url: string; size: { w: number; h: number }; anchorX: number; anchorY: number } {
  const pinSize = opts.highlighted ? 44 : 34;
  const r = pinSize / 2 - 3;
  const cx = pinSize / 2;
  const cy = pinSize / 2;
  const opacity = opts.faded ? 0.55 : 1;
  const ringStroke = opts.faded ? 'rgba(255,255,255,0.4)' : 'rgba(255,255,255,0.85)';
  const glyphPath = EVENT_GLYPH_PATH[type] || EVENT_GLYPH_PATH.DEFAULT;
  const glyphSize = r * 1.3;
  const glyphScale = glyphSize / 24;
  const glyphOffset = cx - (glyphSize / 2);

  const showOrder = !opts.faded && opts.order && opts.order > 0;
  const showContext = opts.faded && opts.contextTag;
  const hasLabel = showOrder || showContext;
  const labelText = showOrder ? `${opts.order}` : (opts.contextTag || '');
  const labelFontSize = showContext ? 9 : 11;
  const labelWidth = showContext ? Math.max(labelText.length * 5.5 + 12, 50) : 22;
  const labelHeight = showContext ? 16 : 18;
  const totalWidth = Math.max(pinSize, labelWidth);
  const labelGap = 3;
  const totalHeight = hasLabel ? pinSize + labelGap + labelHeight : pinSize;
  const pinOffsetX = (totalWidth - pinSize) / 2;
  const labelCx = totalWidth / 2;
  const labelCy = pinSize + labelGap + labelHeight / 2;

  const labelSvg = hasLabel
    ? `<g>
      <rect x="${labelCx - labelWidth / 2}" y="${labelCy - labelHeight / 2}" width="${labelWidth}" height="${labelHeight}" rx="${labelHeight / 2}" fill="${opts.faded ? 'rgba(0,0,0,0.7)' : color}" stroke="${opts.faded ? 'rgba(255,255,255,0.3)' : 'rgba(255,255,255,0.7)'}" stroke-width="1"/>
      <text x="${labelCx}" y="${labelCy + (labelFontSize * 0.35)}" text-anchor="middle" fill="#fff" font-size="${labelFontSize}" font-weight="700" font-family="system-ui,-apple-system,sans-serif">${labelText}</text>
    </g>`
    : '';

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${totalWidth}" height="${totalHeight}" viewBox="0 0 ${totalWidth} ${totalHeight}">
  <defs>
    <filter id="s" x="-30%" y="-30%" width="160%" height="160%">
      <feDropShadow dx="0" dy="1.5" stdDeviation="2" flood-color="#000" flood-opacity="0.5"/>
    </filter>
  </defs>
  <g filter="url(#s)" opacity="${opacity}">
    <circle cx="${pinOffsetX + cx}" cy="${cy}" r="${r}" fill="${color}" stroke="${ringStroke}" stroke-width="2"/>
    <g transform="translate(${(pinOffsetX + glyphOffset).toFixed(1)} ${glyphOffset.toFixed(1)}) scale(${glyphScale.toFixed(3)})">
      <path d="${glyphPath}" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </g>
  </g>
  ${labelSvg}
</svg>`;

  const b64 = typeof btoa === 'function' ? btoa(unescape(encodeURIComponent(svg))) : '';
  return {
    url: b64 ? `data:image/svg+xml;base64,${b64}` : `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`,
    size: { w: totalWidth, h: totalHeight },
    anchorX: totalWidth / 2,
    anchorY: pinSize / 2,
  };
}

// ─── Travel Mode Marker (animated icon during tour) ───────────

const TRAVEL_GLYPH: Record<string, string> = {
  DRIVE:
    'M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2 M5 17a2 2 0 1 0 4 0 2 2 0 1 0-4 0 M9 17h6 M15 17a2 2 0 1 0 4 0 2 2 0 1 0-4 0',
  WALK:
    'M13 4.5a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3z M7 21l3-9 2.5 3v5 M10 14l-2-4L12 7l3 3 2 1',
  BICYCLE:
    'M5.5 17a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M18.5 17a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M12 17V8l-3 3 M12 8h3l2.5 6',
  TRANSIT:
    'M4 16V6a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3v10a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 16z M4 10h16 M8 18l-1 3 M16 18l1 3 M8.5 14h.01 M15.5 14h.01',
  TWO_WHEELER:
    'M5.5 17a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M18.5 17a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M12 17V8l-3 3 M12 8h3l2.5 6',
  FLIGHT:
    'M6.36 17.4 4 17l-2-4 1.1-.55a2 2 0 0 1 1.8 0l.17.1a2 2 0 0 0 1.8 0L8 12 5 6l.9-.45a2 2 0 0 1 2.09.2l4.02 3a2 2 0 0 0 2.1.2l4.19-2.06a2.41 2.41 0 0 1 1.73-.17L21 7a1.4 1.4 0 0 1 .87 1.99l-.38.76c-.23.46-.6.84-1.07 1.08L7.58 17.2a2 2 0 0 1-1.22.18Z',
  None: 'M4.037 4.688a.495.495 0 0 1 .651-.651l16 6.5a.5.5 0 0 1-.063.947l-6.124 1.58a2 2 0 0 0-1.438 1.435l-1.579 6.126a.5.5 0 0 1-.947.063z',
};

function makeTravelMarkerIcon(travelMode: string): { url: string; size: number } {
  const size = 48;
  const color = MODE_COLOR[travelMode] || '#0891b2';
  const glyph = TRAVEL_GLYPH[travelMode] || TRAVEL_GLYPH.None;
  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - 5;
  const gs = r * 1.2;
  const sc = gs / 24;
  const off = cx - gs / 2;

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
  <defs>
    <filter id="gl" x="-50%" y="-50%" width="200%" height="200%">
      <feDropShadow dx="0" dy="0" stdDeviation="4" flood-color="${color}" flood-opacity="0.7"/>
    </filter>
  </defs>
  <circle cx="${cx}" cy="${cy}" r="${r + 4}" fill="${color}" opacity="0.25" filter="url(#gl)"/>
  <circle cx="${cx}" cy="${cy}" r="${r}" fill="${color}" stroke="rgba(255,255,255,0.95)" stroke-width="2.5"/>
  <g transform="translate(${off.toFixed(1)} ${off.toFixed(1)}) scale(${sc.toFixed(3)})">
    <path d="${glyph}" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  </g>
</svg>`;

  const b64 = btoa(unescape(encodeURIComponent(svg)));
  return { url: `data:image/svg+xml;base64,${b64}`, size };
}

// ─── Route Cache (module-level singleton) ─────────────────────

const routeCache = new Map<string, string>();
const pendingRoutes = new Set<string>();

function routeCacheKey(
  origin: { lat: number; lng: number },
  dest: { lat: number; lng: number },
  mode: string,
): string {
  return `${origin.lat},${origin.lng}|${dest.lat},${dest.lng}|${mode}`;
}

// Once the `directions` SKU flips to red we hold off issuing further
// DirectionsService calls for the rest of the page lifetime — the JS
// SDK would bill each one regardless.
let directionsQuotaExhausted = false;

async function fetchRoutePolyline(
  origin: { lat: number; lng: number },
  destination: { lat: number; lng: number },
  travelMode: string,
  onResolve: (encoded: string) => void,
): Promise<void> {
  const key = routeCacheKey(origin, destination, travelMode);
  if (routeCache.has(key)) {
    onResolve(routeCache.get(key)!);
    return;
  }
  if (pendingRoutes.has(key)) return;
  if (directionsQuotaExhausted) return;

  const maps = (window as any).google?.maps;
  if (!maps?.DirectionsService) return;

  // Pre-flight the directions quota — this is a billable client-side call
  // (Google bills the moment DirectionsService.route resolves). If the
  // budget is gone, fall back to the straight-line render the consumer
  // gets when no polyline arrives.
  const status = await checkSkuQuota('directions');
  if (!status.allowed && !status.skipped) {
    directionsQuotaExhausted = true;
    return;
  }

  pendingRoutes.add(key);
  const svc = new maps.DirectionsService();

  let mode = maps.TravelMode.DRIVING;
  if (travelMode === 'WALK') mode = maps.TravelMode.WALKING;
  else if (travelMode === 'TRANSIT') mode = maps.TravelMode.TRANSIT;
  else if (travelMode === 'BICYCLE' || travelMode === 'TWO_WHEELER')
    mode = maps.TravelMode.BICYCLING;

  svc.route(
    { origin, destination, travelMode: mode },
    (result: any, status: any) => {
      pendingRoutes.delete(key);
      if (status === maps.DirectionsStatus.OK && result?.routes?.length > 0) {
        // Bill the impression now that Google has actually served us a route.
        void trackClientSku('directions', 1).then((tracked) => {
          if (!tracked.allowed) directionsQuotaExhausted = true;
        });
        const route = result.routes[0];
        let encoded = '';
        if (typeof route.overview_polyline === 'string') {
          encoded = route.overview_polyline;
        } else if (route.overview_polyline?.points) {
          encoded = route.overview_polyline.points as string;
        }
        if (encoded) {
          routeCache.set(key, encoded);
          onResolve(encoded);
        }
      } else {
        console.warn('[DayMapView] Directions request failed:', status);
      }
    },
  );
}

// ─── Cluster Finder ───────────────────────────────────────────

function findMajorityCluster(
  points: { lat: number; lng: number }[],
  radiusKm = 8,
): number[] {
  if (points.length <= 2) return points.map((_, i) => i);
  let bestCluster: number[] = [];
  for (let i = 0; i < points.length; i++) {
    const cluster = [i];
    for (let j = 0; j < points.length; j++) {
      if (i !== j && haversineKm(points[i], points[j]) <= radiusKm) cluster.push(j);
    }
    if (cluster.length > bestCluster.length) bestCluster = cluster;
  }
  return bestCluster.length > 1 ? bestCluster : points.map((_, i) => i);
}

// ─── Tour Sequence Builder ────────────────────────────────────

const PAUSE_DURATION = 2200;
const CONTEXT_PAUSE_DURATION = 1200;
const TRAVEL_DURATION = 3500;
const JUMP_DURATION = 1500;

function buildTourSequence(
  dayEvents: any[],
  prevContextPin: EventPin | null,
  nextContextPin: EventPin | null,
  geometry: any,
): TourStep[] {
  const raw: Omit<TourStep, 'startTime'>[] = [];

  // Start at previous day's last event if exists
  if (prevContextPin) {
    raw.push({
      type: 'pause',
      duration: CONTEXT_PAUSE_DURATION,
      lat: prevContextPin.lat,
      lng: prevContextPin.lng,
      label: `${prevContextPin.contextTag} · ${prevContextPin.label}`,
      zoom: 14,
      isFaded: true,
    });
  }

  // Walk through the day's events in order
  for (const ev of dayEvents) {
    if (!ev) continue;

    if (ev.event_type === 'COMMUTE') {
      const cd = ev.commute_details;
      const origin = toLatLng(cd?.origin_coordinates);
      const dest = toLatLng(cd?.destination_coordinates);
      if (origin && dest && cd?.travel_mode) {
        const cKey = routeCacheKey(origin, dest, cd.travel_mode);
        const encoded = routeCache.get(cKey);
        let path: { lat: number; lng: number }[] = [origin, dest];

        if (encoded && geometry?.encoding?.decodePath) {
          try {
            const decoded = geometry.encoding.decodePath(encoded);
            if (Array.isArray(decoded) && decoded.length > 1) {
              path = decoded.map((p: any) => ({
                lat: typeof p.lat === 'function' ? p.lat() : p.lat,
                lng: typeof p.lng === 'function' ? p.lng() : p.lng,
              }));
            }
          } catch {
            /* fallback to straight line */
          }
        }
        raw.push({
          type: 'travel',
          duration: path.length > 2 ? TRAVEL_DURATION : JUMP_DURATION,
          path,
          travelMode: cd.travel_mode,
        });
      }
      continue;
    }

    // For FLIGHT_TAKEOFF, add a pause at departure then a flight travel step
    if (ev.event_type === 'FLIGHT_TAKEOFF') {
      const fd = ev.flight_takeoff_details;
      const dep = toLatLng(fd?.departure_coordinates);
      const arr = toLatLng(fd?.arrival_coordinates);
      if (dep) {
        raw.push({
          type: 'pause',
          duration: PAUSE_DURATION,
          lat: dep.lat,
          lng: dep.lng,
          label: `${fd?.departure_airport_name || 'Departure'} (${fd?.departure_airport_code || ''})`,
          zoom: 12,
          isFaded: false,
        });
      }
      if (dep && arr) {
        raw.push({
          type: 'travel',
          duration: TRAVEL_DURATION + 1000, // flights get a longer animation
          path: [dep, arr],
          travelMode: 'FLIGHT',
        });
      }
      continue;
    }

    // For FLIGHT_LAND, add a pause at arrival
    if (ev.event_type === 'FLIGHT_LAND') {
      const fl = ev.flight_land_details;
      const arr = toLatLng(fl?.arrival_coordinates);
      if (arr) {
        raw.push({
          type: 'pause',
          duration: PAUSE_DURATION,
          lat: arr.lat,
          lng: arr.lng,
          label: `${fl?.arrival_airport_name || 'Arrival'} (${fl?.arrival_airport_code || ''})`,
          zoom: 12,
          isFaded: false,
        });
      }
      continue;
    }

    const coord = coordinatesForEvent(ev);
    if (coord) {
      raw.push({
        type: 'pause',
        duration: PAUSE_DURATION,
        lat: coord.latitude,
        lng: coord.longitude,
        label: `${ev.place_details?.event_name || ev.other_details?.event_name || ev.place_details?.place_name || ev.other_details?.location || EVENT_LABEL[ev.event_type] || ev.event_type}`,
        zoom: 15,
        isFaded: false,
      });
    }
  }

  // End at next day's first event if exists
  if (nextContextPin) {
    raw.push({
      type: 'pause',
      duration: CONTEXT_PAUSE_DURATION,
      lat: nextContextPin.lat,
      lng: nextContextPin.lng,
      label: `${nextContextPin.contextTag} · ${nextContextPin.label}`,
      zoom: 14,
      isFaded: true,
    });
  }

  // Post-process: insert jump steps between consecutive pauses with no travel
  const processed: Omit<TourStep, 'startTime'>[] = [];
  for (let i = 0; i < raw.length; i++) {
    processed.push(raw[i]);
    if (
      i < raw.length - 1 &&
      raw[i].type === 'pause' &&
      raw[i + 1].type === 'pause'
    ) {
      processed.push({
        type: 'travel',
        duration: JUMP_DURATION,
        path: [
          { lat: raw[i].lat!, lng: raw[i].lng! },
          { lat: raw[i + 1].lat!, lng: raw[i + 1].lng! },
        ],
        travelMode: 'None',
      });
    }
  }

  // Assign cumulative start times
  let time = 0;
  const steps: TourStep[] = processed.map((s) => {
    const step: TourStep = { ...s, startTime: time };
    time += s.duration;
    return step;
  });

  return steps;
}

// ─── Component ────────────────────────────────────────────────

export default function DayMapViewBody({
  day,
  allDays,
  highlightedEventKey,
  onNavigateToDay,
  isGenerating,
}: DayMapViewBodyProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const mapsLibRef = useRef<any>(null);
  const geometryLibRef = useRef<any>(null);
  const [libsReady, setLibsReady] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);

  const markersRef = useRef<any[]>([]);
  const polylinesRef = useRef<any[]>([]);
  const labelsRef = useRef<any[]>([]);
  const isFirstRenderRef = useRef(true);
  const impressionTrackedRef = useRef(false);

  const [routeVersion, setRouteVersion] = useState(0);
  const bumpRouteVersion = useCallback(() => setRouteVersion((v) => v + 1), []);

  // Tour animation state
  const [isTouring, setIsTouring] = useState(false);
  const [tourLabel, setTourLabel] = useState('');
  const [tourProgress, setTourProgress] = useState(0);
  const tourRef = useRef<{
    rafId: number;
    animStartTime: number;
    steps: TourStep[];
    totalDuration: number;
    lastStepIdx: number;
    travelMarker: any;
  } | null>(null);

  const currentIdx = allDays.findIndex((d) => d.dayNumber === day.dayNumber);

  // ── Derive pins, commutes & flight routes ──────────────────

  const { pins, commutes, flightRoutes } = useMemo(() => {
    const pins: EventPin[] = [];
    const commutes: CommuteLine[] = [];
    const flightRoutes: FlightRoute[] = [];
    let pinOrder = 0;
    let commuteOrder = 0;

    for (const ev of day.events || []) {
      if (!ev) continue;
      if (ev.event_type === 'COMMUTE') {
        const cd = ev.commute_details;
        const origin = toLatLng(cd?.origin_coordinates);
        const destination = toLatLng(cd?.destination_coordinates);
        if (origin && destination && cd?.travel_mode) {
          commuteOrder++;
          commutes.push({
            key: eventKey(ev),
            travel_mode: cd.travel_mode || 'None',
            origin,
            destination,
            order: commuteOrder,
          });
        }
        continue;
      }

      // Extract flight routes from FLIGHT_TAKEOFF events
      if (ev.event_type === 'FLIGHT_TAKEOFF') {
        const fd = ev.flight_takeoff_details;
        const dep = toLatLng(fd?.departure_coordinates);
        const arr = toLatLng(fd?.arrival_coordinates);
        if (dep && arr) {
          flightRoutes.push({
            key: eventKey(ev),
            departure: dep,
            arrival: arr,
            label: `${fd?.departure_airport_code || '?'} → ${fd?.arrival_airport_code || '?'}`,
          });
        }
      }

      const coord = coordinatesForEvent(ev);
      if (!coord) continue;
      pinOrder++;
      pins.push({
        key: eventKey(ev),
        event_type: ev.event_type,
        lat: coord.latitude,
        lng: coord.longitude,
        label: EVENT_LABEL[ev.event_type] || ev.event_type,
        faded: false,
        order: pinOrder,
      });
    }

    // Context pins
    const prevDay = currentIdx > 0 ? allDays[currentIdx - 1] : null;
    const nextDay = currentIdx >= 0 && currentIdx < allDays.length - 1 ? allDays[currentIdx + 1] : null;

    if (prevDay) {
      const last = [...(prevDay.events || [])].reverse().find((e: any) => e && e.event_type !== 'COMMUTE');
      if (last) {
        const c = coordinatesForEvent(last);
        if (c) {
          pins.push({
            key: `ctx-prev-${eventKey(last)}`,
            event_type: last.event_type,
            lat: c.latitude,
            lng: c.longitude,
            label: EVENT_LABEL[last.event_type] || last.event_type,
            faded: true,
            order: 0,
            contextDayNumber: prevDay.dayNumber,
            contextTag: `Day ${prevDay.dayNumber}`,
          });
        }
      }
    }
    if (nextDay) {
      const first = (nextDay.events || []).find((e: any) => e && e.event_type !== 'COMMUTE');
      if (first) {
        const c = coordinatesForEvent(first);
        if (c) {
          pins.push({
            key: `ctx-next-${eventKey(first)}`,
            event_type: first.event_type,
            lat: c.latitude,
            lng: c.longitude,
            label: EVENT_LABEL[first.event_type] || first.event_type,
            faded: true,
            order: 0,
            contextDayNumber: nextDay.dayNumber,
            contextTag: `Day ${nextDay.dayNumber}`,
          });
        }
      }
    }

    return { pins, commutes, flightRoutes };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [day, allDays, currentIdx, routeVersion, libsReady]);

  // ── Fetch routes for commutes (side-effect, not in useMemo) ─

  useEffect(() => {
    if (!libsReady) return;
    for (const c of commutes) {
      const cKey = routeCacheKey(c.origin, c.destination, c.travel_mode);
      if (!routeCache.has(cKey)) {
        fetchRoutePolyline(c.origin, c.destination, c.travel_mode, bumpRouteVersion);
      }
    }
  }, [libsReady, commutes, bumpRouteVersion]);

  // Derived context pins for the tour builder
  const prevContextPin = useMemo(() => pins.find((p) => p.key.startsWith('ctx-prev-')) || null, [pins]);
  const nextContextPin = useMemo(() => pins.find((p) => p.key.startsWith('ctx-next-')) || null, [pins]);

  // ── Load Google Maps libraries ─────────────────────────────

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      let g: any = (window as any).google;
      const start = Date.now();
      while (!g?.maps?.importLibrary && Date.now() - start < 5000) {
        await new Promise((r) => setTimeout(r, 80));
        g = (window as any).google;
        if (cancelled) return;
      }
      try {
        const [maps, geometry] = await Promise.all([
          g.maps.importLibrary('maps'),
          g.maps.importLibrary('geometry'),
        ]);
        if (cancelled) return;
        mapsLibRef.current = maps;
        geometryLibRef.current = geometry;
        setLibsReady(true);
      } catch (err) {
        console.warn('[DayMapView] Google Maps library load failed', err);
        setMapError('Failed to load Google Maps libraries. Please check your browser console.');
      }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  // ── Create map instance ────────────────────────────────────

  useEffect(() => {
    if (!libsReady) return;
    const el = mapContainerRef.current;
    if (!el) return;
    const maps = mapsLibRef.current;
    if (!maps?.Map) return;

    let cancelled = false;
    let ro: ResizeObserver | null = null;

    (async () => {
      // Pre-flight: every Map() instantiation bills one Dynamic Maps impression.
      const status = await checkSkuQuota('dynamic_maps');
      if (cancelled) return;
      if (!status.allowed && !status.skipped) {
        setMapError('Map quota exhausted for this billing period.');
        return;
      }

      try {
        mapRef.current = new maps.Map(el, {
          center: pins.length > 0 ? { lat: pins[0].lat, lng: pins[0].lng } : { lat: 20, lng: 0 },
          zoom: pins.length > 0 ? 12 : 3,
          mapId: GOOGLE_MAPS_MAP_ID,
          disableDefaultUI: true,
          fullscreenControl: true,
          fullscreenControlOptions: { position: maps.ControlPosition?.TOP_RIGHT },
          clickableIcons: false,
          keyboardShortcuts: false,
          gestureHandling: 'greedy',
        });
      } catch (err) {
        console.error('[DayMapView] Map constructor threw:', err);
        setMapError('Failed to initialize the map.');
        return;
      }

      // Bill the impression after a successful mount — once per component
      // instance to avoid StrictMode/effect-rerun double counting.
      if (!impressionTrackedRef.current) {
        impressionTrackedRef.current = true;
        void trackClientSku('dynamic_maps', 1);
      }

      try {
        ro = new ResizeObserver(() => { maps.event?.trigger?.(mapRef.current, 'resize'); });
        ro.observe(el);
      } catch { /* unsupported */ }
    })();

    return () => {
      cancelled = true;
      try { ro?.disconnect(); } catch { /* noop */ }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [libsReady]);

  // ── Render polylines ───────────────────────────────────────

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !libsReady) return;
    const maps = (window as any).google?.maps;
    const geometry = geometryLibRef.current;
    if (!maps?.Polyline) return;

    for (const p of polylinesRef.current) p.setMap(null);
    polylinesRef.current = [];
    for (const l of labelsRef.current) l.setMap(null);
    labelsRef.current = [];

    const arrowIcon = {
      path: maps.SymbolPath?.FORWARD_CLOSED_ARROW || 0,
      scale: 3.5,
      strokeColor: '#013d38ff',
      strokeWeight: 1.5,
      strokeOpacity: 0.7,
      fillColor: '#00d0f0ff',
      fillOpacity: 0.5,
    };

    for (const c of commutes) {
      const cKey = routeCacheKey(c.origin, c.destination, c.travel_mode);
      const encoded = routeCache.get(cKey);
      const color = MODE_COLOR[c.travel_mode] || '#0891b2';

      if (encoded && geometry?.encoding?.decodePath) {
        try {
          const decoded = geometry.encoding.decodePath(encoded);
          if (Array.isArray(decoded) && decoded.length > 1) {
            polylinesRef.current.push(
              new maps.Polyline({
                path: decoded,
                geodesic: false,
                strokeColor: color,
                strokeOpacity: 0.9,
                strokeWeight: 5,
                map,
                icons: [{ icon: arrowIcon, offset: '30%', repeat: '120px' }],
              }),
            );
            continue;
          }
        } catch { /* fallback */ }
      }

      const dashSymbol = {
        path: 'M 0,-1 0,1',
        strokeOpacity: 1,
        strokeColor: color,
        strokeWeight: 3,
        scale: 3,
      };
      polylinesRef.current.push(
        new maps.Polyline({
          path: [c.origin, c.destination],
          geodesic: false,
          strokeOpacity: 0,
          icons: [
            { icon: dashSymbol, offset: '0', repeat: '16px' },
            { icon: arrowIcon, offset: '50%' },
          ],
          map,
        }),
      );
    }

    // Flight routes as geodesic arcs
    const flightColor = MODE_COLOR.FLIGHT;
    const planeIcon = {
      path: maps.SymbolPath?.FORWARD_CLOSED_ARROW || 0,
      scale: 4,
      strokeColor: flightColor,
      strokeWeight: 2,
      strokeOpacity: 1,
      fillColor: flightColor,
      fillOpacity: 0.9,
    };
    for (const fr of flightRoutes) {
      polylinesRef.current.push(
        new maps.Polyline({
          path: [fr.departure, fr.arrival],
          geodesic: true,
          strokeColor: flightColor,
          strokeOpacity: 0.8,
          strokeWeight: 3,
          map,
          icons: [
            { icon: planeIcon, offset: '50%' },
          ],
        }),
      );
    }

    return () => {
      for (const p of polylinesRef.current) p.setMap(null);
      polylinesRef.current = [];
      for (const l of labelsRef.current) l.setMap(null);
      labelsRef.current = [];
    };
  }, [libsReady, commutes, flightRoutes]);

  // ── Render markers & set camera ────────────────────────────

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !libsReady) return;
    const maps = (window as any).google?.maps;
    if (!maps?.Marker || !maps?.LatLngBounds || !maps?.Size || !maps?.Point) return;

    for (const m of markersRef.current) m.setMap(null);
    markersRef.current = [];

    for (const pin of pins) {
      const isHighlighted = highlightedEventKey === pin.key;
      const accent = EVENT_ACCENT[pin.event_type];
      const color = accent?.marker || '#67e8f9';
      const { url, size, anchorX, anchorY } = makePinDataUri(color, pin.event_type, {
        faded: pin.faded,
        highlighted: isHighlighted,
        order: pin.order,
        contextTag: pin.contextTag,
      });
      const m = new maps.Marker({
        map,
        position: { lat: pin.lat, lng: pin.lng },
        title: pin.faded
          ? `${pin.contextTag} · ${pin.label} (click to navigate)`
          : `${pin.order}. ${pin.label}`,
        zIndex: isHighlighted ? 999 : pin.faded ? 1 : 10,
        cursor: pin.faded ? 'pointer' : 'default',
        icon: { url, scaledSize: new maps.Size(size.w, size.h), anchor: new maps.Point(anchorX, anchorY) },
      });

      if (pin.faded && pin.contextDayNumber && onNavigateToDay) {
        m.addListener('click', () => { onNavigateToDay(pin.contextDayNumber!); });
      }
      markersRef.current.push(m);
    }

    if (isFirstRenderRef.current && pins.length > 0) {
      isFirstRenderRef.current = false;
      if (highlightedEventKey) {
        const hl = pins.find((p) => p.key === highlightedEventKey);
        if (hl) { map.setCenter({ lat: hl.lat, lng: hl.lng }); map.setZoom(15); }
      } else {
        const activePins = pins.filter((p) => !p.faded);
        if (activePins.length > 0) {
          const ci = findMajorityCluster(activePins.map((p) => ({ lat: p.lat, lng: p.lng })), 8);
          const bounds = new maps.LatLngBounds();
          for (const idx of ci) bounds.extend({ lat: activePins[idx].lat, lng: activePins[idx].lng });
          if (!bounds.isEmpty()) map.fitBounds(bounds, 80);
        } else {
          const bounds = new maps.LatLngBounds();
          for (const p of pins) bounds.extend({ lat: p.lat, lng: p.lng });
          if (!bounds.isEmpty()) map.fitBounds(bounds, 80);
        }
      }
      maps.event?.trigger?.(map, 'resize');
    }

    return () => { for (const m of markersRef.current) m.setMap(null); markersRef.current = []; };
  }, [libsReady, pins, commutes, highlightedEventKey, onNavigateToDay]);

  // ── Tour Animation ─────────────────────────────────────────

  const stopTour = useCallback(() => {
    const anim = tourRef.current;
    if (!anim) return;

    cancelAnimationFrame(anim.rafId);
    anim.travelMarker?.setMap(null);

    // Snap to nearest current-day pin
    const map = mapRef.current;
    if (map) {
      // Determine current position from the animation
      const elapsed = performance.now() - anim.animStartTime;
      let currentPos: { lat: number; lng: number } | null = null;

      for (let i = anim.steps.length - 1; i >= 0; i--) {
        const s = anim.steps[i];
        if (elapsed >= s.startTime) {
          if (s.type === 'pause') {
            currentPos = { lat: s.lat!, lng: s.lng! };
          } else if (s.type === 'travel' && s.path) {
            const prog = Math.min((elapsed - s.startTime) / s.duration, 1);
            currentPos = interpolateAlongPath(s.path, prog);
          }
          break;
        }
      }

      // Find nearest non-faded pin
      const currentDayPins = pins.filter((p) => !p.faded);
      if (currentDayPins.length > 0 && currentPos) {
        let closest = currentDayPins[0];
        let minDist = haversineKm(currentPos, closest);
        for (const p of currentDayPins) {
          const d = haversineKm(currentPos, p);
          if (d < minDist) { minDist = d; closest = p; }
        }
        map.setCenter({ lat: closest.lat, lng: closest.lng });
        map.setZoom(15);
      }

      // Restore interactive gestures
      map.setOptions({ gestureHandling: 'greedy' });
    }

    tourRef.current = null;
    setIsTouring(false);
    setTourLabel('');
    setTourProgress(0);
  }, [pins]);

  // ── Stop tour on day change ────────────────────────────────

  const prevDayNumberRef = useRef(day.dayNumber);
  useEffect(() => {
    if (day.dayNumber !== prevDayNumberRef.current) {
      prevDayNumberRef.current = day.dayNumber;
      if (tourRef.current) stopTour();
    }
  }, [day.dayNumber, stopTour]);

  const startTour = useCallback(() => {
    const map = mapRef.current;
    const maps = (window as any).google?.maps;
    if (!map || !maps) return;

    // Stop any existing tour
    if (tourRef.current) stopTour();

    const geometry = geometryLibRef.current;
    const steps = buildTourSequence(day.events || [], prevContextPin, nextContextPin, geometry);
    if (steps.length < 2) return; // Nothing meaningful to tour

    const totalDuration = steps.length > 0
      ? steps[steps.length - 1].startTime + steps[steps.length - 1].duration
      : 0;

    // Create the travel mode marker (initially hidden)
    const { url: tmUrl, size: tmSize } = makeTravelMarkerIcon('DRIVE');
    const travelMarker = new maps.Marker({
      map,
      position: { lat: 0, lng: 0 },
      visible: false,
      zIndex: 2000,
      icon: {
        url: tmUrl,
        scaledSize: new maps.Size(tmSize, tmSize),
        anchor: new maps.Point(tmSize / 2, tmSize / 2),
      },
    });

    // Disable map interaction during tour
    map.setOptions({ gestureHandling: 'none' });

    const anim = {
      rafId: 0,
      animStartTime: performance.now(),
      steps,
      totalDuration,
      lastStepIdx: -1,
      travelMarker,
    };
    tourRef.current = anim;
    setIsTouring(true);

    const onFrame = (timestamp: number) => {
      if (!tourRef.current) return;
      const elapsed = timestamp - anim.animStartTime;

      // Find current step
      let stepIdx = 0;
      while (
        stepIdx < steps.length &&
        elapsed >= steps[stepIdx].startTime + steps[stepIdx].duration
      ) {
        stepIdx++;
      }

      if (stepIdx >= steps.length) {
        // Tour complete — snap to last current-day pin
        travelMarker.setVisible(false);
        const lastPin = [...pins].reverse().find((p) => !p.faded);
        if (lastPin) {
          map.setCenter({ lat: lastPin.lat, lng: lastPin.lng });
          map.setZoom(15);
        }
        map.setOptions({ gestureHandling: 'greedy' });
        travelMarker.setMap(null);
        tourRef.current = null;
        setIsTouring(false);
        setTourLabel('Tour complete');
        setTimeout(() => setTourLabel(''), 2000);
        setTourProgress(1);
        return;
      }

      const step = steps[stepIdx];
      const progress = Math.min((elapsed - step.startTime) / step.duration, 1);

      // Update progress bar
      setTourProgress(elapsed / totalDuration);

      // Step changed — update label and mode
      if (stepIdx !== anim.lastStepIdx) {
        anim.lastStepIdx = stepIdx;

        if (step.type === 'pause') {
          travelMarker.setVisible(false);
          map.setCenter({ lat: step.lat!, lng: step.lng! });
          map.setZoom(step.zoom || 15);
          setTourLabel(`${step.label || 'Event'}`);
        } else if (step.type === 'travel') {
          travelMarker.setVisible(true);
          const mode = step.travelMode || 'None';
          const { url, size } = makeTravelMarkerIcon(mode);
          travelMarker.setIcon({
            url,
            scaledSize: new maps.Size(size, size),
            anchor: new maps.Point(size / 2, size / 2),
          });
          map.setZoom(mode === 'WALK' ? 16 : mode === 'BICYCLE' ? 15 : mode === 'FLIGHT' ? 6 : 14);
          if (mode === 'WALK') {
            setTourLabel('Walking to the next event...');
          } else if (mode === 'BICYCLE') {
            setTourLabel('Cycling to the next event...');
          } else if (mode === 'DRIVE') {
            setTourLabel('Driving to the next event...');
          } else if (mode === 'TWO_WHEELER') {
            setTourLabel('Riding a two-wheeler to the next event...');
          } else if (mode === 'TRANSIT') {
            setTourLabel('Taking public transit to the next event...');
          } else if (mode === 'FLIGHT') {
            setTourLabel('✈ Flying to the next destination...');
          } else {
            setTourLabel("What's coming up next...");
          }
        }
      }

      // Animate travel marker position and smoothly follow with camera
      if (step.type === 'travel' && step.path) {
        const pos = interpolateAlongPath(step.path, progress);
        travelMarker.setPosition(pos);

        // Only pan when the marker is near the viewport edge (25% inset).
        // This avoids jittery setCenter calls every frame while still
        // ensuring the marker never goes off-screen.
        const bounds = map.getBounds();
        if (bounds) {
          const ne = bounds.getNorthEast();
          const sw = bounds.getSouthWest();
          const latSpan = ne.lat() - sw.lat();
          const lngSpan = ne.lng() - sw.lng();
          const inset = 0.25; // trigger when within 25% of the edge
          const innerNorth = ne.lat() - latSpan * inset;
          const innerSouth = sw.lat() + latSpan * inset;
          const innerEast = ne.lng() - lngSpan * inset;
          const innerWest = sw.lng() + lngSpan * inset;

          if (
            pos.lat > innerNorth || pos.lat < innerSouth ||
            pos.lng > innerEast || pos.lng < innerWest
          ) {
            map.panTo(pos);
          }
        } else {
          // Fallback: no bounds available yet, just center
          map.panTo(pos);
        }
      }

      anim.rafId = requestAnimationFrame(onFrame);
    };

    anim.rafId = requestAnimationFrame(onFrame);
  }, [day.events, prevContextPin, nextContextPin, flightRoutes, stopTour, pins]);

  // Cleanup tour on unmount
  useEffect(() => {
    return () => {
      if (tourRef.current) {
        cancelAnimationFrame(tourRef.current.rafId);
        tourRef.current.travelMarker?.setMap(null);
        tourRef.current = null;
      }
    };
  }, []);

  // ─── Render ─────────────────────────────────────────────────

  const canTour = pins.filter((p) => !p.faded).length >= 2 && !isGenerating;

  return (
    <div className="relative w-full h-full">
      {!libsReady ? (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="flex items-center gap-2 text-cyan/80 text-xs font-semibold uppercase tracking-wider">
            <Loader2 className="w-4 h-4 animate-spin" />
            Loading map...
          </div>
        </div>
      ) : (
        <div ref={mapContainerRef} className="absolute inset-0 bg-black/40" />
      )}

      {mapError && (
        <div className="absolute inset-0 z-30 flex items-center justify-center pointer-events-none">
          <div className="bg-red-500/10 border border-red-500/30 text-red-200 rounded-2xl px-5 py-4 text-center backdrop-blur-md">
            <p className="text-sm font-semibold">{mapError}</p>
            <p className="text-xs text-white/50 mt-1">Check the browser console for details.</p>
          </div>
        </div>
      )}

      {/* Tour controls (bottom-right) */}
      {libsReady && canTour && (
        <div className="absolute bottom-4 right-4 z-20">
          {!isTouring ? (
            <button
              onClick={startTour}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-cyan/90 bg-carbon/80 hover:bg-carbon/90 text-cyan text-xs font-bold uppercase tracking-wider shadow-lg shadow-cyan/20 transition-all hover:scale-105 active:scale-95"
            >
              <Play className="w-3.5 h-3.5" />
              Start Tour
            </button>
          ) : (
            <button
              onClick={stopTour}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-white bg-red-500/80 hover:bg-red-500/90 text-white text-xs font-bold uppercase tracking-wider shadow-lg shadow-red-500/20 transition-all hover:scale-105 active:scale-95"
            >
              <Square className="w-3.5 h-3.5" />
              Stop Tour
            </button>
          )}
        </div>
      )}

      {/* Tour label banner (top-center) */}
      {isTouring && tourLabel && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 pointer-events-none">
          <div className="bg-black/80 backdrop-blur-md border border-white/15 rounded-xl px-4 py-2 shadow-xl">
            <p className="text-white text-xs font-semibold tracking-wide whitespace-nowrap">
              {tourLabel}
            </p>
          </div>
        </div>
      )}

      {/* Tour progress bar (bottom) */}
      {isTouring && (
        <div className="absolute bottom-0 left-0 right-0 z-20 h-1">
          <div
            className="h-full bg-red-400 transition-[width] duration-100 ease-linear"
            style={{ width: `${Math.min(tourProgress * 100, 100)}%` }}
          />
        </div>
      )}

      {/* Mode legend (bottom-left) */}
      {(commutes.length > 0 || flightRoutes.length > 0) && !isTouring && (
        <div className="absolute bottom-4 left-4 z-20 bg-carbon/80 border border-cyan/90 rounded-xl px-3 py-2 flex flex-wrap items-center gap-3 pointer-events-none">
          {Array.from(new Set(commutes.map((c) => c.travel_mode))).map((mode) => {
            const Icon =
              mode === 'WALK' ? Footprints
                : mode === 'BICYCLE' || mode === 'TWO_WHEELER' ? Bike
                  : mode === 'TRANSIT' ? Train
                    : Car;
            return (
              <div key={mode} className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider">
                <div className="w-4 h-[3px] rounded-full" style={{ background: MODE_COLOR[mode] || '#0891b2' }} />
                <Icon className="w-3 h-3 text-white/70" />
                <span className="text-white font-semibold">{mode.replace('_', ' ')}</span>
              </div>
            );
          })}
          {flightRoutes.length > 0 && (
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider">
              <div className="w-4 h-[3px] rounded-full" style={{ background: MODE_COLOR.FLIGHT }} />
              <Plane className="w-3 h-3 text-white/70" />
              <span className="text-white font-semibold">FLIGHT</span>
            </div>
          )}
        </div>
      )}

      {pins.length === 0 && commutes.length === 0 && (
        <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none">
          <div className="bg-black/70 backdrop-blur-md border border-white/10 rounded-2xl px-5 py-4 text-center">
            <p className="text-sm text-white/70 font-semibold">No locations yet for this day</p>
            <p className="text-xs text-white/40 mt-1">Events with coordinates will appear here as they generate.</p>
          </div>
        </div>
      )}
    </div>
  );
}
