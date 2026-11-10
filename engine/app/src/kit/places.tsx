/**
 * Places and large props in the Pattachitra idiom, drawn from Valmiki's descriptions (Griffith):
 *  Pushpaka: "precious gems and burnished gold… bright as the sun's road… chambers wide and excellent",
 *    Vishvakarma's work, moving at its master's will (Sundara 8, Yuddha 123).
 *  Ayodhya on the Sarayu: "high ramparts… circling moat… gates at even distance… terrace and palace, arch and gate…
 *    banners o'er her roofs… towering Sal trees belted round" (Bala 5).
 *  Nandigram: the sandals "installed upon the royal seat" under "the canopy that shades the king" (Ayodhya 115).
 */
import React from 'react';
import {Dots, PL, WD, almond} from './pattachitra';

const GOLD = '#f2c14e';
const RED = '#b3261e';
const GREEN = '#2e7d4f';

/** Pattachitra cloud: a band of scalloped curls with white inner lines. */
export const PCloud: React.FC<{x: number; y: number; w: number; fill?: string; t?: number}> = ({x, y, w, fill = WD, t = 0}) => {
  const n = Math.max(3, Math.round(w / 70));
  const r = w / (2 * n);
  let d = `M 0 0`;
  for (let i = 0; i < n; i++) d += ` a ${r} ${r * (1 + 0.25 * (i % 2))} 0 0 1 ${2 * r} 0`;
  d += ` C ${w + r} ${r} ${w} ${r * 1.4} ${w * 0.5} ${r * 1.3} C 0 ${r * 1.4} ${-r} ${r} 0 0 Z`;
  return (
    <g transform={`translate(${x + 8 * Math.sin(t * 0.6)} ${y})`} stroke={PL} strokeWidth={3}>
      <path d={d} fill={fill} />
      {Array.from({length: n}, (_, i) => <path key={i} d={`M ${r * (2 * i + 0.55)} ${-r * 0.1} a ${r * 0.45} ${r * 0.45} 0 1 1 ${r * 0.9} 0`} fill="none" stroke={fill === WD ? '#5b7fc4' : WD} strokeWidth={2} />)}
    </g>
  );
};

/** Odisha temple tower (rekha deul): curved spire with horizontal courses, amalaka and a flag. */
export const Deul: React.FC<{x: number; y: number; s: number; t: number; fill?: string}> = ({x, y, s, t, fill = '#e8b860'}) => (
  <g transform={`translate(${x} ${y}) scale(${s})`} stroke={PL} strokeWidth={3} strokeLinejoin="round">
    <rect x={-70} y={-90} width={140} height={90} fill="#f2e3c0" />
    <path d="M -16 0 L -16 -50 C -16 -66 16 -66 16 -50 L 16 0 Z" fill={PL} />
    <path d="M -64 -90 C -70 -200 -50 -300 -30 -340 L 30 -340 C 50 -300 70 -200 64 -90 Z" fill={fill} />
    {Array.from({length: 9}, (_, i) => { const y2 = -110 - i * 26; const w2 = 64 - i * 3.6; return <path key={i} d={`M ${-w2} ${y2} L ${w2} ${y2}`} strokeWidth={1.8} />; })}
    <path d="M -10 -90 L -8 -330 M 10 -90 L 8 -330" strokeWidth={1.6} />
    <ellipse cx={0} cy={-352} rx={40} ry={14} fill={GOLD} />
    <path d="M -10 -366 C -10 -390 10 -390 10 -366 Z" fill={GOLD} />
    <path d="M 0 -390 L 0 -460" strokeWidth={3} />
    <path d={`M 0 -460 L ${46 + 4 * Math.sin(t * 3)} ${-448 + 3 * Math.sin(t * 4)} L 0 -432 Z`} fill={RED} strokeWidth={2} />
  </g>
);

/** A palace of several storeys: terraces, arched windows, a domed pavilion on top, banners on the roof. */
export const Palace: React.FC<{x: number; y: number; s: number; t: number; lit?: number; fill?: string; k?: number}> = ({x, y, s, t, lit = 0, fill = '#f2e3c0', k = 0}) => {
  const win = lit > 0 ? (k % 2 ? GOLD : '#e8742a') : '#3a2418';
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`} stroke={PL} strokeWidth={3} strokeLinejoin="round">
      {[0, 1, 2].map((lv) => {
        const w = 150 - lv * 30, y0 = -lv * 110;
        return (
          <g key={lv}>
            <rect x={-w} y={y0 - 110} width={2 * w} height={110} fill={lv % 2 ? '#e8d4a8' : fill} />
            <path d={`M ${-w - 14} ${y0 - 110} L ${w + 14} ${y0 - 110} L ${w} ${y0 - 124} L ${-w} ${y0 - 124} Z`} fill={RED} />
            <Dots d={`M ${-w} ${y0 - 117} C ${-w / 3} ${y0 - 117} ${w / 3} ${y0 - 117} ${w} ${y0 - 117}`} n={Math.round(w / 12)} r={2} />
            {Array.from({length: Math.round(w / 40)}, (_, i) => {
              const wx = -w + (2 * w * (i + 0.5)) / Math.round(w / 40);
              return <path key={i} d={`M ${wx - 12} ${y0 - 20} L ${wx - 12} ${y0 - 70} C ${wx - 12} ${y0 - 88} ${wx + 12} ${y0 - 88} ${wx + 12} ${y0 - 70} L ${wx + 12} ${y0 - 20} Z`} fill={win} opacity={lit > 0 ? 0.5 + 0.5 * lit : 1} />;
            })}
          </g>
        );
      })}
      {/* domed pavilion (chhatri) with a finial */}
      <path d="M -70 -344 L 70 -344 L 70 -380 L -70 -380 Z" fill={fill} />
      <path d="M -80 -380 C -80 -470 80 -470 80 -380 Z" fill={GOLD} />
      {[-40, 0, 40].map((dx) => <path key={dx} d={`M ${dx} -380 C ${dx} -420 ${dx * 0.3} -446 0 -456`} fill="none" strokeWidth={1.6} />)}
      <circle cx={0} cy={-466} r={10} fill={GOLD} />
      {[-130, 130].map((bx, i) => (
        <g key={bx}>
          <path d={`M ${bx} -234 L ${bx} -320`} strokeWidth={3} />
          <path d={`M ${bx} -320 L ${bx + 44 * (i ? 1 : -1) + 5 * Math.sin(t * 3 + bx)} ${-308 + 4 * Math.sin(t * 4 + bx)} L ${bx} -294 Z`} fill={i ? '#e8742a' : RED} strokeWidth={2} />
        </g>
      ))}
      <path d="M 0 -476 L 0 -540" strokeWidth={3} />
      <path d={`M 0 -540 L ${56 + 6 * Math.sin(t * 3)} ${-526 + 4 * Math.sin(t * 4)} L 0 -510 Z`} fill={RED} strokeWidth={2} />
    </g>
  );
};

/** A Sal tree: tall straight trunk, layered leaf canopy. */
export const SalTree: React.FC<{x: number; y: number; s: number; t: number}> = ({x, y, s, t}) => (
  <g transform={`translate(${x} ${y}) scale(${s})`} stroke={PL} strokeWidth={3}>
    <path d="M -10 0 L -6 -300 L 6 -300 L 10 0 Z" fill="#6a3b1e" />
    <g transform={`rotate(${1.5 * Math.sin(t * 1.2 + x)} 0 -300)`}>
      {[[0, -440, 70], [-50, -360, 66], [50, -360, 66], [0, -320, 60]].map(([cx, cy, r], i) => (
        <g key={i}>
          <ellipse cx={cx} cy={cy} rx={r} ry={r * 1.15} fill={i % 2 ? '#3f7a3a' : GREEN} />
          {Array.from({length: 6}, (_, k) => <path key={k} d={almond(r * 0.6, r * 0.16)} transform={`translate(${cx} ${cy}) rotate(${-90 + (k - 2.5) * 22}) translate(${r * 0.5} 0)`} fill="none" stroke={WD} strokeWidth={1.4} />)}
        </g>
      ))}
    </g>
  </g>
);

/** River water band with Pattachitra waves, fish and lotuses (the Sarayu). */
export const River: React.FC<{y: number; h: number; t: number; id: string; fill?: string}> = ({y, h, t, id, fill = '#2d5aa8'}) => (
  <g>
    <defs>
      <pattern id={`${id}-rv`} width="80" height="40" patternUnits="userSpaceOnUse" patternTransform={`translate(${((t * 24) % 80).toFixed(1)} 0)`}>
        <rect width="80" height="40" fill={fill} />
        <path d="M 0 28 C 10 10 30 10 40 28 C 50 10 70 10 80 28" fill="none" stroke={WD} strokeWidth="2" />
        <circle cx="20" cy="12" r="1.8" fill={WD} /><circle cx="60" cy="12" r="1.8" fill={WD} />
      </pattern>
    </defs>
    <rect x={-300} y={y} width={1680} height={h} fill={`url(#${id}-rv)`} stroke={PL} strokeWidth={4} />
    {[[180, 0.4], [760, 0.6]].map(([lx, ph], i) => (
      <g key={i} transform={`translate(${lx + 8 * Math.sin(t + ph * 6)} ${y + h * 0.45})`} stroke={PL} strokeWidth={2.4}>
        <ellipse cy={10} rx={46} ry={10} fill={GREEN} />
        {[-50, -25, 0, 25, 50].map((a) => <path key={a} d="M 0 0 C -12 -16 -9 -40 0 -52 C 9 -40 12 -16 0 0 Z" fill={a === 0 ? WD : '#f08fa8'} transform={`rotate(${a})`} />)}
      </g>
    ))}
  </g>
);

/** Ayodhya: a moat and crenellated rampart with a great gate, palaces and temple towers behind, banners above. */
export const Ayodhya: React.FC<{y: number; t: number; lit?: number; night?: boolean}> = ({y, t, lit = 0, night = false}) => {
  const wall = night ? '#c9955a' : '#d9a25a';
  return (
    <g strokeLinejoin="round">
      {/* skyline: temples and palaces in two rows */}
      <Deul x={150} y={y - 150} s={0.75} t={t} />
      <Palace x={330} y={y - 150} s={0.7} t={t} lit={lit} k={1} />
      <Deul x={540} y={y - 150} s={1.05} t={t + 1} fill={GOLD} />
      <Palace x={760} y={y - 150} s={0.75} t={t + 2} lit={lit} k={2} />
      <Deul x={940} y={y - 150} s={0.7} t={t + 3} />
      {/* rampart with merlons */}
      <g stroke={PL} strokeWidth={3}>
        <rect x={-300} y={y - 150} width={1680} height={150} fill={wall} />
        {Array.from({length: 40}, (_, i) => <path key={i} d={`M ${-300 + i * 44} ${y - 150} l 0 -26 l 26 0 l 0 26`} fill={wall} />)}
        {Array.from({length: 13}, (_, i) => <path key={`l${i}`} d={`M ${-300 + i * 130} ${y - 120} l 0 40`} strokeWidth={2} />)}
        <Dots d={`M -300 ${y - 136} C 300 ${y - 136} 800 ${y - 136} 1380 ${y - 136}`} n={70} r={2.4} />
        {/* the great gate (torana) */}
        <rect x={430} y={y - 260} width={220} height={260} fill={wall} />
        <path d={`M 410 ${y - 260} L 670 ${y - 260} L 650 ${y - 300} L 430 ${y - 300} Z`} fill={RED} />
        <path d={`M 480 ${y} L 480 ${y - 120} C 480 ${y - 200} 600 ${y - 200} 600 ${y - 120} L 600 ${y} Z`} fill={night ? GOLD : '#3a2418'} opacity={night ? 0.5 + 0.5 * lit : 1} />
        <Dots d={`M 470 ${y - 125} C 480 ${y - 215} 600 ${y - 215} 610 ${y - 125}`} n={14} r={2.6} />
        {[455, 625].map((gx) => <circle key={gx} cx={gx} cy={y - 220} r={14} fill={GOLD} />)}
      </g>
      {/* lamps along the rampart at night */}
      {night && Array.from({length: 24}, (_, i) => {
        const on = Math.min(1, Math.max(0, lit * 2.2 - Math.abs(i - 11.5) / 12));
        const fl = 1 + 0.1 * Math.sin(t * 11 + i * 1.7);
        return on > 0 ? (
          <g key={i} transform={`translate(${-80 + i * 50} ${y - 178})`} stroke={PL} strokeWidth={1.6}>
            <circle r={18 * on} fill={GOLD} opacity={0.3} stroke="none" />
            <path d={almond(20 * on * fl, 6 * on)} transform="rotate(-90)" fill={GOLD} />
          </g>
        ) : null;
      })}
    </g>
  );
};

/** The flying Pushpaka: a two-storey golden palace on a lotus base, jewelled, with chambers and a spire. */
export const Pushpaka: React.FC<{x: number; y: number; s: number; t: number; children?: React.ReactNode; glow?: number}> = ({x, y, s, t, children, glow = 1}) => (
  <g transform={`translate(${x} ${y + 10 * Math.sin(t * 1.1)}) rotate(${1.2 * Math.sin(t * 0.8)}) scale(${s})`} stroke={PL} strokeWidth={3.5} strokeLinejoin="round">
    {/* the sun-like sheen */}
    <ellipse cx={0} cy={-260} rx={560} ry={420} fill={GOLD} opacity={0.16 * glow} stroke="none" />
    {Array.from({length: 18}, (_, i) => <path key={i} d="M -12 -520 L 0 -600 L 12 -520 Z" fill={GOLD} opacity={0.5 * glow} transform={`translate(0 -260) rotate(${i * 20 + t * 6}) translate(0 260)`} strokeWidth={1.5} />)}
    {/* lotus base (it is the flower chariot) */}
    {Array.from({length: 11}, (_, i) => <path key={i} d="M 0 0 C -36 30 -30 90 0 120 C 30 90 36 30 0 0 Z" fill={i % 2 ? '#f08fa8' : WD} transform={`translate(${(i - 5) * 70} 20) rotate(${(i - 5) * 6})`} />)}
    {/* platform */}
    <path d="M -420 -20 L 420 -20 L 380 40 L -380 40 Z" fill={GOLD} />
    {Array.from({length: 14}, (_, i) => <circle key={i} cx={-360 + i * 55.4} cy={10} r={9} fill={i % 3 === 0 ? RED : i % 3 === 1 ? GREEN : '#3b5fb0'} strokeWidth={2} />)}
    <Dots d="M -400 -12 C -150 -12 150 -12 400 -12" n={40} r={2.4} />
    {/* lower storey: open pillared hall (the figures stand here, drawn by children) */}
    <rect x={-360} y={-340} width={720} height={320} fill="#7a1f16" />
    {children}
    {[-360, -200, 200, 360].map((px) => (
      <g key={px}>
        <rect x={px - 16} y={-340} width={32} height={320} fill={GOLD} />
        <Dots d={`M ${px} -330 C ${px} -240 ${px} -120 ${px} -30`} n={10} r={2.2} />
      </g>
    ))}
    {/* cusped arches above the hall */}
    {[-280, 0, 280].map((ax) => <path key={ax} d={`M ${ax - 90} -340 C ${ax - 80} -400 ${ax - 30} -420 ${ax} -440 C ${ax + 30} -420 ${ax + 80} -400 ${ax + 90} -340`} fill="none" stroke={PL} strokeWidth={6} />)}
    <path d="M -400 -340 L 400 -340 L 360 -380 L -360 -380 Z" fill={RED} />
    {/* upper storey: chambers with windows */}
    <rect x={-300} y={-520} width={600} height={140} fill={GOLD} />
    {Array.from({length: 7}, (_, i) => <path key={i} d={`M ${-260 + i * 86} -400 L ${-260 + i * 86} -470 C ${-260 + i * 86} -496 ${-230 + i * 86} -496 ${-230 + i * 86} -470 L ${-230 + i * 86} -400 Z`} fill="#3a2418" />)}
    <path d="M -340 -520 L 340 -520 L 300 -560 L -300 -560 Z" fill={RED} />
    <Dots d="M -320 -540 C -100 -540 100 -540 320 -540" n={30} r={2.2} />
    {/* spire */}
    <path d="M -160 -560 C -170 -700 -80 -800 0 -840 C 80 -800 170 -700 160 -560 Z" fill={GOLD} />
    {Array.from({length: 6}, (_, i) => <path key={i} d={`M ${-150 + i * 14} ${-600 - i * 38} L ${150 - i * 14} ${-600 - i * 38}`} strokeWidth={2} />)}
    <circle cx={0} cy={-850} r={20} fill={RED} />
    <path d="M 0 -870 L 0 -940" strokeWidth={3.5} />
    <path d={`M 0 -940 L ${70 + 6 * Math.sin(t * 3)} ${-924 + 5 * Math.sin(t * 4)} L 0 -906 Z`} fill={RED} strokeWidth={2} />
    {[-300, 300].map((bx, i) => (
      <g key={bx}>
        <path d={`M ${bx} -560 L ${bx} -650`} strokeWidth={3} />
        <path d={`M ${bx} -650 L ${bx + (i ? 50 : -50) + 6 * Math.sin(t * 3 + i)} ${-636 + 4 * Math.sin(t * 4 + i)} L ${bx} -620 Z`} fill={i ? '#e8742a' : GREEN} strokeWidth={2} />
      </g>
    ))}
    {/* swan-headed prows at both ends */}
    {[-1, 1].map((d) => (
      <g key={d} transform={`translate(${420 * d} -20) scale(${d} 1)`}>
        <path d="M 0 0 C 60 -10 90 -70 70 -120 C 60 -146 92 -160 108 -140" fill="none" stroke={PL} strokeWidth={26} strokeLinecap="round" />
        <path d="M 0 0 C 60 -10 90 -70 70 -120 C 60 -146 92 -160 108 -140" fill="none" stroke={WD} strokeWidth={18} strokeLinecap="round" />
        <path d="M 108 -140 L 136 -132 L 108 -126 Z" fill={GOLD} />
        <circle cx={96} cy={-146} r={4} fill={PL} />
      </g>
    ))}
  </g>
);

/** The royal seat with the sandals installed on it, under the white royal canopy (chhatra). */
export const ThroneOfSandals: React.FC<{x: number; y: number; s: number; t: number; glow?: number; empty?: boolean}> = ({x, y, s, t, glow = 0.5, empty = false}) => (
  <g transform={`translate(${x} ${y}) scale(${s})`} stroke={PL} strokeWidth={3.5} strokeLinejoin="round">
    {/* canopy */}
    <path d="M 0 -560 L 0 -200" strokeWidth={6} />
    <path d="M -170 -470 C -120 -560 120 -560 170 -470 Z" fill={WD} />
    {Array.from({length: 9}, (_, i) => <path key={i} d={`M ${-170 + i * 42.5} -470 c 6 ${16 + 3 * Math.sin(t * 3 + i)} 16 ${16 + 3 * Math.sin(t * 3 + i)} 21 0`} fill={RED} strokeWidth={2} />)}
    <Dots d="M -150 -484 C -80 -540 80 -540 150 -484" n={14} r={2.6} />
    <circle cx={0} cy={-566} r={12} fill={GOLD} />
    {/* seat */}
    <path d="M -150 -260 C -170 -330 -110 -360 -110 -300 L 110 -300 C 110 -360 170 -330 150 -260 Z" fill={GOLD} />
    <rect x={-160} y={-260} width={320} height={90} fill={RED} />
    <Dots d="M -150 -215 C -60 -215 60 -215 150 -215" n={16} r={2.4} />
    <path d="M -140 -170 L -120 0 M 140 -170 L 120 0" strokeWidth={14} />
    <path d="M -140 -170 L -120 0 M 140 -170 L 120 0" stroke={GOLD} strokeWidth={8} />
    {!empty && <ellipse cx={0} cy={-280} rx={140} ry={50} fill={GOLD} opacity={0.35 * glow} stroke="none" />}
    {!empty && [-38, 38].map((dx, i) => (
      <g key={dx} transform={`translate(${dx} -282) rotate(${90 + (i ? 4 : -4)}) scale(0.42)`}>
        <path d="M -30 -80 C -40 -40 -36 50 -26 80 C -14 96 14 96 26 80 C 36 50 40 -40 30 -80 C 20 -98 -20 -98 -30 -80 Z" fill="#a8723f" />
        <path d="M -20 -70 C -28 -36 -26 44 -18 70 C -8 82 8 82 18 70 C 26 44 28 -36 20 -70 C 12 -84 -12 -84 -20 -70 Z" fill={GOLD} strokeWidth={2} />
        <circle cy={-46} r={11} fill={RED} />
      </g>
    ))}
  </g>
);

/** A hermit's hut (kutir): bamboo frame, thatched roof, darbha grass. */
export const Kutir: React.FC<{x: number; y: number; s: number}> = ({x, y, s}) => (
  <g transform={`translate(${x} ${y}) scale(${s})`} stroke={PL} strokeWidth={3} strokeLinejoin="round">
    <rect x={-120} y={-150} width={240} height={150} fill="#d9a25a" />
    {Array.from({length: 7}, (_, i) => <path key={i} d={`M ${-110 + i * 36} -146 L ${-110 + i * 36} -4`} stroke="#8a5a2b" strokeWidth={4} />)}
    <path d="M -160 -140 L 0 -280 L 160 -140 Z" fill="#b5893e" />
    {Array.from({length: 14}, (_, i) => <path key={i} d={`M ${-150 + i * 22} -146 L ${-60 + i * 9} -250`} strokeWidth={1.4} stroke="#6a4a1e" />)}
    <path d="M -160 -140 C -60 -128 60 -128 160 -140" fill="none" strokeWidth={4} />
    <path d="M -34 0 L -34 -84 C -34 -110 34 -110 34 -84 L 34 0 Z" fill={PL} />
    <path d="M -150 0 C -140 -24 -130 -24 -124 0 M 120 0 C 130 -28 140 -28 146 0" fill={GREEN} />
  </g>
);
