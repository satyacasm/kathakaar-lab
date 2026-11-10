/**
 * Held objects, creatures and set pieces in the Pattachitra idiom (thick outline, flat colour, white dots), first
 * drawn for episode 003. Props are centred on the grip at (0, 0) and drawn upright; place them with wristAt().
 */
import React from 'react';
import {Dots, PL, WD} from './pattachitra';
import {GOLD, GREEN, RED} from './cloth';

const BLUE = '#3b5fb0';
const SAFF = '#e8742a';

/** Sudarshana: a spinning gold wheel with a red hub, flames on the rim. */
export const Chakra: React.FC<{r?: number; t: number; glow?: number}> = ({r = 70, t, glow = 0}) => (
  <g transform={`rotate(${(t * 360) % 360})`} stroke={PL} strokeWidth={3}>
    {glow > 0 && <circle r={r * 1.9} fill={GOLD} opacity={0.25 * glow} stroke="none" />}
    {Array.from({length: 16}, (_, i) => <path key={i} d={`M -7 ${-r} L 0 ${-r - 24} L 7 ${-r} Z`} fill={i % 2 ? GOLD : SAFF} transform={`rotate(${i * 22.5})`} strokeWidth={2} />)}
    <circle r={r} fill={GOLD} />
    <circle r={r * 0.72} fill="none" strokeWidth={2.4} />
    {Array.from({length: 8}, (_, i) => <path key={i} d={`M 0 0 L 0 ${-r * 0.72}`} transform={`rotate(${i * 45})`} strokeWidth={4} />)}
    <circle r={r * 0.24} fill={RED} />
  </g>
);

/** The conch (shankha), white with an orange mouth. */
export const Conch: React.FC<{s?: number}> = ({s = 1}) => (
  <g transform={`scale(${s})`} stroke={PL} strokeWidth={3} strokeLinejoin="round">
    <path d="M 0 -70 C 34 -60 44 -20 34 20 C 26 50 10 64 0 70 C -10 50 -30 30 -32 0 C -34 -40 -20 -64 0 -70 Z" fill={WD} />
    <path d="M -4 -40 C 10 -30 14 -10 6 10 C 2 22 -6 30 -10 34" fill="none" stroke={SAFF} strokeWidth={6} />
    {[-50, -30, -10].map((y) => <path key={y} d={`M -24 ${y} C -8 ${y - 6} 14 ${y - 6} 28 ${y + 2}`} fill="none" strokeWidth={2} />)}
  </g>
);

/** An open lotus, petals in pink and white; s scales it. */
export const Lotus: React.FC<{s?: number; open?: number}> = ({s = 1, open = 1}) => (
  <g transform={`scale(${s})`} stroke={PL} strokeWidth={3} strokeLinejoin="round">
    {[-70, -40, -14, 14, 40, 70].map((a, i) => (
      <path key={a} d="M 0 0 C -22 -30 -18 -78 0 -100 C 18 -78 22 -30 0 0 Z" fill={i % 2 ? '#f08fa8' : '#f6c3cf'} transform={`rotate(${a * open})`} />
    ))}
    <path d="M 0 0 C -16 -26 -12 -66 0 -84 C 12 -66 16 -26 0 0 Z" fill="#f6c3cf" />
    <ellipse cx={0} cy={-8} rx={30} ry={10} fill={GOLD} />
  </g>
);

/** The lotus seat a goddess stands or sits on. */
export const LotusSeat: React.FC<{w?: number}> = ({w = 300}) => (
  <g stroke={PL} strokeWidth={3.5} strokeLinejoin="round">
    {Array.from({length: 9}, (_, i) => {
      const x = -w / 2 + (w * i) / 8;
      return <path key={i} d={`M ${x} 0 C ${x - 30} -40 ${x - 14} -90 ${x} -110 C ${x + 14} -90 ${x + 30} -40 ${x} 0 Z`} fill={i % 2 ? '#f08fa8' : '#f6c3cf'} />;
    })}
    <path d={`M ${-w / 2 - 20} 0 C ${-w / 4} 40 ${w / 4} 40 ${w / 2 + 20} 0 Z`} fill={GREEN} />
    <Dots d={`M ${-w / 2} 6 C ${-w / 4} 34 ${w / 4} 34 ${w / 2} 6`} n={16} r={2.6} />
  </g>
);

/** Kali's curved sword (khadga), blade up from the grip. */
export const Sword: React.FC<{s?: number}> = ({s = 1}) => (
  <g transform={`scale(${s})`} stroke={PL} strokeWidth={3.5} strokeLinejoin="round">
    <path d="M -8 -20 C -14 -160 10 -300 60 -380 C 50 -300 36 -160 12 -20 Z" fill="#d8dde6" />
    <path d="M 2 -40 C 0 -160 20 -280 50 -360" fill="none" stroke={WD} strokeWidth={2} />
    <rect x={-30} y={-26} width={60} height={14} rx={6} fill={GOLD} />
    <rect x={-8} y={-12} width={16} height={50} fill={RED} />
  </g>
);

/** Vamana's parasol (chhatra), held by its staff. */
export const Umbrella: React.FC<{s?: number}> = ({s = 1}) => (
  <g transform={`scale(${s})`} stroke={PL} strokeWidth={3.5} strokeLinejoin="round">
    <path d="M 0 40 L 0 -300" strokeWidth={8} />
    <path d="M -150 -280 C -130 -360 130 -360 150 -280 Z" fill={WD} />
    {[-110, -55, 0, 55, 110].map((x) => <path key={x} d={`M 0 -340 L ${x} -282`} strokeWidth={2} />)}
    <path d="M -150 -280 C -100 -270 100 -270 150 -280" fill="none" stroke={RED} strokeWidth={10} />
    <Dots d="M -146 -284 C -100 -274 100 -274 146 -284" n={14} r={2.4} />
  </g>
);

/** A brass water pot (kamandalu) hanging from the hand. */
export const Kamandalu: React.FC<{s?: number}> = ({s = 1}) => (
  <g transform={`scale(${s})`} stroke={PL} strokeWidth={3}>
    <path d="M -10 0 C -30 10 -30 30 -14 36" fill="none" strokeWidth={5} />
    <path d="M -40 40 C -50 90 -30 120 0 120 C 30 120 50 90 40 40 Z" fill={GOLD} />
    <path d="M 40 60 C 60 56 70 46 76 36" fill="none" strokeWidth={7} />
    <Dots d="M -40 60 C -10 70 10 70 40 60" n={8} r={2.2} />
  </g>
);

/** Krishna's flute, held across at the grip. */
export const Flute: React.FC<{len?: number}> = ({len = 260}) => (
  <g stroke={PL} strokeWidth={3}>
    <rect x={-20} y={-8} width={len} height={16} rx={8} fill="#8a5a2b" />
    {[0.3, 0.45, 0.6, 0.75].map((u) => <circle key={u} cx={-20 + len * u} cy={0} r={3.5} fill={PL} stroke="none" />)}
    <path d={`M ${len - 40} -8 l 0 16`} stroke={GOLD} strokeWidth={6} />
  </g>
);

/**
 * Garuda in flight, facing right: a crowned bird-man with red-gold wings spread; a seat on his back at (0, -150)
 * for riders (pass them as children, feet on the seat).
 */
export const Garuda: React.FC<{t: number; s?: number; children?: React.ReactNode}> = ({t, s = 1, children}) => {
  const flap = Math.sin(t * 5);
  const wing = (dir: number) => (
    <g transform={`rotate(${dir * (-18 + 16 * flap)} ${dir * 60} -60)`}>
      <path d={`M ${dir * 40} -60 C ${dir * 200} -260 ${dir * 420} -300 ${dir * 560} -250 C ${dir * 470} -200 ${dir * 520} -150 ${dir * 430} -120 C ${dir * 480} -80 ${dir * 400} -40 ${dir * 320} -40 C ${dir * 260} 0 ${dir * 140} 0 ${dir * 40} -20 Z`}
        fill={dir > 0 ? '#c0392b' : '#a52a1e'} stroke={PL} strokeWidth={4} strokeLinejoin="round" />
      {[0, 1, 2, 3, 4].map((i) => <path key={i} d={`M ${dir * (120 + i * 80)} ${-60 - i * 34} C ${dir * (150 + i * 80)} ${-30 - i * 30} ${dir * (160 + i * 80)} ${-10 - i * 20} ${dir * (150 + i * 74)} ${0 - i * 10}`} fill="none" stroke={GOLD} strokeWidth={5} />)}
      <Dots d={`M ${dir * 60} -40 C ${dir * 200} -220 ${dir * 400} -270 ${dir * 540} -246`} n={16} r={2.6} />
    </g>
  );
  return (
    <g transform={`scale(${s})`} strokeLinejoin="round">
      {wing(-1)}
      {/* body, lying along the flight, legs trailing */}
      <path d="M -260 -40 C -200 -110 120 -120 200 -70 C 230 -40 210 0 160 10 C 40 30 -160 30 -260 -40 Z" fill={GOLD} stroke={PL} strokeWidth={4} />
      <path d="M -260 -40 C -320 -30 -380 -10 -420 20 L -400 30 C -360 10 -300 0 -240 -10 Z" fill="#e8b860" stroke={PL} strokeWidth={3.5} />
      {[0, 1, 2, 3].map((i) => <path key={i} d={`M ${-180 + i * 80} -70 C ${-170 + i * 80} -40 ${-170 + i * 80} -10 ${-180 + i * 80} 14`} fill="none" stroke={RED} strokeWidth={4} />)}
      <Dots d="M -230 -50 C -100 -96 100 -100 190 -70" n={18} r={2.6} />
      {/* tail feathers */}
      {[-30, -10, 10].map((a) => <path key={a} d="M -250 -30 C -340 -60 -420 -80 -470 -60 C -420 -40 -340 -20 -250 -20 Z" fill={a === -10 ? GREEN : BLUE} stroke={PL} strokeWidth={3} transform={`rotate(${a} -250 -30)`} />)}
      {/* head: crowned, with the hooked beak */}
      <g transform="translate(220 -90)">
        <path d="M -30 0 C -30 -60 30 -80 60 -50 C 80 -34 84 -20 80 -6 C 60 10 20 20 -10 20 Z" fill={GOLD} stroke={PL} strokeWidth={4} />
        <path d="M 72 -40 C 110 -40 130 -20 124 6 C 112 -6 96 -10 78 -8 Z" fill={SAFF} stroke={PL} strokeWidth={3.5} />
        <path d="M 30 -44 C 40 -54 56 -54 64 -44 C 54 -38 40 -38 30 -44 Z" fill={WD} stroke={PL} strokeWidth={2.4} />
        <circle cx={48} cy={-45} r={5} fill={PL} />
        <path d="M -20 -40 L 40 -60 L 30 -100 L -10 -90 Z" fill={GOLD} stroke={PL} strokeWidth={3} />
        <path d="M -10 -90 L 30 -100 L 6 -140 Z" fill={RED} stroke={PL} strokeWidth={3} />
      </g>
      {children && <g transform="translate(-40 -110)">{children}</g>}
      {wing(1)}
    </g>
  );
};

/** A cow in profile facing right, white with a red-and-gold saddle cloth; head bobs. */
export const Cow: React.FC<{t: number; s?: number; fill?: string}> = ({t, s = 1, fill = WD}) => (
  <g transform={`scale(${s})`} stroke={PL} strokeWidth={4} strokeLinejoin="round">
    {[-110, -60, 70, 120].map((x, i) => <path key={x} d={`M ${x} -40 L ${x + (i % 2 ? 6 : -4)} 120`} strokeWidth={26} strokeLinecap="round" />)}
    {[-110, -60, 70, 120].map((x, i) => <path key={`l${x}`} d={`M ${x} -40 L ${x + (i % 2 ? 6 : -4)} 120`} stroke={fill} strokeWidth={18} strokeLinecap="round" />)}
    <path d="M -160 -60 C -170 -150 -60 -170 60 -160 C 150 -150 190 -120 180 -50 C 170 0 -150 10 -160 -60 Z" fill={fill} />
    <path d="M -170 -100 C -210 -80 -220 -20 -200 40" fill="none" strokeWidth={6} />
    <path d="M -60 -150 C -30 -170 30 -170 60 -150 L 70 -40 L -70 -40 Z" fill={RED} />
    <Dots d="M -60 -50 C -20 -46 30 -46 70 -50" n={10} r={2.6} />
    <path d="M -50 -150 L 60 -150" stroke={GOLD} strokeWidth={8} />
    <g transform={`translate(180 -110) rotate(${4 * Math.sin(t * 1.6)})`}>
      <path d="M 0 0 C 20 -40 70 -40 90 -10 C 110 20 100 50 80 60 C 50 64 20 40 0 30 Z" fill={fill} />
      <path d="M 30 -30 C 20 -70 30 -90 50 -100 M 60 -30 C 70 -70 90 -86 110 -90" fill="none" strokeWidth={6} />
      <circle cx={60} cy={4} r={5} fill={PL} />
      <path d="M 0 30 C 10 60 30 80 40 90" fill="none" stroke={GOLD} strokeWidth={6} />
      <circle cx={42} cy={92} r={9} fill={GOLD} strokeWidth={2} />
    </g>
  </g>
);

/** Govardhan hill: green tiers with trees and a white rim, its base at y = 0 (w wide). */
export const Hill: React.FC<{w?: number; h?: number; t: number}> = ({w = 900, h = 420, t}) => (
  <g stroke={PL} strokeWidth={4} strokeLinejoin="round">
    <path d={`M ${-w / 2} 0 C ${-w / 2.4} ${-h * 0.6} ${-w / 4} ${-h} 0 ${-h} C ${w / 4} ${-h} ${w / 2.4} ${-h * 0.6} ${w / 2} 0 Z`} fill="#4e8a3e" />
    <path d={`M ${-w / 2.6} ${-h * 0.25} C ${-w / 4} ${-h * 0.75} ${w / 4} ${-h * 0.75} ${w / 2.6} ${-h * 0.25}`} fill="none" stroke="#2e5d2a" strokeWidth={6} />
    {Array.from({length: 9}, (_, i) => {
      const u = (i + 0.5) / 9, x = -w / 2 + w * u, y = -h * Math.sin(Math.PI * u) * 0.9;
      return <g key={i} transform={`translate(${x} ${y}) rotate(${2 * Math.sin(t + i)})`}><path d="M 0 0 L 0 -40" strokeWidth={6} /><circle cy={-60} r={30} fill={i % 2 ? GREEN : '#7fb069'} /></g>;
    })}
    <path d={`M ${-w / 2} 0 L ${w / 2} 0`} stroke={WD} strokeWidth={8} />
    <path d={`M ${-w / 2} 0 C ${-w / 4} 26 ${w / 4} 26 ${w / 2} 0 Z`} fill="#6a4a2a" />
  </g>
);

/** A red merchant's ledger (bahi-khata) bound with string, "शुभ लाभ" on the cover. */
export const Ledger: React.FC<{s?: number; open?: number}> = ({s = 1, open = 0}) => (
  <g transform={`scale(${s})`} stroke={PL} strokeWidth={3.5} strokeLinejoin="round">
    <rect x={-120} y={-160} width={240} height={320} rx={10} fill="#b3261e" />
    <rect x={-100} y={-140} width={200} height={280} rx={6} fill="none" stroke={GOLD} strokeWidth={5} />
    <text x={0} y={-30} textAnchor="middle" fontSize={56} fontWeight={700} fill={GOLD} stroke="none" fontFamily="Kohinoor Devanagari, Devanagari Sangam MN, Noto Sans Devanagari, sans-serif">शुभ</text>
    <text x={0} y={50} textAnchor="middle" fontSize={56} fontWeight={700} fill={GOLD} stroke="none" fontFamily="Kohinoor Devanagari, Devanagari Sangam MN, Noto Sans Devanagari, sans-serif">लाभ</text>
    <path d="M -120 100 L 120 100" stroke={WD} strokeWidth={4} />
    {open > 0 && <circle cx={0} cy={110} r={16 * open} fill={RED} stroke={GOLD} strokeWidth={3} />}
  </g>
);

/** Kauriya kathi: a bundle of jute sticks with a flame at the top; grip at (0, 0). */
export const JuteTorch: React.FC<{t: number; s?: number; k?: number; ph?: number}> = ({t, s = 1, k = 1, ph = 0}) => {
  const w = 1 + 0.12 * Math.sin(t * 9 + ph);
  return (
    <g transform={`scale(${s})`} stroke={PL} strokeWidth={3}>
      {[-12, 0, 12].map((x) => <path key={x} d={`M ${x * 0.5} 60 L ${x} -220`} stroke="#c9a46a" strokeWidth={9} />)}
      <path d="M -16 -150 L 16 -150" stroke={RED} strokeWidth={6} />
      {k > 0 && (
        <g transform={`translate(0 -230) scale(${k * w} ${k * (2 - w)})`}>
          <circle r={70} fill={GOLD} opacity={0.2} stroke="none" />
          <path d="M 0 30 C -40 10 -40 -40 0 -110 C 40 -40 40 10 0 30 Z" fill="#e8742a" />
          <path d="M 0 22 C -20 6 -20 -26 0 -66 C 20 -26 20 6 0 22 Z" fill={GOLD} strokeWidth={2} />
        </g>
      )}
    </g>
  );
};

/** A kolam / rangoli medallion on the ground, drawn in as k goes 0 -> 1. */
export const Kolam: React.FC<{r?: number; k?: number}> = ({r = 120, k = 1}) => (
  <g transform="scale(1 0.42)" fill="none" strokeLinecap="round">
    <circle r={r} stroke={WD} strokeWidth={6} strokeDasharray={`${2 * Math.PI * r * k} 9999`} />
    {Array.from({length: 8}, (_, i) => (
      <path key={i} d={`M 0 0 C ${r * 0.3} ${-r * 0.3} ${r * 0.3} ${-r * 0.7} 0 ${-r * 0.9} C ${-r * 0.3} ${-r * 0.7} ${-r * 0.3} ${-r * 0.3} 0 0`}
        stroke={i % 2 ? '#f08fa8' : GOLD} strokeWidth={6} transform={`rotate(${i * 45})`} opacity={Math.min(1, Math.max(0, k * 8 - i))} />
    ))}
    {Array.from({length: 16}, (_, i) => <circle key={i} cx={r * 1.15 * Math.cos((i * Math.PI) / 8)} cy={r * 1.15 * Math.sin((i * Math.PI) / 8)} r={6} fill={WD} opacity={k} />)}
  </g>
);

/** Annakut: a mountain of food (rice, sweets, fruit) in a dish, base at y = 0. */
export const FoodMountain: React.FC<{w?: number; k?: number}> = ({w = 520, k = 1}) => {
  const h = w * 0.7 * k;
  return (
    <g stroke={PL} strokeWidth={3.5} strokeLinejoin="round">
      <path d={`M ${-w / 2 - 40} 0 C ${-w / 2} 50 ${w / 2} 50 ${w / 2 + 40} 0 Z`} fill={GOLD} />
      <Dots d={`M ${-w / 2} 10 C ${-w / 4} 34 ${w / 4} 34 ${w / 2} 10`} n={18} r={2.6} />
      {k > 0 && <path d={`M ${-w / 2} 0 C ${-w / 3} ${-h * 0.5} ${-w / 8} ${-h} 0 ${-h} C ${w / 8} ${-h} ${w / 3} ${-h * 0.5} ${w / 2} 0 Z`} fill="#f6efdc" />}
      {k > 0 && Array.from({length: 30}, (_, i) => {
        const u = ((i * 37) % 30) / 30, v = ((i * 11) % 10) / 10;
        const x = (u - 0.5) * w * (1 - v * 0.8), y = -h * v * 0.92 - 16;
        const c = [GOLD, SAFF, RED, GREEN, '#f08fa8'][i % 5];
        return i % 3 ? <circle key={i} cx={x} cy={y} r={14} fill={c} strokeWidth={2} /> : <path key={i} d={`M ${x - 16} ${y + 8} L ${x} ${y - 14} L ${x + 16} ${y + 8} Z`} fill={c} strokeWidth={2} />;
      })}
      {k > 0 && <circle cx={0} cy={-h - 10} r={20} fill={RED} />}
    </g>
  );
};

/** A fortress gate with towers and battlements (Pragjyotisha), base at y = 0. */
export const Fort: React.FC<{w?: number; fill?: string}> = ({w = 900, fill = '#6a4a6a'}) => (
  <g stroke={PL} strokeWidth={4} strokeLinejoin="round">
    <rect x={-w / 2} y={-360} width={w} height={360} fill={fill} />
    {Array.from({length: Math.floor(w / 60)}, (_, i) => <rect key={i} x={-w / 2 + i * 60 + 8} y={-400} width={36} height={40} fill={fill} />)}
    {[-w / 2, w / 2 - 140].map((x) => <g key={x}><rect x={x} y={-560} width={140} height={560} fill="#4e344e" /><path d={`M ${x - 10} -560 L ${x + 70} -660 L ${x + 150} -560 Z`} fill="#b3261e" /></g>)}
    <path d="M -110 0 L -110 -200 C -110 -290 110 -290 110 -200 L 110 0 Z" fill="#1a120c" />
    {[-60, -20, 20, 60].map((x) => <path key={x} d={`M ${x} 0 L ${x} -230`} stroke="#5a3a1a" strokeWidth={8} />)}
    <Dots d={`M ${-w / 2} -340 L ${w / 2} -340`} n={Math.floor(w / 30)} r={3} />
  </g>
);

/** Slanting rain over a band (x0..x1, y0..y1); f drives the fall. */
export const Rain: React.FC<{f: number; x0?: number; x1?: number; y0?: number; y1?: number; n?: number; k?: number}> = ({f, x0 = -200, x1 = 1280, y0 = -200, y1 = 2100, n = 90, k = 1}) => (
  <g stroke={WD} strokeWidth={3} opacity={0.75 * k} strokeLinecap="round">
    {Array.from({length: n}, (_, i) => {
      const x = x0 + ((i * 97) % (x1 - x0));
      const y = y0 + ((i * 263 + f * 38) % (y1 - y0));
      return <path key={i} d={`M ${x} ${y} l -14 44`} />;
    })}
  </g>
);

/** A region name on a red cloth banner with gold border, centred at (x, y); k fades and unrolls it. */
export const RegionBanner: React.FC<{x: number; y: number; text: string; k: number; w?: number}> = ({x, y, text, k, w = 560}) => (
  <g transform={`translate(${x} ${y}) scale(${0.6 + 0.4 * k} 1)`} opacity={k}>
    <path d={`M ${-w / 2 - 40} -60 L ${w / 2 + 40} -60 L ${w / 2 + 10} 0 L ${w / 2 + 40} 60 L ${-w / 2 - 40} 60 L ${-w / 2 - 10} 0 Z`} fill="#b3261e" stroke={PL} strokeWidth={4} strokeLinejoin="round" />
    <rect x={-w / 2} y={-46} width={w} height={92} fill="none" stroke={GOLD} strokeWidth={4} />
    <Dots d={`M ${-w / 2 + 10} -34 L ${w / 2 - 10} -34`} n={Math.floor(w / 26)} r={2.4} />
    <Dots d={`M ${-w / 2 + 10} 34 L ${w / 2 - 10} 34`} n={Math.floor(w / 26)} r={2.4} />
    <text x={0} y={20} textAnchor="middle" fontSize={64} fontWeight={700} fill={WD} fontFamily="Kohinoor Devanagari, Devanagari Sangam MN, Noto Sans Devanagari, sans-serif">{text}</text>
  </g>
);
