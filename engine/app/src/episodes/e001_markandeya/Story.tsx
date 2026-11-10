/**
 * The Markandeya story in Pattachitra (final style), on the approved English timeline (timing.json, 1103 frames).
 * Every scene is a multiplane of depth layers (p = 0 far ... 1 near) with its own slow camera; transitions come from
 * the scroll-painting idiom: a creeper band unrolling across the cloth, or a lotus-ring iris. The border is fixed.
 * Cue frames match the existing sound: lightning 14/48, wave impact 82, burst 103, swell 125, distant thunder 228,
 * whoosh 643, whiteout 675-734, word cuts 848/872/892, fade 1074-1103.
 */
import React from 'react';
import {AbsoluteFill, Audio, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {BRANCH, BRANCH_UP, CHILD_GLOW, CHILD_POS, HORIZON, ROOTS, SAGE_POS, TRUNK, TRUNK_STRANDS, canopy, rng} from '../../kit/geometry';
import {Cam, ChildOnLeaf, Clump, Dots, Handmade, Layer, PL, PattaFish, PattaSage, Pose, Surface, WD, almond, smooth, waterPattern} from '../../kit/pattachitra';

const W = 1080;
const H = 1920;
const I = 92;                     // inner panel inset (border width)
const RED = '#a8281f';
const NIGHT = '#120c0a';
const GOLD = '#f2c14e';
const GREEN = '#2e7d4f';
const STORY_FRAMES = 1103;
const lerp = (a: number, b: number, x: number) => a + (b - a) * Math.min(1, Math.max(0, x));
const span = (f: number, a: number, b: number) => smooth((f - a) / (b - a));
const hexMix = (a: string, b: string, x: number) => {
  const p = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const [A, B] = [p(a), p(b)];
  return '#' + A.map((v, i) => Math.round(lerp(v, B[i], x)).toString(16).padStart(2, '0')).join('');
};
const NOCAM: Cam = {x: 0, y: 0, z: 0};

type SceneProps = {f: number; id: string};

// ------------------------------------------------------------------ motifs
const cloudPath = (w: number, n: number) => {
  const r = w / (2 * n);
  let d = `M 0 0`;
  for (let i = 0; i < n; i++) d += ` a ${r} ${r * 1.1} 0 0 1 ${2 * r} 0`;
  return d + ` C ${w} ${r * 0.8} 0 ${r * 0.8} 0 0 Z`;
};
const Cloud: React.FC<{x: number; y: number; w: number; n?: number; fill?: string}> = ({x, y, w, n = 5, fill = '#2a1f2a'}) => {
  const r = w / (2 * (n));
  return (
    <g transform={`translate(${x} ${y})`} stroke={PL} strokeWidth={2.6}>
      <path d={cloudPath(w, n)} fill={fill} />
      {Array.from({length: n}, (_, i) => <path key={i} d={`M ${r * (2 * i + 0.5)} -${r * 0.2} a ${r * 0.5} ${r * 0.5} 0 1 1 ${r} 0`} fill="none" stroke={WD} strokeWidth={1.8} />)}
    </g>
  );
};
const Hut: React.FC<{x: number; y: number; s: number}> = ({x, y, s}) => (
  <g transform={`translate(${x} ${y}) scale(${s})`} stroke={PL} strokeWidth={2.4} strokeLinejoin="round">
    <rect x={-50} y={-60} width={100} height={60} fill="#d9a25a" />
    {[-30, -10, 10, 30].map((x2) => <path key={x2} d={`M ${x2} -56 L ${x2} -4`} stroke="#b3261e" strokeWidth={2} />)}
    <path d="M -64 -56 L 0 -112 L 64 -56 Z" fill="#6a3b1e" />
    {[-40, -20, 0, 20, 40].map((x2) => <path key={x2} d={`M ${x2 * 0.9} -62 L ${x2 * 0.2} -104`} strokeWidth={1.2} />)}
    <path d="M -14 0 L -14 -30 C -14 -42 14 -42 14 -30 L 14 0 Z" fill={PL} />
  </g>
);
const Temple: React.FC<{x: number; y: number; s: number}> = ({x, y, s}) => (
  <g transform={`translate(${x} ${y}) scale(${s})`} stroke={PL} strokeWidth={2.4} strokeLinejoin="round">
    <rect x={-60} y={-70} width={120} height={70} fill="#f2e3c0" />
    <path d="M -46 -70 C -50 -170 -20 -230 0 -240 C 20 -230 50 -170 46 -70 Z" fill="#e8b860" />
    {[-90, -115, -140, -165, -190].map((y2) => <path key={y2} d={`M ${-46 + (y2 + 70) * -0.12} ${y2} L ${46 - (y2 + 70) * -0.12} ${y2}`} strokeWidth={1.6} />)}
    <circle cy={-248} r={10} fill={GOLD} />
    <path d="M 0 -258 L 0 -300 L 30 -290 L 0 -280" fill="#b3261e" strokeWidth={1.8} />
    <path d="M -16 0 L -16 -36 C -16 -50 16 -50 16 -36 L 16 0 Z" fill={PL} />
  </g>
);
const Palm: React.FC<{x: number; y: number; s: number; t: number}> = ({x, y, s, t}) => (
  <g transform={`translate(${x} ${y}) scale(${s})`} stroke={PL} strokeWidth={2.4}>
    <path d="M 0 0 C 6 -60 -4 -130 10 -200" fill="none" stroke={PL} strokeWidth={14} />
    <path d="M 0 0 C 6 -60 -4 -130 10 -200" fill="none" stroke="#6a3b1e" strokeWidth={9} />
    <g transform={`translate(10 -200) rotate(${4 * Math.sin(t * 2)})`}>
      {[-150, -115, -80, -45, -10, 25].map((a) => <path key={a} d={almond(110, 14)} transform={`rotate(${a}) translate(55 0)`} fill={GREEN} />)}
    </g>
  </g>
);
const Lightning: React.FC<{x: number; on: number}> = ({x, on}) =>
  on > 0 ? <path d={`M ${x} 120 L ${x - 50} 340 L ${x + 10} 330 L ${x - 70} 620`} fill="none" stroke={GOLD} strokeWidth={10} strokeLinejoin="round" opacity={on} /> : null;

/** Big curling wave with a white-dotted crest; top edge at y. */
const WaveWall: React.FC<{y: number; t: number; fill: string}> = ({y, t, fill}) => {
  let d = `M -200 ${H + 200} L -200 ${y + 60}`;
  for (let i = 0; i < 6; i++) {
    const x0 = -200 + i * 260 + 30 * Math.sin(t * 2 + i);
    d += ` C ${x0 + 80} ${y + 60} ${x0 + 120} ${y - 40} ${x0 + 190} ${y - 30} C ${x0 + 250} ${y - 20} ${x0 + 240} ${y + 40} ${x0 + 200} ${y + 30} C ${x0 + 220} ${y + 70} ${x0 + 250} ${y + 60} ${x0 + 260} ${y + 60}`;
  }
  d += ` L ${W + 400} ${H + 200} Z`;
  return (
    <g>
      <path d={d} fill={fill} stroke={PL} strokeWidth={4} />
      {Array.from({length: 6}, (_, i) => {
        const x0 = -200 + i * 260 + 30 * Math.sin(t * 2 + i);
        return <path key={i} d={`M ${x0 + 120} ${y + 10} C ${x0 + 150} ${y - 20} ${x0 + 200} ${y - 20} ${x0 + 210} ${y + 10}`} fill="none" stroke={WD} strokeWidth={3} />;
      })}
    </g>
  );
};

/** Rain: short white strokes falling at a slant. */
const Rain: React.FC<{f: number; n?: number; seed?: number; o?: number}> = ({f, n = 90, seed = 3, o = 0.7}) => {
  const r = rng(seed);
  return (
    <g stroke={WD} strokeWidth={2} strokeLinecap="round" opacity={o}>
      {Array.from({length: n}, (_, i) => {
        const x0 = r() * (W + 400) - 200, y0 = r() * H, v = 22 + r() * 10;
        const y = ((y0 + f * v) % (H + 100)) - 50;
        const x = x0 - ((f * v) % (H + 100)) * 0.25;
        return <path key={i} d={`M ${x} ${y} l -8 32`} />;
      })}
    </g>
  );
};

const NightSky: React.FC<{seed?: number}> = ({seed = 9}) => {
  const r = rng(seed);
  return (
    <>
      <rect x={-300} y={-300} width={W + 600} height={H + 600} fill={NIGHT} />
      {Array.from({length: 120}, (_, i) => <circle key={i} cx={r() * (W + 200) - 100} cy={r() * 1300} r={1 + r() * 2.2} fill={WD} opacity={0.5 + r() * 0.5} />)}
      {Array.from({length: 14}, (_, i) => {
        const x = r() * W, y = r() * 1100;
        return <g key={`s${i}`} transform={`translate(${x} ${y})`}>{[0, 45, 90, 135].map((a) => <path key={a} d="M 0 -9 L 0 9" stroke={WD} strokeWidth={1.6} transform={`rotate(${a})`} />)}</g>;
      })}
    </>
  );
};

/** Moon with a phase in [0,1]: 0 new, 0.5 full. */
const Moon: React.FC<{x: number; y: number; r: number; phase: number; ground: string}> = ({x, y, r, phase, ground}) => {
  const off = Math.cos(phase * Math.PI * 2) * r * 2.1;
  return (
    <g>
      <circle cx={x} cy={y} r={r} fill={WD} stroke={PL} strokeWidth={3} />
      {Math.abs(off) < r * 2.05 && <circle cx={x + off} cy={y - r * 0.15} r={r * 1.02} fill={ground} />}
    </g>
  );
};

// ------------------------------------------------------------------ scenes
/** A: dusk on the riverbank, storm, lightning, the wave wall swallows everything (0-110). */
const Deluge: React.FC<SceneProps> = ({f}) => {
  const t = f / 30;
  const dark = span(f, 0, 50);
  const flash = Math.max(f >= 14 && f <= 18 ? 1 - (f - 14) / 5 : 0, f >= 48 && f <= 51 ? 1 - (f - 48) / 4 : 0);
  const waveY = lerp(1950, -260, ((f - 18) / 66) ** 1.4);
  const cam: Cam = {x: 0, y: 10 * Math.sin(f * 1.7) * span(f, 60, 82), z: 0.05 * span(f, 0, 90)};
  return (
    <g>
      <Layer p={0.1} cam={cam}><rect x={-300} y={-300} width={W + 600} height={H + 600} fill={hexMix(RED, '#4a1210', dark)} /></Layer>
      <Layer p={0.25} cam={cam}>
        {[[-60, 220, 520], [420, 160, 600], [160, 420, 460], [640, 470, 520]].map(([x, y, w], i) => (
          <Cloud key={i} x={x + (i % 2 ? -1 : 1) * 120 * (1 - span(f, 0, 40))} y={y} w={w} n={6} />
        ))}
        <Lightning x={720} on={f < 30 ? flash : 0} />
        <Lightning x={300} on={f > 40 ? flash : 0} />
      </Layer>
      <Layer p={0.5} cam={cam}>
        <rect x={-300} y={1250} width={W + 600} height={800} fill="#3f7a3a" stroke={PL} strokeWidth={4} />
        {Array.from({length: 7}, (_, i) => <path key={i} d={`M -300 ${1290 + i * 40} L ${W + 300} ${1290 + i * 40}`} stroke="#2a5a2a" strokeWidth={3} strokeDasharray="30 14" />)}
        <path d="M -300 1420 C 200 1380 500 1480 1400 1440 L 1400 1520 C 500 1560 200 1460 -300 1500 Z" fill="url(#A-river)" stroke={PL} strokeWidth={3} />
        <Palm x={140} y={1260} s={1.1} t={t} />
        <Temple x={560} y={1262} s={1.15} />
        <Hut x={300} y={1262} s={1} />
        <Hut x={820} y={1262} s={1.1} />
        <Palm x={960} y={1260} s={0.9} t={t + 1} />
      </Layer>
      <Layer p={0.9} cam={cam}><WaveWall y={waveY} t={t} fill="url(#A-water)" /></Layer>
      {flash > 0 && <rect x={-300} y={-300} width={W + 600} height={H + 600} fill={WD} opacity={0.55 * flash} />}
    </g>
  );
};

/** B: the sage bursts up through the surface and is tossed by the swell (96-153). */
const Burst: React.FC<SceneProps> = ({f}) => {
  const t = f / 30;
  const up = span(f, 0, 8);
  const hit = span(f, 26, 34) * (1 - span(f, 34, 56));
  const cam: Cam = {x: 18 * Math.sin(f * 0.9) * (1 - span(f, 0, 50)), y: 0, z: 0};
  return (
    <g>
      <Layer p={0.1} cam={cam}><rect x={-300} y={-300} width={W + 600} height={H + 600} fill="#4a1210" /></Layer>
      <Layer p={0.25} cam={cam}><Cloud x={-80} y={240} w={620} n={6} /><Cloud x={520} y={180} w={560} n={6} /></Layer>
      <Layer p={0.4} cam={cam}><Rain f={f + 96} n={60} o={0.5} /></Layer>
      <Layer p={0.5} cam={cam}><WaveWall y={900 + 30 * Math.sin(t * 3)} t={t} fill="url(#B-water0)" /></Layer>
      <Layer p={0.8} cam={cam}>
        <g transform={`translate(${215 - 60 * hit} ${-170 + 520 * (1 - up) + 18 * Math.sin(t * 4)}) rotate(${-8 * hit + 4 * Math.sin(t * 3)} ${SAGE_POS.x} ${SAGE_POS.y})`}>
          <PattaSage f={f + 200} pose="swim" look={0.8} />
        </g>
      </Layer>
      {/* splash: white drops flying out from where he breaks the surface */}
      {f >= 6 && f < 30 && (
        <Layer p={0.85} cam={cam}>
          {Array.from({length: 22}, (_, i) => {
            const a = -Math.PI * (0.15 + 0.7 * (i / 21));
            const k = (f - 6) / 24;
            return <circle key={i} cx={520 + Math.cos(a) * 320 * k} cy={1180 + Math.sin(a) * 300 * k + 400 * k * k} r={7 - 4 * k} fill={WD} stroke={PL} strokeWidth={1.5} />;
          })}
        </Layer>
      )}
      <Layer p={0.95} cam={cam}><WaveWall y={1300 - 120 * hit + 26 * Math.sin(t * 2.6 + 1)} t={t + 2} fill="url(#B-water1)" /></Layer>
    </g>
  );
};

/** C1: a tiny figure alone on the endless night ocean in the rain; the moon cycles: years pass (153-237). */
const DriftWide: React.FC<SceneProps> = ({f}) => {
  const t = f / 30;
  const cam: Cam = {x: 0, y: 0, z: 0.08 * span(f, 0, 100)};
  return (
    <g>
      <Layer p={0.1} cam={cam}><NightSky /></Layer>
      <Layer p={0.2} cam={cam}>
        {/* one moon crossing the sky while its phases turn over and over: years passing */}
        <Moon x={lerp(1000, 80, f / 84)} y={460 - 260 * Math.sin((f / 84) * Math.PI)} r={44} phase={(0.1 + f / 28) % 1} ground={NIGHT} />
      </Layer>
      <Layer p={0.35} cam={cam}><rect x={-300} y={1000} width={W + 600} height={1200} fill="url(#C1-water0)" /><path d={`M -300 1000 L ${W + 300} 1000`} stroke={PL} strokeWidth={4} /></Layer>
      <Layer p={0.45} cam={cam}>
        <g transform={`translate(${540 - SAGE_POS.x * 0.32} ${1010 - SAGE_POS.y * 0.32 + 6 * Math.sin(t * 1.4)}) scale(0.32)`}>
          <PattaSage f={f} pose="namaste" look={0.2} bow={0.3} />
        </g>
      </Layer>
      <Layer p={0.6} cam={cam}><rect x={-300} y={1080} width={W + 600} height={1200} fill="url(#C1-water1)" /><path d={`M -300 1080 L ${W + 300} 1080`} stroke={PL} strokeWidth={3} /></Layer>
      <Layer p={0.8} cam={cam}><Rain f={f + 153} n={110} /></Layer>
      {f >= 75 && f <= 79 && <rect x={-300} y={-300} width={W + 600} height={H + 600} fill={WD} opacity={0.45 * (1 - (f - 75) / 5)} />}
    </g>
  );
};

/** C2: closer; he calls out, his voice rings spread and fade, nothing answers (237-321). */
const DriftCall: React.FC<SceneProps> = ({f}) => {
  const t = f / 30;
  const cam: Cam = {x: -30 + 40 * span(f, 0, 84), y: 0, z: 0.05 * span(f, 0, 84)};
  return (
    <g>
      <Layer p={0.1} cam={cam}><NightSky seed={13} /></Layer>
      <Layer p={0.2} cam={cam}><Moon x={820} y={330} r={50} phase={0.12} ground={NIGHT} /></Layer>
      <Layer p={0.35} cam={cam}><rect x={-300} y={1150} width={W + 600} height={1200} fill="url(#C2-water0)" /><path d={`M -300 1150 L ${W + 300} 1150`} stroke={PL} strokeWidth={4} /></Layer>
      <Layer p={0.8} cam={cam}>
        <g transform={`translate(80 ${-60 + 10 * Math.sin(t * 1.3)})`}><PattaSage f={f} pose="call" look={0.35} /></g>
        {/* voice rings: dotted arcs that widen and fade */}
        {[0, 1, 2].map((k) => {
          const u = ((f + k * 28) % 84) / 84;
          const R = 40 + u * 420;
          return <path key={k} d={`M ${520 + R * Math.cos(-0.6)} ${1080 + R * Math.sin(-0.6)} A ${R} ${R} 0 0 1 ${520 + R * Math.cos(0.6)} ${1080 + R * Math.sin(0.6)}`}
            fill="none" stroke={WD} strokeWidth={4} strokeDasharray="2 14" strokeLinecap="round" opacity={(1 - u) * 0.9} />;
        })}
      </Layer>
      <Layer p={0.95} cam={cam}><WaveWall y={1640 + 14 * Math.sin(t * 1.6)} t={t} fill="url(#C2-water1)" /></Layer>
      <Layer p={1} cam={cam}><Rain f={f + 237} n={80} seed={5} /></Layer>
    </g>
  );
};

/** D: a point of light on the horizon becomes the banyan standing in the flood, leaves edged in gold (321-416). */
const BanyanReveal: React.FC<SceneProps> = ({f}) => {
  const t = f / 30;
  const cam: Cam = {x: 0, y: 30, z: 0.18 * span(f, 0, 95)};
  const s = 0.78;
  const tree = `translate(${540 - 720 * s} ${1180 - HORIZON * s}) scale(${s})`;
  return (
    <g>
      <Layer p={0.1} cam={cam}><NightSky seed={21} /></Layer>
      <Layer p={0.4} cam={cam}><rect x={-300} y={1180} width={W + 600} height={1200} fill="url(#D-water0)" /><path d={`M -300 1180 L ${W + 300} 1180`} stroke={PL} strokeWidth={4} /></Layer>
      <Layer p={0.5} cam={cam}>
        <g transform={tree}>
          {ROOTS.map((x, i) => <path key={i} d={`M ${x} ${700 + (i % 3) * 30} C ${x - 6 + 3 * Math.sin(t + i)} 900 ${x + 8} 1050 ${x - 2} ${HORIZON + 30}`} stroke={PL} strokeWidth={i % 3 ? 4 : 6} fill="none" />)}
          <path d={TRUNK} fill="#3a2418" stroke={PL} strokeWidth={3} />
          {TRUNK_STRANDS.map((d, i) => <path key={i} d={d} fill="none" stroke={WD} strokeWidth={1.4} strokeDasharray="10 8" />)}
          {BRANCH_UP.map((d, i) => <path key={i} d={d} fill="none" stroke={PL} strokeWidth={18 - i * 3} strokeLinecap="round" />)}
          {canopy.map((c, i) => <Clump key={i} c={c} i={i} t={t} />)}
          {canopy.map((c, i) => <circle key={`g${i}`} cx={c.x + 2.5 * Math.sin(t * 0.9 + i * 0.7)} cy={c.y} r={c.r - 1} fill="none" stroke={GOLD} strokeWidth={3} opacity={0.85} />)}
        </g>
      </Layer>
      <Layer p={0.7} cam={cam}><rect x={-300} y={1330} width={W + 600} height={1200} fill="url(#D-water1)" /><path d={`M -300 1330 L ${W + 300} 1330`} stroke={PL} strokeWidth={3} /></Layer>
    </g>
  );
};

/** The motion-test composition: banyan, child on the leaf, the sage in the water. Shared by E and F. */
const BanyanScene: React.FC<SceneProps & {cam: Cam; look?: number; bow?: number; halo?: number; pull?: number}> = ({f, id, cam, look, bow, halo = 0, pull = 0}) => {
  const t = f / 30;
  const waterY = SAGE_POS.y + 236 * SAGE_POS.s;
  const r = rng(41);
  const back = canopy.map((c, i) => ({c, i})).filter(({c}) => c.k < 0.5);
  const front = canopy.map((c, i) => ({c, i})).filter(({c}) => c.k >= 0.5);
  const bob = 4 * Math.sin(t * 1.1);
  const bands = [{y0: HORIZON, v: 0.25, p: 0.35}, {y0: HORIZON + 130, v: 0.55, p: 0.5}, {y0: HORIZON + 300, v: 0.9, p: 0.65}];
  const sprays = Array.from({length: 26}, () => ({x: 120 + r() * 840, y: 130 + r() * 980, a: r() * 60 - 30}))
    .filter(({x, y}) => !((x > 270 && x < 1000 && y > 300 && y < 1080) || Math.hypot(x - 220, y - 270) < 110));
  const pullT = `translate(${(CHILD_GLOW.x - SAGE_POS.x) * pull} ${(CHILD_GLOW.y - SAGE_POS.y - 100) * pull}) rotate(${-260 * pull * pull} ${SAGE_POS.x} ${SAGE_POS.y}) translate(${SAGE_POS.x} ${SAGE_POS.y}) scale(${1 - 0.85 * pull}) translate(${-SAGE_POS.x} ${-SAGE_POS.y})`;
  return (
    <g>
      <defs>
        {bands.map((b, i) => waterPattern(`${id}-w${i}`, (f * b.v) % 80, 0, ['#1b2550', '#1f2a55', '#22305e'][i]))}
        {waterPattern(`${id}-wF`, (-f * 1.3) % 80, 2 * Math.sin(t * 1.4), '#141c40')}
      </defs>
      <Layer p={0.08} cam={cam}><rect x={-300} y={-300} width={W + 600} height={H + 600} fill={RED} /></Layer>
      <Layer p={0.15} cam={cam}>
        <g transform={`translate(0 ${3 * Math.sin(t * 0.5)})`}>
          <circle cx={220} cy={270} r={60} fill={WD} stroke={PL} strokeWidth={3} />
          <circle cx={246} cy={252} r={54} fill={RED} />
        </g>
      </Layer>
      <Layer p={0.25} cam={cam}>
        {sprays.map((s, i) => (
          <g key={i} transform={`translate(${s.x} ${s.y}) rotate(${s.a + 5 * Math.sin(t * 1.2 + i)} 0 18)`}>
            <path d="M 0 18 C 0 6 0 -6 0 -14" stroke={WD} strokeWidth={1.6} fill="none" />
            {[-50, 0, 50].map((a) => <ellipse key={a} cx={0} cy={-18} rx={3.6} ry={8} fill={WD} transform={`rotate(${a} 0 -10)`} />)}
            <circle cy={-12} r={2.4} fill={GOLD} />
          </g>
        ))}
      </Layer>
      {bands.slice(0, 2).map((b, i) => (
        <Layer key={i} p={b.p} cam={cam}>
          <rect x={-300} y={b.y0} width={W + 600} height={900} fill={`url(#${id}-w${i})`} />
          <path d={`M -300 ${b.y0} L ${W + 300} ${b.y0}`} stroke={PL} strokeWidth={i ? 2 : 4} />
        </Layer>
      ))}
      <Layer p={0.45} cam={cam}>
        {ROOTS.map((x, i) => <path key={i} d={`M ${x} ${700 + (i % 3) * 30} C ${x - 6 + 3 * Math.sin(t + i)} 900 ${x + 8} 1050 ${x - 2} ${HORIZON + 40}`} stroke={PL} strokeWidth={i % 3 ? 4 : 6} fill="none" />)}
        <path d={TRUNK} fill="#3a2418" stroke={PL} strokeWidth={3} />
        {TRUNK_STRANDS.map((d, i) => <path key={i} d={d} fill="none" stroke={WD} strokeWidth={1.4} strokeDasharray="10 8" />)}
        {BRANCH_UP.map((d, i) => <path key={i} d={d} fill="none" stroke={PL} strokeWidth={18 - i * 3} strokeLinecap="round" />)}
        <path d={BRANCH} fill="#3a2418" stroke={PL} strokeWidth={2} />
        {back.map(({c, i}) => <Clump key={i} c={c} i={i} t={t} />)}
      </Layer>
      <Layer p={0.52} cam={cam}>{front.map(({c, i}) => <Clump key={i} c={c} i={i} t={t} />)}</Layer>
      <Layer p={0.5} cam={cam}>
        <g transform={`translate(0 ${bob})`}>
          <g transform={`translate(${CHILD_GLOW.x} ${CHILD_GLOW.y}) scale(${1 + 0.025 * Math.sin(t * 1.8) + 0.12 * halo})`} stroke={PL} strokeWidth={3}>
            {halo > 0 && <circle r={150} fill={GOLD} opacity={0.35 * halo} stroke="none" />}
            <circle r={124} fill="#b3261e" />
            <circle r={112} fill={GOLD} />
            <circle r={98} fill={WD} />
            <g transform={`rotate(${f * 0.5})`}>
              {Array.from({length: 40}, (_, i) => <circle key={i} cx={Math.cos((i / 40) * Math.PI * 2) * 118} cy={Math.sin((i / 40) * Math.PI * 2) * 118} r={2} fill={WD} stroke="none" />)}
            </g>
          </g>
          <ChildOnLeaf leaf={GREEN} vein={WD} body="#e8a92c" line={PL} lw={2.6} />
        </g>
      </Layer>
      <Layer p={bands[2].p} cam={cam}>
        <rect x={-300} y={bands[2].y0} width={W + 600} height={900} fill={`url(#${id}-w2)`} />
        <path d={`M -300 ${bands[2].y0} L ${W + 300} ${bands[2].y0}`} stroke={PL} strokeWidth={2} />
        <PattaFish x={640 + f * 0.9} y={1300} dir={-1} t={t} />
        <PattaFish x={930 - f * 0.7} y={1440} dir={1} t={t} />
      </Layer>
      <Layer p={0.8} cam={cam}><g transform={pullT}><PattaSage f={f} look={look} bow={bow} /></g></Layer>
      <Layer p={0.95} cam={cam}>
        <g transform={`translate(0 ${3 * Math.sin(t * 1.4) + 500 * pull})`}>
          <rect x={-300} y={waterY} width={W + 600} height={H} fill={`url(#${id}-wF)`} />
          <path d={`M -300 ${waterY} L ${W + 300} ${waterY}`} stroke={PL} strokeWidth={4} />
          <Dots d={`M -200 ${waterY + 10} C 300 ${waterY + 10} 700 ${waterY + 10} ${W + 200} ${waterY + 10}`} n={70} r={2} />
        </g>
      </Layer>
      <Layer p={1} cam={cam}>
        {[[860, waterY + 150, 0], [300, waterY + 220, 2]].map(([x, y, ph], i) => (
          <g key={i} transform={`translate(${x + 6 * Math.sin(t * 0.8 + ph)} ${y + 4 * Math.sin(t * 1.3 + ph) + 500 * pull}) rotate(${3 * Math.sin(t + ph)})`} stroke={PL} strokeWidth={2.2}>
            {[-56, -28, 0, 28, 56].map((a) => <path key={a} d="M 0 0 C -14 -18 -10 -46 0 -60 C 10 -46 14 -18 0 0 Z" fill={a === 0 ? WD : '#f08fa8'} transform={`rotate(${a})`} />)}
            <ellipse cy={4} rx={42} ry={8} fill={GREEN} />
          </g>
        ))}
      </Layer>
    </g>
  );
};

/** Camera that zooms by z and, with focus 1, puts (cx, cy) on a depth-p layer at the frame centre (focus 0: original framing). */
const camOn = (cx: number, cy: number, z: number, focus: number, p = 0.5): Cam =>
  ({x: (-(cx - W / 2) * (1 + z * p) / p) * focus, y: (-(cy - H / 2) * (1 + z * p) / p) * focus, z});
/** Where a point on a depth-p layer lands on screen under cam. */
const onScreen = (x: number, y: number, cam: Cam, p = 0.5) =>
  [W / 2 + cam.x * p + (x - W / 2) * (1 + cam.z * p), H / 2 + cam.y * p + (y - H / 2) * (1 + cam.z * p)];

/** E: on its branch, a child (pull out from the child to the sage); "You're tired. Come inside me. Rest." (416-641). */
const ChildScene: React.FC<SceneProps> = ({f, id}) => {
  const out = span(f, 0, 85);
  const cam = camOn(CHILD_GLOW.x, CHILD_GLOW.y + 60, lerp(0.9, 0.04, out), 1 - out);
  const halo = Math.max(...[124, 160, 196].map((p) => Math.exp(-(((f - p) / 9) ** 2))));
  return <BanyanScene f={f} id={id} cam={cam} look={span(f, 40, 100)} bow={span(f, 192, 214)} halo={halo} />;
};

/** F: the child opens its mouth: the light opens and fills the frame; he is pulled in (641-735). */
const Mouth: React.FC<SceneProps> = ({f, id}) => {
  const z = lerp(0.04, 1.4, span(f, 4, 60));
  const cam = camOn(CHILD_GLOW.x, CHILD_GLOW.y, z, span(f, 0, 40));
  const [lx, ly] = onScreen(CHILD_GLOW.x - 60, CHILD_GLOW.y - 40, cam);   // the child's head, where the light opens
  const R = 30 + 2400 * span(f, 6, 62) ** 2;
  return (
    <g>
      <BanyanScene f={f + 225} id={id} cam={cam} look={1} pull={span(f, 6, 44)} halo={1} />
      <g transform={`translate(${lx} ${ly})`}>
        {Array.from({length: 24}, (_, i) => <path key={i} d={`M 0 0 L ${R * 1.6} -${R * 0.12} L ${R * 1.6} ${R * 0.12} Z`} fill={GOLD} opacity={0.45} transform={`rotate(${i * 15 + f * 1.5})`} />)}
        <circle r={R} fill={WD} />
        <circle r={R} fill="none" stroke={GOLD} strokeWidth={10} opacity={1 - span(f, 40, 60)} />
      </g>
      {f > 40 && <rect x={-300} y={-300} width={W + 600} height={H + 600} fill={WD} opacity={span(f, 40, 56)} />}
    </g>
  );
};

/** G: out of the white, down through stars and clouds into a living world; he floats, in awe (717-848). */
const Inside: React.FC<SceneProps> = ({f, id}) => {
  const t = f / 30;
  const D = 2300 * (1 - span(f, 0, 118));      // vertical descent through a tall world
  const cam: Cam = {x: 0, y: 0, z: 0.03 * span(f, 60, 130)};
  const L = (p: number, children: React.ReactNode) => <Layer p={p} cam={cam}><g transform={`translate(0 ${D * p})`}>{children}</g></Layer>;
  const r = rng(77);
  return (
    <g>
      <defs>{waterPattern(`${id}-riv`, (f * 0.8) % 80, 0, '#2d5aa8')}</defs>
      {L(0.3, <>
        <rect x={-300} y={-2700} width={W + 600} height={1700} fill={NIGHT} />
        {Array.from({length: 90}, (_, i) => <circle key={i} cx={r() * W} cy={-2600 + r() * 1500} r={1 + r() * 2} fill={WD} />)}
        <rect x={-300} y={-1000} width={W + 600} height={3200} fill={RED} />
        <g transform="translate(800 260)">
          {Array.from({length: 16}, (_, i) => <path key={i} d="M -14 -96 L 0 -132 L 14 -96 Z" fill={i % 2 ? GOLD : '#e8742a'} stroke={PL} strokeWidth={2.4} transform={`rotate(${i * 22.5 + f * 0.3})`} />)}
          <circle r={92} fill={GOLD} stroke={PL} strokeWidth={3} />
          <circle r={74} fill="#f6d77a" stroke={PL} strokeWidth={2} />
        </g>
      </>)}
      {L(0.55, <>
        {[[-120, -620, 560], [460, -760, 620], [80, -380, 520], [600, -300, 500]].map(([x, y, w], i) => <Cloud key={i} x={x + 30 * Math.sin(t + i)} y={y} w={w} n={6} fill={WD} />)}
      </>)}
      {L(0.8, <>
        <rect x={-300} y={900} width={W + 600} height={1400} fill="#3f7a3a" stroke={PL} strokeWidth={4} />
        {Array.from({length: 12}, (_, i) => <path key={i} d={`M -300 ${940 + i * 70} L ${W + 300} ${940 + i * 70}`} stroke="#2a5a2a" strokeWidth={3} strokeDasharray="34 16" />)}
        <path d="M 760 900 C 600 1100 900 1250 560 1450 C 260 1620 520 1800 380 2100 L 520 2100 C 660 1800 400 1640 690 1470 C 1040 1260 720 1100 880 900 Z" fill={`url(#${id}-riv)`} stroke={PL} strokeWidth={4} />
        <Temple x={250} y={1060} s={0.9} />
        <Hut x={120} y={1290} s={0.8} /><Hut x={900} y={1160} s={0.8} /><Hut x={980} y={1480} s={0.7} />
        <Palm x={60} y={1080} s={0.8} t={t} /><Palm x={1010} y={980} s={0.8} t={t + 2} />
        {[[200, 1560], [820, 1740], [140, 1840]].map(([x, y], i) => (
          <g key={i} transform={`translate(${x} ${y})`} stroke={PL} strokeWidth={2.2}>
            <ellipse rx={46} ry={24} fill={WD} /><circle cx={50} cy={-14} r={16} fill={WD} />
            {[-30, -10, 20, 36].map((x2) => <path key={x2} d={`M ${x2} 18 L ${x2} 44`} strokeWidth={5} />)}
            <path d="M 56 -28 C 64 -40 72 -38 74 -30" fill="none" strokeWidth={3} />
          </g>
        ))}
      </>)}
      <Layer p={0.9} cam={cam}>
        <g transform={`translate(${540 - SAGE_POS.x * 0.62} ${720 - SAGE_POS.y * 0.62 + 16 * Math.sin(t * 1.1)}) scale(0.62)`}>
          <PattaSage f={f} look={0.6} />
        </g>
      </Layer>
      {f < 24 && <rect x={-300} y={-300} width={W + 600} height={H + 600} fill={WD} opacity={1 - span(f, 0, 22)} />}
    </g>
  );
};

/** H1-H3: one image per word: Rivers, Mountains, Gods (848 / 872 / 892). */
const Rivers: React.FC<SceneProps> = ({f, id}) => {
  const cam: Cam = {x: 0, y: 0, z: 0.06 * span(f, 0, 30)};
  return (
    <g>
      <defs>{waterPattern(`${id}-riv`, (f * 1.4) % 80, 0, '#2d5aa8')}</defs>
      <Layer p={0.3} cam={cam}>
        <rect x={-300} y={-300} width={W + 600} height={H + 600} fill="#3f7a3a" />
        {Array.from({length: 22}, (_, i) => <path key={i} d={`M -300 ${i * 90} L ${W + 300} ${i * 90 + 120}`} stroke="#2a5a2a" strokeWidth={4} strokeDasharray="40 18" />)}
      </Layer>
      <Layer p={0.6} cam={cam}>
        <path d="M 300 -100 C 100 300 800 500 520 900 C 260 1270 860 1500 640 2100 L 900 2100 C 1080 1500 480 1270 760 900 C 1040 500 360 300 560 -100 Z" fill={`url(#${id}-riv)`} stroke={PL} strokeWidth={5} />
        <Dots d="M 300 -100 C 100 300 800 500 520 900" n={30} r={3} />
        <Dots d="M 520 900 C 260 1270 860 1500 640 2100" n={30} r={3} />
        <PattaFish x={560} y={860} dir={1} t={f / 30} s={0.9} />
        <PattaFish x={700} y={1500} dir={-1} t={f / 30 + 1} s={0.9} />
      </Layer>
    </g>
  );
};
const Mountains: React.FC<SceneProps> = ({f}) => {
  const cam: Cam = {x: -20 * span(f, 0, 24), y: 0, z: 0.05 * span(f, 0, 24)};
  const peak = (x: number, y: number, w: number, h: number, fill: string, k: number) => (
    <g key={k}>
      <path d={`M ${x - w} ${y} L ${x} ${y - h} L ${x + w} ${y} Z`} fill={fill} stroke={PL} strokeWidth={4} />
      <path d={`M ${x - w * 0.28} ${y - h * 0.72} L ${x} ${y - h} L ${x + w * 0.28} ${y - h * 0.72} L ${x + w * 0.12} ${y - h * 0.78} L ${x} ${y - h * 0.7} L ${x - w * 0.12} ${y - h * 0.78} Z`} fill={WD} stroke={PL} strokeWidth={2.4} />
      {[0.2, 0.4, 0.6].map((u) => <path key={u} d={`M ${x - w * u * 0.9} ${y - h * (1 - u) + 30} L ${x} ${y - h * (1 - u) - 10} L ${x + w * u * 0.9} ${y - h * (1 - u) + 30}`} fill="none" stroke={PL} strokeWidth={2} />)}
      <Dots d={`M ${x - w} ${y} C ${x - w * 0.66} ${y - h / 3} ${x - w * 0.33} ${y - (2 * h) / 3} ${x} ${y - h}`} n={18} r={2.6} />
    </g>
  );
  return (
    <g>
      <Layer p={0.1} cam={cam}><rect x={-300} y={-300} width={W + 600} height={H + 600} fill={RED} />
        <circle cx={760} cy={420} r={90} fill={GOLD} stroke={PL} strokeWidth={3} /></Layer>
      <Layer p={0.3} cam={cam}>{[peak(200, 1200, 340, 640, '#5b6aa8', 0), peak(820, 1180, 380, 720, '#4a5a9a', 1)]}</Layer>
      <Layer p={0.55} cam={cam}>{[peak(540, 1420, 420, 820, '#2d3f7a', 2), peak(-40, 1500, 300, 520, GREEN, 3), peak(1100, 1520, 320, 560, GREEN, 4)]}</Layer>
      <Layer p={0.8} cam={cam}><rect x={-300} y={1500} width={W + 600} height={700} fill="#3f7a3a" stroke={PL} strokeWidth={4} />
        {Array.from({length: 5}, (_, i) => <path key={i} d={`M -300 ${1540 + i * 60} L ${W + 300} ${1540 + i * 60}`} stroke="#2a5a2a" strokeWidth={3} strokeDasharray="30 14" />)}</Layer>
    </g>
  );
};
const Gods: React.FC<SceneProps> = ({f}) => {
  const rot = f * 0.4;
  return (
    <g>
      <rect x={-300} y={-300} width={W + 600} height={H + 600} fill={NIGHT} />
      {Array.from({length: 60}, (_, i) => <circle key={i} cx={(i * 197) % W} cy={(i * 331) % H} r={1.6} fill={WD} opacity={0.6} />)}
      <g transform={`translate(540 960) scale(${1 + 0.04 * span(f, 0, 23)})`}>
        <circle r={430} fill="none" stroke={GOLD} strokeWidth={3} strokeDasharray="3 12" />
        <g transform={`rotate(${rot})`}>
          {Array.from({length: 8}, (_, i) => (
            <g key={i} transform={`rotate(${i * 45}) translate(0 -330) rotate(${-i * 45 - rot})`} stroke={PL} strokeWidth={3}>
              {/* a luminous crowned silhouette: light and outline only, no faces */}
              <circle r={78} fill="#b3261e" /><circle r={68} fill={GOLD} /><circle r={58} fill={WD} />
              <path d="M -16 -38 L -10 -58 L 0 -46 L 10 -58 L 16 -38 Z" fill={GOLD} />
              <circle cy={-22} r={17} fill="#e8a92c" />
              <path d="M -30 46 C -30 8 -18 -4 0 -4 C 18 -4 30 8 30 46 Z" fill="#e8a92c" />
            </g>
          ))}
        </g>
        {/* central lotus */}
        <g stroke={PL} strokeWidth={3}>
          {Array.from({length: 12}, (_, i) => <path key={i} d="M 0 0 C -26 -40 -18 -110 0 -140 C 18 -110 26 -40 0 0 Z" fill={i % 2 ? '#f08fa8' : WD} transform={`rotate(${i * 30})`} />)}
          <circle r={34} fill={GOLD} />
        </g>
      </g>
    </g>
  );
};

/** I: back outside: only the black flood, a temple spire going under, rain (915-992). */
const FloodOutside: React.FC<SceneProps> = ({f}) => {
  const t = f / 30;
  const cam: Cam = {x: 0, y: 0, z: 0.1 * (1 - span(f, 0, 77))};
  return (
    <g>
      <Layer p={0.1} cam={cam}><NightSky seed={31} /></Layer>
      <Layer p={0.4} cam={cam}><rect x={-300} y={820} width={W + 600} height={1400} fill="url(#I-water0)" /><path d={`M -300 820 L ${W + 300} 820`} stroke={PL} strokeWidth={4} /></Layer>
      <Layer p={0.6} cam={cam}>
        <g transform={`translate(0 ${140 * span(f, 0, 77)})`}><Temple x={640} y={1190} s={1.1} /></g>
        <rect x={-300} y={1080} width={W + 600} height={1400} fill="url(#I-water1)" /><path d={`M -300 1080 L ${W + 300} 1080`} stroke={PL} strokeWidth={3} />
        {[0, 1, 2, 3].map((k) => <circle key={k} cx={630 + 30 * Math.sin(k * 2)} cy={1060 - ((f * 2 + k * 30) % 120)} r={6} fill="none" stroke={WD} strokeWidth={2} />)}
      </Layer>
      <Layer p={0.9} cam={cam}><WaveWall y={1560 + 12 * Math.sin(t * 1.5)} t={t} fill="url(#I-water2)" /></Layer>
      <Layer p={1} cam={cam}><Rain f={f + 915} n={90} seed={8} /></Layer>
    </g>
  );
};

/** J: the whole ocean shrinks into a drop held in the child's light; hold; fade (992-1103). */
const Final: React.FC<SceneProps> = ({f, id}) => {
  const t = f / 30;
  const R = lerp(1500, 26, span(f, 0, 52) ** 0.7);
  const s = 1.7;
  const childT = `translate(${540} ${1000}) scale(${s}) translate(${-CHILD_GLOW.x} ${-CHILD_GLOW.y})`;
  return (
    <g>
      <defs><clipPath id={`${id}-drop`}><circle cx={540 - 90} cy={1000 + 20} r={R} /></clipPath></defs>
      <NightSky seed={41} />
      <g transform={childT}>
        <g transform={`translate(${CHILD_GLOW.x} ${CHILD_GLOW.y}) scale(${1 + 0.03 * Math.sin(t * 1.6)})`} stroke={PL} strokeWidth={3}>
          <circle r={150} fill={GOLD} opacity={0.3} stroke="none" />
          <circle r={124} fill="#b3261e" /><circle r={112} fill={GOLD} /><circle r={98} fill={WD} />
          <g transform={`rotate(${f * 0.4})`}>{Array.from({length: 40}, (_, i) => <circle key={i} cx={Math.cos((i / 40) * Math.PI * 2) * 118} cy={Math.sin((i / 40) * Math.PI * 2) * 118} r={2} fill={WD} stroke="none" />)}</g>
        </g>
        <ChildOnLeaf leaf={GREEN} vein={WD} body="#e8a92c" line={PL} lw={2.6} />
      </g>
      {/* the ocean, now inside a drop of light */}
      <g clipPath={`url(#${id}-drop)`}><FloodOutside f={f + 77} id={`${id}-o`} /></g>
      <circle cx={540 - 90} cy={1020} r={R} fill="none" stroke={GOLD} strokeWidth={6} />
      {R < 40 && <circle cx={540 - 90} cy={1020} r={R} fill={WD} opacity={span(f, 46, 60)} />}
      {f > 82 && <rect x={-300} y={-300} width={W + 600} height={H + 600} fill="#000" opacity={span(f, 82, 110)} />}
    </g>
  );
};

// ------------------------------------------------------------------ timeline and transitions
type Tin = {type: 'scroll' | 'iris' | 'irisOut' | 'cut'; d: number; cx?: number; cy?: number};
type Scene = {start: number; C: React.FC<SceneProps>; id: string; tin?: Tin};
const SCENES: Scene[] = [
  {start: 0, C: Deluge, id: 'A'},
  {start: 96, C: Burst, id: 'B'},                                                 // the wave already fills the frame
  {start: 153, C: DriftWide, id: 'C1', tin: {type: 'scroll', d: 18}},
  {start: 237, C: DriftCall, id: 'C2', tin: {type: 'scroll', d: 16}},
  {start: 321, C: BanyanReveal, id: 'D', tin: {type: 'iris', d: 26, cx: 540, cy: 1000}},
  {start: 416, C: ChildScene, id: 'E', tin: {type: 'scroll', d: 18}},
  {start: 641, C: Mouth, id: 'F'},
  {start: 717, C: Inside, id: 'G'},                                               // out of the white
  {start: 848, C: Rivers, id: 'H1'},                                              // cuts on the words
  {start: 872, C: Mountains, id: 'H2'},
  {start: 892, C: Gods, id: 'H3'},
  {start: 915, C: FloodOutside, id: 'I', tin: {type: 'irisOut', d: 24, cx: 540, cy: 960}},
  {start: 992, C: Final, id: 'J'},                                                // continuous: J opens on I's ocean
];

/** Static water patterns per scene (ids prefixed); moving ones are made inside the scenes. */
const ScenePatterns: React.FC<{g: number}> = ({g}) => (
  <defs>
    {waterPattern('A-water', (g * 2) % 80, 0, '#1f2a55')}
    {waterPattern('A-river', (g * 0.8) % 80, 0, '#2d5aa8')}
    {waterPattern('B-water0', (g * 1.2) % 80, 0, '#1b2550')}
    {waterPattern('B-water1', (-g * 2) % 80, 0, '#141c40')}
    {waterPattern('C1-water0', (g * 0.3) % 80, 0, '#141a38')}
    {waterPattern('C1-water1', (g * 0.6) % 80, 0, '#10162e')}
    {waterPattern('C2-water0', (g * 0.4) % 80, 0, '#141a38')}
    {waterPattern('C2-water1', (-g * 1) % 80, 0, '#0e1328')}
    {waterPattern('D-water0', (g * 0.3) % 80, 0, '#141a38')}
    {waterPattern('D-water1', (g * 0.7) % 80, 0, '#10162e')}
    {waterPattern('I-water0', (g * 0.3) % 80, 0, '#10162e')}
    {waterPattern('I-water1', (g * 0.6) % 80, 0, '#0c1226')}
    {waterPattern('I-water2', (-g * 1.1) % 80, 0, '#080c1c')}
  </defs>
);

/** Scroll band: a strip of the creeper border with white dots, sweeping across like cloth being unrolled. */
const ScrollBand: React.FC<{x: number}> = ({x}) => (
  <g>
    <rect x={x - 30} y={-300} width={60} height={H + 600} fill="url(#creeperV)" stroke={PL} strokeWidth={4} />
    <rect x={x - 42} y={-300} width={12} height={H + 600} fill={GOLD} stroke={PL} strokeWidth={2} />
    <rect x={x + 30} y={-300} width={12} height={H + 600} fill={GOLD} stroke={PL} strokeWidth={2} />
  </g>
);
const LotusRing: React.FC<{cx: number; cy: number; r: number}> = ({cx, cy, r}) => {
  const n = Math.max(12, 2 * Math.round(r / 44));
  return (
  <g transform={`translate(${cx} ${cy})`} stroke={PL} strokeWidth={3}>
    {Array.from({length: n}, (_, i) => (
      <path key={i} d="M 0 0 C -14 -20 -10 -46 0 -60 C 10 -46 14 -20 0 0 Z" fill={i % 2 ? '#f08fa8' : WD} transform={`rotate(${(i * 360) / n}) translate(0 ${-r})`} />
    ))}
    <circle r={r} fill="none" stroke={GOLD} strokeWidth={10} />
  </g>
  );
};

const SceneAt: React.FC<{s: Scene; g: number}> = ({s, g}) => <s.C f={g - s.start} id={s.id} />;

const Timeline: React.FC<{g: number}> = ({g}) => {
  let i = 0;
  while (i + 1 < SCENES.length && SCENES[i + 1].start <= g) i++;
  const cur = SCENES[i];
  const tin = cur.tin;
  const k = tin ? (g - cur.start) / tin.d : 1;
  if (!tin || k >= 1 || i === 0) return <SceneAt s={cur} g={g} />;
  const prev = SCENES[i - 1];
  const e = smooth(k);
  if (tin.type === 'scroll') {
    const x = lerp(I - 60, W - I + 60, e);
    return (
      <>
        <SceneAt s={prev} g={g} />
        <defs><clipPath id="tr-clip"><rect x={-300} y={-300} width={x + 300} height={H + 600} /></clipPath></defs>
        <g clipPath="url(#tr-clip)"><SceneAt s={cur} g={g} /></g>
        <ScrollBand x={x} />
      </>
    );
  }
  const cx = tin.cx ?? W / 2, cy = tin.cy ?? H / 2;
  if (tin.type === 'iris') {
    const r = 1500 * e * e;
    return (
      <>
        <SceneAt s={prev} g={g} />
        <defs><clipPath id="tr-clip"><circle cx={cx} cy={cy} r={r} /></clipPath></defs>
        <g clipPath="url(#tr-clip)"><SceneAt s={cur} g={g} /></g>
        <LotusRing cx={cx} cy={cy} r={r} />
      </>
    );
  }
  // irisOut: the old scene shrinks into a glowing sphere over the new one
  const r = 1500 * (1 - e) ** 2;
  return (
    <>
      <SceneAt s={cur} g={g} />
      <defs><clipPath id="tr-clip"><circle cx={cx} cy={cy} r={r} /></clipPath></defs>
      <g clipPath="url(#tr-clip)"><SceneAt s={prev} g={g} /></g>
      <LotusRing cx={cx} cy={cy} r={r} />
    </>
  );
};

/** Fixed Pattachitra border: black with shimmering white dots, red creeper band, yellow rule. */
const Border: React.FC<{t: number}> = ({t}) => (
  <>
    <path fillRule="evenodd" d={`M 0 0 H ${W} V ${H} H 0 Z M ${I} ${I} V ${H - I} H ${W - I} V ${I} Z`} fill={PL} />
    {Array.from({length: 54}, (_, i) => <circle key={`t${i}`} cx={10 + i * 20} cy={16} r={3.4} fill={WD} opacity={0.75 + 0.25 * Math.sin(t * 3 + i * 0.7)} />)}
    {Array.from({length: 54}, (_, i) => <circle key={`b${i}`} cx={10 + i * 20} cy={H - 16} r={3.4} fill={WD} opacity={0.75 + 0.25 * Math.sin(t * 3 + i * 0.7 + 2)} />)}
    {Array.from({length: 96}, (_, i) => <circle key={`l${i}`} cx={16} cy={10 + i * 20} r={3.4} fill={WD} opacity={0.75 + 0.25 * Math.sin(t * 3 + i * 0.7 + 4)} />)}
    {Array.from({length: 96}, (_, i) => <circle key={`r${i}`} cx={W - 16} cy={10 + i * 20} r={3.4} fill={WD} opacity={0.75 + 0.25 * Math.sin(t * 3 + i * 0.7 + 1)} />)}
    <path fillRule="evenodd" d={`M 34 34 H ${W - 34} V ${H - 34} H 34 Z M ${I - 8} ${I - 8} V ${H - I + 8} H ${W - I + 8} V ${I - 8} Z`} fill="url(#creeper)" stroke={WD} strokeWidth={2} />
    <path fillRule="evenodd" d={`M ${I - 8} ${I - 8} H ${W - I + 8} V ${H - I + 8} H ${I - 8} Z M ${I} ${I} V ${H - I} H ${W - I} V ${I} Z`} fill={GOLD} stroke={PL} strokeWidth={3} />
    <rect x={I} y={I} width={W - 2 * I} height={H - 2 * I} fill="none" stroke={PL} strokeWidth={4} />
  </>
);

const CreeperDefs: React.FC = () => (
  <defs>
    <pattern id="creeper" width="70" height="44" patternUnits="userSpaceOnUse">
      <rect width="70" height="44" fill="#b3261e" />
      <path d="M 0 22 C 18 4 36 40 52 22 C 60 14 66 16 70 22" fill="none" stroke={WD} strokeWidth="2.4" />
      <path d={almond(20, 6)} transform="translate(18 12) rotate(-40)" fill={GREEN} stroke={PL} strokeWidth="1.4" />
      <path d={almond(20, 6)} transform="translate(44 32) rotate(-40)" fill={GREEN} stroke={PL} strokeWidth="1.4" />
      <circle cx="34" cy="22" r="5" fill={GOLD} stroke={PL} strokeWidth="1.4" />
    </pattern>
    <pattern id="creeperV" width="44" height="70" patternUnits="userSpaceOnUse">
      <rect width="44" height="70" fill="#b3261e" />
      <path d="M 22 0 C 4 18 40 36 22 52 C 14 60 16 66 22 70" fill="none" stroke={WD} strokeWidth="2.4" />
      <path d={almond(20, 6)} transform="translate(12 18) rotate(50)" fill={GREEN} stroke={PL} strokeWidth="1.4" />
      <path d={almond(20, 6)} transform="translate(32 44) rotate(50)" fill={GREEN} stroke={PL} strokeWidth="1.4" />
      <circle cx="22" cy="34" r="5" fill={GOLD} stroke={PL} strokeWidth="1.4" />
    </pattern>
    <pattern id="backdrop" width="120" height="120" patternUnits="userSpaceOnUse">
      <rect width="120" height="120" fill="#3a0f0b" />
      <circle cx="60" cy="60" r="16" fill="none" stroke="#6a2a1e" strokeWidth="2" />
      {[0, 60, 120, 180, 240, 300].map((a) => <ellipse key={a} cx="60" cy="38" rx="6" ry="12" fill="#5a1f16" transform={`rotate(${a} 60 60)`} />)}
      <circle cx="0" cy="0" r="3" fill="#6a2a1e" /><circle cx="120" cy="120" r="3" fill="#6a2a1e" />
    </pattern>
  </defs>
);

/** The painted cloth: scenes inside the panel, fixed border on top, hand-made surface over all. */
export const PattaCloth: React.FC<{g: number; frame: number}> = ({g, frame}) => (
  <g>
    <Handmade id="pc" wobble={2.6} paper={[0.55, 0.4, 0.3]} cloth seed={7 + (Math.floor(frame / 8) % 3)} />
    <CreeperDefs />
    <ScenePatterns g={g} />
    <defs><clipPath id="panel"><rect x={I} y={I} width={W - 2 * I} height={H - 2 * I} /></clipPath></defs>
    <g filter="url(#pc-wob)">
      <g clipPath="url(#panel)"><Timeline g={g} /></g>
      <Border t={frame / 30} />
    </g>
    <Surface id="pc" mottle={0.45} />
  </g>
);

const remap = (x: number, from: number[], to: number[]) => {
  let k = 0;
  while (k + 2 < from.length && from[k + 1] <= x) k++;
  return to[k] + ((x - from[k]) * (to[k + 1] - to[k])) / (from[k + 1] - from[k]);
};

/** Portrait: the cloth fills the frame. Landscape: the cloth hangs centred on a patterned wall. */
export const PattaStory: React.FC<{audio?: string; warp?: {hi: number[]; en: number[]}}> = ({audio = 'episodes/001-markandeya-pralaya/mix.wav', warp}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const g = warp ? Math.min(remap(frame, warp.hi, warp.en), STORY_FRAMES - 1) : frame;
  const vw = Math.max(W, (H * width) / height);
  return (
    <AbsoluteFill style={{background: '#000'}}>
      <svg viewBox={`${-(vw - W) / 2} 0 ${vw} ${H}`} width="100%" height="100%">
        {vw > W && <rect x={-(vw - W) / 2} y={0} width={vw} height={H} fill="url(#backdrop)" />}
        <PattaCloth g={g} frame={frame} />
        {vw > W && <rect x={-6} y={0} width={W + 12} height={H} fill="none" stroke="#000" strokeOpacity={0.35} strokeWidth={12} />}
      </svg>
      <Audio src={staticFile(audio)} />
    </AbsoluteFill>
  );
};
