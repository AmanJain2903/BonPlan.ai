import { useEffect, useRef } from 'react';
import { feature } from 'topojson-client';
import type { Topology } from 'topojson-specification';
import worldData from 'world-atlas/countries-110m.json';
import { airports } from '../../data/airports';

interface Airport { code: string; lat: number; lng: number }
interface Flight {
  from: Airport;
  to: Airport;
  startTime: number;
  duration: number;
  arriveTriggered: boolean;
}
interface Pin { airport: Airport; startTime: number }

const AIRPORTS: Airport[] = airports;

const SPAWN_MS = 2200;
const FLIGHT_MIN = 4500;
const FLIGHT_MAX = 7500;
const PIN_MS = 3200;
const MAX_FLIGHTS = 8;

const LAT_MIN = -58;
const LAT_MAX = 78;
const LAT_RANGE = LAT_MAX - LAT_MIN;
const MAP_ASPECT = 360 / LAT_RANGE;

function qBez(t: number, a: number, b: number, c: number) {
  return (1 - t) ** 2 * a + 2 * (1 - t) * t * b + t ** 2 * c;
}

function pickPair(): [Airport, Airport] {
  for (;;) {
    const a = AIRPORTS[Math.floor(Math.random() * AIRPORTS.length)];
    const b = AIRPORTS[Math.floor(Math.random() * AIRPORTS.length)];
    if (a !== b && Math.abs(a.lng - b.lng) <= 160) return [a, b];
  }
}

function drawPlane(
  ctx: CanvasRenderingContext2D,
  x: number, y: number,
  angle: number,
  size: number,
  alpha: number,
) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(angle);
  ctx.fillStyle = `rgba(102,252,241,${alpha.toFixed(3)})`;
  ctx.beginPath();
  ctx.moveTo(size, 0);
  ctx.lineTo(-size * 0.4, -size * 0.65);
  ctx.lineTo(-size * 0.1, 0);
  ctx.lineTo(-size * 0.4, size * 0.65);
  ctx.closePath();
  ctx.fill();
  ctx.beginPath();
  ctx.moveTo(-size * 0.1, 0);
  ctx.lineTo(-size * 0.55, -size * 0.35);
  ctx.lineTo(-size * 0.45, 0);
  ctx.lineTo(-size * 0.55, size * 0.35);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

export default function WorldMapBackground() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const dpr = Math.min(window.devicePixelRatio, 2);
    const canvas = document.createElement('canvas');
    canvas.style.display = 'block';
    el.appendChild(canvas);
    const ctx = canvas.getContext('2d')!;

    const topo = worldData as unknown as Topology;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const countries = feature(topo, (topo.objects as any).countries) as any;

    let W = 0;
    let H = 0;
    const PAD = 20;
    const mapLayer = document.createElement('canvas');

    // Aspect-ratio-preserving viewport
    let mapW = 0;
    let mapH = 0;
    let offX = 0;
    let offY = 0;

    function computeViewport() {
      const canvasAspect = W / H;

      if (canvasAspect > MAP_ASPECT) {
        // Screen is wider than the map — fill width, overflow height
        mapW = W;
        mapH = mapW / MAP_ASPECT;
      } else {
        // Screen is taller than the map — fill height, overflow width
        mapH = H;
        mapW = mapH * MAP_ASPECT;
      }

      offX = (W - mapW) / 2;
      offY = (H - mapH) / 2;
    }

    function proj(lng: number, lat: number): [number, number] {
      const c = Math.max(LAT_MIN, Math.min(LAT_MAX, lat));
      return [
        offX + ((lng + 180) / 360) * mapW,
        offY + ((LAT_MAX - c) / LAT_RANGE) * mapH,
      ];
    }

    function bakeMap() {
      mapLayer.width = W * dpr;
      mapLayer.height = H * dpr;
      const mc = mapLayer.getContext('2d')!;
      mc.setTransform(dpr, 0, 0, dpr, 0, 0);

      mc.fillStyle = 'rgba(102,252,241,0.025)';
      mc.strokeStyle = 'rgba(102,252,241,0.10)';
      mc.lineWidth = 0.6;

      for (const feat of countries.features) {
        const g = feat.geometry;
        const polys: number[][][][] =
          g.type === 'Polygon'
            ? [g.coordinates]
            : g.type === 'MultiPolygon'
              ? g.coordinates
              : [];

        for (const rings of polys) {
          mc.beginPath();
          for (const ring of rings) {
            let prevLng = 0;

            for (let i = 0; i < ring.length; i++) {
              const lng = ring[i][0];
              const lat = ring[i][1];
              const [x, y] = proj(lng, lat);

              if (i === 0) {
                mc.moveTo(x, y);
              } else {
                if (Math.abs(lng - prevLng) > 180) {
                  mc.moveTo(x, y);
                } else {
                  mc.lineTo(x, y);
                }
              }
              prevLng = lng;
            }
            mc.closePath();
          }
          mc.fill('evenodd');
          mc.stroke();
        }
      }

      mc.fillStyle = 'rgba(102,252,241,0.06)';
      for (const a of AIRPORTS) {
        const [x, y] = proj(a.lng, a.lat);
        mc.beginPath();
        mc.arc(x, y, 1.5, 0, Math.PI * 2);
        mc.fill();
      }
    }

    const isMobile = () => window.innerWidth < 768;

    function resize() {
      W = el!.clientWidth;
      H = el!.clientHeight;
      canvas.width = W * dpr;
      canvas.height = H * dpr;
      canvas.style.width = W + 'px';
      canvas.style.height = H + 'px';
      computeViewport();
      bakeMap();
    }

    const flights: Flight[] = [];
    const pins: Pin[] = [];
    let lastSpawn = 0;
    let started = false;

    function spawnFlight(now: number) {
      const [from, to] = pickPair();
      flights.push({
        from, to,
        startTime: now,
        duration: FLIGHT_MIN + Math.random() * (FLIGHT_MAX - FLIGHT_MIN),
        arriveTriggered: false,
      });
      pins.push({ airport: from, startTime: now });
    }

    function tick(now: number) {
      if (!started) {
        started = true;
        lastSpawn = now;
        for (let i = 0; i < 3; i++) spawnFlight(now - i * 1400);
      }

      if (now - lastSpawn > SPAWN_MS && flights.length < MAX_FLIGHTS) {
        spawnFlight(now);
        lastSpawn = now;
      }

      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(mapLayer, 0, 0);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      // Flights
      for (let i = flights.length - 1; i >= 0; i--) {
        const fl = flights[i];
        const t = (now - fl.startTime) / fl.duration;
        if (t > 1.4) { flights.splice(i, 1); continue; }

        const [x0, y0] = proj(fl.from.lng, fl.from.lat);
        const [x1, y1] = proj(fl.to.lng, fl.to.lat);
        const mx = (x0 + x1) / 2;
        const my = (y0 + y1) / 2;
        const d = Math.hypot(x1 - x0, y1 - y0);
        const cpX = mx;
        const cpY = my - Math.min(d * 0.35, 110);
        const fade = Math.min(1, (1.4 - t) / 0.4);

        ctx.strokeStyle = `rgba(102,252,241,${(0.04 * fade).toFixed(3)})`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x0, y0);
        ctx.quadraticCurveTo(cpX, cpY, x1, y1);
        ctx.stroke();

        if (t <= 1) {
          const segs = 50;
          const headSeg = Math.floor(t * segs);

          ctx.strokeStyle = `rgba(102,252,241,${(0.10 * fade).toFixed(3)})`;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(x0, y0);
          for (let s = 1; s <= headSeg; s++) {
            ctx.lineTo(qBez(s / segs, x0, cpX, x1), qBez(s / segs, y0, cpY, y1));
          }
          ctx.stroke();

          const dx = qBez(t, x0, cpX, x1);
          const dy = qBez(t, y0, cpY, y1);
          const tdx = 2 * (1 - t) * (cpX - x0) + 2 * t * (x1 - cpX);
          const tdy = 2 * (1 - t) * (cpY - y0) + 2 * t * (y1 - cpY);
          const angle = Math.atan2(tdy, tdx);

          const glow = ctx.createRadialGradient(dx, dy, 0, dx, dy, 14);
          glow.addColorStop(0, `rgba(102,252,241,${(0.4 * fade).toFixed(3)})`);
          glow.addColorStop(1, 'rgba(102,252,241,0)');
          ctx.fillStyle = glow;
          ctx.beginPath();
          ctx.arc(dx, dy, 14, 0, Math.PI * 2);
          ctx.fill();

          drawPlane(ctx, dx, dy, angle, 7, 0.9 * fade);

          if (t > 0.85 && !fl.arriveTriggered) {
            fl.arriveTriggered = true;
            pins.push({ airport: fl.to, startTime: now });
          }
        }
      }

      // Pins
      for (let i = pins.length - 1; i >= 0; i--) {
        const p = pins[i];
        const age = now - p.startTime;
        if (age > PIN_MS) { pins.splice(i, 1); continue; }

        const pr = age / PIN_MS;
        const aIn = Math.min(1, age / 250);
        const aOut = pr > 0.7 ? 1 - (pr - 0.7) / 0.3 : 1;
        const alpha = aIn * aOut;

        const [px, py] = proj(p.airport.lng, p.airport.lat);

        ctx.strokeStyle = `rgba(102,252,241,${(alpha * 0.35 * (1 - pr)).toFixed(3)})`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(px, py, 4 + pr * 18, 0, Math.PI * 2);
        ctx.stroke();

        ctx.strokeStyle = `rgba(102,252,241,${(alpha * 0.15 * (1 - pr)).toFixed(3)})`;
        ctx.lineWidth = 0.5;
        ctx.beginPath();
        ctx.arc(px, py, 4 + pr * 28, 0, Math.PI * 2);
        ctx.stroke();

        const sc = age < 180 ? 0.5 + (age / 180) * 0.7 : age < 300 ? 1.2 - ((age - 180) / 120) * 0.2 : 1;
        ctx.fillStyle = `rgba(102,252,241,${(alpha * 0.8).toFixed(3)})`;
        ctx.beginPath();
        ctx.arc(px, py, 3 * sc, 0, Math.PI * 2);
        ctx.fill();

        ctx.font = `bold 9px "SF Mono","Fira Code","Cascadia Code",monospace`;
        ctx.textAlign = 'center';
        ctx.shadowColor = 'rgba(102,252,241,0.5)';
        ctx.shadowBlur = 4;
        ctx.fillStyle = `rgba(102,252,241,${(alpha * 0.9).toFixed(3)})`;
        ctx.fillText(p.airport.code, px, py - 10);
        ctx.shadowColor = 'transparent';
        ctx.shadowBlur = 0;
      }

      // Vignette
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      const v = ctx.createRadialGradient(
        canvas.width / 2, canvas.height / 2,
        Math.min(canvas.width, canvas.height) * 0.28,
        canvas.width / 2, canvas.height / 2,
        Math.max(canvas.width, canvas.height) * 0.68,
      );
      v.addColorStop(0, 'rgba(11,12,16,0)');
      v.addColorStop(1, 'rgba(11,12,16,0.85)');
      ctx.fillStyle = v;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      animId = requestAnimationFrame(tick);
    }

    resize();
    let animId = requestAnimationFrame(tick);

    const onResize = () => resize();
    window.addEventListener('resize', onResize);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', onResize);
      if (el.contains(canvas)) el.removeChild(canvas);
    };
  }, []);


  return <div ref={ref} className={`fixed inset-0 z-0 pointer-events-none scale-110 translate-x-[-5%] translate-y-[5%] opacity-75 from-white/1 via-black/50 to-white/1 bg-gradient-to-r`} />;
}
