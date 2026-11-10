/**
 * Episode 005 motion layer: atmosphere over the paintings (embers, mist, rays, stars, sea glint, storm, glow, dust)
 * and the Short-only layouts for landscape pictures (the photo print and the stacked then/now).
 * All particles are seeded, so every render of a shot is identical.
 */
import React from 'react';
import {AbsoluteFill, Img, interpolate, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig, Easing} from 'remotion';
import {CONCH, DEV, GOLD, INK, LAT, Pic, RED} from './kit';

export type Fx = 'embers' | 'mist' | 'rays' | 'stars' | 'sea' | 'storm' | 'glow' | 'dust' | 'laser';
const IMG = (n: string) => staticFile(`episodes/005-ramayana-evidence/img/${n}.jpg`);
const ease = Easing.bezier(0.45, 0, 0.55, 1);

const rng = (seed: number) => () => {
  seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};

/** Atmosphere over a painting. `at` places the glow (0..1 of the frame). */
export const Atmos: React.FC<{fx: Fx[]; seed?: number; at?: [number, number]}> = ({fx, seed = 7, at = [0.5, 0.4]}) => {
  const f = useCurrentFrame();
  const {width: W, height: H, fps} = useVideoConfig();
  const t = f / fps;
  const R = rng(seed);
  const parts: React.ReactNode[] = [];
  if (fx.includes('rays')) {
    const sw = Math.sin(t * 0.5) * 6;
    parts.push(
      <AbsoluteFill key="rays" style={{mixBlendMode: 'screen', opacity: 0.55,
        background: `repeating-conic-gradient(from ${200 + sw}deg at 15% -10%, rgba(255,214,140,0.0) 0deg, rgba(255,214,140,0.22) 4deg, rgba(255,214,140,0.0) 9deg)`,
        maskImage: 'linear-gradient(180deg, #000 0%, transparent 85%)', WebkitMaskImage: 'linear-gradient(180deg, #000 0%, transparent 85%)'}} />,
    );
  }
  if (fx.includes('mist')) {
    for (let i = 0; i < 4; i++) {
      const y = H * (0.25 + 0.18 * i + 0.05 * R()), sp = 18 + 22 * R(), x0 = R() * W;
      const x = ((x0 + t * sp * (i % 2 ? 1 : -1)) % (W * 1.6)) - W * 0.3;
      parts.push(<div key={`m${i}`} style={{position: 'absolute', left: x - W * 0.5, top: y - H * 0.08, width: W * 1.1, height: H * 0.16,
        background: 'radial-gradient(ellipse at center, rgba(246,239,220,0.30), rgba(246,239,220,0) 70%)', filter: 'blur(10px)'}} />);
    }
  }
  if (fx.includes('stars')) {
    for (let i = 0; i < 70; i++) {
      const x = R() * W, y = R() * H * 0.45, ph = R() * 6.28, s = 2 + R() * 3;
      const o = 0.35 + 0.65 * Math.abs(Math.sin(t * (1 + R() * 2) + ph));
      parts.push(<div key={`s${i}`} style={{position: 'absolute', left: x, top: y, width: s, height: s, borderRadius: s,
        background: '#fff7da', opacity: o, boxShadow: `0 0 ${s * 3}px #fff2c0`}} />);
    }
  }
  if (fx.includes('embers') || fx.includes('dust')) {
    const n = fx.includes('embers') ? 46 : 36;
    for (let i = 0; i < n; i++) {
      const ember = fx.includes('embers') && i % 3 !== 0;
      const x0 = R() * W, sp = (ember ? 60 : 14) + R() * (ember ? 90 : 20), ph = R() * 1000, s = ember ? 3 + R() * 5 : 2 + R() * 3;
      const y = H - (((t * sp + ph) % (H * 1.1)));
      const x = x0 + Math.sin(t * (0.6 + R()) + ph) * (ember ? 40 : 25);
      const o = ember ? 0.5 + 0.5 * Math.sin(t * 7 + ph) : 0.45;
      parts.push(<div key={`e${i}`} style={{position: 'absolute', left: x, top: y, width: s, height: s, borderRadius: s,
        background: ember ? '#ffb347' : '#fff3d0', opacity: o, boxShadow: ember ? `0 0 ${s * 4}px #ff7a1a` : `0 0 ${s * 2}px #fff3d0`}} />);
    }
  }
  if (fx.includes('sea')) {
    for (let i = 0; i < 40; i++) {
      const y = H * (0.68 + 0.3 * R()), x0 = R() * W, len = 20 + R() * 50, ph = R() * 6.28;
      const x = (x0 + t * 25 * (0.5 + R())) % W;
      parts.push(<div key={`g${i}`} style={{position: 'absolute', left: x, top: y, width: len, height: 3, borderRadius: 2,
        background: '#ffffff', opacity: 0.5 * Math.max(0, Math.sin(t * 2.2 + ph))}} />);
    }
  }
  if (fx.includes('storm')) {
    for (let i = 0; i < 90; i++) {
      const x0 = R() * W * 1.3, sp = 900 + R() * 600, ph = R() * 2000, len = 30 + R() * 40;
      const y = ((t * sp + ph) % (H + 100)) - 50, x = x0 - y * 0.35;
      parts.push(<div key={`r${i}`} style={{position: 'absolute', left: x, top: y, width: 2, height: len, background: 'rgba(220,230,255,0.45)',
        transform: 'rotate(20deg)'}} />);
    }
    const flash = [1.2, 3.9, 6.1].some((k) => t > k && t < k + 0.12) ? 0.55 : 0;
    parts.push(<AbsoluteFill key="flash" style={{background: '#dfe8ff', opacity: flash, mixBlendMode: 'screen'}} />);
  }
  if (fx.includes('glow')) {
    const p = 0.6 + 0.4 * Math.sin(t * 2.4);
    parts.push(<div key="glow" style={{position: 'absolute', left: at[0] * W - W * 0.45, top: at[1] * H - W * 0.45, width: W * 0.9, height: W * 0.9,
      borderRadius: '50%', background: 'radial-gradient(circle, rgba(255,230,140,0.55), rgba(255,200,80,0) 60%)', opacity: p, mixBlendMode: 'screen'}} />);
    for (let i = 0; i < 24; i++) {
      const a = R() * 6.28, r0 = R() * W * 0.25, sp = 20 + R() * 40;
      const r = (r0 + t * sp) % (W * 0.35), o = 1 - r / (W * 0.35);
      parts.push(<div key={`k${i}`} style={{position: 'absolute', left: at[0] * W + Math.cos(a) * r, top: at[1] * H + Math.sin(a) * r,
        width: 5, height: 5, borderRadius: 5, background: '#fff6c8', opacity: o, boxShadow: '0 0 12px #ffe27a'}} />);
    }
  }
  if (fx.includes('laser')) {
    // ICESat-2 style: green laser pulses fanning down from the top, each leaving a dot where it meets the sea floor.
    const N = 6;
    for (let i = 0; i < N; i++) {
      const x1 = W * (0.2 + 0.6 * (i / (N - 1))), y1 = H * (0.42 + 0.25 * Math.sin(i * 1.7) ** 2);
      const ph = (t * 2.2 + i * 0.37) % 1;
      parts.push(<svg key={`l${i}`} width={W} height={H} style={{position: 'absolute'}}>
        <line x1={W / 2} y1={-20} x2={x1} y2={y1} stroke="#7dff7a" strokeWidth={3} opacity={0.35} />
        <line x1={W / 2 + (x1 - W / 2) * ph} y1={-20 + (y1 + 20) * ph} x2={W / 2 + (x1 - W / 2) * Math.min(1, ph + 0.08)} y2={-20 + (y1 + 20) * Math.min(1, ph + 0.08)}
          stroke="#c8ffc4" strokeWidth={7} strokeLinecap="round" />
        <circle cx={x1} cy={y1} r={10 + 14 * ph} fill="none" stroke="#7dff7a" strokeWidth={3} opacity={1 - ph} />
        <circle cx={x1} cy={y1} r={5} fill="#c8ffc4" />
      </svg>);
    }
    parts.push(<div key="sat" style={{position: 'absolute', left: W / 2 - 34, top: -6, width: 68, height: 30, background: '#d9dde6', borderRadius: 4,
      boxShadow: '0 0 20px #7dff7a', border: '2px solid #1b2550'}} />);
  }
  // A soft vignette on every painting keeps the eye in the middle and the captions readable.
  parts.push(<AbsoluteFill key="vig" style={{background: 'radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,0.45) 100%)'}} />);
  return <AbsoluteFill style={{pointerEvents: 'none'}}>{parts}</AbsoluteFill>;
};

const PinIcon: React.FC<{s: number}> = ({s}) => (
  <svg width={s} height={s * 1.3} viewBox="0 0 20 26" style={{marginRight: 12, flex: 'none'}}>
    <path d="M10 0 C4.5 0 0 4.4 0 9.8 C0 17 10 26 10 26 C10 26 20 17 20 9.8 C20 4.4 15.5 0 10 0 Z" fill={RED} stroke={CONCH} strokeWidth={1.6} />
    <circle cx={10} cy={9.6} r={3.6} fill={GOLD} />
  </svg>
);

/** Place label chip with a map pin. */
export const PlaceChip: React.FC<{text: string; o?: number; size?: number}> = ({text, o = 1, size = 46}) => (
  <div style={{display: 'inline-flex', alignItems: 'center', opacity: o, fontFamily: DEV, fontSize: size, fontWeight: 700, color: CONCH,
    background: 'rgba(18,12,10,0.78)', padding: '10px 28px 8px 18px', borderRadius: 50, border: `3px solid ${GOLD}`}}>
    <PinIcon s={size * 0.7} />{text}
  </div>
);

/**
 * Short layout for a real photo: the whole photo as a print at full width, over a blurred copy of itself,
 * with the place name above and the licence credit under it. Nothing important gets cropped away.
 */
export const PhotoCard: React.FC<{src: string; w: number; h: number; dur: number; place?: string; credit?: string;
  a?: [number, number, number]; b?: [number, number, number]}> = ({src, w, h, dur, place, credit, a = [0.5, 0.45, 1], b = [0.5, 0.45, 1.07]}) => {
  const f = useCurrentFrame();
  const {width: W, height: H} = useVideoConfig();
  const inP = interpolate(f, [0, 16], [0, 1], {extrapolateRight: 'clamp', easing: ease});
  const p = ease(Math.min(1, Math.max(0, f / Math.max(1, dur))));
  const maxW = W - 72, maxH = H * (h > w ? 0.42 : 0.56); // tall photos stay clear of the big text below
  const s = Math.min(maxW / w, maxH / h);
  const cw = w * s, ch = h * s;
  const top = H * 0.47 - ch / 2;
  // Zoom inside the print towards a focus point (cx, cy as fractions of the photo).
  const z = a[2] + (b[2] - a[2]) * p, fx = a[0] + (b[0] - a[0]) * p, fy = a[1] + (b[1] - a[1]) * p;
  return (
    <AbsoluteFill>
      <Img src={IMG(src)} style={{position: 'absolute', left: -W * 0.15, top: -H * 0.05, width: W * 1.3, height: H * 1.1, objectFit: 'cover',
        filter: 'blur(36px) brightness(0.42) saturate(1.2)', transform: `scale(${1.05 + 0.05 * p})`}} />
      <div style={{position: 'absolute', left: (W - cw) / 2 - 10, top: top - 10, width: cw + 20, height: ch + 20, background: CONCH,
        borderRadius: 10, boxShadow: '0 24px 60px rgba(0,0,0,0.65)', opacity: inP,
        transform: `translateY(${(1 - inP) * 60}px) rotate(${(1 - inP) * -2.5 + Math.sin(f / 50) * 0.35}deg) scale(${0.94 + 0.06 * inP})`}}>
        <div style={{position: 'absolute', left: 10, top: 10, width: cw, height: ch, overflow: 'hidden', borderRadius: 4}}>
          <Img src={IMG(src)} style={{width: cw, height: ch, transform: `scale(${z})`, transformOrigin: `${fx * 100}% ${fy * 100}%`}} />
        </div>
      </div>
      {place && (
        <div style={{position: 'absolute', top: top - 110, left: 0, right: 0, textAlign: 'center',
          opacity: interpolate(f, [8, 22], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}}>
          <PlaceChip text={place} />
        </div>
      )}
      {credit && (
        <div style={{position: 'absolute', top: top + ch + 26, left: 40, right: 40, textAlign: 'center', fontFamily: LAT, fontSize: 26,
          color: 'rgba(246,239,220,0.8)', opacity: inP}}>{credit}</div>
      )}
    </AbsoluteFill>
  );
};

/**
 * Short layout for then/now: the painting on top, the photo below, both whole, sliding in one after the other,
 * with the gold "तब" / "आज" labels on the seam.
 */
export const StackThenNow: React.FC<{then: [string, number, number]; now: [string, number, number]; dur: number; at: number;
  credit?: string; place?: string}> = ({then, now, dur, at, credit, place}) => {
  const f = useCurrentFrame();
  const {width: W, height: H} = useVideoConfig();
  const p = ease(Math.min(1, Math.max(0, f / Math.max(1, dur))));
  const a = interpolate(f, [0, 18], [0, 1], {extrapolateRight: 'clamp', easing: ease});
  const b = interpolate(f, [at, at + 18], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
  const panel = (src: string, w: number, h: number, y: number, k: number, from: number, z: number) => {
    const ph = H * 0.36, s = Math.max(W / w, ph / h) * z;
    return (
      <div style={{position: 'absolute', left: 0, top: y, width: W, height: ph, overflow: 'hidden', opacity: k,
        transform: `translateX(${(1 - k) * from}px)`, borderTop: `6px solid ${GOLD}`, borderBottom: `6px solid ${GOLD}`}}>
        <Img src={IMG(src)} style={{position: 'absolute', left: (W - w * s) / 2, top: (ph - h * s) / 2, width: w * s, height: h * s}} />
      </div>
    );
  };
  const lab = (t: string, y: number, bg: string, k: number) => (
    <div style={{position: 'absolute', top: y, left: 40, opacity: k, fontFamily: DEV, fontSize: 50, fontWeight: 700, color: CONCH,
      background: bg, padding: '6px 26px', borderRadius: 12, border: `3px solid ${GOLD}`}}>{t}</div>
  );
  const y1 = H * 0.13, y2 = H * 0.13 + H * 0.36 + 30;
  return (
    <AbsoluteFill style={{background: INK}}>
      <Img src={IMG(then[0])} style={{position: 'absolute', width: W, height: H, objectFit: 'cover', filter: 'blur(40px) brightness(0.35)'}} />
      {panel(then[0], then[1], then[2], y1, a, -W, 1.02 + 0.06 * p)}
      {panel(now[0], now[1], now[2], y2, b, W, 1.08 - 0.06 * p)}
      {lab('तब', y1 + 24, 'rgba(168,40,31,0.9)', a)}
      {lab('आज', y2 + 24, 'rgba(27,37,80,0.9)', b)}
      {place && <div style={{position: 'absolute', top: y2 + H * 0.36 + 30, left: 0, right: 0, textAlign: 'center', opacity: b}}><PlaceChip text={place} size={42} /></div>}
      {credit && <div style={{position: 'absolute', top: y2 + H * 0.36 + 120, left: 40, right: 40, textAlign: 'center', fontFamily: LAT,
        fontSize: 26, color: 'rgba(246,239,220,0.8)', opacity: b}}>{credit}</div>}
    </AbsoluteFill>
  );
};

/** A painting with motion: Ken Burns (in a Short, a wider sweep across the canvas) plus its atmosphere. */
export const Painting: React.FC<{src: string; w: number; h: number; dur: number; a?: [number, number, number]; b?: [number, number, number];
  fx?: Fx[]; seed?: number; glowAt?: [number, number]; flip?: boolean; clip?: string}> = ({src, w, h, dur, a = [0.5, 0.5, 1], b = [0.5, 0.5, 1.08], fx = [], seed, glowAt, flip, clip}) => {
  const {width: W, height: H} = useVideoConfig();
  const f = useCurrentFrame();
  if (clip) {
    // An AI-animated version of the painting (assets/clips): played once, cover-cropped, centred on `a`'s focus,
    // and held on its last frame if the line runs longer.
    const s = Math.max(W / w, H / h) * a[2];
    const x = Math.min(0, Math.max(W - w * s, W / 2 - a[0] * w * s)), y = Math.min(0, Math.max(H - h * s, H / 2 - a[1] * h * s));
    return (
      <AbsoluteFill>
        <OffthreadVideo src={staticFile(`episodes/005-ramayana-evidence/clips/${clip}.mp4`)} muted
          style={{position: 'absolute', left: x, top: y, width: w * s, height: h * s, transform: `scale(${1 + 0.04 * Math.min(1, f / Math.max(1, dur))})`}} />
        <Atmos fx={fx} seed={seed} at={glowAt} />
      </AbsoluteFill>
    );
  }
  let A = a, B = b;
  if (H > 1500 && Math.abs(b[0] - a[0]) < 0.2) {
    // Portrait shows about a third of a 16:9 painting: travel across it so the viewer sees the whole scene.
    const c = (a[0] + b[0]) / 2, d = flip ? -0.2 : 0.2;
    A = [Math.min(0.85, Math.max(0.15, c - d)), a[1], a[2]];
    B = [Math.min(0.85, Math.max(0.15, c + d)), b[1], b[2]];
  }
  return (
    <AbsoluteFill>
      <Pic src={src} w={w} h={h} dur={dur} a={A} b={B} />
      <Atmos fx={fx} seed={seed} at={glowAt} />
    </AbsoluteFill>
  );
};

/** Photo inset that pops up during a map tour. */
export const TourCard: React.FC<{src: string; w: number; h: number; name: string; t0: number; t1: number; credit?: string}> = ({src, w, h, name, t0, t1, credit}) => {
  const f = useCurrentFrame();
  const {width: W, height: H} = useVideoConfig();
  // Stops can be named only a few frames apart ("Panchavati, Chitrakoot"): keep the fade points in order.
  const end = Math.max(t1, t0 + 4), inE = Math.min(t0 + 10, t0 + (end - t0) / 2), outS = Math.max(inE + 1, end - 8);
  const k = interpolate(f, [t0, inE, outS, Math.max(outS + 1, end)], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
  if (k <= 0) return null;
  const portrait = H > W;
  const cw = portrait ? W * 0.62 : W * 0.3;
  const ch = Math.min(cw * (h / w), portrait ? H * 0.26 : H * 0.42);
  const cww = ch / (h / w) < cw ? ch / (h / w) : cw;
  const left = portrait ? (W - cww) / 2 : W - cww - 70, top = portrait ? H * 0.64 : H * 0.18;
  return (
    <div style={{position: 'absolute', left: left - 8, top, width: cww + 16, opacity: k, transform: `translateY(${(1 - k) * 40}px) scale(${0.9 + 0.1 * k})`}}>
      <div style={{background: CONCH, padding: 8, borderRadius: 8, boxShadow: '0 16px 40px rgba(0,0,0,0.6)', width: cww, height: ch}}>
        <Img src={IMG(src)} style={{display: 'block', width: cww, height: ch, objectFit: 'cover'}} />
      </div>
      <div style={{marginTop: 14, textAlign: 'center', whiteSpace: 'nowrap', marginLeft: -200, marginRight: -200}}><PlaceChip text={name} size={40} /></div>
      {credit && <div style={{marginTop: 8, marginLeft: -200, marginRight: -200, textAlign: 'center', fontFamily: LAT, fontSize: 20, color: 'rgba(246,239,220,0.8)',
        textShadow: '0 1px 3px #000'}}>{credit}</div>}
    </div>
  );
};

/** Long video: chapter card, lower left, as each chapter begins. */
export const ChapterCard: React.FC<{n: number; title: string}> = ({n, title}) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, 14, 125, 150], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
  return (
    <div style={{position: 'absolute', left: 60, bottom: 110, opacity: o, transform: `translateX(${(1 - o) * -40}px)`}}>
      <div style={{fontFamily: DEV, fontSize: 30, color: GOLD, letterSpacing: 2, marginBottom: 6, textShadow: '0 2px 8px #000'}}>रामायण का मार्ग · भाग {n}/17</div>
      <div style={{fontFamily: DEV, fontSize: 64, fontWeight: 700, color: CONCH, background: 'rgba(18,12,10,0.72)', padding: '10px 30px 6px',
        borderLeft: `8px solid ${GOLD}`, borderRadius: 6}}>{title}</div>
    </div>
  );
};
