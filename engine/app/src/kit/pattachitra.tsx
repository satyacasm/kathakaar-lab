/**
 * The same moment (Markandeya in the flood, the divine child on the banyan leaf) in three Indian painting
 * traditions. Each tradition gets its own sage, drawn to that school's figure conventions, not a recolour:
 *   Kangra (Pahari): slender figure, straight brow-to-nose line, small gazelle eye, fine brown line, soft washes,
 *     leaf-by-leaf trees, silver-lined water, cranes, lightning in night clouds, plain dark margin with rules.
 *   Madhubani (Mithila): large fish-shaped eye, long pointed nose, profile head on a frontal torso, double outlines
 *     filled with hatching, no empty space, moon with a face, fish, double-line border with motifs.
 *   Pattachitra (Odisha): long tapering frontal eye on a profile face, sharp nose, thick black outline, flat red
 *     ground, white-dot ornament, fan-leaf tree, layered floral border.
 * Hand-made look: no gradients or glow; every line gets a slight wobble; uneven pigment over paper or cloth.
 * The child stays light and silhouette only (project rule), rendered in each school's idiom.
 */
import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {BRANCH, BRANCH_UP, CHILD, CHILD_GLOW, CHILD_POS, HORIZON, LEAF, LEAF_VEINS, ROOTS, SAGE_POS, TRUNK, TRUNK_STRANDS, canopy, crest, rng, stars} from './geometry';

const W = 1080;
const H = 1920;
const SP = SAGE_POS;
const sageT = `translate(${SP.x} ${SP.y}) scale(${SP.s})`;

export const almond = (len: number, w: number) =>
  `M ${-len / 2} 0 C ${-len / 4} ${-w} ${len / 4} ${-w} ${len / 2} 0 C ${len / 4} ${w} ${-len / 4} ${w} ${-len / 2} 0 Z`;

/** Hand-made surface: line wobble, pigment mottling and paper/cloth grain. */
/** seed changes give a slow hand-drawn 'line boil' when animated */
export const Handmade: React.FC<{id: string; wobble: number; paper: [number, number, number]; cloth?: boolean; seed?: number}> = ({id, wobble, paper, cloth, seed = 7}) => (
  <defs>
    <filter id={`${id}-wob`} x="-5%" y="-5%" width="110%" height="110%">
      <feTurbulence type="fractalNoise" baseFrequency="0.018" numOctaves="2" seed={seed} result="n" />
      <feDisplacementMap in="SourceGraphic" in2="n" scale={wobble} xChannelSelector="R" yChannelSelector="G" />
    </filter>
    <filter id={`${id}-mottle`} x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="0.006" numOctaves="4" seed="12" />
      <feColorMatrix values={`0 0 0 0 ${paper[0] * 0.6}  0 0 0 0 ${paper[1] * 0.6}  0 0 0 0 ${paper[2] * 0.6}  -0.9 0 0 0 0.62`} />
    </filter>
    <filter id={`${id}-grain`} x="0" y="0" width="100%" height="100%">
      <feTurbulence type={cloth ? 'turbulence' : 'fractalNoise'} baseFrequency={cloth ? '0.5 0.04' : '0.85'} numOctaves="2" seed="3" />
      <feColorMatrix values={`0 0 0 0 ${paper[0] * 0.5}  0 0 0 0 ${paper[1] * 0.5}  0 0 0 0 ${paper[2] * 0.5}  0 0 0 0.2 0`} />
    </filter>
  </defs>
);
export const Surface: React.FC<{id: string; mottle?: number}> = ({id, mottle = 0.5}) => (
  <>
    <rect width={W} height={H} filter={`url(#${id}-mottle)`} opacity={mottle} style={{mixBlendMode: 'multiply'}} />
    <rect width={W} height={H} filter={`url(#${id}-grain)`} />
  </>
);

export const ChildOnLeaf: React.FC<{leaf: string; vein: string; body: string; line: string; lw: number}> = ({leaf, vein, body, line, lw}) => (
  <g transform={`translate(${CHILD_POS.x} ${CHILD_POS.y}) rotate(${CHILD_POS.rot}) scale(${CHILD_POS.s})`}>
    <path d={LEAF} fill={leaf} stroke={line} strokeWidth={lw} />
    {LEAF_VEINS.map((d, i) => <path key={i} d={d} fill="none" stroke={vein} strokeWidth={i ? 1.3 : 2.2} />)}
    {/* outline pass, then fill pass: a clean silhouette with the school's line around it */}
    {[{c: line, e: lw * 2}, {c: body, e: 0}].map(({c, e}, k) => (
      <g key={k} fill={c} stroke={c} strokeLinecap="round" strokeLinejoin="round">
        <path d={CHILD.restLeg} fill="none" strokeWidth={17 + e} />
        <ellipse {...CHILD.restFoot} strokeWidth={e} />
        <path d={CHILD.body} strokeWidth={2 + e} />
        <path d={CHILD.thigh} fill="none" strokeWidth={22 + e} />
        <path d={CHILD.shin} fill="none" strokeWidth={15 + e} />
        <ellipse {...CHILD.foot} transform="rotate(-30 -46 -72)" strokeWidth={e} />
        <circle {...CHILD.head} strokeWidth={e} />
        <path d={CHILD.arm} fill="none" strokeWidth={11 + e} />
      </g>
    ))}
  </g>
);

// =================================================================================== KANGRA
const KL = '#5b3524'; // fine brown line
const kangraLeaves = (() => {
  const r = rng(21);
  const out: {x: number; y: number; a: number; s: number; k: number}[] = [];
  for (const c of canopy) {
    const n = Math.round(c.r / 6);
    for (let i = 0; i < n; i++) {
      const a = r() * Math.PI * 2;
      const d = Math.sqrt(r()) * c.r;
      out.push({x: c.x + Math.cos(a) * d, y: c.y + Math.sin(a) * d, a: r() * 180, s: 0.7 + r() * 0.6, k: r()});
    }
  }
  return out;
})();

const KangraSage: React.FC = () => (
  <g transform={sageT} stroke={KL} strokeWidth={0.9} strokeLinejoin="round">
    {/* matted hair piled high, white with grey strands */}
    <path d="M -60 -40 C -70 -86 -40 -118 -6 -112 C 22 -106 26 -80 10 -60 C -10 -52 -40 -48 -60 -40 Z" fill="#ece6da" />
    {[0, 1, 2, 3].map((i) => <path key={i} d={`M ${-52 + i * 14} -46 C ${-50 + i * 14} -80 ${-30 + i * 10} -104 ${-8 + i * 4} -106`} fill="none" stroke="#a69c8c" strokeWidth={0.8} />)}
    <path d="M -54 -60 C -36 -70 -10 -70 8 -62" fill="none" stroke="#8a5a2a" strokeWidth={4} />
    <path d="M -32 -50 C -60 -40 -70 0 -64 34 C -60 70 -76 104 -96 130 C -60 120 -42 92 -30 64 Z" fill="#ece6da" />
    {/* slender body, soft skin, deer-skin over one shoulder */}
    <path d="M -28 58 C -34 90 -60 108 -74 136 C -82 200 -82 300 -80 380 L 70 380 C 72 300 70 220 58 172 C 50 140 34 112 20 80 Z" fill="#dcae8a" />
    <path d="M -74 136 C -82 200 -82 300 -80 380 L -40 380 C -46 300 -48 200 -40 140 Z" fill="#c4906c" stroke="none" opacity={0.6} />
    <path d="M -78 134 C -50 110 0 108 24 126 C 36 170 44 250 50 380 L -82 380 Z" fill="#c9a36a" />
    {Array.from({length: 26}, (_, i) => <circle key={i} cx={-60 + (i % 6) * 18 + (i % 2) * 6} cy={160 + Math.floor(i / 6) * 40} r={3.2} fill="#8a6a3a" stroke="none" />)}
    <path d="M -78 134 C -50 110 0 108 24 126" fill="none" stroke="#b5352a" strokeWidth={2.2} />
    {/* head: forehead and nose in one straight line, the Kangra profile */}
    <path d="M -26 64 C -58 40 -62 -26 -30 -50 C -12 -64 18 -62 34 -48 L 63 10 C 64 15 60 18 55 19 L 52 30 C 44 52 18 62 -26 64 Z" fill="#e3b693" />
    <path d="M -2 4 C -12 2 -14 18 -2 20" fill="none" />
    <path d="M 18 -26 C 30 -32 44 -30 52 -22" fill="none" stroke="#f4f1ea" strokeWidth={3} strokeLinecap="round" />
    <path d="M 24 -15 C 32 -21 44 -20 50 -13 C 42 -9 32 -9 24 -15 Z" fill="#fbf7ee" />
    <circle cx={41} cy={-15} r={2.6} fill="#1d120c" stroke="none" />
    {[-44, -40, -36].map((y) => <path key={y} d={`M ${16 + (y + 44) * 0.4} ${y} L ${36 + (y + 44) * 0.5} ${y + 2}`} stroke="#f7f3ea" strokeWidth={1.6} />)}
    {/* long combed beard of fine lines */}
    <path d="M -12 8 C 8 30 34 30 55 22 C 64 40 68 70 64 110 C 60 160 50 210 30 266 C 22 248 14 236 6 248 C 0 200 -12 150 -20 100 C -24 60 -22 30 -12 8 Z" fill="#f4f1ea" />
    {Array.from({length: 11}, (_, i) => <path key={i} d={`M ${-8 + i * 6} ${24 + (i % 3) * 4} C ${-4 + i * 6} ${90} ${-10 + i * 5} ${170} ${-4 + i * 4} ${230 + (i % 4) * 8}`} fill="none" stroke="#b9b2a4" strokeWidth={0.7} />)}
    <path d="M 55 21 C 46 32 36 40 22 44 C 38 48 50 40 57 28 Z" fill="#f4f1ea" />
    {/* rudraksha */}
    {Array.from({length: 14}, (_, i) => { const t = i / 13; return <circle key={i} cx={-20 + t * 70 - 40 * t * (1 - t)} cy={66 + 190 * t * (1 - t) * 1.6 + t * 80} r={3.4} fill="#6a2c1c" />; })}
    {/* hands joined, slender fingers */}
    <path d="M -40 150 C -30 190 0 214 30 210 C 50 206 66 192 78 180" fill="none" stroke="#c4906c" strokeWidth={24} strokeLinecap="round" />
    <path d="M 0 140 C 4 180 16 210 36 214 C 56 212 72 196 84 178" fill="none" stroke={KL} strokeWidth={27} strokeLinecap="round" />
    <path d="M 0 140 C 4 180 16 210 36 214 C 56 212 72 196 84 178" fill="none" stroke="#dcae8a" strokeWidth={25} strokeLinecap="round" />
    <path d="M 78 186 C 80 160 88 128 102 98 C 108 94 112 98 110 106 C 106 134 100 162 94 190 Z" fill="#e3b693" />
    {[0, 1, 2].map((i) => <path key={i} d={`M ${86 + i * 3} 182 C ${90 + i * 3} 156 ${96 + i * 3} 130 ${104 + i * 2} 106`} fill="none" strokeWidth={0.6} />)}
  </g>
);

export const StyleKangra: React.FC = () => {
  const M = 64;
  const waterY = SP.y + 236 * SP.s;
  return (
    <AbsoluteFill style={{background: '#1e2747'}}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%">
        <Handmade id="k" wobble={2.2} paper={[0.55, 0.45, 0.3]} />
        <defs>
          <pattern id="k-water" width="64" height="26" patternUnits="userSpaceOnUse">
            <rect width="64" height="26" fill="#566f72" />
            <path d="M 0 18 C 8 8 24 8 32 18 C 40 8 56 8 64 18" fill="none" stroke="#c9d3cf" strokeWidth="1" />
            <path d="M 8 22 C 14 16 20 16 26 22 M 40 22 C 46 16 52 16 58 22" fill="none" stroke="#9fb0ad" strokeWidth="0.7" />
          </pattern>
          <clipPath id="k-panel"><rect x={M} y={M} width={W - 2 * M} height={H - 2 * M} /></clipPath>
        </defs>
        {/* margin: plain dark blue with a pale speckle, as on old wasli sheets */}
        <rect width={W} height={H} fill="#1e2747" />
        <g clipPath="url(#k-panel)" filter="url(#k-wob)">
          {/* night sky as flat washes, lightest at the horizon */}
          <rect width={W} height={H} fill="#28355e" />
          <rect y={560} width={W} height={400} fill="#33416b" />
          <rect y={900} width={W} height={300} fill="#45507a" />
          {/* rolling storm clouds with scalloped edges and a thin gold lightning streak */}
          {[[180, 230, 1.2], [520, 170, 1], [880, 260, 1.3], [360, 420, 0.8]].map(([x, y, s], i) => (
            <g key={i} transform={`translate(${x} ${y}) scale(${s})`} stroke="#c9cfe0" strokeWidth={1}>
              <path d="M -170 30 C -170 -10 -130 -20 -110 -6 C -100 -50 -40 -60 -20 -24 C 0 -64 70 -60 80 -16 C 110 -40 170 -20 160 30 Z" fill="#59648c" />
              <path d="M -150 30 C -140 6 -110 4 -96 18 M -40 30 C -30 0 10 -6 30 16 M 60 30 C 80 4 120 4 140 24" fill="none" stroke="#8d97bd" />
            </g>
          ))}
          <path d="M 640 260 L 610 330 L 636 330 L 598 420" fill="none" stroke="#e8c35a" strokeWidth={2.4} />
          {stars.filter((s) => s.y > 470 && s.y < 1100 && s.a > 0.6).map((s, i) => <circle key={i} cx={s.x} cy={s.y} r={1.3} fill="#e9e4c8" />)}
          {/* a flight of cranes */}
          {[[180, 640], [230, 610], [280, 590], [330, 580], [385, 585]].map(([x, y], i) => (
            <g key={i} transform={`translate(${x} ${y}) scale(${0.9 + (i % 2) * 0.15})`} fill="none" stroke="#f1eee4" strokeWidth={2} strokeLinecap="round">
              <path d="M -22 -4 C -12 -14 -4 -8 0 0 C 4 -10 14 -16 24 -10" />
              <path d="M 0 0 L 20 4" strokeWidth={1.4} />
            </g>
          ))}
          {/* flood */}
          <rect y={HORIZON} width={W} height={H} fill="url(#k-water)" />
          <rect y={HORIZON - 1} width={W} height={2} fill="#3d4f58" />
          {/* banyan: slender aerial roots, trunk with fine bark lines, foliage leaf by leaf */}
          {ROOTS.map((x, i) => <path key={i} d={`M ${x} ${700 + (i % 3) * 30} C ${x - 6} 900 ${x + 8} 1050 ${x - 2} ${HORIZON + 4}`} stroke="#6e4a36" strokeWidth={i % 3 ? 2.5 : 4} fill="none" />)}
          <path d={TRUNK} fill="#7d5a44" stroke={KL} strokeWidth={1} />
          {TRUNK_STRANDS.concat(['M 735 1190 C 740 1050 726 920 736 800', 'M 790 1196 C 784 1050 784 920 790 790']).map((d, i) => <path key={i} d={d} fill="none" stroke={KL} strokeWidth={0.8} />)}
          {BRANCH_UP.map((d, i) => <path key={i} d={d} fill="none" stroke="#6e4a36" strokeWidth={16 - i * 3} strokeLinecap="round" />)}
          <path d={BRANCH} fill="#7d5a44" stroke={KL} strokeWidth={1} />
          {canopy.map((c, i) => <circle key={i} cx={c.x} cy={c.y} r={c.r} fill="#23402c" />)}
          {kangraLeaves.map((l, i) => (
            <path key={i} d={almond(16 * l.s, 5 * l.s)} transform={`translate(${l.x} ${l.y}) rotate(${l.a})`}
              fill={l.k < 0.45 ? '#3e6a3e' : l.k < 0.8 ? '#58854a' : '#86a85e'} stroke="#1b3020" strokeWidth={0.5} />
          ))}
          {/* the child: pale gold silhouette inside a thin halo of fine rays */}
          <g transform={`translate(${CHILD_GLOW.x} ${CHILD_GLOW.y})`}>
            <circle r={112} fill="#f3e2a6" opacity={0.85} />
            {Array.from({length: 72}, (_, i) => <path key={i} d="M 0 -112 L 0 -132" stroke="#d6a93a" strokeWidth={1} transform={`rotate(${i * 5})`} />)}
            <circle r={112} fill="none" stroke="#c0902c" strokeWidth={2} />
          </g>
          <ChildOnLeaf leaf="#6f9a52" vein="#c9dc9a" body="#e6b84a" line={KL} lw={1} />
          <KangraSage />
          <rect y={waterY} width={W} height={H} fill="url(#k-water)" />
          <path d={crest(waterY, 4, 180, 0.4)} fill="none" stroke="#3d4f58" strokeWidth={1.4} />
          {[[860, 1560], [960, 1650]].map(([x, y], i) => (
            <g key={i} transform={`translate(${x} ${y})`} stroke={KL} strokeWidth={0.8}>
              <ellipse cx={0} cy={6} rx={40} ry={8} fill="#3f6a44" />
              {[-40, -18, 0, 18, 40].map((a) => <path key={a} d={almond(36, 9)} transform={`rotate(${a - 90}) translate(18 0)`} fill="#efc3c9" />)}
            </g>
          ))}
        </g>
        <Surface id="k" mottle={0.35} />
        {/* inner rules: red, then white, the plain Kangra frame */}
        <rect x={M} y={M} width={W - 2 * M} height={H - 2 * M} fill="none" stroke="#b5352a" strokeWidth={5} />
        <rect x={M - 9} y={M - 9} width={W - 2 * M + 18} height={H - 2 * M + 18} fill="none" stroke="#efe9da" strokeWidth={1.6} />
      </svg>
    </AbsoluteFill>
  );
};

// =================================================================================== MADHUBANI
const INK = '#151010';
const MPAPER = '#f1e2bf';
/** Madhubani double outline: two black lines with the paper showing between them. */
const Dbl: React.FC<{d: string; fill: string; w?: number}> = ({d, fill, w = 1}) => (
  <>
    <path d={d} fill={fill} stroke={INK} strokeWidth={7 * w} strokeLinejoin="round" />
    <path d={d} fill={fill} stroke={MPAPER} strokeWidth={3.4 * w} strokeLinejoin="round" />
  </>
);

const MadhubaniSage: React.FC = () => (
  <g transform={sageT}>
    {/* frontal torso, wide shoulders, the profile head set on top */}
    <Dbl d="M -96 128 C -50 100 60 100 116 128 L 92 400 L -76 400 Z" fill="#f0b048" />
    <Dbl d="M -96 128 C -50 104 -10 104 12 116 L 30 400 L -76 400 Z" fill="url(#m-red)" />
    {Array.from({length: 9}, (_, i) => <circle key={i} cx={-82 + i * 11} cy={136 - Math.sin(i / 3) * 8} r={2.6} fill={INK} />)}
    <Dbl d="M -18 62 L 22 62 L 26 112 L -22 112 Z" fill="#f0b048" w={0.8} />
    {/* bun and hair */}
    <Dbl d="M -54 -58 C -62 -104 -10 -120 10 -92 C 24 -72 4 -56 -18 -54 Z" fill="url(#m-hatchW)" />
    <Dbl d="M -32 -48 C -60 -30 -64 20 -46 58 L -22 60 C -34 20 -30 -20 -12 -44 Z" fill="url(#m-hatchW)" w={0.8} />
    {/* head: receding forehead running straight into a long pointed nose */}
    <Dbl d="M -30 60 C -54 30 -52 -30 -22 -50 C -6 -60 12 -56 22 -44 L 80 8 L 52 18 C 46 40 20 56 -30 60 Z" fill="#f0b048" />
    {/* large fish-shaped eye */}
    <path d="M -4 -18 C 12 -40 46 -36 62 -12 C 46 0 14 2 -4 -18 Z M -4 -18 L -18 -28 M -4 -18 L -18 -8" fill="#fffaf0" stroke={INK} strokeWidth={3} strokeLinejoin="round" />
    <circle cx={30} cy={-18} r={9} fill={INK} />
    <circle cx={33} cy={-21} r={2.4} fill="#fffaf0" />
    <path d="M -2 -40 C 16 -54 44 -50 60 -32" fill="none" stroke={INK} strokeWidth={4} strokeLinecap="round" />
    {[-60, -55, -50].map((y, i) => <path key={i} d={`M ${0 + i * 4} ${y + 10} L ${18 + i * 4} ${y + 14}`} stroke="#c8322a" strokeWidth={3} strokeLinecap="round" />)}
    {/* beard and mustache in kachni line-fill */}
    <Dbl d="M -14 12 C 10 30 34 28 52 22 C 62 46 62 90 52 130 C 44 160 30 186 12 210 C 0 180 -10 140 -16 100 C -20 60 -22 30 -14 12 Z" fill="url(#m-hatchW)" />
    <Dbl d="M 52 20 C 40 34 26 42 6 44 C 22 52 44 44 56 30 Z" fill="#fffaf0" w={0.7} />
    {/* arms bent, palms joined at the chest, drawn flat and frontal */}
    <Dbl d="M -88 140 C -96 200 -70 250 -20 250 L 6 236 L -6 220 C -40 226 -60 200 -62 150 Z" fill="#f0b048" w={0.8} />
    <Dbl d="M 108 140 C 118 200 96 250 50 250 L 22 236 L 34 220 C 66 226 84 200 82 150 Z" fill="#f0b048" w={0.8} />
    <Dbl d="M 0 246 C 0 210 8 184 18 166 C 28 184 36 210 36 246 Z" fill="#f0b048" w={0.8} />
    <path d="M 18 170 L 18 244" stroke={INK} strokeWidth={2.4} />
    {/* bead necklace: alternating red and black */}
    {Array.from({length: 11}, (_, i) => <circle key={i} cx={-30 + i * 9} cy={114 + Math.sin((i / 10) * Math.PI) * 26} r={4.4} fill={i % 2 ? '#c8322a' : INK} />)}
  </g>
);

const Fish: React.FC<{x: number; y: number; s: number; flip?: boolean; c: string}> = ({x, y, s, flip, c}) => (
  <g transform={`translate(${x} ${y}) scale(${flip ? -s : s} ${s})`}>
    <Dbl d="M -60 0 C -30 -34 30 -34 54 0 C 30 34 -30 34 -60 0 Z" fill="url(#m-scales)" w={0.7} />
    <Dbl d="M 50 0 L 86 -26 L 78 0 L 86 26 Z" fill={c} w={0.7} />
    <Dbl d="M -10 -24 L 8 -42 L 20 -22 Z" fill={c} w={0.6} />
    <circle cx={-38} cy={-4} r={8} fill="#fffaf0" stroke={INK} strokeWidth={2.4} />
    <circle cx={-38} cy={-4} r={3.6} fill={INK} />
    <path d="M -24 -18 C -18 -6 -18 6 -24 18" fill="none" stroke={INK} strokeWidth={2.4} />
  </g>
);

export const StyleMadhubani: React.FC = () => {
  const B = 70;
  const waterY = SP.y + 300 * SP.s;
  const r = rng(31);
  return (
    <AbsoluteFill style={{background: MPAPER}}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%">
        <Handmade id="mb" wobble={3.2} paper={[0.6, 0.45, 0.25]} />
        <defs>
          <pattern id="m-hatchW" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(80)"><rect width="8" height="8" fill="#fffaf0" /><path d="M 0 4 L 8 4" stroke={INK} strokeWidth="1.1" /></pattern>
          <pattern id="m-red" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="10" height="10" fill="#c8322a" /><path d="M 0 5 L 10 5" stroke={INK} strokeWidth="1.4" /></pattern>
          <pattern id="m-scales" width="16" height="12" patternUnits="userSpaceOnUse"><rect width="16" height="12" fill="#f2b705" /><path d="M 0 12 C 0 4 8 4 8 12 C 8 4 16 4 16 12" fill="none" stroke={INK} strokeWidth="1.3" /></pattern>
          <pattern id="m-water" width="60" height="30" patternUnits="userSpaceOnUse"><rect width="60" height="30" fill="#2c5aa0" /><path d="M 0 10 C 15 0 15 20 30 10 C 45 0 45 20 60 10 M 0 20 C 15 10 15 30 30 20 C 45 10 45 30 60 20" fill="none" stroke={INK} strokeWidth="2" /></pattern>
          <pattern id="m-sky" width="44" height="44" patternUnits="userSpaceOnUse"><rect width="44" height="44" fill="#1d2c5c" /><circle cx="10" cy="10" r="2" fill="#f2b705" /><circle cx="32" cy="30" r="1.6" fill="#f1e2bf" /></pattern>
          <pattern id="m-leafG" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(30)"><rect width="7" height="7" fill="#2f8f4e" /><path d="M 0 3.5 L 7 3.5" stroke={INK} strokeWidth="1" /></pattern>
          <pattern id="m-border" width="64" height="64" patternUnits="userSpaceOnUse">
            <rect width="64" height="64" fill={MPAPER} />
            <path d="M 0 64 L 32 8 L 64 64 Z" fill="#c8322a" stroke={INK} strokeWidth="2.4" />
            <path d="M 16 64 L 32 36 L 48 64" fill="#f2b705" stroke={INK} strokeWidth="2" />
            <circle cx="10" cy="14" r="4" fill="#2f8f4e" stroke={INK} strokeWidth="1.5" /><circle cx="54" cy="14" r="4" fill="#2f8f4e" stroke={INK} strokeWidth="1.5" />
          </pattern>
          <clipPath id="m-panel"><rect x={B} y={B} width={W - 2 * B} height={H - 2 * B} /></clipPath>
        </defs>
        <g filter="url(#mb-wob)">
          <rect width={W} height={H} fill="url(#m-border)" />
          <g clipPath="url(#m-panel)">
            <rect width={W} height={H} fill="url(#m-sky)" />
            {/* moon with a face, ringed by petals */}
            <g transform="translate(230 290)">
              {Array.from({length: 16}, (_, i) => <path key={i} d="M -12 -78 L 0 -112 L 12 -78 Z" fill={i % 2 ? '#c8322a' : '#f2b705'} stroke={INK} strokeWidth={2.2} transform={`rotate(${i * 22.5})`} />)}
              <Dbl d="M -76 0 A 76 76 0 1 0 76 0 A 76 76 0 1 0 -76 0 Z" fill="#f6e7b0" />
              <path d="M -46 -12 C -36 -26 -16 -26 -8 -12 C -18 -4 -36 -4 -46 -12 Z M 8 -12 C 16 -26 36 -26 46 -12 C 36 -4 18 -4 8 -12 Z" fill="#fffaf0" stroke={INK} strokeWidth={2.4} />
              <circle cx={-26} cy={-13} r={5} fill={INK} /><circle cx={28} cy={-13} r={5} fill={INK} />
              <path d="M 0 -6 L -6 22 L 6 24" fill="none" stroke={INK} strokeWidth={2.4} />
              <path d="M -16 38 C -6 46 6 46 16 38" fill="#c8322a" stroke={INK} strokeWidth={2.4} />
              <path d="M -50 -30 C -36 -40 -16 -38 -8 -28 M 8 -28 C 16 -38 36 -40 50 -30" fill="none" stroke={INK} strokeWidth={3} />
            </g>
            {/* flowers filling the sky: no empty space */}
            {Array.from({length: 22}, (_, i) => {
              const x = 110 + r() * 860, y = 120 + r() * 900;
              if (Math.hypot(x - 230, y - 290) < 150 || (x > 260 && y > 280)) return null;
              return (
                <g key={i} transform={`translate(${x} ${y})`}>
                  {[0, 60, 120, 180, 240, 300].map((a) => <ellipse key={a} cx={0} cy={-10} rx={5} ry={10} fill={i % 3 ? '#c8322a' : '#2f8f4e'} stroke={INK} strokeWidth={1.8} transform={`rotate(${a})`} />)}
                  <circle r={5} fill="#f2b705" stroke={INK} strokeWidth={1.8} />
                </g>
              );
            })}
            {/* tree of life: hatched trunk, leaves as big double-lined almonds */}
            <rect y={HORIZON} width={W} height={H} fill="url(#m-water)" />
            <path d={`M 0 ${HORIZON} L ${W} ${HORIZON}`} stroke={INK} strokeWidth={5} />
            {ROOTS.map((x, i) => <path key={i} d={`M ${x} ${700 + (i % 3) * 30} L ${x} ${HORIZON}`} stroke={INK} strokeWidth={5} />)}
            <Dbl d={TRUNK} fill="url(#m-red)" />
            {BRANCH_UP.map((d, i) => <g key={i}><path d={d} fill="none" stroke={INK} strokeWidth={20 - i * 3} strokeLinecap="round" /><path d={d} fill="none" stroke="#c8322a" strokeWidth={12 - i * 3} strokeLinecap="round" /></g>)}
            <Dbl d={BRANCH} fill="#c8322a" />
            {canopy.map((c, i) => (
              <g key={i} transform={`translate(${c.x} ${c.y}) rotate(${(c.k * 360) | 0})`}>
                <Dbl d={almond(c.r * 1.7, c.r * 0.62)} fill={c.k < 0.33 ? 'url(#m-leafG)' : c.k < 0.66 ? '#2f8f4e' : '#7bb342'} w={0.75} />
                <path d={`M ${-c.r * 0.8} 0 L ${c.r * 0.8} 0`} stroke={INK} strokeWidth={2.4} />
              </g>
            ))}
            {/* the child: yellow silhouette, a sun-like aureole of triangles and dots */}
            <g transform={`translate(${CHILD_GLOW.x} ${CHILD_GLOW.y})`}>
              {Array.from({length: 24}, (_, i) => <path key={i} d="M -11 -106 L 0 -136 L 11 -106 Z" fill={i % 2 ? '#f2b705' : '#c8322a'} stroke={INK} strokeWidth={2} transform={`rotate(${i * 15})`} />)}
              <Dbl d="M -106 0 A 106 106 0 1 0 106 0 A 106 106 0 1 0 -106 0 Z" fill="#fff3c4" />
              {Array.from({length: 30}, (_, i) => <circle key={i} cx={Math.cos((i / 30) * Math.PI * 2) * 94} cy={Math.sin((i / 30) * Math.PI * 2) * 94} r={3} fill="#c8322a" />)}
            </g>
            <ChildOnLeaf leaf="#2f8f4e" vein={INK} body="#f2b705" line={INK} lw={3} />
            {/* fish and a lotus fill the water */}
            <Fish x={620} y={1290} s={0.8} c="#c8322a" />
            <Fish x={900} y={1420} s={0.7} flip c="#2f8f4e" />
            <MadhubaniSage />
            <rect y={waterY} width={W} height={H} fill="url(#m-water)" />
            <path d={`M 0 ${waterY} L ${W} ${waterY}`} stroke={INK} strokeWidth={5} />
            <Fish x={420} y={waterY + 120} s={0.9} c="#f2b705" />
            <Fish x={820} y={waterY + 70} s={0.75} flip c="#c8322a" />
            <g transform={`translate(860 ${HORIZON + 300})`}>
              {[-50, -25, 0, 25, 50].map((a) => <g key={a} transform={`rotate(${a})`}><Dbl d="M 0 0 C -16 -20 -12 -50 0 -64 C 12 -50 16 -20 0 0 Z" fill="#e57399" w={0.6} /></g>)}
            </g>
          </g>
          <rect x={B} y={B} width={W - 2 * B} height={H - 2 * B} fill="none" stroke={INK} strokeWidth={5} />
          <rect x={B - 12} y={B - 12} width={W - 2 * B + 24} height={H - 2 * B + 24} fill="none" stroke={INK} strokeWidth={3} />
          <rect x={14} y={14} width={W - 28} height={H - 28} fill="none" stroke={INK} strokeWidth={5} />
        </g>
        <Surface id="mb" mottle={0.4} />
      </svg>
    </AbsoluteFill>
  );
};

// =================================================================================== PATTACHITRA
// Built as a multiplane: every element sits on its own depth layer (p = 0 far ... 1 near). A slow camera
// drift moves near layers more than far ones; leaves, waves, fish, halo and the sage also move on their own.
// The border stays fixed, like the frame of a painted cloth. Frame 0 is the approved still.
export const PL = '#120c0a';
export const WD = '#f6efdc'; // conch-shell white
export const PATTA_FRAMES = 180;

export const Dots: React.FC<{d: string; n: number; r?: number}> = ({d, n, r = 2.2}) => {
  // white dots evenly along a cubic path given as "M x y C x y x y x y"
  const v = d.replace(/[MC]/g, ' ').trim().split(/[\s,]+/).map(Number);
  const [x0, y0, x1, y1, x2, y2, x3, y3] = v;
  return (
    <>
      {Array.from({length: n}, (_, i) => {
        const t = i / (n - 1), u = 1 - t;
        const x = u * u * u * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t * t * t * x3;
        const y = u * u * u * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t * t * t * y3;
        return <circle key={i} cx={x} cy={y} r={r} fill={WD} />;
      })}
    </>
  );
};

export const smooth = (x: number) => {
  const c = Math.min(1, Math.max(0, x));
  return c * c * (3 - 2 * c);
};

export type Cam = {x: number; y: number; z: number};
export const Layer: React.FC<{p: number; cam: Cam; children: React.ReactNode}> = ({p, cam, children}) => (
  <g transform={`translate(${W / 2 + cam.x * p} ${H / 2 + cam.y * p}) scale(${1 + cam.z * p}) translate(${-W / 2} ${-H / 2})`}>{children}</g>
);

export type Pose = 'namaste' | 'call' | 'swim';
/** look: 0..1 overrides the gaze lift; bow: 0..1 lowers the head. Without them, the motion-test timing applies. */
export const PattaSage: React.FC<{f: number; pose?: Pose; look?: number; bow?: number}> = ({f, pose = 'namaste', look, bow = 0}) => {
  const t = f / 30;
  const lift = look ?? smooth((t - 0.8) / 2.4);                            // head and gaze rise towards the child
  const headRot = -3.5 * lift + 9 * bow + 0.35 * Math.sin(t * 1.3);
  const blink = Math.min(...[1.7, 4.6].map((b) => Math.abs(t - b)));
  const eyeK = blink < 0.1 ? Math.max(0.08, blink / 0.1) : 1;
  const breathe = 1 + 0.006 * Math.sin(t * 2.1);
  const beard = 1.4 * Math.sin(t * 1.6 + 0.6);
  const tremble = 0.45 * Math.sin(t * 8.5);
  const head = `rotate(${headRot} 0 60)`;
  return (
    <g transform={sageT} stroke={PL} strokeWidth={2.6} strokeLinejoin="round">
      <g transform={head}>
        {/* tall striped jata */}
        <path d="M -50 -52 C -56 -100 -40 -150 -14 -160 C 6 -150 14 -100 6 -56 Z" fill="#f2c14e" />
        {[-70, -90, -110, -130].map((y, i) => <path key={i} d={`M ${-48 + i * 4} ${y + 12} C ${-30} ${y} ${-10} ${y} ${4 - i * 2} ${y + 10}`} fill="none" stroke={PL} strokeWidth={2} />)}
        <Dots d="M -50 -54 C -36 -60 -14 -60 6 -56" n={8} r={2.4} />
        <path d="M -32 -48 C -58 -34 -62 16 -48 56 L -26 60 C -36 20 -30 -20 -12 -42 Z" fill="#f2c14e" />
      </g>
      {/* body breathes: narrow waist, yellow uttariya with red border and white dots */}
      <g transform={`translate(0 380) scale(1 ${breathe}) translate(0 -380)`}>
        <path d="M -28 58 C -34 92 -64 110 -80 140 C -90 200 -88 300 -84 380 L 74 380 C 76 300 74 220 62 172 C 54 140 36 112 20 80 Z" fill="#e2a868" />
        <path d="M -84 138 C -56 108 -6 106 24 126 C 40 172 54 250 62 380 L -88 380 Z" fill="#f2c14e" />
        <path d="M -84 138 C -56 108 -6 106 24 126" fill="none" stroke="#b3261e" strokeWidth={12} />
        <path d="M -84 138 C -56 108 -6 106 24 126" fill="none" stroke={PL} strokeWidth={1.2} />
        <Dots d="M -80 136 C -56 110 -6 108 22 126" n={13} />
        {[0, 1, 2].map((i) => <path key={i} d={`M ${-60 + i * 30} 150 C ${-50 + i * 32} 220 ${-44 + i * 34} 300 ${-46 + i * 36} 380`} fill="none" stroke="#b3261e" strokeWidth={3} />)}
      </g>
      <g transform={head}>
        {/* head: rounded chin under the beard, sharp nose, long tapering eye drawn frontally */}
        <path d="M -28 62 C -56 34 -56 -28 -26 -50 C -6 -64 22 -58 38 -40 C 44 -32 46 -22 48 -14 L 70 8 C 66 12 58 14 54 16 L 52 30 C 44 50 18 60 -28 62 Z" fill="#e2a868" />
        <g transform={`translate(0 -16) scale(1 ${eyeK}) translate(0 16)`}>
          <path d="M -10 -16 C 8 -32 40 -30 58 -14 C 40 -4 10 -4 -10 -16 Z" fill={WD} />
          <circle cx={30 + 3 * lift} cy={-16 - 3 * lift} r={6.4} fill={PL} />
        </g>
        <path d="M -10 -16 L -26 -12" strokeWidth={2.4} />
        <path d={`M -4 ${-32 - 2 * lift} C 14 ${-44 - 3 * lift} 40 ${-42 - 3 * lift} 56 ${-28 - 2 * lift}`} fill="none" strokeWidth={3.4} strokeLinecap="round" />
        <path d="M 20 -48 L 44 -36" stroke="#b3261e" strokeWidth={5} />
        <circle cx={-6} cy={12} r={7} fill="#f2c14e" />
        {/* beard: white, combed with fine black pen-work; sways from the chin */}
        <g transform={`translate(20 24) skewX(${beard}) translate(-20 -24)`}>
          <path d="M -12 10 C 8 30 34 30 54 22 C 64 42 66 76 60 116 C 54 160 44 200 26 244 C 18 228 10 220 2 232 C -4 190 -14 146 -20 100 C -24 60 -22 30 -12 10 Z" fill={WD} />
          {Array.from({length: 8}, (_, i) => <path key={i} d={`M ${-6 + i * 8} ${28 + (i % 2) * 6} C ${-2 + i * 8} 100 ${-6 + i * 6} 170 ${i * 5} ${214 + (i % 3) * 6}`} fill="none" strokeWidth={1} />)}
        </g>
        <path d="M 54 22 C 42 34 28 42 10 44 C 28 50 46 42 58 30 Z" fill={WD} />
      </g>
      {/* rudraksha with a red bead */}
      {Array.from({length: 13}, (_, i) => { const u = i / 12; return <circle key={i} cx={-20 + u * 74 - 40 * u * (1 - u)} cy={68 + 180 * u * (1 - u) * 1.6 + u * 80} r={4} fill={i === 6 ? '#b3261e' : '#5a2416'} strokeWidth={1} />; })}
      {pose === 'call' && (
        <g transform={`rotate(${2 * Math.sin(t * 2)} 0 140)`}>
          <path d="M 0 140 C 30 150 62 124 64 74" fill="none" stroke={PL} strokeWidth={30} strokeLinecap="round" />
          <path d="M 0 140 C 30 150 62 124 64 74" fill="none" stroke="#e2a868" strokeWidth={25} strokeLinecap="round" />
          <path d="M 4 150 L 26 142" stroke="#f2c14e" strokeWidth={7} />
          <path d="M 52 70 C 56 46 70 34 84 38 C 82 54 72 66 60 76 Z" fill="#e2a868" />
        </g>
      )}
      {pose === 'swim' && (
        <g>
          <g transform={`rotate(${14 * Math.sin(t * 4)} -40 150)`}>
            <path d="M -40 150 C -80 150 -120 126 -156 136" fill="none" stroke={PL} strokeWidth={26} strokeLinecap="round" />
            <path d="M -40 150 C -80 150 -120 126 -156 136" fill="none" stroke="#c98a52" strokeWidth={21} strokeLinecap="round" />
          </g>
          <g transform={`rotate(${-14 * Math.sin(t * 4 + 1.4)} 0 140)`}>
            <path d="M 0 140 C 40 128 92 112 136 128" fill="none" stroke={PL} strokeWidth={30} strokeLinecap="round" />
            <path d="M 0 140 C 40 128 92 112 136 128" fill="none" stroke="#e2a868" strokeWidth={25} strokeLinecap="round" />
            <path d="M 132 116 C 150 112 166 120 168 130 C 156 138 142 138 132 136 Z" fill="#e2a868" />
          </g>
        </g>
      )}
      {/* arms with armlets, palms joined in a crisp mudra; a faint tremble of devotion */}
      {pose === 'namaste' && <g transform={`rotate(${tremble} 30 210)`}>
        <path d="M -40 150 C -30 190 0 214 30 210 C 50 206 66 192 78 180" fill="none" stroke={PL} strokeWidth={26} strokeLinecap="round" />
        <path d="M -40 150 C -30 190 0 214 30 210 C 50 206 66 192 78 180" fill="none" stroke="#c98a52" strokeWidth={21} strokeLinecap="round" />
        <path d="M 0 140 C 4 180 16 210 36 214 C 56 212 72 196 84 178" fill="none" stroke={PL} strokeWidth={30} strokeLinecap="round" />
        <path d="M 0 140 C 4 180 16 210 36 214 C 56 212 72 196 84 178" fill="none" stroke="#e2a868" strokeWidth={25} strokeLinecap="round" />
        <path d="M -4 170 L 22 166" stroke="#f2c14e" strokeWidth={7} />
        <path d="M 64 196 L 76 186" stroke="#f2c14e" strokeWidth={7} />
        <path d="M 76 188 C 78 160 86 126 102 94 C 108 90 112 94 110 102 C 106 132 100 162 94 192 Z" fill="#e2a868" />
        <path d="M 86 186 C 90 158 96 130 104 102" fill="none" strokeWidth={1} />
      </g>}
    </g>
  );
};

export const waterPattern = (id: string, dx: number, dy: number, fill: string) => (
  <pattern id={id} width="80" height="40" patternUnits="userSpaceOnUse" patternTransform={`translate(${dx.toFixed(2)} ${dy.toFixed(2)})`}>
    <rect width="80" height="40" fill={fill} />
    <path d="M 0 28 C 10 10 30 10 40 28 C 50 10 70 10 80 28" fill="none" stroke={WD} strokeWidth="2" />
    <path d="M 14 28 C 18 20 26 20 30 26" fill="none" stroke={WD} strokeWidth="1.4" />
    <circle cx="20" cy="12" r="1.8" fill={WD} /><circle cx="60" cy="12" r="1.8" fill={WD} />
  </pattern>
);

export const PattaFish: React.FC<{x: number; y: number; dir: number; t: number; s?: number}> = ({x, y, dir, t, s = 0.8}) => (
  <g transform={`translate(${x} ${y + 4 * Math.sin(t * 1.5 + x)}) scale(${s * dir} ${s})`} stroke={PL} strokeWidth={2.4}>
    <path d="M -60 0 C -30 -32 30 -32 54 0 C 30 32 -30 32 -60 0 Z" fill="#f2c14e" />
    <g transform={`rotate(${10 * Math.sin(t * 5 + x)} 52 0)`}><path d="M 50 0 L 84 -24 L 76 0 L 84 24 Z" fill="#b3261e" /></g>
    {[-20, 0, 20].map((x2) => <path key={x2} d={`M ${x2} -20 C ${x2 + 8} -6 ${x2 + 8} 6 ${x2} 20`} fill="none" strokeWidth={1.4} />)}
    <circle cx={-40} cy={-4} r={6} fill={WD} /><circle cx={-40} cy={-4} r={2.6} fill={PL} />
  </g>
);

export const Clump: React.FC<{c: (typeof canopy)[number]; i: number; t: number}> = ({c, i, t}) => (
  <g transform={`translate(${c.x + 2.5 * Math.sin(t * 0.9 + i * 0.7)} ${c.y}) rotate(${1.6 * Math.sin(t * 1.1 + i)})`}>
    <circle r={c.r} fill={c.k < 0.5 ? '#1f5a3a' : '#2e7d4f'} stroke={PL} strokeWidth={2.6} />
    {Array.from({length: 9}, (_, j) => <path key={j} d={almond(c.r * 0.9, c.r * 0.16)} transform={`rotate(${j * 20 - 170 + 3 * Math.sin(t * 1.7 + i + j)}) translate(${c.r * 0.45} 0)`} fill={c.k < 0.5 ? '#3f9a5e' : '#6cb36e'} stroke={PL} strokeWidth={1.2} />)}
    {Array.from({length: 16}, (_, j) => <circle key={j} cx={Math.cos((j / 16) * Math.PI * 2) * (c.r - 6)} cy={Math.sin((j / 16) * Math.PI * 2) * (c.r - 6)} r={1.8} fill={WD} />)}
  </g>
);

export const StylePattachitra: React.FC = () => {
  const f = useCurrentFrame();
  const t = f / 30;
  const e = smooth(f / PATTA_FRAMES);
  const cam: Cam = {x: 26 - 52 * e, y: -14 + 22 * e, z: 0.07 * e};        // slow drift and push-in
  const waterY = SP.y + 236 * SP.s;
  const r = rng(41);
  const I = 92; // inner panel inset
  const back = canopy.map((c, i) => ({c, i})).filter(({c}) => c.k < 0.5);
  const front = canopy.map((c, i) => ({c, i})).filter(({c}) => c.k >= 0.5);
  const bob = 4 * Math.sin(t * 1.1);
  const bands = [{y0: HORIZON, y1: HORIZON + 130, v: 0.25, p: 0.35, c: '#1b2550'}, {y0: HORIZON + 130, y1: HORIZON + 300, v: 0.55, p: 0.5, c: '#1f2a55'},
    {y0: HORIZON + 300, y1: waterY + 40, v: 0.9, p: 0.65, c: '#22305e'}];
  const sprays = Array.from({length: 26}, () => ({x: 120 + r() * 840, y: 130 + r() * 980, a: r() * 60 - 30}))
    .filter(({x, y}) => !((x > 270 && x < 1000 && y > 300 && y < 1080) || Math.hypot(x - 220, y - 270) < 110));
  return (
    <AbsoluteFill style={{background: PL}}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%">
        <Handmade id="pc" wobble={2.6} paper={[0.55, 0.4, 0.3]} cloth seed={7 + (Math.floor(f / 8) % 3)} />
        <defs>
          {bands.map((b, i) => waterPattern(`p-water${i}`, (f * b.v) % 80, 0, b.c))}
          {waterPattern('p-waterF', (-f * 1.3) % 80, 2 * Math.sin(t * 1.4), '#141c40')}
          <pattern id="p-creeper" width="70" height="44" patternUnits="userSpaceOnUse">
            <rect width="70" height="44" fill="#b3261e" />
            <path d="M 0 22 C 18 4 36 40 52 22 C 60 14 66 16 70 22" fill="none" stroke={WD} strokeWidth="2.4" />
            <path d={almond(20, 6)} transform="translate(18 12) rotate(-40)" fill="#2e7d4f" stroke={PL} strokeWidth="1.4" />
            <path d={almond(20, 6)} transform="translate(44 32) rotate(-40)" fill="#2e7d4f" stroke={PL} strokeWidth="1.4" />
            <circle cx="34" cy="22" r="5" fill="#f2c14e" stroke={PL} strokeWidth="1.4" />
          </pattern>
          <clipPath id="p-panel"><rect x={I} y={I} width={W - 2 * I} height={H - 2 * I} /></clipPath>
        </defs>
        <g filter="url(#pc-wob)">
          <g clipPath="url(#p-panel)">
            {/* L0 sky: flat red ground */}
            <Layer p={0.08} cam={cam}><rect x={-200} y={-200} width={W + 400} height={H + 400} fill="#a8281f" /></Layer>
            {/* L1 moon */}
            <Layer p={0.15} cam={cam}>
              <g transform={`translate(0 ${3 * Math.sin(t * 0.5)})`}>
                <circle cx={220} cy={270} r={60} fill={WD} stroke={PL} strokeWidth={3} />
                <circle cx={246} cy={252} r={54} fill="#a8281f" />
              </g>
            </Layer>
            {/* L2 flower sprays sway on their stems */}
            <Layer p={0.25} cam={cam}>
              {sprays.map((s, i) => (
                <g key={i} transform={`translate(${s.x} ${s.y}) rotate(${s.a + 5 * Math.sin(t * 1.2 + i)} 0 18)`}>
                  <path d="M 0 18 C 0 6 0 -6 0 -14" stroke={WD} strokeWidth={1.6} fill="none" />
                  {[-50, 0, 50].map((a) => <ellipse key={a} cx={0} cy={-18} rx={3.6} ry={8} fill={WD} transform={`rotate(${a} 0 -10)`} />)}
                  <circle cy={-12} r={2.4} fill="#f2c14e" />
                </g>
              ))}
            </Layer>
            {/* L3 far waves */}
            {bands.slice(0, 2).map((b, i) => (
              <Layer key={i} p={b.p} cam={cam}>
                <rect x={-200} y={b.y0} width={W + 400} height={900} fill={`url(#p-water${i})`} />
                <path d={`M -200 ${b.y0} L ${W + 200} ${b.y0}`} stroke={PL} strokeWidth={i ? 2 : 4} />
              </Layer>
            ))}
            {/* L4 tree: roots and trunk, then the back clumps */}
            <Layer p={0.45} cam={cam}>
              {ROOTS.map((x, i) => <path key={i} d={`M ${x} ${700 + (i % 3) * 30} C ${x - 6 + 3 * Math.sin(t + i)} 900 ${x + 8} 1050 ${x - 2} ${HORIZON + 40}`} stroke={PL} strokeWidth={i % 3 ? 4 : 6} fill="none" />)}
              <path d={TRUNK} fill="#3a2418" stroke={PL} strokeWidth={3} />
              {TRUNK_STRANDS.map((d, i) => <path key={i} d={d} fill="none" stroke={WD} strokeWidth={1.4} strokeDasharray="10 8" />)}
              {BRANCH_UP.map((d, i) => <path key={i} d={d} fill="none" stroke={PL} strokeWidth={18 - i * 3} strokeLinecap="round" />)}
              <path d={BRANCH} fill="#3a2418" stroke={PL} strokeWidth={2} />
              {back.map(({c, i}) => <Clump key={i} c={c} i={i} t={t} />)}
            </Layer>
            {/* L5 front clumps, a touch nearer so they slide over the back ones */}
            <Layer p={0.52} cam={cam}>{front.map(({c, i}) => <Clump key={i} c={c} i={i} t={t} />)}</Layer>
            {/* L6 the child: halo turns slowly and breathes, leaf bobs */}
            <Layer p={0.5} cam={cam}>
              <g transform={`translate(0 ${bob})`}>
                <g transform={`translate(${CHILD_GLOW.x} ${CHILD_GLOW.y}) scale(${1 + 0.025 * Math.sin(t * 1.8)})`} stroke={PL} strokeWidth={3}>
                  <circle r={124} fill="#b3261e" />
                  <circle r={112} fill="#f2c14e" />
                  <circle r={98} fill={WD} />
                  <g transform={`rotate(${f * 0.5})`}>
                    {Array.from({length: 40}, (_, i) => <circle key={i} cx={Math.cos((i / 40) * Math.PI * 2) * 118} cy={Math.sin((i / 40) * Math.PI * 2) * 118} r={2} fill={WD} stroke="none" />)}
                  </g>
                </g>
                <ChildOnLeaf leaf="#2e7d4f" vein={WD} body="#e8a92c" line={PL} lw={2.6} />
              </g>
            </Layer>
            {/* L7 near waves and fish */}
            <Layer p={bands[2].p} cam={cam}>
              <rect x={-200} y={bands[2].y0} width={W + 400} height={900} fill="url(#p-water2)" />
              <path d={`M -200 ${bands[2].y0} L ${W + 200} ${bands[2].y0}`} stroke={PL} strokeWidth={2} />
              <PattaFish x={640 + f * 0.9} y={1300} dir={-1} t={t} />
              <PattaFish x={930 - f * 0.7} y={1440} dir={1} t={t} />
            </Layer>
            {/* L8 the sage */}
            <Layer p={0.8} cam={cam}><PattaSage f={f} /></Layer>
            {/* L9 foreground water rises and falls over him, lotuses on top */}
            <Layer p={0.95} cam={cam}>
              <g transform={`translate(0 ${3 * Math.sin(t * 1.4)})`}>
                <rect x={-200} y={waterY} width={W + 400} height={H} fill="url(#p-waterF)" />
                <path d={`M -200 ${waterY} L ${W + 200} ${waterY}`} stroke={PL} strokeWidth={4} />
                <Dots d={`M -100 ${waterY + 10} C 300 ${waterY + 10} 700 ${waterY + 10} ${W + 100} ${waterY + 10}`} n={64} r={2} />
              </g>
            </Layer>
            <Layer p={1} cam={cam}>
              {[[860, waterY + 150, 0], [300, waterY + 220, 2]].map(([x, y, ph], i) => (
                <g key={i} transform={`translate(${x + 6 * Math.sin(t * 0.8 + ph)} ${y + 4 * Math.sin(t * 1.3 + ph)}) rotate(${3 * Math.sin(t + ph)})`} stroke={PL} strokeWidth={2.2}>
                  {[-56, -28, 0, 28, 56].map((a) => <path key={a} d="M 0 0 C -14 -18 -10 -46 0 -60 C 10 -46 14 -18 0 0 Z" fill={a === 0 ? WD : '#f08fa8'} transform={`rotate(${a})`} />)}
                  <ellipse cy={4} rx={42} ry={8} fill="#2e7d4f" />
                </g>
              ))}
            </Layer>
          </g>
          {/* fixed border: black with shimmering white dots, red creeper band, yellow rule */}
          <path fillRule="evenodd" d={`M 0 0 H ${W} V ${H} H 0 Z M ${I} ${I} V ${H - I} H ${W - I} V ${I} Z`} fill={PL} />
          {Array.from({length: 54}, (_, i) => <circle key={`t${i}`} cx={10 + i * 20} cy={16} r={3.4} fill={WD} opacity={0.75 + 0.25 * Math.sin(t * 3 + i * 0.7)} />)}
          {Array.from({length: 54}, (_, i) => <circle key={`b${i}`} cx={10 + i * 20} cy={H - 16} r={3.4} fill={WD} opacity={0.75 + 0.25 * Math.sin(t * 3 + i * 0.7 + 2)} />)}
          {Array.from({length: 96}, (_, i) => <circle key={`l${i}`} cx={16} cy={10 + i * 20} r={3.4} fill={WD} opacity={0.75 + 0.25 * Math.sin(t * 3 + i * 0.7 + 4)} />)}
          {Array.from({length: 96}, (_, i) => <circle key={`r${i}`} cx={W - 16} cy={10 + i * 20} r={3.4} fill={WD} opacity={0.75 + 0.25 * Math.sin(t * 3 + i * 0.7 + 1)} />)}
          <path fillRule="evenodd" d={`M 34 34 H ${W - 34} V ${H - 34} H 34 Z M ${I - 8} ${I - 8} V ${H - I + 8} H ${W - I + 8} V ${I - 8} Z`} fill="url(#p-creeper)" stroke={WD} strokeWidth={2} />
          <path fillRule="evenodd" d={`M ${I - 8} ${I - 8} H ${W - I + 8} V ${H - I + 8} H ${I - 8} Z M ${I} ${I} V ${H - I} H ${W - I} V ${I} Z`} fill="#f2c14e" stroke={PL} strokeWidth={3} />
          <rect x={I} y={I} width={W - 2 * I} height={H - 2 * I} fill="none" stroke={PL} strokeWidth={4} />
        </g>
        <Surface id="pc" mottle={0.45} />
      </svg>
    </AbsoluteFill>
  );
};
