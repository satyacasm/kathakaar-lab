/**
 * The painted-cloth frame shared by episodes: scene timeline with house transitions (scroll band, lotus iris,
 * iris out, cut), the fixed Pattachitra border, the hand-made surface, and the portrait/landscape wrapper.
 * Also common scenery motifs (night sky, moon, clouds, huts, palms, temples, rain).
 * Episode 001 keeps its own copy inside its Story.tsx so its approved render stays bit-identical; new episodes use this.
 */
import React from 'react';
import {AbsoluteFill, Audio, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {rng} from './geometry';
import {Handmade, PL, Surface, WD, almond, smooth} from './pattachitra';

export const W = 1080;
export const H = 1920;
export const I = 92;                     // inner panel inset (border width)
export const RED = '#a8281f';
export const NIGHT = '#120c0a';
export const GOLD = '#f2c14e';
export const GREEN = '#2e7d4f';
export const lerp = (a: number, b: number, x: number) => a + (b - a) * Math.min(1, Math.max(0, x));
export const span = (f: number, a: number, b: number) => smooth((f - a) / (b - a));
export const hexMix = (a: string, b: string, x: number) => {
  const p = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const [A, B] = [p(a), p(b)];
  return '#' + A.map((v, i) => Math.round(lerp(v, B[i], x)).toString(16).padStart(2, '0')).join('');
};
export type SceneProps = {f: number; id: string};
export type Tin = {type: 'scroll' | 'iris' | 'irisOut' | 'cut'; d: number; cx?: number; cy?: number};
export type Scene = {start: number; C: React.FC<SceneProps>; id: string; tin?: Tin};

// ------------------------------------------------------------------ motifs
const cloudPath = (w: number, n: number) => {
  const r = w / (2 * n);
  let d = `M 0 0`;
  for (let i = 0; i < n; i++) d += ` a ${r} ${r * 1.1} 0 0 1 ${2 * r} 0`;
  return d + ` C ${w} ${r * 0.8} 0 ${r * 0.8} 0 0 Z`;
};
export const Cloud: React.FC<{x: number; y: number; w: number; n?: number; fill?: string}> = ({x, y, w, n = 5, fill = '#2a1f2a'}) => {
  const r = w / (2 * n);
  return (
    <g transform={`translate(${x} ${y})`} stroke={PL} strokeWidth={2.6}>
      <path d={cloudPath(w, n)} fill={fill} />
      {Array.from({length: n}, (_, i) => <path key={i} d={`M ${r * (2 * i + 0.5)} -${r * 0.2} a ${r * 0.5} ${r * 0.5} 0 1 1 ${r} 0`} fill="none" stroke={WD} strokeWidth={1.8} />)}
    </g>
  );
};
export const Hut: React.FC<{x: number; y: number; s: number}> = ({x, y, s}) => (
  <g transform={`translate(${x} ${y}) scale(${s})`} stroke={PL} strokeWidth={2.4} strokeLinejoin="round">
    <rect x={-50} y={-60} width={100} height={60} fill="#d9a25a" />
    {[-30, -10, 10, 30].map((x2) => <path key={x2} d={`M ${x2} -56 L ${x2} -4`} stroke="#b3261e" strokeWidth={2} />)}
    <path d="M -64 -56 L 0 -112 L 64 -56 Z" fill="#6a3b1e" />
    {[-40, -20, 0, 20, 40].map((x2) => <path key={x2} d={`M ${x2 * 0.9} -62 L ${x2 * 0.2} -104`} strokeWidth={1.2} />)}
    <path d="M -14 0 L -14 -30 C -14 -42 14 -42 14 -30 L 14 0 Z" fill={PL} />
  </g>
);
export const Palm: React.FC<{x: number; y: number; s: number; t: number}> = ({x, y, s, t}) => (
  <g transform={`translate(${x} ${y}) scale(${s})`} stroke={PL} strokeWidth={2.4}>
    <path d="M 0 0 C 6 -60 -4 -130 10 -200" fill="none" stroke={PL} strokeWidth={14} />
    <path d="M 0 0 C 6 -60 -4 -130 10 -200" fill="none" stroke="#6a3b1e" strokeWidth={9} />
    <g transform={`translate(10 -200) rotate(${4 * Math.sin(t * 2)})`}>
      {[-150, -115, -80, -45, -10, 25].map((a) => <path key={a} d={almond(110, 14)} transform={`rotate(${a}) translate(55 0)`} fill={GREEN} />)}
    </g>
  </g>
);
/** A round Pattachitra tree: trunk and a canopy of leaf-clusters, swaying. */
export const RoundTree: React.FC<{x: number; y: number; s: number; t: number; fill?: string}> = ({x, y, s, t, fill = GREEN}) => (
  <g transform={`translate(${x} ${y}) scale(${s})`} stroke={PL} strokeWidth={2.6}>
    <path d="M -14 0 C -10 -60 -18 -120 -6 -180 L 6 -180 C 18 -120 10 -60 14 0 Z" fill="#6a3b1e" />
    <g transform={`rotate(${1.5 * Math.sin(t * 1.3)} 0 -180)`}>
      {[[-70, -230, 70], [60, -240, 74], [0, -300, 80], [-40, -170, 56], [50, -170, 56]].map(([cx, cy, r], i) => (
        <g key={i}>
          <circle cx={cx} cy={cy} r={r} fill={fill} />
          {Array.from({length: 7}, (_, k) => <path key={k} d={almond(r * 0.5, r * 0.14)} transform={`translate(${cx} ${cy}) rotate(${k * 51 + i * 20}) translate(${r * 0.45} 0)`} fill="none" stroke={WD} strokeWidth={1.4} />)}
        </g>
      ))}
    </g>
  </g>
);
export const NightSky: React.FC<{seed?: number; n?: number}> = ({seed = 9, n = 120}) => {
  const r = rng(seed);
  return (
    <>
      <rect x={-300} y={-300} width={W + 600} height={H + 600} fill={NIGHT} />
      {Array.from({length: n}, (_, i) => <circle key={i} cx={r() * (W + 200) - 100} cy={r() * 1300} r={1 + r() * 2.2} fill={WD} opacity={0.5 + r() * 0.5} />)}
      {Array.from({length: 14}, (_, i) => {
        const x = r() * W, y = r() * 1100;
        return <g key={`s${i}`} transform={`translate(${x} ${y})`}>{[0, 45, 90, 135].map((a) => <path key={a} d="M 0 -9 L 0 9" stroke={WD} strokeWidth={1.6} transform={`rotate(${a})`} />)}</g>;
      })}
    </>
  );
};
/** Moon with a phase in [0,1]: 0 new, 0.5 full. */
export const Moon: React.FC<{x: number; y: number; r: number; phase: number; ground: string}> = ({x, y, r, phase, ground}) => {
  const off = Math.cos(phase * Math.PI * 2) * r * 2.1;
  return (
    <g>
      <circle cx={x} cy={y} r={r} fill={WD} stroke={PL} strokeWidth={3} />
      {Math.abs(off) < r * 2.05 && <circle cx={x + off} cy={y - r * 0.15} r={r * 1.02} fill={ground} />}
    </g>
  );
};

// ------------------------------------------------------------------ transitions
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

export const Timeline: React.FC<{g: number; scenes: Scene[]}> = ({g, scenes}) => {
  let i = 0;
  while (i + 1 < scenes.length && scenes[i + 1].start <= g) i++;
  const cur = scenes[i];
  const tin = cur.tin;
  const k = tin ? (g - cur.start) / tin.d : 1;
  if (!tin || tin.type === 'cut' || k >= 1 || i === 0) return <SceneAt s={cur} g={g} />;
  const prev = scenes[i - 1];
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

// ------------------------------------------------------------------ border and cloth
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

const PattaCloth: React.FC<{g: number; frame: number; scenes: Scene[]; patterns?: (g: number) => React.ReactNode}> = ({g, frame, scenes, patterns}) => (
  <g>
    <Handmade id="pc" wobble={2.6} paper={[0.55, 0.4, 0.3]} cloth seed={7 + (Math.floor(frame / 8) % 3)} />
    <CreeperDefs />
    {patterns && <defs>{patterns(g)}</defs>}
    <defs><clipPath id="panel"><rect x={I} y={I} width={W - 2 * I} height={H - 2 * I} /></clipPath></defs>
    <g filter="url(#pc-wob)">
      <g clipPath="url(#panel)"><Timeline g={g} scenes={scenes} /></g>
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
export const ClothStory: React.FC<{audio: string; frames: number; scenes: Scene[]; patterns?: (g: number) => React.ReactNode; warp?: {hi: number[]; en: number[]}}> = ({
  audio, frames, scenes, patterns, warp,
}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const g = warp ? Math.min(remap(frame, warp.hi, warp.en), frames - 1) : frame;
  const vw = Math.max(W, (H * width) / height);
  return (
    <AbsoluteFill style={{background: '#000'}}>
      <svg viewBox={`${-(vw - W) / 2} 0 ${vw} ${H}`} width="100%" height="100%">
        {vw > W && <rect x={-(vw - W) / 2} y={0} width={vw} height={H} fill="url(#backdrop)" />}
        <PattaCloth g={g} frame={frame} scenes={scenes} patterns={patterns} />
        {vw > W && <rect x={-6} y={0} width={W + 12} height={H} fill="none" stroke="#000" strokeOpacity={0.35} strokeWidth={12} />}
      </svg>
      <Audio src={staticFile(audio)} />
    </AbsoluteFill>
  );
};
