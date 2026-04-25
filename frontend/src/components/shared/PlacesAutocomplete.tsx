import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { createPortal } from 'react-dom';
import { Search, Loader2 } from 'lucide-react';
import { GOOGLE_MAPS_API_KEY } from '../../apis/config';
import { logRateLimitBlock } from '../../utils/clientLog';
import { checkSkuQuota, trackClientSku } from '../../utils/rateLimiter';

// ─── Types ────────────────────────────────────────────────────

type AddressComponent = {
  longText: string;
  shortText: string;
  types: string[];
};

type Suggestion = {
  placeId: string;
  mainText: string;
  secondaryText: string;
};

export type ParsedPlace = {
  city: string;
  state: string;
  country: string;
  lat: number;
  lng: number;
};

type PlacesAutocompleteProps = {
  placeholder?: string;
  onPlaceChange: (place: ParsedPlace) => void;
  className?: string;
};

export type PlacesAutocompleteHandle = {
  clear: () => void;
  focus: () => void;
};

// ─── Endpoints ────────────────────────────────────────────────

const AUTOCOMPLETE_URL = 'https://places.googleapis.com/v1/places:autocomplete';
const DETAILS_URL = 'https://places.googleapis.com/v1/places';
// Essentials tier — no displayName. City name is taken from the autocomplete
// suggestion's `structuredFormat.mainText.text` (free within the session).
const DETAILS_FIELD_MASK = 'location,addressComponents';

// ─── Session token helpers ────────────────────────────────────

const newSessionToken = (): string => {
  const c = (typeof crypto !== 'undefined' ? crypto : undefined) as Crypto | undefined;
  if (c?.randomUUID) return c.randomUUID();
  // Fallback: RFC4122-ish v4
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (ch) => {
    const r = (Math.random() * 16) | 0;
    const v = ch === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

// ─── Parsing ──────────────────────────────────────────────────

const parseAddress = (
  components: AddressComponent[] | undefined,
): { city: string; state: string; country: string } => {
  let city = '';
  let state = '';
  let country = '';
  for (const c of components ?? []) {
    const t = c.types || [];
    if (!city && (t.includes('locality') || t.includes('postal_town'))) city = c.longText;
    if (!state && t.includes('administrative_area_level_1')) state = c.shortText;
    if (!country && t.includes('country')) country = c.longText;
  }
  return { city, state, country };
};

// ─── Component ────────────────────────────────────────────────

const PlacesAutocomplete = forwardRef<PlacesAutocompleteHandle, PlacesAutocompleteProps>(
  ({ placeholder = 'Search for a place', onPlaceChange, className = '' }, ref) => {
    const [query, setQuery] = useState('');
    const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
    const [isOpen, setIsOpen] = useState(false);
    const [activeIdx, setActiveIdx] = useState(-1);
    const [isFetching, setIsFetching] = useState(false);
    const [isResolving, setIsResolving] = useState(false);
    const [menuRect, setMenuRect] = useState<{ top: number; left: number; width: number } | null>(
      null,
    );

    const inputRef = useRef<HTMLInputElement>(null);
    const shellRef = useRef<HTMLDivElement>(null);
    const menuRef = useRef<HTMLDivElement>(null);
    const sessionRef = useRef<string>(newSessionToken());
    const debounceRef = useRef<number | null>(null);
    const abortRef = useRef<AbortController | null>(null);
    const reqIdRef = useRef(0);
    const skipNextFetchRef = useRef(false);
    // Once the keystroke quota goes red, freeze further autocomplete fetches
    // for the rest of the page lifetime — the next call would still bill.
    const keystrokeQuotaExhaustedRef = useRef(false);
    // Pending keystrokes for the *current* session token. Google credits these
    // back on a successful Place Details call within the same session, so we
    // hold them locally and only commit on session abandonment. See
    // `flushPendingKeystrokes` and `selectSuggestion` for the two outcomes.
    const pendingKeystrokesRef = useRef(0);

    const flushPendingKeystrokes = useCallback(() => {
      const n = pendingKeystrokesRef.current;
      if (n <= 0) return;
      pendingKeystrokesRef.current = 0;
      void trackClientSku('autocomplete_requests', n);
    }, []);

    useImperativeHandle(ref, () => ({
      clear: () => {
        // External clear without a selection ⇒ session is abandoned. Commit
        // its keystrokes before rotating the token.
        flushPendingKeystrokes();
        setQuery('');
        setSuggestions([]);
        setIsOpen(false);
        setActiveIdx(-1);
        sessionRef.current = newSessionToken();
      },
      focus: () => inputRef.current?.focus(),
    }));

    // Fetch autocomplete suggestions (debounced)
    const fetchSuggestions = useCallback(async (input: string) => {
      if (!input.trim()) {
        setSuggestions([]);
        setIsOpen(false);
        return;
      }

      // Hard stop once the quota has been exhausted in this session — every
      // additional keystroke would still bill Google.
      if (keystrokeQuotaExhaustedRef.current) {
        setSuggestions([]);
        setIsOpen(false);
        return;
      }

      // Pre-flight: bail out cheaply if we already know the budget is gone.
      // Read-only — we don't bill keystrokes upfront. Google will credit this
      // request on a successful Place Details call in the same session, and
      // charge for it only if the user abandons the session. We mirror that
      // by deferring the increment to one of those two outcomes.
      const preflight = await checkSkuQuota('autocomplete_requests');
      if (!preflight.allowed && !preflight.skipped) {
        keystrokeQuotaExhaustedRef.current = true;
        logRateLimitBlock(
          'autocomplete_requests',
          'Autocomplete keystroke blocked — autocomplete_requests quota exhausted',
          { current: preflight.current, limit: preflight.limit },
        );
        setSuggestions([]);
        setIsOpen(false);
        return;
      }

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const myReqId = ++reqIdRef.current;

      setIsFetching(true);
      try {
        const res = await fetch(AUTOCOMPLETE_URL, {
          method: 'POST',
          signal: controller.signal,
          headers: {
            'Content-Type': 'application/json',
            'X-Goog-Api-Key': GOOGLE_MAPS_API_KEY,
          },
          body: JSON.stringify({
            input,
            sessionToken: sessionRef.current,
          }),
        });
        if (!res.ok) throw new Error(`Autocomplete ${res.status}`);
        const data = await res.json();
        // Hold the keystroke locally instead of billing now. Committed on
        // session abandonment, discarded on a successful Place Details call.
        pendingKeystrokesRef.current += 1;
        if (myReqId !== reqIdRef.current) return; // a newer request has superseded
        const parsed: Suggestion[] = (data?.suggestions ?? [])
          .map((s: any) => s?.placePrediction)
          .filter(Boolean)
          .map((p: any) => ({
            placeId: p.placeId,
            mainText: p?.structuredFormat?.mainText?.text ?? p?.text?.text ?? '',
            secondaryText: p?.structuredFormat?.secondaryText?.text ?? '',
          }))
          .filter((s: Suggestion) => s.placeId && s.mainText);
        setSuggestions(parsed);
        setIsOpen(parsed.length > 0);
        setActiveIdx(parsed.length > 0 ? 0 : -1);
      } catch (err) {
        if ((err as any)?.name === 'AbortError') return;
        console.warn('[PlacesAutocomplete] autocomplete failed:', err);
      } finally {
        if (myReqId === reqIdRef.current) setIsFetching(false);
      }
    }, []);

    useEffect(() => {
      if (skipNextFetchRef.current) {
        skipNextFetchRef.current = false;
        return;
      }
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
      debounceRef.current = window.setTimeout(() => {
        fetchSuggestions(query);
      }, 200);
      return () => {
        if (debounceRef.current) window.clearTimeout(debounceRef.current);
      };
    }, [query, fetchSuggestions]);

    // Flush pending keystrokes when the component unmounts without a selection
    // (route change, parent collapses the picker, etc.) and when the page is
    // hidden (tab close / nav away). `pagehide` is best-effort — `sendBeacon`
    // would be more reliable on close, but trackClientSku's regular POST is
    // good enough for our soft cap.
    useEffect(() => {
      const onPageHide = () => flushPendingKeystrokes();
      window.addEventListener('pagehide', onPageHide);
      return () => {
        window.removeEventListener('pagehide', onPageHide);
        flushPendingKeystrokes();
      };
    }, [flushPendingKeystrokes]);

    // Click-outside handler — account for the portal-rendered menu too.
    useEffect(() => {
      const onDocClick = (e: MouseEvent) => {
        const target = e.target as Node;
        if (shellRef.current?.contains(target)) return;
        if (menuRef.current?.contains(target)) return;
        setIsOpen(false);
      };
      document.addEventListener('mousedown', onDocClick);
      return () => document.removeEventListener('mousedown', onDocClick);
    }, []);

    // Track the input's viewport rect so the portal-rendered dropdown aligns
    // with it across scroll/resize. Only active while open.
    useLayoutEffect(() => {
      if (!isOpen) return;
      const update = () => {
        const el = inputRef.current;
        if (!el) return;
        const r = el.getBoundingClientRect();
        setMenuRect({ top: r.bottom + 6, left: r.left, width: r.width });
      };
      update();
      window.addEventListener('scroll', update, true);
      window.addEventListener('resize', update);
      return () => {
        window.removeEventListener('scroll', update, true);
        window.removeEventListener('resize', update);
      };
    }, [isOpen]);

    // Select a suggestion → fetch Place Details (New) with session token
    const selectSuggestion = useCallback(
      async (s: Suggestion) => {
        setIsOpen(false);

        // Pre-check the Place Details Essentials budget — this is the
        // billable end of the session token. Block selection if exhausted.
        const preflight = await checkSkuQuota('places_place_details_essentials');
        if (!preflight.allowed && !preflight.skipped) {
          console.warn(
            '[PlacesAutocomplete] place_details_essentials quota exhausted — selection blocked',
          );
          logRateLimitBlock(
            'places_place_details_essentials',
            'Place selection blocked — places_place_details_essentials quota exhausted',
            { current: preflight.current, limit: preflight.limit },
          );
          return;
        }

        setIsResolving(true);
        const tokenAtSelection = sessionRef.current;
        try {
          const url = `${DETAILS_URL}/${encodeURIComponent(s.placeId)}?sessionToken=${encodeURIComponent(tokenAtSelection)}`;
          const res = await fetch(url, {
            headers: {
              'X-Goog-Api-Key': GOOGLE_MAPS_API_KEY,
              'X-Goog-FieldMask': DETAILS_FIELD_MASK,
            },
          });
          if (!res.ok) throw new Error(`Details ${res.status}`);
          const data = await res.json();
          // Place Details billed by Google → also closes the session and
          // credits all autocomplete keystrokes inside it. Mirror both:
          //   - bill places_place_details_essentials (1)
          //   - bill autocomplete_session_usage (1) — only completed sessions
          //     count as "used", per the user spec
          //   - discard pending keystrokes (Google credits them)
          void trackClientSku('places_place_details_essentials', 1);
          void trackClientSku('autocomplete_session_usage', 1);
          pendingKeystrokesRef.current = 0;
          const lat = data?.location?.latitude;
          const lng = data?.location?.longitude;
          if (typeof lat !== 'number' || typeof lng !== 'number') {
            throw new Error('Missing coordinates in Place Details response');
          }
          const { city, state, country } = parseAddress(data?.addressComponents);
          // Show the selected suggestion in the input. Callers that need the
          // box cleared (e.g. multi-hop destination picker) should call the
          // imperative `clear()` handle from their onPlaceChange callback.
          skipNextFetchRef.current = true;
          setQuery(s.mainText);
          setSuggestions([]);
          onPlaceChange({
            city: city || s.mainText,
            state,
            country,
            lat,
            lng,
          });
        } catch (err) {
          console.warn('[PlacesAutocomplete] details failed:', err);
          // Place Details failed → session ends without a billable close,
          // so Google will charge for the keystrokes after all. Commit them.
          flushPendingKeystrokes();
        } finally {
          setIsResolving(false);
          // End of session — rotate token for the next search.
          sessionRef.current = newSessionToken();
        }
      },
      [onPlaceChange, flushPendingKeystrokes],
    );

    const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (!isOpen || suggestions.length === 0) {
        if (e.key === 'ArrowDown' && suggestions.length > 0) {
          setIsOpen(true);
          e.preventDefault();
        }
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIdx((i) => (i + 1) % suggestions.length);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIdx((i) => (i - 1 + suggestions.length) % suggestions.length);
      } else if (e.key === 'Enter') {
        if (activeIdx >= 0 && activeIdx < suggestions.length) {
          e.preventDefault();
          selectSuggestion(suggestions[activeIdx]);
        }
      } else if (e.key === 'Escape') {
        setIsOpen(false);
      }
    };

    const showSpinner = useMemo(() => isFetching || isResolving, [isFetching, isResolving]);

    return (
      <div ref={shellRef} className={`relative ${className}`}>
        <div className="relative">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-white/40">
            <Search size={16} />
          </span>
          <input
            ref={inputRef}
            type="text"
            value={query}
            placeholder={placeholder}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => suggestions.length > 0 && setIsOpen(true)}
            onKeyDown={onKeyDown}
            autoComplete="off"
            spellCheck={false}
            className="w-full rounded-xl border border-white/10 bg-white/[0.03] pl-10 pr-10 py-3 text-sm text-white/90 placeholder:text-white/35 outline-none transition-colors focus:border-cyan/40 focus:shadow-[0_0_0_1px_rgba(102,252,241,0.2)]"
          />
          {showSpinner && (
            <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-cyan/70">
              <Loader2 size={16} className="animate-spin" />
            </span>
          )}
        </div>

        {isOpen && suggestions.length > 0 && menuRect &&
          createPortal(
            <div
              ref={menuRef}
              style={{
                position: 'fixed',
                top: menuRect.top,
                left: menuRect.left,
                width: menuRect.width,
                zIndex: 9999,
              }}
              className="overflow-hidden rounded-xl border border-white/10 bg-[rgba(11,12,16,0.95)] backdrop-blur-xl shadow-xl"
            >
              <ul role="listbox" className="max-h-72 overflow-y-auto">
                {suggestions.map((s, idx) => (
                  <li
                    key={s.placeId}
                    role="option"
                    aria-selected={idx === activeIdx}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      selectSuggestion(s);
                    }}
                    onMouseEnter={() => setActiveIdx(idx)}
                    className={`cursor-pointer px-4 py-2.5 text-sm transition-colors ${idx === activeIdx
                      ? 'bg-white/[0.06] text-white'
                      : 'text-white/70 hover:bg-white/[0.04]'
                      }`}
                  >
                    <div className="font-medium">{s.mainText}</div>
                    {s.secondaryText && (
                      <div className="text-xs text-white/40">{s.secondaryText}</div>
                    )}
                  </li>
                ))}
              </ul>
            </div>,
            document.body,
          )}
      </div>
    );
  },
);

PlacesAutocomplete.displayName = 'PlacesAutocomplete';

export default PlacesAutocomplete;
