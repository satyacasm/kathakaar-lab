/**
 * Three style frames for the same moment: Markandeya, chest-deep in the cosmic flood, looks up at the
 * divine child (light and silhouette only) lying on a banyan leaf. Same geometry, three treatments:
 *   StyleVector     premium flat vector: rounded shapes, gradients, rim light, glow, layered depth
 *   StyleMiniature  inspired by Pahari miniature painting: flat colour, fine outlines, patterned water, border
 *   StylePainterly  painterly 2.5D: textured edges, haze, god rays, moody light
 * SVG (not three.js) so gradients, blur and texture filters are available. Original artwork, no references traced.
 */
import React from 'react';
import {AbsoluteFill} from 'remotion';

const W = 1080;
const H = 1920;
export const HORIZON = 1190;

export const rng = (seed: number) => () => {
  seed = (seed + 0x6d2b79f5) | 0;
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};

// ---------------------------------------------------------------- shared geometry
// Sage, local coords: head centre at 0,0, facing +x, head radius about 55.
export const SAGE = {
  head: 'M -28 64 C -58 40 -64 -24 -32 -50 C -8 -68 30 -60 44 -36 C 50 -26 50 -16 53 -8 C 58 2 68 10 72 17 C 67 22 61 22 57 23 L 50 40 C 40 55 20 64 -28 64 Z',
  hair: 'M -30 -52 C -56 -40 -68 -6 -62 30 C -58 62 -72 98 -92 126 C -60 118 -40 92 -30 64 C -42 30 -38 -10 -12 -44 Z',
  jata: 'M -52 -62 C -54 -90 -20 -104 2 -88 C 14 -78 8 -60 -8 -54 C -24 -50 -44 -50 -52 -62 Z',
  jataBand: 'M -40 -58 C -30 -66 -14 -66 -4 -58',
  beard: 'M -12 8 C 8 30 34 30 57 24 C 66 40 72 70 68 110 C 64 160 52 210 30 272 C 24 252 14 240 6 252 C 0 200 -12 150 -20 100 C -24 60 -22 30 -12 8 Z',
  beardStrands: ['M 50 40 C 56 90 50 150 34 220', 'M 30 40 C 36 100 30 160 18 220', 'M 10 36 C 10 90 4 140 -4 180', 'M 62 70 C 64 120 54 170 44 210'],
  mustache: 'M 57 24 C 48 34 40 42 26 46 C 40 49 52 41 59 30 Z',
  brow: 'M 20 -22 C 32 -32 48 -29 56 -17 C 45 -22 32 -21 20 -15 Z',
  ear: 'M -4 -10 C -16 -12 -18 10 -4 14',
  torso: 'M -30 58 C -36 90 -66 110 -82 140 C -92 200 -92 300 -88 380 L 80 380 C 82 300 80 220 66 170 C 58 140 40 112 22 80 Z',
  shawl: 'M -88 140 C -60 106 -10 106 26 128 C 46 170 62 250 72 380 L -92 380 Z',
  shawlFolds: ['M -60 130 C -40 200 -30 280 -34 380', 'M -20 122 C 0 200 10 290 8 380', 'M 14 128 C 34 200 46 300 46 380'],
  arm: 'M 0 140 C 4 180 16 210 36 214 C 56 212 72 196 84 178',
  farArm: 'M -40 150 C -30 190 0 214 30 210 C 50 206 66 192 78 180',
  hands: 'M 76 186 C 78 160 86 128 100 100 C 106 96 110 100 108 108 C 104 134 98 162 92 190 Z',
  fingers: 'M 84 184 C 88 160 94 134 104 106',
  waterLocal: 236,
};
export const SAGE_POS = {x: 285, y: 1235, s: 1.75};
export const beadPts = (n: number) => {
  const p0 = [-22, 66], p1 = [6, 230], p2 = [56, 150];
  return Array.from({length: n}, (_, i) => {
    const t = i / (n - 1);
    const u = 1 - t;
    return [u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0], u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]];
  });
};

// Child and leaf, local coords: leaf centre at 0,0, tip to +x. Child lies on its back, toe to mouth.
export const LEAF = 'M -120 0 C -90 -64 40 -74 110 -8 C 120 -4 128 0 142 4 C 122 6 112 8 104 14 C 40 72 -90 62 -120 0 Z';
export const LEAF_VEINS = ['M -116 0 C -40 -4 60 -2 136 4', 'M -60 -2 C -50 -24 -40 -36 -26 -44', 'M -10 -2 C 0 -24 14 -38 30 -44',
  'M 40 0 C 50 -18 62 -28 76 -32', 'M -60 0 C -50 20 -40 32 -26 40', 'M -10 0 C 0 22 14 36 30 42', 'M 40 2 C 52 20 64 28 78 30'];
export const CHILD = {
  head: {cx: -66, cy: -40, r: 29},
  curl: 'M -92 -56 C -100 -66 -92 -76 -82 -70',
  body: 'M -44 -24 C -40 -52 -4 -58 22 -48 C 40 -42 44 -26 38 -16 C 20 -12 -20 -12 -44 -16 Z',
  restLeg: 'M 34 -24 C 56 -30 72 -26 92 -20',
  restFoot: {cx: 98, cy: -22, rx: 9, ry: 6},
  thigh: 'M 30 -34 C 34 -62 26 -84 10 -92',
  shin: 'M 10 -92 C -8 -96 -26 -86 -40 -74',
  foot: {cx: -46, cy: -72, rx: 11, ry: 7},
  arm: 'M -30 -42 C -34 -56 -40 -64 -44 -70',
};
export const CHILD_POS = {x: 540, y: 905, s: 1.05, rot: -6};
export const CHILD_GLOW = {x: CHILD_POS.x - 10, y: CHILD_POS.y - 45};

// Banyan.
export const TRUNK = 'M 690 1205 C 712 1060 684 920 700 790 C 704 760 720 744 744 742 L 812 742 C 838 748 846 772 842 800 C 836 930 846 1070 880 1205 Z';
export const TRUNK_STRANDS = ['M 712 1200 C 724 1060 704 930 718 790', 'M 760 1205 C 760 1060 748 920 758 770', 'M 820 1200 C 806 1060 812 920 818 790'];
export const BRANCH = 'M 712 812 C 670 830 620 850 590 882 C 584 890 594 896 602 890 C 632 866 676 850 716 838 Z';
export const BRANCH_UP = ['M 760 760 C 700 700 600 650 470 630', 'M 790 760 C 840 690 920 640 1060 620', 'M 770 750 C 760 680 740 600 720 500'];
export const ROOTS = [655, 668, 860, 884, 930, 968, 1004, 1046, 350, 372];
export const canopy = (() => {
  const r = rng(11);
  const out: {x: number; y: number; r: number; k: number}[] = [];
  for (let i = 0; i < 110; i++) {
    const a = r() * Math.PI * 2;
    const d = Math.sqrt(r());
    out.push({x: 700 + Math.cos(a) * d * 430, y: 545 + Math.sin(a) * d * 225, r: 48 + r() * 52, k: r()});
  }
  return out.sort((p, q) => p.y - q.y);
})();
export const stars = (() => {
  const r = rng(5);
  return Array.from({length: 170}, () => ({x: r() * W, y: r() * (HORIZON - 60), r: 0.6 + r() * r() * 2.6, a: 0.25 + r() * 0.75}));
})();

const wave = (y: number, amp: number, len: number, phase: number, bottom = H + 20) => {
  let d = `M -20 ${bottom} L -20 ${y}`;
  for (let x = -20; x <= W + 20; x += 12) d += ` L ${x} ${(y + amp * Math.sin((x / len) * Math.PI * 2 + phase)).toFixed(1)}`;
  return d + ` L ${W + 20} ${bottom} Z`;
};
export const crest = (y: number, amp: number, len: number, phase: number) => {
  let d = `M -20 ${y}`;
  for (let x = -20; x <= W + 20; x += 12) d += ` L ${x} ${(y + amp * Math.sin((x / len) * Math.PI * 2 + phase)).toFixed(1)}`;
  return d;
};

type SageLook = {
  skin: string; skinShade: string; beard: string; beardShade: string; shawl: string; shawlShade: string;
  jata: string; line?: string; lineW?: number; rim?: string; bead: string; filter?: string;
};

const Sage: React.FC<{L: SageLook; id: string}> = ({L, id}) => {
  const st = L.line ? {stroke: L.line, strokeWidth: L.lineW ?? 1.6, strokeLinejoin: 'round' as const} : {};
  return (
    <g transform={`translate(${SAGE_POS.x} ${SAGE_POS.y}) scale(${SAGE_POS.s})`} filter={L.filter}>
      <defs>
        <linearGradient id={`${id}skin`} x1="0" x2="1"><stop offset="0" stopColor={L.skinShade} /><stop offset="0.75" stopColor={L.skin} /></linearGradient>
        <linearGradient id={`${id}beard`} x1="0" x2="1"><stop offset="0" stopColor={L.beardShade} /><stop offset="0.8" stopColor={L.beard} /></linearGradient>
        <linearGradient id={`${id}shawl`} x1="0" x2="1"><stop offset="0" stopColor={L.shawlShade} /><stop offset="0.85" stopColor={L.shawl} /></linearGradient>
      </defs>
      <path d={SAGE.hair} fill={`url(#${id}beard)`} {...st} />
      <path d={SAGE.torso} fill={`url(#${id}skin)`} {...st} />
      <path d={SAGE.shawl} fill={`url(#${id}shawl)`} {...st} />
      {SAGE.shawlFolds.map((d, i) => <path key={i} d={d} fill="none" stroke={L.shawlShade} strokeWidth={3} opacity={0.55} strokeLinecap="round" />)}
      {beadPts(15).map(([x, y], i) => <circle key={i} cx={x} cy={y} r={4.6} fill={L.bead} stroke={L.line ?? 'none'} strokeWidth={0.8} />)}
      <path d={SAGE.jata} fill={L.jata} {...st} />
      <path d={SAGE.jataBand} fill="none" stroke={L.shawl} strokeWidth={5} strokeLinecap="round" />
      <path d={SAGE.head} fill={`url(#${id}skin)`} {...st} />
      <path d={SAGE.ear} fill="none" stroke={L.skinShade} strokeWidth={3} strokeLinecap="round" />
      {[-44, -38, -32].map((y) => <path key={y} d={`M ${22 + (y + 44) * 0.3} ${y} L ${42 + (y + 44) * 0.5} ${y + 3}`} stroke="#f4efe6" strokeWidth={2.4} strokeLinecap="round" opacity={0.9} />)}
      <circle cx={47} cy={-30} r={2.6} fill="#c8322a" />
      <path d={SAGE.farArm} fill="none" stroke={L.skinShade} strokeWidth={28} strokeLinecap="round" strokeLinejoin="round" />
      <path d={SAGE.beard} fill={`url(#${id}beard)`} {...st} />
      {SAGE.beardStrands.map((d, i) => <path key={i} d={d} fill="none" stroke={L.beardShade} strokeWidth={1.8} opacity={0.7} strokeLinecap="round" />)}
      <path d={SAGE.mustache} fill={L.beard} {...st} />
      <path d={SAGE.brow} fill={L.beard} {...st} />
      <path d="M 33 -8 C 37 -13 45 -13 49 -9 C 45 -5 37 -5 33 -8 Z" fill="#f6efe2" stroke={L.line ?? L.skinShade} strokeWidth={1.2} />
      <circle cx={44} cy={-10.5} r={2.6} fill="#1a1210" />
      <path d={SAGE.arm} fill="none" stroke={L.line ?? L.skinShade} strokeWidth={L.line ? 33 : 0} strokeLinecap="round" strokeLinejoin="round" />
      <path d={SAGE.arm} fill="none" stroke={`url(#${id}skin)`} strokeWidth={30} strokeLinecap="round" strokeLinejoin="round" />
      <path d={SAGE.hands} fill={L.skin} {...st} />
      <path d={SAGE.fingers} fill="none" stroke={L.skinShade} strokeWidth={1.6} opacity={0.8} />
      {L.rim && (
        <g fill="none" stroke={L.rim} strokeLinecap="round" opacity={0.9}>
          <path d="M 44 -36 C 50 -26 50 -16 53 -8 C 58 2 68 10 72 17" strokeWidth={3} />
          <path d="M 57 24 C 66 40 72 70 68 110 C 64 160 52 210 30 272" strokeWidth={3} />
          <path d="M 2 -88 C 14 -78 8 -60 -8 -54" strokeWidth={2.5} />
          <path d="M 106 102 C 110 104 108 112 106 118 C 102 140 98 162 92 190" strokeWidth={2.5} />
          <path d="M 66 170 C 80 220 82 300 80 380" strokeWidth={2.5} />
        </g>
      )}
    </g>
  );
};

type ChildLook = {leaf: string; leafShade: string; vein: string; body: string; line?: string; filter?: string};
const Child: React.FC<{L: ChildLook}> = ({L}) => (
  <g transform={`translate(${CHILD_POS.x} ${CHILD_POS.y}) rotate(${CHILD_POS.rot}) scale(${CHILD_POS.s})`} filter={L.filter}>
    <path d={LEAF} fill={L.leaf} stroke={L.line ?? L.leafShade} strokeWidth={L.line ? 1.6 : 2} />
    {LEAF_VEINS.map((d, i) => <path key={i} d={d} fill="none" stroke={L.vein} strokeWidth={i ? 1.4 : 2.4} opacity={0.8} />)}
    <g fill={L.body} stroke={L.body} strokeLinecap="round" strokeLinejoin="round">
      <path d={CHILD.restLeg} fill="none" strokeWidth={17} />
      <ellipse {...CHILD.restFoot} />
      <path d={CHILD.body} strokeWidth={2} />
      <path d={CHILD.thigh} fill="none" strokeWidth={22} />
      <path d={CHILD.shin} fill="none" strokeWidth={15} />
      <ellipse {...CHILD.foot} transform="rotate(-30 -46 -72)" />
      <circle {...CHILD.head} />
      <path d={CHILD.curl} fill="none" strokeWidth={5} />
      <path d={CHILD.arm} fill="none" strokeWidth={11} />
    </g>
  </g>
);

// ================================================================ 1. premium flat vector
export const StyleVector: React.FC = () => (
  <AbsoluteFill style={{background: '#050a20'}}>
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%">
      <defs>
        <linearGradient id="v-sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#030617" /><stop offset="0.45" stopColor="#0d1a4a" /><stop offset="0.62" stopColor="#273a85" /><stop offset="0.66" stopColor="#3d4d9a" />
        </linearGradient>
        <radialGradient id="v-glow"><stop offset="0" stopColor="#fff6da" stopOpacity="1" /><stop offset="0.18" stopColor="#ffd77a" stopOpacity="0.85" /><stop offset="0.5" stopColor="#f0a93c" stopOpacity="0.25" /><stop offset="1" stopColor="#f0a93c" stopOpacity="0" /></radialGradient>
        <radialGradient id="v-neb1"><stop offset="0" stopColor="#6a4fd1" stopOpacity="0.35" /><stop offset="1" stopColor="#6a4fd1" stopOpacity="0" /></radialGradient>
        <radialGradient id="v-neb2"><stop offset="0" stopColor="#1fa0b8" stopOpacity="0.25" /><stop offset="1" stopColor="#1fa0b8" stopOpacity="0" /></radialGradient>
        <radialGradient id="v-moon"><stop offset="0" stopColor="#e9f0ff" /><stop offset="0.7" stopColor="#bcd0ff" /><stop offset="1" stopColor="#8fa6e8" /></radialGradient>
        <radialGradient id="v-lit" cx={CHILD_GLOW.x} cy={CHILD_GLOW.y} r="520" gradientUnits="userSpaceOnUse"><stop offset="0" stopColor="#fff" /><stop offset="1" stopColor="#000" /></radialGradient>
        <mask id="v-litmask"><rect width={W} height={H} fill="url(#v-lit)" /></mask>
        <linearGradient id="v-trunk" x1="0" x2="1"><stop offset="0" stopColor="#8a5f3e" /><stop offset="0.35" stopColor="#4a3127" /><stop offset="1" stopColor="#241821" /></linearGradient>
        <linearGradient id="v-sea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#2b3f8c" /><stop offset="1" stopColor="#081233" /></linearGradient>
        <linearGradient id="v-front" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#1a2c6e" /><stop offset="1" stopColor="#050b24" /></linearGradient>
        <linearGradient id="v-leaf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#c9e07a" /><stop offset="1" stopColor="#5f9a3e" /></linearGradient>
        <filter id="v-blur20" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="20" /></filter>
        <filter id="v-blur6" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6" /></filter>
        <filter id="v-childglow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="7" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <radialGradient id="v-vig" cx="0.5" cy="0.5" r="0.75"><stop offset="0.6" stopColor="#000" stopOpacity="0" /><stop offset="1" stopColor="#000" stopOpacity="0.6" /></radialGradient>
        <linearGradient id="v-streak" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#ffd77a" stopOpacity="0.55" /><stop offset="1" stopColor="#ffd77a" stopOpacity="0" /></linearGradient>
      </defs>
      <rect width={W} height={H} fill="url(#v-sky)" />
      <ellipse cx={260} cy={420} rx={520} ry={260} fill="url(#v-neb1)" />
      <ellipse cx={860} cy={250} rx={420} ry={220} fill="url(#v-neb2)" />
      {stars.map((s, i) => <circle key={i} cx={s.x} cy={s.y} r={s.r} fill="#e8eeff" opacity={s.a} />)}
      {[[150, 200], [930, 880], [380, 120]].map(([x, y], i) => (
        <path key={i} d={`M ${x} ${y - 16} L ${x + 3} ${y - 3} L ${x + 16} ${y} L ${x + 3} ${y + 3} L ${x} ${y + 16} L ${x - 3} ${y + 3} L ${x - 16} ${y} L ${x - 3} ${y - 3} Z`} fill="#fff" opacity={0.85} />
      ))}
      <circle cx={190} cy={330} r={150} fill="#9fb6ff" opacity={0.12} filter="url(#v-blur20)" />
      <circle cx={190} cy={330} r={64} fill="url(#v-moon)" />
      <circle cx={214} cy={318} r={58} fill="#0d1a4a" opacity={0.92} />
      {/* far sea bands */}
      <rect y={HORIZON - 4} width={W} height={H} fill="url(#v-sea)" />
      <rect y={HORIZON - 3} width={W} height={3} fill="#9fb6ff" opacity={0.5} />
      {[0, 1, 2, 3].map((i) => (
        <g key={i}>
          <path d={wave(HORIZON + 24 + i * 46, 5 + i * 3, 160 + i * 70, i * 1.7)} fill={['#24398a', '#1d317c', '#18296d', '#13225e'][i]} />
          <path d={crest(HORIZON + 24 + i * 46, 5 + i * 3, 160 + i * 70, i * 1.7)} fill="none" stroke="#8fb1ff" strokeWidth={2} opacity={0.35} />
        </g>
      ))}
      {/* banyan */}
      {ROOTS.map((x, i) => <path key={i} d={`M ${x} ${700 + (i % 3) * 30} C ${x - 6} 900 ${x + 8} 1050 ${x - 2} ${HORIZON + 6}`} stroke={i % 2 ? '#3a2a2a' : '#4c3530'} strokeWidth={i % 3 ? 4 : 6} fill="none" />)}
      <path d={TRUNK} fill="url(#v-trunk)" />
      {TRUNK_STRANDS.map((d, i) => <path key={i} d={d} fill="none" stroke="#1c1218" strokeWidth={3} opacity={0.5} />)}
      <path d="M 692 1200 C 714 1060 686 920 702 790" fill="none" stroke="#ffcf7a" strokeWidth={4} opacity={0.6} />
      {BRANCH_UP.map((d, i) => <path key={i} d={d} fill="none" stroke="#3a2826" strokeWidth={22 - i * 4} strokeLinecap="round" />)}
      <path d={BRANCH} fill="#4a3127" />
      <g>{canopy.map((c, i) => <circle key={i} cx={c.x} cy={c.y} r={c.r} fill={['#0c3236', '#11433f', '#175548', '#0f3a3d'][Math.floor(c.k * 4)]} />)}</g>
      <g mask="url(#v-litmask)">{canopy.map((c, i) => <circle key={i} cx={c.x - c.r * 0.18} cy={c.y + c.r * 0.22} r={c.r * 0.82} fill="#3f8a5c" opacity={0.75} />)}</g>
      {/* child glow and rays */}
      <circle cx={CHILD_GLOW.x} cy={CHILD_GLOW.y} r={380} fill="url(#v-glow)" opacity={0.75} />
      <g opacity={0.13} filter="url(#v-blur6)" transform={`translate(${CHILD_GLOW.x} ${CHILD_GLOW.y})`}>
        {Array.from({length: 12}, (_, i) => <path key={i} d={`M -18 0 L 18 0 L 50 -${380 + (i % 3) * 90} L -50 -${380 + (i % 3) * 90} Z`} fill="#ffe7a8" transform={`rotate(${i * 30 + 12})`} />)}
      </g>
      <Child L={{leaf: 'url(#v-leaf)', leafShade: '#3d6b2a', vein: '#e8f2b0', body: '#fffaf0', filter: 'url(#v-childglow)'}} />
      {/* reflection streak */}
      <rect x={CHILD_GLOW.x - 46} y={HORIZON} width={92} height={520} fill="url(#v-streak)" filter="url(#v-blur6)" />
      {Array.from({length: 14}, (_, i) => <rect key={i} x={CHILD_GLOW.x - 40 + ((i * 37) % 80)} y={HORIZON + 18 + i * 34} width={30 - i} height={3} rx={1.5} fill="#ffe7a8" opacity={0.7 - i * 0.04} />)}
      {/* golden motes */}
      {stars.slice(0, 40).map((s, i) => <circle key={i} cx={CHILD_GLOW.x + (s.x - W / 2) * 0.55} cy={CHILD_GLOW.y + (s.y - 500) * 0.45} r={1 + s.r * 0.8} fill="#ffe7a8" opacity={s.a * 0.8} />)}
      <Sage id="v" L={{skin: '#a86b48', skinShade: '#5e3826', beard: '#eef2fa', beardShade: '#8e9cb8', shawl: '#e5852f', shawlShade: '#9a3f1a', jata: '#d8dde8', rim: '#ffd77a', bead: '#6b2b1e'}} />
      {/* foreground water over the sage */}
      <path d={wave(SAGE_POS.y + SAGE.waterLocal * SAGE_POS.s, 10, 260, 0.6)} fill="url(#v-front)" />
      <path d={crest(SAGE_POS.y + SAGE.waterLocal * SAGE_POS.s, 10, 260, 0.6)} fill="none" stroke="#7fa3ff" strokeWidth={3} opacity={0.45} />
      <ellipse cx={SAGE_POS.x + 20} cy={SAGE_POS.y + SAGE.waterLocal * SAGE_POS.s + 14} rx={190} ry={18} fill="none" stroke="#9fc0ff" strokeWidth={2.5} opacity={0.4} />
      <ellipse cx={SAGE_POS.x + 20} cy={SAGE_POS.y + SAGE.waterLocal * SAGE_POS.s + 30} rx={260} ry={26} fill="none" stroke="#9fc0ff" strokeWidth={2} opacity={0.22} />
      {[0, 1, 2].map((i) => <path key={i} d={crest(1720 + i * 70, 8, 220 + i * 40, i * 2.1)} fill="none" stroke="#5f80d8" strokeWidth={2} opacity={0.25} />)}
      <rect width={W} height={H} fill="url(#v-vig)" />
    </svg>
  </AbsoluteFill>
);

// ================================================================ 2. miniature-painting inspired
const INK = '#2a1a12';
export const StyleMiniature: React.FC = () => {
  const B = 46;
  return (
    <AbsoluteFill style={{background: '#7a1f1a'}}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%">
        <defs>
          <pattern id="m-water" width="96" height="44" patternUnits="userSpaceOnUse">
            <rect width="96" height="44" fill="#24418f" />
            <path d="M 0 30 C 12 8 36 8 48 30 C 60 8 84 8 96 30" fill="none" stroke="#d9e4ff" strokeWidth="2.2" />
            <path d="M 10 30 C 18 18 30 18 38 30 M 58 30 C 66 18 78 18 86 30" fill="none" stroke="#8fa9ea" strokeWidth="1.6" />
            <circle cx="24" cy="14" r="2.2" fill="#d9e4ff" /><circle cx="72" cy="14" r="2.2" fill="#d9e4ff" />
          </pattern>
          <pattern id="m-water2" width="96" height="44" patternUnits="userSpaceOnUse" patternTransform="translate(48 22)">
            <rect width="96" height="44" fill="#1d3577" />
            <path d="M 0 30 C 12 8 36 8 48 30 C 60 8 84 8 96 30" fill="none" stroke="#c4d3fa" strokeWidth="2.2" />
            <path d="M 10 30 C 18 18 30 18 38 30 M 58 30 C 66 18 78 18 86 30" fill="none" stroke="#7d97da" strokeWidth="1.6" />
          </pattern>
          <pattern id="m-leaves" width="40" height="34" patternUnits="userSpaceOnUse">
            <rect width="40" height="34" fill="#1f4a2a" />
            <path d="M 6 20 C 10 8 20 6 24 12 C 20 20 12 24 6 20 Z" fill="#3f7a3a" stroke="#14301c" strokeWidth="1" />
            <path d="M 22 32 C 26 20 36 18 40 24 C 36 32 28 36 22 32 Z" fill="#5a9446" stroke="#14301c" strokeWidth="1" />
          </pattern>
          <pattern id="m-shawl" width="22" height="22" patternUnits="userSpaceOnUse">
            <rect width="22" height="22" fill="#e07a1f" /><circle cx="11" cy="11" r="2.6" fill="#f8d36a" /><circle cx="0" cy="0" r="1.6" fill="#a8421a" /><circle cx="22" cy="22" r="1.6" fill="#a8421a" />
          </pattern>
          <pattern id="m-border" width="60" height="60" patternUnits="userSpaceOnUse">
            <rect width="60" height="60" fill="#7a1f1a" />
            <circle cx="30" cy="30" r="10" fill="#e8b24a" stroke={INK} strokeWidth="1.2" />
            {[0, 60, 120, 180, 240, 300].map((a) => <ellipse key={a} cx="30" cy="16" rx="5" ry="9" fill="#f4e3c0" stroke={INK} strokeWidth="1" transform={`rotate(${a} 30 30)`} />)}
            <circle cx="30" cy="30" r="4" fill="#c8322a" />
          </pattern>
          <filter id="m-paper"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="3" /><feColorMatrix values="0 0 0 0 0.45  0 0 0 0 0.33  0 0 0 0 0.2  0 0 0 0.22 0" /></filter>
          <clipPath id="m-panel"><rect x={B + 14} y={B + 14} width={W - 2 * B - 28} height={H - 2 * B - 28} rx={6} /></clipPath>
        </defs>
        <rect width={W} height={H} fill="url(#m-border)" />
        <g clipPath="url(#m-panel)">
          <rect width={W} height={H} fill="#13235a" />
          <rect y={HORIZON - 160} width={W} height={160} fill="#1d3a7a" />
          <rect y={HORIZON - 70} width={W} height={70} fill="#2c4e94" />
          {stars.filter((_, i) => i % 2 === 0).map((s, i) => (
            <path key={i} d={`M ${s.x} ${s.y - 5} L ${s.x + 1.5} ${s.y - 1.5} L ${s.x + 5} ${s.y} L ${s.x + 1.5} ${s.y + 1.5} L ${s.x} ${s.y + 5} L ${s.x - 1.5} ${s.y + 1.5} L ${s.x - 5} ${s.y} L ${s.x - 1.5} ${s.y - 1.5} Z`} fill="#f2c94c" opacity={0.6 + s.a * 0.4} />
          ))}
          <circle cx={200} cy={300} r={62} fill="#f2d27a" stroke={INK} strokeWidth={1.6} />
          <circle cx={226} cy={284} r={56} fill="#13235a" />
          <rect y={HORIZON} width={W} height={H} fill="url(#m-water)" />
          <rect y={HORIZON} width={W} height={2.5} fill={INK} />
          {/* banyan */}
          {ROOTS.map((x, i) => <path key={i} d={`M ${x} ${700 + (i % 3) * 30} C ${x - 6} 900 ${x + 8} 1050 ${x - 2} ${HORIZON + 4}`} stroke="#6b4428" strokeWidth={i % 3 ? 4 : 6} fill="none" />)}
          <path d={TRUNK} fill="#7a4e2c" stroke={INK} strokeWidth={2} />
          {TRUNK_STRANDS.map((d, i) => <path key={i} d={d} fill="none" stroke={INK} strokeWidth={1.4} opacity={0.8} />)}
          {BRANCH_UP.map((d, i) => <path key={i} d={d} fill="none" stroke="#6b4428" strokeWidth={22 - i * 4} strokeLinecap="round" />)}
          <path d={BRANCH} fill="#7a4e2c" stroke={INK} strokeWidth={1.6} />
          <g stroke={INK} strokeWidth={1.1} strokeOpacity={0.6}>{canopy.map((c, i) => <circle key={i} cx={c.x} cy={c.y} r={c.r} fill="url(#m-leaves)" />)}</g>
          {/* child: gold silhouette with a flat aureole */}
          <g transform={`translate(${CHILD_GLOW.x} ${CHILD_GLOW.y})`}>
            {Array.from({length: 36}, (_, i) => <path key={i} d="M -9 -118 L 0 -146 L 9 -118 Z" fill="#f2c94c" stroke={INK} strokeWidth={1} transform={`rotate(${i * 10})`} />)}
            <circle r={120} fill="#f6dd8a" stroke={INK} strokeWidth={1.6} />
            <circle r={104} fill="none" stroke="#c8322a" strokeWidth={3} />
            <circle r={96} fill="#fbecc0" />
          </g>
          <Child L={{leaf: '#4f8f3a', leafShade: '#2a5a24', vein: '#d6e9a0', body: '#d9a520', line: INK}} />
          <Sage id="m" L={{skin: '#b97a4f', skinShade: '#b97a4f', beard: '#f7f3ea', beardShade: '#b9b2a2', shawl: 'url(#m-shawl)', shawlShade: '#a8421a', jata: '#ece6d8', line: INK, lineW: 1.3, bead: '#7a2a1a'}} />
          <rect y={SAGE_POS.y + SAGE.waterLocal * SAGE_POS.s} width={W} height={H} fill="url(#m-water2)" />
          <rect y={SAGE_POS.y + SAGE.waterLocal * SAGE_POS.s} width={W} height={2.5} fill={INK} />
          {/* a pair of lotuses, a common miniature motif */}
          {[[820, 1560], [930, 1700]].map(([x, y], i) => (
            <g key={i} transform={`translate(${x} ${y})`} stroke={INK} strokeWidth={1.3}>
              {[-50, -25, 0, 25, 50].map((a) => <ellipse key={a} cx={0} cy={-22} rx={11} ry={26} fill="#f3a7b8" transform={`rotate(${a} 0 0)`} />)}
              <ellipse cx={0} cy={4} rx={44} ry={9} fill="#3f7a3a" />
            </g>
          ))}
          <rect width={W} height={H} filter="url(#m-paper)" />
        </g>
        <rect x={B + 14} y={B + 14} width={W - 2 * B - 28} height={H - 2 * B - 28} rx={6} fill="none" stroke="#e8b24a" strokeWidth={8} />
        <rect x={B + 4} y={B + 4} width={W - 2 * B - 8} height={H - 2 * B - 8} rx={8} fill="none" stroke={INK} strokeWidth={2} />
        <rect x={B + 24} y={B + 24} width={W - 2 * B - 48} height={H - 2 * B - 48} rx={4} fill="none" stroke={INK} strokeWidth={1.5} />
      </svg>
    </AbsoluteFill>
  );
};

// ================================================================ 3. painterly 2.5D
export const StylePainterly: React.FC = () => (
  <AbsoluteFill style={{background: '#070a14'}}>
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%">
      <defs>
        <linearGradient id="p-sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#06070f" /><stop offset="0.4" stopColor="#141a33" /><stop offset="0.6" stopColor="#3a3550" /><stop offset="0.64" stopColor="#6a5a63" />
        </linearGradient>
        <filter id="p-clouds" x="0" y="0" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency="0.0022 0.006" numOctaves="5" seed="8" />
          <feColorMatrix values="0 0 0 0 0.55  0 0 0 0 0.52  0 0 0 0 0.62  0 0 0 1.9 -0.85" />
        </filter>
        <filter id="p-brush" x="-10%" y="-10%" width="120%" height="120%">
          <feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="3" seed="2" result="n" />
          <feDisplacementMap in="SourceGraphic" in2="n" scale="14" xChannelSelector="R" yChannelSelector="G" />
        </filter>
        <filter id="p-brushfine" x="-10%" y="-10%" width="120%" height="120%">
          <feTurbulence type="fractalNoise" baseFrequency="0.08" numOctaves="2" seed="4" result="n" />
          <feDisplacementMap in="SourceGraphic" in2="n" scale="5" xChannelSelector="R" yChannelSelector="G" />
        </filter>
        <filter id="p-soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="28" /></filter>
        <filter id="p-soft8" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="8" /></filter>
        <filter id="p-grain" x="0" y="0" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency="0.75" numOctaves="2" seed="9" />
          <feColorMatrix values="0 0 0 0 0.5  0 0 0 0 0.45  0 0 0 0 0.4  0 0 0 0.16 0" />
        </filter>
        <filter id="p-childglow" x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="10" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <radialGradient id="p-glow"><stop offset="0" stopColor="#fff3cf" /><stop offset="0.15" stopColor="#ffc96a" stopOpacity="0.85" /><stop offset="0.55" stopColor="#d9772e" stopOpacity="0.2" /><stop offset="1" stopColor="#d9772e" stopOpacity="0" /></radialGradient>
        <linearGradient id="p-sea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#4a4560" /><stop offset="0.25" stopColor="#1d2238" /><stop offset="1" stopColor="#05070f" /></linearGradient>
        <linearGradient id="p-haze" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#9a8ea0" stopOpacity="0" /><stop offset="0.5" stopColor="#9a8ea0" stopOpacity="0.35" /><stop offset="1" stopColor="#9a8ea0" stopOpacity="0" /></linearGradient>
        <radialGradient id="p-lit" cx={CHILD_GLOW.x} cy={CHILD_GLOW.y} r="600" gradientUnits="userSpaceOnUse"><stop offset="0" stopColor="#fff" /><stop offset="1" stopColor="#000" /></radialGradient>
        <mask id="p-litmask"><rect width={W} height={H} fill="url(#p-lit)" /></mask>
        <radialGradient id="p-vig" cx="0.45" cy="0.5" r="0.75"><stop offset="0.5" stopColor="#000" stopOpacity="0" /><stop offset="1" stopColor="#000" stopOpacity="0.75" /></radialGradient>
      </defs>
      <rect width={W} height={H} fill="url(#p-sky)" />
      <rect width={W} height={HORIZON} filter="url(#p-clouds)" opacity={0.75} />
      {stars.filter((s) => s.y < 500).map((s, i) => <circle key={i} cx={s.x} cy={s.y} r={s.r * 0.7} fill="#dfe4ff" opacity={s.a * 0.5} />)}
      {/* god rays */}
      <g filter="url(#p-soft8)" opacity={0.22} transform={`translate(${CHILD_GLOW.x} ${CHILD_GLOW.y})`}>
        {[-160, -130, -100, -70, -40, -10, 20, 50, 160, 200].map((a, i) => <path key={i} d={`M 0 0 L ${40 + i * 6} -1300 L ${-40 - i * 4} -1300 Z`} fill="#ffd89a" transform={`rotate(${a})`} />)}
      </g>
      <rect y={HORIZON - 4} width={W} height={H} fill="url(#p-sea)" />
      {/* distant tree layers in haze */}
      <g filter="url(#p-brush)">
        {ROOTS.map((x, i) => <path key={i} d={`M ${x} ${700 + (i % 3) * 30} C ${x - 6} 900 ${x + 8} 1050 ${x - 2} ${HORIZON + 6}`} stroke="#241a1c" strokeWidth={i % 3 ? 5 : 8} fill="none" />)}
        <path d={TRUNK} fill="#21181b" />
        {BRANCH_UP.map((d, i) => <path key={i} d={d} fill="none" stroke="#21181b" strokeWidth={24 - i * 4} strokeLinecap="round" />)}
        <path d={BRANCH} fill="#21181b" />
        {canopy.map((c, i) => <circle key={i} cx={c.x} cy={c.y} r={c.r} fill={['#0f1714', '#141f1a', '#18251e'][Math.floor(c.k * 3)]} />)}
        <g mask="url(#p-litmask)">
          {canopy.map((c, i) => <circle key={i} cx={c.x - c.r * 0.2} cy={c.y + c.r * 0.25} r={c.r * 0.75} fill="#6b5a2c" opacity={0.55} />)}
          <path d="M 694 1200 C 716 1060 688 920 704 790" fill="none" stroke="#c98a4a" strokeWidth={6} opacity={0.7} />
        </g>
      </g>
      <rect y={HORIZON - 240} width={W} height={420} fill="url(#p-haze)" />
      <circle cx={CHILD_GLOW.x} cy={CHILD_GLOW.y} r={460} fill="url(#p-glow)" opacity={0.85} />
      <Child L={{leaf: '#7d8a3c', leafShade: '#3f4a1e', vein: '#e8d58a', body: '#fff6dc', filter: 'url(#p-childglow)'}} />
      {/* water: painted glints and the light's reflection */}
      <g filter="url(#p-brush)">
        {Array.from({length: 26}, (_, i) => {
          const y = HORIZON + 20 + i * i * 1.2 + i * 10;
          const w = 60 + i * 9;
          return <ellipse key={i} cx={CHILD_GLOW.x + Math.sin(i * 2.3) * (14 + i * 3)} cy={y} rx={w} ry={2 + i * 0.25} fill="#ffcf85" opacity={0.6 - i * 0.02} />;
        })}
        {[0, 1, 2, 3, 4].map((i) => <path key={i} d={crest(HORIZON + 60 + i * 90, 10 + i * 4, 260 + i * 80, i * 1.3)} fill="none" stroke="#7b7fa8" strokeWidth={3 + i} opacity={0.18} />)}
      </g>
      <g filter="url(#p-brushfine)">
        <Sage id="p" L={{skin: '#5c3a2c', skinShade: '#1d1414', beard: '#b9b3b0', beardShade: '#3d3a40', shawl: '#8a4a26', shawlShade: '#2a1612', jata: '#8a8590', rim: '#ffc978', bead: '#2a1410'}} />
      </g>
      <g filter="url(#p-brush)">
        <path d={wave(SAGE_POS.y + SAGE.waterLocal * SAGE_POS.s, 12, 260, 0.6)} fill="#0b0e1c" />
        <path d={crest(SAGE_POS.y + SAGE.waterLocal * SAGE_POS.s, 12, 260, 0.6)} fill="none" stroke="#e0a860" strokeWidth={3} opacity={0.5} />
      </g>
      <ellipse cx={SAGE_POS.x + 40} cy={SAGE_POS.y + SAGE.waterLocal * SAGE_POS.s + 120} rx={500} ry={90} fill="#8a7f95" opacity={0.18} filter="url(#p-soft)" />
      {stars.slice(0, 50).map((s, i) => <circle key={i} cx={CHILD_GLOW.x + (s.x - W / 2) * 0.7} cy={CHILD_GLOW.y + (s.y - 500) * 0.6} r={0.8 + s.r * 0.7} fill="#ffe2a8" opacity={s.a * 0.7} />)}
      <rect width={W} height={H} fill="url(#p-vig)" />
      <rect width={W} height={H} filter="url(#p-grain)" />
    </svg>
  </AbsoluteFill>
);
