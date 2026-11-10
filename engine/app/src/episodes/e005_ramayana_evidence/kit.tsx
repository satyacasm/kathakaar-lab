/**
 * Episode 005 visual kit: "then" paintings and "now" photos, the flight map and the claim tags.
 * Everything is driven by a shot list (shots.ts) keyed to narration lines, so the same chapter renders
 * as a 1080x1920 Short and inside the 1920x1080 long video.
 */
import React from 'react';
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig, Easing} from 'remotion';
import MAP from './map_india.json';

export const DEV = 'Kohinoor Devanagari, Devanagari Sangam MN, Noto Sans Devanagari, sans-serif';
export const LAT = 'Georgia, "Times New Roman", serif';
export const GOLD = '#f2c14e', RED = '#a8281f', INK = '#120c0a', CONCH = '#f6efdc', INDIGO = '#1b2550';
const IMG = (n: string) => staticFile(`episodes/005-ramayana-evidence/img/${n}.jpg`);
const ease = Easing.bezier(0.45, 0, 0.55, 1);

type Focus = [number, number, number]; // cx, cy (0..1 of the image), zoom (1 = cover)

/** Ken Burns over a cover-cropped image: moves the focus point and zoom from `a` to `b` across `dur` frames. */
export const Pic: React.FC<{src: string; w: number; h: number; dur: number; a?: Focus; b?: Focus; t0?: number}> = ({
  src, w, h, dur, a = [0.5, 0.5, 1], b = [0.5, 0.5, 1.08], t0 = 0,
}) => {
  const f = useCurrentFrame() - t0;
  const {width: W, height: H} = useVideoConfig();
  const p = ease(Math.min(1, Math.max(0, f / Math.max(1, dur))));
  const cx = a[0] + (b[0] - a[0]) * p, cy = a[1] + (b[1] - a[1]) * p, z = a[2] + (b[2] - a[2]) * p;
  const s = Math.max(W / w, H / h) * z;
  // Keep the focus point centred but never show past the image edge.
  const x = Math.min(0, Math.max(W - w * s, W / 2 - cx * w * s));
  const y = Math.min(0, Math.max(H - h * s, H / 2 - cy * h * s));
  return <Img src={IMG(src)} style={{position: 'absolute', left: x, top: y, width: w * s, height: h * s}} />;
};

/** Small licence credit, bottom-left, for photos that need attribution. */
export const Credit: React.FC<{text?: string}> = ({text}) => {
  const {height: H} = useVideoConfig();
  if (!text) return null;
  return (
    <div style={{position: 'absolute', left: 24, bottom: H > 1500 ? 300 : 22, fontFamily: LAT, fontSize: 26,
      color: 'rgba(246,239,220,0.85)', textShadow: '0 1px 3px #000', maxWidth: '80%'}}>{text}</div>
  );
};

/** Diagonal gold-edged wipe from the painting (then) to the photo (now). `at` is the frame the wipe starts. */
export const Wipe: React.FC<{then: React.ReactNode; now: React.ReactNode; at: number; d?: number}> = ({then, now, at, d = 24}) => {
  const f = useCurrentFrame();
  const {width: W, height: H} = useVideoConfig();
  const p = interpolate(f, [at, at + d], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
  const span = W + H * 0.4, x = -H * 0.4 + p * (span + H * 0.4);
  const poly = `polygon(0 0, ${x + H * 0.4}px 0, ${x}px ${H}px, 0 ${H}px)`;
  return (
    <AbsoluteFill>
      {then}
      <AbsoluteFill style={{clipPath: poly}}>{now}</AbsoluteFill>
      {p > 0 && p < 1 && (
        <svg width={W} height={H} style={{position: 'absolute'}}>
          <line x1={x + H * 0.4} y1={0} x2={x} y2={H} stroke={GOLD} strokeWidth={10} />
        </svg>
      )}
    </AbsoluteFill>
  );
};

/** THEN / NOW corner labels during a wipe. */
export const ThenNow: React.FC<{at: number}> = ({at}) => {
  const f = useCurrentFrame();
  const {height: H} = useVideoConfig();
  const top = H > 1500 ? 260 : 40;
  const lab = (t: string, o: number, right: boolean) => (
    <div style={{position: 'absolute', top, [right ? 'right' : 'left']: 40, opacity: o, fontFamily: DEV, fontSize: 52,
      fontWeight: 700, color: CONCH, background: right ? 'rgba(27,37,80,0.85)' : 'rgba(168,40,31,0.85)',
      padding: '6px 26px', borderRadius: 12, border: `3px solid ${GOLD}`}}>{t}</div>
  );
  const o1 = interpolate(f, [0, 10, at + 6, at + 16], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const o2 = interpolate(f, [at + 10, at + 22], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <>{lab('तब', o1, false)}{lab('आज', o2, true)}</>;
};

export type TagKind = 'valmiki' | 'purana' | 'science' | 'belief' | 'history';
const TAGS: Record<TagKind, {t: string; bg: string}> = {
  valmiki: {t: 'वाल्मीकि ने लिखा', bg: RED},
  purana: {t: 'पुराणों के अनुसार', bg: '#7a3b12'},
  science: {t: 'विज्ञान · पुरातत्व', bg: '#1f5f4a'},
  history: {t: 'इतिहास', bg: '#5a4a2a'},
  belief: {t: 'मान्यता', bg: INDIGO},
};
/** The claim tag: every fact on screen says where it comes from. */
export const Tag: React.FC<{k: TagKind; from?: number}> = ({k, from = 0}) => {
  const f = useCurrentFrame() - from;
  const {width: W, height: H} = useVideoConfig();
  const o = interpolate(f, [0, 8], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const T = TAGS[k];
  return (
    <div style={{position: 'absolute', right: 36, bottom: H > 1500 ? 420 : 60, opacity: o,
      transform: `translateY(${(1 - o) * 20}px)`, fontFamily: DEV, fontSize: W > 1500 ? 40 : 44, color: CONCH,
      background: T.bg, padding: '8px 24px 6px', borderRadius: 40, border: `3px solid ${GOLD}`, boxShadow: '0 4px 16px rgba(0,0,0,0.5)'}}>
      {T.t}
    </div>
  );
};

/** Big on-screen text (a number, a name). */
export const BigText: React.FC<{text: string; sub?: string; from?: number; y?: number}> = ({text, sub, from = 0, y}) => {
  const f = useCurrentFrame() - from;
  const {height: H, width: W} = useVideoConfig();
  const o = interpolate(f, [0, 10], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <div style={{position: 'absolute', left: 0, right: 0, top: y ?? H * (H > W ? 0.69 : 0.62), textAlign: 'center', opacity: o,
      transform: `scale(${0.9 + 0.1 * o})`}}>
      <div style={{fontFamily: DEV, fontWeight: 700, fontSize: W > 1500 ? 96 : 96, color: GOLD,
        textShadow: '0 4px 18px rgba(0,0,0,0.9), 0 0 2px #000', padding: '0 40px', lineHeight: 1.25}}>{text}</div>
      {sub && <div style={{fontFamily: DEV, fontSize: W > 1500 ? 44 : 50, color: CONCH, textShadow: '0 2px 10px #000', marginTop: 8}}>{sub}</div>}
    </div>
  );
};

// ---------- the map ----------
type Cam = {lon: number; lat: number; z: number}; // z = how many map widths fit the frame (1 = whole India)
const WP = MAP.waypoints as unknown as Record<string, {lon: number; lat: number; xy: [number, number]}>;
const toXY = (lon: number, lat: number): [number, number] => {
  const [W0, , E0, N0] = MAP.bbox as number[];
  const k = 2000 / (E0 - W0);
  const merc = (l: number) => Math.log(Math.tan(Math.PI / 4 + (l * Math.PI) / 360));
  return [(lon - W0) * k, (merc(N0) - merc(lat)) * k * (180 / Math.PI)];
};
export const ROUTE = ['lanka', 'dhanushkodi', 'kishkindha', 'panchavati', 'agastya', 'chitrakoot', 'prayag', 'shringverpur', 'ayodhya'];
export const HI_NAME: Record<string, string> = {
  lanka: 'लंका', dhanushkodi: 'धनुषकोडि', rameswaram: 'रामेश्वरम', kishkindha: 'किष्किंधा', lepakshi: 'लेपाक्षी',
  panchavati: 'पंचवटी', agastya: 'अगस्त्य आश्रम', chitrakoot: 'चित्रकूट', anasuya: 'अनसूया आश्रम', prayag: 'प्रयाग',
  shringverpur: 'शृंगवेरपुर', ayodhya: 'अयोध्या', nandigram: 'नंदीग्राम', dronagiri: 'द्रोणागिरि', kailash: 'कैलास',
  talaimannar: 'तलैमन्नार', pamban: 'पंबन', ella: 'एल्ला', taked: 'टाकेड', jatayupara: 'जटायुपारा', akole: 'अकोले', nashik: 'नासिक',
};
const LEFT = new Set(['taked', 'lanka', 'chitrakoot', 'shringverpur', 'anasuya', 'dhanushkodi', 'pamban', 'agastya', 'kailash']);
const RIVER_HI: Record<string, string> = {ganga: 'गंगा', yamuna: 'यमुना', godavari: 'गोदावरी', sarayu: 'सरयू', tungabhadra: 'तुंगभद्रा'};

const RELIEF = staticFile('episodes/005-ramayana-evidence/img/map_relief.jpg');
const MAP_H = MAP.height as number;
// Physical features, labelled only when the whole subcontinent is in view.
const PHYS: [string, number, number, number][] = [ // name, lon, lat, rotation
  ['हिमालय', 83.2, 28.9, -14], ['थार मरुस्थल', 71.2, 26.6, 0], ['दक्कन का पठार', 77.3, 17.2, 0], ['पश्चिमी घाट', 74.0, 13.6, -72],
  ['गंगा का मैदान', 81.6, 25.9, -12], ['अरब सागर', 67.8, 15.5, 0], ['बंगाल की खाड़ी', 88.0, 15.5, 0], ['हिंद महासागर', 75.5, 6.2, 0],
];

/**
 * Animated physical map: a satellite-style relief (map_relief.jpg, built by tools/relief.py) under the vector layer,
 * seen at a slight tilt with drifting cloud shadows. Camera eases from `a` to `b`; `route` draws the flight line up to
 * waypoint progress (0..ROUTE.length-1, fractional); `pins` pop in with a ripple; `glow` lights named rivers in order;
 * `tour` flies the camera from pin to pin (the caller shows a photo card for each stop).
 */
export const MapView: React.FC<{dur: number; a: Cam; b?: Cam; route?: [number, number]; pins?: string[];
  glow?: string[]; line?: [string, string]; grow?: boolean; label?: boolean; tour?: string[]; tourAt?: number[]; tz?: number}> = ({dur, a, b, route, pins = [], glow = [], line, grow, label = true, tour, tourAt, tz = 3.2}) => {
  const f = useCurrentFrame();
  const {width: W, height: H, fps} = useVideoConfig();
  const p = ease(Math.min(1, Math.max(0, f / Math.max(1, dur))));
  let cam = b ? {lon: a.lon + (b.lon - a.lon) * p, lat: a.lat + (b.lat - a.lat) * p, z: a.z * Math.pow(b.z / a.z, p)} : a;
  let shown = pins;
  if (tour && tour.length) {
    // Stop i is reached at frame at[i] (the phrase naming it); the flight to it takes up to 18 frames before that.
    const at = tourAt ?? tour.map((_, i) => Math.round((dur / tour.length) * i));
    let i = -1;
    for (let j = 0; j < tour.length; j++) if (f >= at[j] - 18) i = j;
    if (i >= 0) {
      const start = at[i] - 18, q = ease(Math.min(1, Math.max(0, (f - start) / 18)));
      const from = i === 0 ? a : {lon: WP[tour[i - 1]].lon, lat: WP[tour[i - 1]].lat, z: tz};
      const to = {lon: WP[tour[i]].lon, lat: WP[tour[i]].lat, z: tz};
      const zMid = Math.min(from.z, to.z) * 0.75;
      const zz = q < 0.5 ? from.z * Math.pow(zMid / from.z, q * 2) : zMid * Math.pow(to.z / zMid, (q - 0.5) * 2);
      cam = {lon: from.lon + (to.lon - from.lon) * q, lat: from.lat + (to.lat - from.lat) * q, z: zz};
    }
    shown = tour.slice(0, i + 1);
  }
  const [cx, cy] = toXY(cam.lon, cam.lat);
  const s = (Math.max(W, H) / 2000) * cam.z;
  const tx = W / 2 - cx * s, ty = H / 2 - cy * s;
  const tr = `translate(${tx} ${ty}) scale(${s})`;
  const inv = 1 / s;
  // Flight line through the route waypoints, drawn up to progress.
  const pts = ROUTE.map((k) => WP[k].xy);
  let d = '';
  if (route) {
    const prog = route[0] + (route[1] - route[0]) * p;
    const n = Math.floor(prog), fr = prog - n;
    d = 'M' + pts.slice(0, n + 1).map((q) => `${q[0]} ${q[1]}`).join(' L');
    if (n + 1 < pts.length && fr > 0) {
      const q0 = pts[n], q1 = pts[n + 1];
      d += ` L${q0[0] + (q1[0] - q0[0]) * fr} ${q0[1] + (q1[1] - q0[1]) * fr}`;
    }
  }
  const plane = (() => {
    if (!route) return null;
    const prog = route[0] + (route[1] - route[0]) * p;
    const n = Math.min(pts.length - 2, Math.floor(prog)), fr = Math.min(1, prog - n);
    const q0 = pts[n], q1 = pts[n + 1];
    return {x: q0[0] + (q1[0] - q0[0]) * fr, y: q0[1] + (q1[1] - q0[1]) * fr, ang: Math.atan2(q1[1] - q0[1], q1[0] - q0[0])};
  })();
  // `grow` draws the line from the first point to the second across the shot (the bridge being built).
  const gq = grow ? Math.min(1, f / Math.max(1, dur * 0.92)) : 1;
  const lineD = line ? `M${WP[line[0]].xy[0]} ${WP[line[0]].xy[1]} L${WP[line[0]].xy[0] + (WP[line[1]].xy[0] - WP[line[0]].xy[0]) * gq} ${WP[line[0]].xy[1] + (WP[line[1]].xy[1] - WP[line[0]].xy[1]) * gq}` : '';
  const physO = interpolate(cam.z, [1.3, 1.7], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) *
    interpolate(f, [6, 20], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const t = f / fps;
  const clouds = [0, 1, 2, 3, 4].map((i) => {
    const x = ((i * 0.31 + t * 0.012 * (1 + (i % 3) * 0.4)) % 1.4 - 0.2) * W, y = (0.12 + 0.19 * i) * H;
    return <div key={i} style={{position: 'absolute', left: x - W * 0.3, top: y - H * 0.08, width: W * 0.6, height: H * 0.16, borderRadius: '50%',
      background: 'radial-gradient(ellipse at center, rgba(255,255,255,0.22), rgba(255,255,255,0) 70%)', filter: 'blur(8px)'}} />;
  });
  const tilt = 12;
  return (
    <AbsoluteFill style={{background: '#0b1a3a', overflow: 'hidden'}}>
      <AbsoluteFill style={{transform: `perspective(${Math.max(W, H) * 1.6}px) rotateX(${tilt}deg) scale(1.16)`, transformOrigin: '50% 60%'}}>
        <Img src={RELIEF} style={{position: 'absolute', left: 0, top: 0, width: 2000, height: MAP_H, transformOrigin: '0 0',
          transform: `translate(${tx}px, ${ty}px) scale(${s})`}} />
        <svg width={W} height={H} style={{position: 'absolute'}}>
          <g transform={tr}>
            {Object.entries(MAP.rivers as Record<string, string>).map(([k, rd]) => {
              const gi = glow.indexOf(k);
              const on = gi < 0 ? 0 : interpolate(f, [gi * 18, gi * 18 + 14], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
              return (
                <g key={k}>
                  <path d={rd} fill="none" stroke="#5aa8e6" strokeWidth={1.8 * inv} opacity={0.75} />
                  {on > 0 && <path d={rd} fill="none" stroke="#7fd3ff" strokeWidth={10 * inv} opacity={on * (0.75 + 0.25 * Math.sin(t * 4))} strokeLinecap="round" />}
                </g>
              );
            })}
            {physO > 0 && PHYS.map(([n, lon, lat, rot]) => {
              const [x, y] = toXY(lon, lat);
              return <text key={n} x={x} y={y} transform={`rotate(${rot} ${x} ${y})`} textAnchor="middle" opacity={physO * 0.9} fontFamily={DEV}
                fontSize={34 * inv * (W > H ? 1 : 1.25)} fontWeight={600} letterSpacing={6 * inv} fill="rgba(255,250,235,0.92)"
                stroke="rgba(10,20,40,0.55)" strokeWidth={5 * inv} paintOrder="stroke">{n}</text>;
            })}
            {lineD && grow && <path d={lineD} stroke={GOLD} strokeWidth={20 * inv} opacity={0.35} strokeLinecap="round" />}
            {lineD && <path d={lineD} stroke={GOLD} strokeWidth={7 * inv} strokeDasharray={`${14 * inv} ${10 * inv}`} strokeDashoffset={-t * 40 * inv} />}
            {d && <path d={d} fill="none" stroke={GOLD} strokeWidth={22 * inv} strokeLinecap="round" strokeLinejoin="round" opacity={0.25} />}
            {d && <path d={d} fill="none" stroke={RED} strokeWidth={8 * inv} strokeLinecap="round" strokeLinejoin="round" />}
            {d && <path d={d} fill="none" stroke={GOLD} strokeWidth={3 * inv} strokeDasharray={`${12 * inv} ${10 * inv}`} />}
            {shown.map((k, i) => {
              const t0 = tour ? (tourAt ? tourAt[i] - 6 : Math.floor((dur / tour.length) * i)) : i * 8;
              const o = interpolate(f, [t0, t0 + 10], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
              const rip = ((f - t0) % 45) / 45;
              const [x, y] = WP[k].xy;
              return (
                <g key={k} opacity={o} transform={`translate(${x} ${y}) scale(${inv * (0.6 + 0.4 * o)})`}>
                  <circle r={16 + rip * 40} fill="none" stroke={GOLD} strokeWidth={4} opacity={(1 - rip) * 0.9} />
                  <circle r={16} fill={RED} stroke={CONCH} strokeWidth={5} />
                  <circle r={5} fill={GOLD} />
                  {label && (
                    <text x={LEFT.has(k) ? -24 : 24} y={12} textAnchor={LEFT.has(k) ? 'end' : 'start'} fontFamily={DEV} fontSize={44} fontWeight={700} fill={INK} stroke={CONCH}
                      strokeWidth={8} paintOrder="stroke">{HI_NAME[k] ?? k}</text>
                  )}
                </g>
              );
            })}
            {glow.map((k, i) => {
              const rd = (MAP.rivers as Record<string, string>)[k];
              if (!rd || !RIVER_HI[k]) return null;
              const all = [...rd.matchAll(/([\d.]+) ([\d.]+)/g)];
              const m = all[Math.floor(all.length * 0.45)];
              const o = interpolate(f, [i * 18 + 8, i * 18 + 18], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
              return m ? (
                <text key={k} x={+m[1]} y={+m[2]} opacity={o} fontFamily={DEV} fontSize={46 * inv} fontWeight={700}
                  fill="#0d2a66" stroke={CONCH} strokeWidth={8 * inv} paintOrder="stroke">{RIVER_HI[k]}</text>
              ) : null;
            })}
            {plane && (
              <g transform={`translate(${plane.x} ${plane.y}) rotate(${(plane.ang * 180) / Math.PI}) scale(${inv})`}>
                <circle r={40} fill="rgba(242,193,78,0.35)" />
                <path d="M-26 -14 L30 0 L-26 14 L-14 0 Z" fill={GOLD} stroke={INK} strokeWidth={4} />
              </g>
            )}
          </g>
        </svg>
        {clouds}
      </AbsoluteFill>
      {/* sky haze at the far edge of the tilted map, and a vignette */}
      <AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(200,220,255,0.28) 0%, rgba(200,220,255,0) 18%), radial-gradient(ellipse at center, rgba(0,0,0,0) 60%, rgba(0,0,0,0.4) 100%)'}} />
      <div style={{position: 'absolute', left: 24, bottom: H > 1500 ? 300 : 22, fontFamily: LAT, fontSize: 22, color: 'rgba(246,239,220,0.7)',
        textShadow: '0 1px 3px #000'}}>Map: Kathakaar · relief from Natural Earth and NOAA ETOPO 2022 (public domain)</div>
    </AbsoluteFill>
  );
};

/** Short-only chapter tag (top), e.g. "रामायण का मार्ग · भाग 3/17". */
export const PartTag: React.FC<{n: number; of: number}> = ({n, of}) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, 10, 100, 115], [0, 1, 1, 0.85], {extrapolateRight: 'clamp'});
  return (
    <div style={{position: 'absolute', top: 120, left: 0, right: 0, textAlign: 'center', opacity: o}}>
      <span style={{fontFamily: DEV, fontSize: 46, fontWeight: 700, color: CONCH, background: 'rgba(18,12,10,0.72)',
        padding: '10px 30px 8px', borderRadius: 40, border: `3px solid ${GOLD}`}}>रामायण का मार्ग · भाग {n}/{of}</span>
    </div>
  );
};

/** Short-only follow card behind the "next part" line. */
export const FollowCard: React.FC<{next?: string}> = ({next}) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, 12], [0, 1], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: `rgba(18,12,10,${0.78 * o})`, alignItems: 'center', justifyContent: 'center'}}>
      <div style={{opacity: o, textAlign: 'center', transform: `translateY(${(1 - o) * 30}px)`}}>
        {next && <div style={{fontFamily: DEV, fontSize: 54, color: CONCH, marginBottom: 40, padding: '0 60px', lineHeight: 1.35}}>{next}</div>}
        <div style={{display: 'inline-block', fontFamily: DEV, fontSize: 64, fontWeight: 700, color: INK, background: GOLD,
          padding: '18px 54px 12px', borderRadius: 60}}>फ़ॉलो कीजिए</div>
      </div>
    </AbsoluteFill>
  );
};
