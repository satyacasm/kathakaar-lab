/**
 * Episodes 003-004, "Is Diwali only Rama's?" parts 1 and 2: one night across India, in Odisha Pattachitra.
 * The shared scenes; each part's Story.tsx picks its scenes and maps the line numbers (see makeLines).
 * Deities are full traditional figures (rule of 7 Nov 2026), two arms each. Kali is fierce but dignified: hibiscus
 * garland, no severed heads, the asuras simply fall away. Every region opens with its name on a red banner.
 *
 *  A  1-3    a single diya on the dark cloth; Kali and the ledger appear (Bengal? Gujarat?); a ring of five emblems
 *  B  4-5    Ayodhya: Rama, Sita and Lakshmana at the gate, petals and banners; then today's lamps light up (scroll)
 *  C  6      Rama's figure becomes Vishnu; the discus spins off to the south                                (iris)
 *  D  7-9    the South: Pragjyotisha fort, Narakasura, the captive women; Krishna and Satyabhama on Garuda; the discus (scroll)
 *  E  10     the women walk free; dawn: kolam, oil lamps before sunrise                                    (iris)
 *  F  11-13  the East: the Devi, Kali from her brow, Chanda and Munda fall; Kali worshipped among lamps      (scroll)
 *  G  14     Odisha: jute-stick flames raised to the ancestors, sparks rising                               (iris)
 *  H  15-17  the West: Lakshmi's footsteps at a lit door; the milk ocean, Lakshmi on the lotus, Vishnu; the ledger, sunrise (scroll)
 *  J  18-21  Bali's sacrifice; Vamana with his parasol; the three steps; Bali returns to his people           (scroll)
 *  K  22-25  Braj: the hill worshipped, Indra's rain, Krishna lifts Govardhan, Indra bows; Annakut           (scroll)
 *  L  26-28  the five faces of the answer; every home lit; fade                                              (iris)
 */
import React from 'react';
import {Cam, Dots, Layer, PL, WD, waterPattern} from '../../kit/pattachitra';
import {ClothStory, GOLD, H, NightSky, RED, Scene, SceneProps, W, hexMix, lerp, span} from '../../kit/cloth';
import {Diya, FireAltar, Skyline} from '../../kit/figures';
import {Arm, Figure, Glory, LOOKS, Look, wristAt} from '../../kit/people';
import {Ayodhya, Deul, PCloud, Palace, River, SalTree} from '../../kit/places';
import {Chakra, Conch, Cow, FoodMountain, Fort, Garuda, Hill, JuteTorch, Kamandalu, Kolam, Ledger, Lotus, LotusSeat, Rain, RegionBanner, Sword, Umbrella} from '../../kit/props';

/**
 * Line timing for the scenes. Scenes use the original 28-line numbering of the full script; each part's Story maps
 * those numbers to its own lines.ts (part 1 = 1-14, part 2 = 15-28) and gives its local lines for its own cards.
 */
export type LineT = {s: number; e: number};
type Lines = {S: (n: number) => number; E: (n: number) => number; MID: (n: number) => number; SL: (n: number) => number; EL: (n: number) => number; FRAMES: number};
export const makeLines = (lines: LineT[], map: (orig: number) => number, frames: number): Lines => {
  const at = (n: number) => lines[Math.min(lines.length, Math.max(1, map(n))) - 1];
  const S = (n: number) => at(n).s, E = (n: number) => at(n).e;
  return {S, E, MID: (n) => Math.round((S(n) + E(n)) / 2), SL: (n) => lines[n - 1].s, EL: (n) => lines[n - 1].e, FRAMES: frames};
};
export const LinesCtx = React.createContext<Lines | null>(null);
export const useL = () => React.useContext(LinesCtx)!;
const SKY = '#2d4a8a';
const DUSK = '#e8742a';
const DAWN = '#f2a65a';
const mixArm = (p: Arm, q: Arm, k: number): Arm => ({a: lerp(p.a, q.a, k), b: lerp(p.b, q.b, k), hand: k < 0.5 ? p.hand : q.hand});
const NAMASTE: Arm = {a: 18, b: 148, hand: 'open'};
const REST: Arm = {a: 8, b: 14, hand: 'open'};
const UP: Arm = {a: 150, b: 10, hand: 'fist'};
const OFFER: Arm = {a: 60, b: 50, hand: 'open'};

/** Place a figure: feet at (x, y), scale s, facing left when dir = -1. */
export const At: React.FC<{x: number; y: number; s: number; dir?: number; rot?: number; o?: number; children: React.ReactNode}> = ({x, y, s, dir = 1, rot = 0, o = 1, children}) => (
  <g transform={`translate(${x} ${y}) rotate(${rot}) scale(${dir * s} ${s})`} opacity={o}>{children}</g>
);
/** A prop held in a hand: drawn at the wrist of that arm, in the figure's coordinates. */
export const InHand: React.FC<{side: 'far' | 'near'; arm: Arm; stance?: 'stand' | 'kneel' | 'sit'; dx?: number; dy?: number; children: React.ReactNode}> = ({side, arm, stance, dx = 0, dy = 0, children}) => {
  const w = wristAt(side, arm, stance);
  return <g transform={`translate(${w.x + dx} ${w.y + dy})`}>{children}</g>;
};
export const Ground: React.FC<{y: number; fill: string; line?: string}> = ({y, fill, line = '#00000033'}) => (
  <g>
    <rect x={-300} y={y} width={W + 600} height={H - y + 400} fill={fill} stroke={PL} strokeWidth={4} />
    {Array.from({length: 5}, (_, i) => <path key={i} d={`M -300 ${y + 40 + i * 50} L ${W + 300} ${y + 40 + i * 50}`} stroke={line} strokeWidth={3} strokeDasharray="30 14" />)}
  </g>
);
export const Sky: React.FC<{fill: string; dots?: number; seed?: number}> = ({fill, dots = 24, seed = 1}) => (
  <g>
    <rect x={-300} y={-300} width={W + 600} height={H + 600} fill={fill} />
    {Array.from({length: dots}, (_, i) => <circle key={i} cx={(i * 157 * seed) % 1000 + 40} cy={140 + ((i * 241 * seed) % 760)} r={3} fill={WD} opacity={0.75} />)}
  </g>
);
/** A round gold-rimmed medallion with its own clip. */
export const Medallion: React.FC<{id: string; x: number; y: number; r: number; k: number; bg: string; children: React.ReactNode}> = ({id, x, y, r, k, bg, children}) => (
  <g transform={`translate(${x} ${y}) scale(${0.4 + 0.6 * k})`} opacity={k}>
    <defs><clipPath id={id}><circle r={r} /></clipPath></defs>
    <circle r={r + 26} fill={GOLD} stroke={PL} strokeWidth={4} />
    <Dots d={`M ${-r - 13} 0 A ${r + 13} ${r + 13} 0 1 1 ${r + 13} 0 A ${r + 13} ${r + 13} 0 1 1 ${-r - 13} 0`} n={40} r={3} />
    <circle r={r} fill={bg} stroke={PL} strokeWidth={4} />
    <g clipPath={`url(#${id})`}>{children}</g>
  </g>
);
/** A figure's bust inside a medallion: head and shoulders centred. */
export const Bust: React.FC<{look: Look; t: number; s?: number; glory?: boolean; blinkOff?: number}> = ({look, t, s = 0.62, glory, blinkOff = 0}) => (
  <g transform={`translate(-10 ${830 * s - 40}) scale(${s})`}>
    {glory && <Glory x={10} y={-960} r={150} t={t} />}
    <Figure look={look} t={t} far={REST} near={NAMASTE} blinkOff={blinkOff} />
  </g>
);
export const Petals: React.FC<{f: number; n?: number; k?: number}> = ({f, n = 40, k = 1}) => (
  <g stroke={PL} strokeWidth={1.6} opacity={k}>
    {Array.from({length: n}, (_, i) => {
      const x = (i * 263) % W, v = 3 + (i % 5);
      const y = ((i * 431 + f * v) % (H + 200)) - 100;
      return <ellipse key={i} cx={x + 20 * Math.sin(f / 20 + i)} cy={y} rx={7} ry={12} fill={i % 3 ? '#f08fa8' : i % 2 ? GOLD : WD} transform={`rotate(${(f * 3 + i * 40) % 360} ${x} ${y})`} />;
    })}
  </g>
);
export const DiyaRow: React.FC<{y: number; n: number; w: number; s: number; t: number; f: number; at: number; step?: number}> = ({y, n, w, s, t, f, at, step = 5}) => (
  <g>
    {Array.from({length: n}, (_, i) => {
      const c = Math.abs(i - (n - 1) / 2);
      return <Diya key={i} x={540 + (i - (n - 1) / 2) * (w / Math.max(1, n - 1))} y={y} s={s} t={t} lit={span(f, at + c * step, at + 16 + c * step)} ph={i * 1.7} />;
    })}
  </g>
);
export const Banner: React.FC<{f: number; at: number; text: string; y?: number; until?: number; w?: number}> = ({f, at, text, y = 300, until = 1e9, w}) => (
  <RegionBanner x={540} y={y} text={text} k={span(f, at, at + 18) * (1 - span(f, until, until + 14))} w={w} />
);

// ------------------------------------------------------------------ A: one lamp, many gods (1-3)
export const Hook: React.FC<SceneProps> = ({f, id}) => {
  const {S, E, MID, FRAMES} = useL();
  const t = f / 30;
  const lamp = span(f, S(1) - 6, S(1) + 20);
  const kali = span(f, S(2) + 10, S(2) + 34);
  const ledger = span(f, MID(2) + 10, MID(2) + 34);
  const ring = span(f, S(3) - 10, S(3) + 30);
  const pair = 1 - ring;
  const cam: Cam = {x: 0, y: 0, z: 0.06 * span(f, 0, E(3))};
  const emblems: [string, React.ReactNode][] = [
    ['bow', <g transform="scale(0.5) rotate(20)" stroke={PL}><path d="M 0 -300 C 60 -200 60 -100 0 0 C 60 100 60 200 0 300" fill="none" strokeWidth={22} /><path d="M 0 -300 C 60 -200 60 -100 0 0 C 60 100 60 200 0 300" fill="none" stroke="#8a3a1e" strokeWidth={14} /><path d="M 0 -300 L 0 300" stroke={WD} strokeWidth={3} /></g>],
    ['chakra', <Chakra r={60} t={t * 0.3} />],
    ['sword', <g transform="translate(-10 120) scale(0.55)"><Sword /></g>],
    ['lotus', <g transform="translate(0 40)"><Lotus s={0.95} /></g>],
    ['umbrella', <g transform="translate(0 150) scale(0.6)"><Umbrella /></g>],
  ];
  return (
    <g>
      <Layer p={0.06} cam={cam}><NightSky seed={13} /></Layer>
      <Layer p={0.3} cam={cam}>
        <rect x={-300} y={1500} width={W + 600} height={700} fill="#2a1a12" stroke={PL} strokeWidth={4} />
        <Dots d="M -300 1530 L 1380 1530" n={60} r={2.6} />
        <g transform="translate(540 1480)"><circle r={260 * lamp} fill={GOLD} opacity={0.12} /></g>
        <Diya x={540} y={1480} s={3.2} t={t} lit={lamp} />
      </Layer>
      <Layer p={0.5} cam={cam}>
        {pair > 0 && (
          <g opacity={pair}>
            <Medallion id={`${id}-k`} x={300} y={760} r={190} k={kali} bg="#1b2550"><Bust look={LOOKS.kali} t={t} /></Medallion>
            <Medallion id={`${id}-l`} x={780} y={980} r={190} k={ledger} bg="#f2c14e"><g transform="translate(0 10)"><Ledger s={0.85} /></g></Medallion>
            <RegionBanner x={300} y={1010} text="बंगाल" k={kali} w={300} />
            <RegionBanner x={780} y={1230} text="गुजरात" k={ledger} w={300} />
          </g>
        )}
        {ring > 0 && emblems.map(([key, node], i) => {
          const a = (-90 + i * 72 + 6 * span(f, S(3), E(3) + 30)) * (Math.PI / 180);
          const r = 380 * ring;
          return (
            <Medallion key={key} id={`${id}-e${i}`} x={540 + r * Math.cos(a)} y={900 + r * Math.sin(a) * 0.9} r={110} k={span(f, S(3) - 10 + i * 6, S(3) + 14 + i * 6)} bg={[RED, '#1b2550', '#1b2550', '#2e7d4f', '#7a2a8a'][i]}>
              {node}
            </Medallion>
          );
        })}
      </Layer>
    </g>
  );
};

// ------------------------------------------------------------------ B: Ayodhya, and today's lamps (4-5)
export const AyodhyaScene: React.FC<SceneProps> = ({f, id}) => {
  const {S, E, MID, FRAMES} = useL();
  const t = f / 30;
  const g = f + S(4) - 10;
  const walk = span(g, S(4), MID(4) + 20);
  const night = span(g, S(5) + 30, MID(5) + 20);
  const cam: Cam = {x: 0, y: -20 * span(g, S(4), E(5)), z: 0.03 + 0.05 * span(g, S(4), E(5))};
  const rx = lerp(160, 470, walk);
  return (
    <g>
      <Layer p={0.06} cam={cam}><rect x={-300} y={-300} width={W + 600} height={H + 600} fill={hexMix(GOLD, '#141a3a', night)} />
        {night > 0 && <g opacity={night}><NightSky seed={29} /></g>}
        {Array.from({length: 26}, (_, i) => <circle key={i} cx={(i * 197) % W} cy={120 + (i * 311) % 700} r={3} fill={WD} opacity={1 - night} />)}</Layer>
      <Layer p={0.2} cam={cam}><g transform="translate(540 1180) scale(0.82) translate(-540 -1180)">
        {night < 1 && <g opacity={1 - night}><Ayodhya y={1180} t={t} lit={night} /></g>}
        {night > 0 && <g opacity={night}><Ayodhya y={1180} t={t} lit={night} night /></g>}
      </g></Layer>
      <Layer p={0.35} cam={cam}><River y={1180} h={140} t={t} id={`${id}-sar`} fill={hexMix('#2d5aa8', '#1b2550', night)} />
        {[40, 1040].map((x, i) => <SalTree key={x} x={x} y={1330} s={0.9} t={t + i} />)}</Layer>
      <Layer p={0.5} cam={cam}>
        <Ground y={1320} fill={hexMix('#c98a52', '#3a2418', night)} />
        <Dots d="M -300 1350 C 200 1350 800 1350 1380 1350" n={60} r={2.4} />
        {/* the townspeople greet them, arms raised with flowers */}
        {[0, 1, 2].map((i) => (
          <At key={i} x={860 + i * 90} y={1700 - i * 30} s={0.42 - i * 0.04} dir={-1}>
            <Figure look={i % 2 ? LOOKS.villager : LOOKS.villagerW} t={t + i} far={mixArm(REST, UP, span(g, S(4) + 40 + i * 8, S(4) + 70 + i * 8))} near={mixArm(REST, {a: 140, b: 20, hand: 'open'}, span(g, S(4) + 30 + i * 8, S(4) + 60 + i * 8))} blinkOff={i} />
          </At>
        ))}
        <At x={rx - 150} y={1720} s={0.46}><Figure look={LOOKS.sita} t={t} far={REST} near={{a: 20, b: 60, hand: 'open'}} blinkOff={1} /></At>
        <g transform={`translate(${rx} 1740) scale(0.5)`}><Glory x={10} y={-960} r={150} t={t} /></g>
        <At x={rx} y={1740} s={0.5}><Figure look={LOOKS.rama} t={t} far={{a: 10, b: 20, hand: 'fist'}} near={mixArm({a: 20, b: 30, hand: 'open'}, {a: 120, b: 10, hand: 'abhaya'}, span(g, MID(4), MID(4) + 30))} bow /></At>
        <At x={rx + 150} y={1730} s={0.47}><Figure look={LOOKS.lakshmana} t={t} far={REST} near={NAMASTE} blinkOff={2} /></At>
      </Layer>
      <Layer p={0.8} cam={cam}><Petals f={g} k={1 - night} /></Layer>
      <Layer p={0.9} cam={cam}>
        {night > 0 && <rect x={-300} y={1730} width={W + 600} height={400} fill="#2a1a12" stroke={PL} strokeWidth={4} opacity={night} />}
        {night > 0 && <DiyaRow y={1760} n={9} w={860} s={1.2} t={t} f={g} at={S(5) + 50} />}
      </Layer>
      <Banner f={g} at={S(4) - 4} text="अयोध्या" y={260} until={S(5) + 20} w={380} />
    </g>
  );
};

// ------------------------------------------------------------------ C: Rama is Vishnu; the discus turns south (6)
export const Bridge: React.FC<SceneProps> = ({f}) => {
  const {S, E, MID, FRAMES} = useL();
  const t = f / 30;
  const g = f + S(6) - 10;
  const become = span(g, S(6) + 20, S(6) + 60);
  const fly = span(g, MID(6) + 10, E(6) + 16);
  const cam: Cam = {x: 0, y: 0, z: 0.04 * span(g, S(6), E(6))};
  const vArm: Arm = {a: 150, b: 10, hand: 'open'};
  const w = wristAt('near', vArm);
  return (
    <g>
      <Layer p={0.06} cam={cam}><Sky fill={hexMix('#141a3a', SKY, become)} dots={30} seed={3} /></Layer>
      <Layer p={0.2} cam={cam}><PCloud x={-80} y={1460} w={520} t={t} /><PCloud x={620} y={1540} w={500} t={t + 1} /></Layer>
      <Layer p={0.45} cam={cam}>
        <g transform="translate(540 1500) scale(0.95)"><Glory x={10} y={-960} r={170 + 40 * become} t={t} /></g>
        <At x={540} y={1500} s={0.95} o={1 - become}><Figure look={LOOKS.rama} t={t} far={{a: 10, b: 20, hand: 'fist'}} near={{a: 120, b: 10, hand: 'abhaya'}} bow /></At>
        <At x={540} y={1500} s={0.95} o={become}>
          <Figure look={LOOKS.vishnu} t={t} far={{a: 40, b: 60, hand: 'open'}} near={vArm} />
          <InHand side="far" arm={{a: 40, b: 60}}><Conch s={1.1} /></InHand>
          {fly === 0 && <g transform={`translate(${w.x} ${w.y - 70})`}><Chakra t={t} glow={become} /></g>}
        </At>
      </Layer>
      <Layer p={0.7} cam={cam}>
        {fly > 0 && <g transform={`translate(${lerp(540 + 0.95 * w.x, 980, fly)} ${lerp(1500 + 0.95 * (w.y - 70), 1900, fly)}) scale(${lerp(0.95, 1.6, fly)})`}><Chakra t={t * 2} glow={1} /></g>}
      </Layer>
    </g>
  );
};

// ------------------------------------------------------------------ D: the South; Narakasura's fort; Garuda (7-9)
export const South: React.FC<SceneProps> = ({f}) => {
  const {S, E, MID, FRAMES} = useL();
  const t = f / 30;
  const g = f + S(7) - 10;
  const garuda = span(g, S(9) - 20, S(9) + 50);
  const throwK = span(g, MID(9) + 10, MID(9) + 36);
  const fall = span(g, MID(9) + 34, MID(9) + 64);
  const cam: Cam = {x: lerp(0, 40, span(g, S(8), E(8))), y: 0, z: 0.04 + 0.06 * span(g, S(7), E(9))};
  const gx = lerp(1350, 700, garuda), gy = lerp(300, 720, garuda);
  const kArm: Arm = mixArm({a: 100, b: 20, hand: 'open'}, {a: 120, b: -20, hand: 'open'}, throwK);
  return (
    <g>
      <Layer p={0.06} cam={cam}><Sky fill="#4a2a5a" dots={30} seed={5} /><circle cx={860} cy={420} r={70} fill="#f08fa8" opacity={0.5} /></Layer>
      <Layer p={0.2} cam={cam}>
        {[60, 1020].map((x, i) => <g key={x} transform={`translate(${x} 1240) scale(1.4)`}><path d="M 0 0 C 6 -60 -4 -130 10 -200" fill="none" stroke={PL} strokeWidth={14} /><path d="M 0 0 C 6 -60 -4 -130 10 -200" fill="none" stroke="#6a3b1e" strokeWidth={9} />{[-150, -110, -70, -30, 10, 40].map((a) => <path key={a} d="M 0 0 C 30 -12 80 -12 110 0 C 80 12 30 12 0 0 Z" transform={`translate(10 -200) rotate(${a + 4 * Math.sin(t * 2 + i)})`} fill="#2e7d4f" stroke={PL} strokeWidth={2.4} />)}</g>)}
        <g transform="translate(540 1300)"><Fort w={820} /></g>
        {/* the captive women behind the bars of a high window */}
        <g transform="translate(540 1010)">
          <rect x={-200} y={-150} width={400} height={170} fill="#1a120c" stroke={PL} strokeWidth={4} />
          {[-130, -10, 110].map((x, i) => <At key={x} x={x} y={190} s={0.3}><Figure look={LOOKS.maiden} t={t + i} far={REST} near={{a: 30, b: 120, hand: 'open'}} head={8} gaze={-0.5 + fall} blinkOff={i} tears={(1 - fall) * 0.8} /></At>)}
          {Array.from({length: 9}, (_, i) => <path key={i} d={`M ${-180 + i * 45} -150 L ${-180 + i * 45} 20`} stroke="#5a3a1a" strokeWidth={10} />)}
        </g>
      </Layer>
      <Layer p={0.45} cam={cam}>
        <Ground y={1300} fill="#8a5a3a" />
        <At x={320} y={1780} s={0.62} rot={-40 * fall} o={1 - fall}>
          <Figure look={LOOKS.naraka} t={t} far={{a: 40, b: 50, hand: 'fist'}} near={mixArm({a: 30, b: 40, hand: 'fist'}, {a: 130, b: 20, hand: 'fist'}, span(g, S(9) + 20, S(9) + 50))} head={-8 * garuda} gaze={-0.6 * garuda} />
        </At>
      </Layer>
      <Layer p={0.6} cam={cam}>
        {garuda > 0 && (
          <g transform={`translate(${gx} ${gy}) scale(-1 1)`}>
            <Garuda t={t} s={0.62}>
              <At x={-90} y={0} s={0.5}><Figure look={LOOKS.satyabhama} t={t} stance="sit" far={REST} near={{a: 40, b: 90, hand: 'open'}} blinkOff={1} /></At>
              <At x={90} y={0} s={0.55}><Figure look={LOOKS.krishna} t={t} stance="sit" far={{a: 40, b: 60, hand: 'open'}} near={kArm} /></At>
            </Garuda>
          </g>
        )}
        {throwK > 0 && fall < 1 && <g transform={`translate(${lerp(gx - 160, 360, throwK)} ${lerp(gy - 300, 1260, throwK)})`}><Chakra r={50} t={t * 3} glow={1} /></g>}
        {fall > 0 && fall < 1 && <circle cx={360} cy={1300} r={80 + 500 * fall} fill="none" stroke={GOLD} strokeWidth={12} opacity={1 - fall} />}
      </Layer>
      <Banner f={g} at={S(7) - 4} text="दक्षिण भारत" y={260} until={E(7) + 10} w={460} />
    </g>
  );
};

// ------------------------------------------------------------------ E: the women walk free; dawn lamps and kolam (10)
export const SouthDawn: React.FC<SceneProps> = ({f}) => {
  const {S, E, MID, FRAMES} = useL();
  const t = f / 30;
  const g = f + S(10);
  const free = span(g, S(10), MID(10));
  const dawn = span(g, MID(10) - 10, MID(10) + 30);
  const cam: Cam = {x: 0, y: 0, z: 0.04 * span(g, S(10), E(10))};
  return (
    <g>
      <Layer p={0.06} cam={cam}><rect x={-300} y={-300} width={W + 600} height={H + 600} fill={hexMix('#4a2a5a', '#3a2a6a', dawn)} />
        <rect x={-300} y={900} width={W + 600} height={600} fill={hexMix('#4a2a5a', DAWN, dawn)} opacity={0.8} />
        {dawn > 0 && <circle cx={540} cy={lerp(1320, 1180, dawn)} r={110} fill={GOLD} stroke={PL} strokeWidth={4} opacity={dawn} />}</Layer>
      {dawn < 1 && (
        <g opacity={1 - dawn}>
          <Layer p={0.25} cam={cam}><g transform="translate(980 1300)"><Fort w={820} /></g></Layer>
          <Layer p={0.45} cam={cam}>
            <Ground y={1300} fill="#8a5a3a" />
            {[0, 1, 2, 3, 4].map((i) => (
              <At key={i} x={lerp(700, 120, free) + i * 150} y={1760 - (i % 2) * 40} s={0.5} dir={-1}>
                <Figure look={i % 2 ? LOOKS.maiden : LOOKS.villagerW} t={t + i} far={REST} near={mixArm(NAMASTE, {a: 150, b: 10, hand: 'open'}, span(g, S(10) + 20 + i * 6, S(10) + 50 + i * 6))} blinkOff={i} />
              </At>
            ))}
          </Layer>
          <Layer p={0.7} cam={cam}><Petals f={g} n={24} /></Layer>
        </g>
      )}
      {dawn > 0 && (
        <g opacity={dawn}>
          <Layer p={0.3} cam={cam}>
            {/* a southern house front: tiled roof, pillars, the threshold */}
            <g transform="translate(540 1420)" stroke={PL} strokeWidth={4} strokeLinejoin="round">
              <rect x={-420} y={-360} width={840} height={360} fill="#e8d0a0" />
              <path d="M -480 -360 L 0 -560 L 480 -360 Z" fill="#a8281f" />
              {Array.from({length: 12}, (_, i) => <path key={i} d={`M ${-440 + i * 80} -370 L ${-40 + i * 7} -540`} stroke="#7a1f16" strokeWidth={3} />)}
              {[-340, -170, 170, 340].map((x) => <rect key={x} x={x - 18} y={-360} width={36} height={360} fill="#c98a52" />)}
              <path d="M -90 0 L -90 -230 C -90 -300 90 -300 90 -230 L 90 0 Z" fill="#3a2418" />
              <path d="M -120 -250 C -60 -230 60 -230 120 -250" fill="none" stroke="#2e7d4f" strokeWidth={10} />
              {Array.from({length: 9}, (_, i) => <path key={i} d={`M ${-110 + i * 27} -246 l 6 26 l 6 -26`} fill={GOLD} strokeWidth={2} />)}
            </g>
          </Layer>
          <Layer p={0.5} cam={cam}>
            <Ground y={1420} fill="#c98a52" />
            <g transform="translate(540 1600)"><Kolam r={150} k={span(g, MID(10), E(10))} /></g>
            <DiyaRow y={1470} n={7} w={760} s={1.0} t={t} f={g} at={MID(10) + 10} step={4} />
            <At x={200} y={1800} s={0.55}><Figure look={LOOKS.villagerW} t={t} stance="kneel" far={OFFER} near={{a: 70, b: 40, hand: 'open'}} head={10} /></At>
          </Layer>
          <Layer p={0.8} cam={cam}><DiyaRow y={1820} n={9} w={980} s={1.3} t={t} f={g} at={MID(10) + 24} step={4} /></Layer>
        </g>
      )}
    </g>
  );
};

// ------------------------------------------------------------------ F: the East; Kali (11-13)
export const East: React.FC<SceneProps> = ({f}) => {
  const {S, E, MID, FRAMES} = useL();
  const t = f / 30;
  const g = f + S(11) - 10;
  const anger = span(g, S(12) + 10, S(12) + 50);
  const born = span(g, MID(12), MID(12) + 40);
  const strike = span(g, S(13) + 10, S(13) + 40);
  const gone = span(g, S(13) + 40, S(13) + 70);
  const puja = span(g, MID(13) - 6, MID(13) + 30);
  const cam: Cam = {x: 0, y: -30 * born, z: 0.04 + 0.06 * span(g, S(11), MID(13))};
  const sArm: Arm = mixArm({a: 150, b: 10, hand: 'fist'}, {a: 100, b: 20, hand: 'fist'}, strike);
  const kaliX = lerp(300, 560, born), kaliS = lerp(0.2, 0.9, born);
  return (
    <g>
      <Layer p={0.06} cam={cam}><NightSky seed={47} /><rect x={-300} y={-300} width={W + 600} height={H + 600} fill={RED} opacity={0.35 * anger * (1 - puja)} /></Layer>
      {puja < 1 && (
        <g opacity={1 - puja}>
          <Layer p={0.3} cam={cam}><Ground y={1500} fill="#3a2418" /></Layer>
          <Layer p={0.45} cam={cam}>
            <At x={240} y={1820} s={0.72} o={1 - 0.6 * born}>
              <Figure look={LOOKS.devi} t={t} far={{a: 40, b: 60, hand: 'open'}} near={mixArm(OFFER, {a: 110, b: 20, hand: 'fist'}, anger)} head={-6 * anger} gaze={anger} />
            </At>
            {/* the brow, and the light from it */}
            {born > 0 && born < 1 && <path d={`M ${240 + 0.72 * 40} ${1820 - 0.72 * 1000} L ${kaliX} ${1820 - kaliS * 600}`} stroke={GOLD} strokeWidth={14 * (1 - born)} strokeLinecap="round" opacity={0.8} />}
            {born > 0 && (
              <g>
                <circle cx={kaliX} cy={1820 - kaliS * 520} r={kaliS * 600} fill={GOLD} opacity={0.12} />
                <At x={kaliX} y={1820} s={kaliS}>
                  <Figure look={LOOKS.kali} t={t} far={{a: 40, b: 70, hand: 'abhaya'}} near={sArm} gaze={0.4} />
                  <InHand side="near" arm={sArm}><g transform={`rotate(${-40 * strike})`}><Sword /></g></InHand>
                </At>
              </g>
            )}
            {[0, 1].map((i) => (
              <At key={i} x={lerp(1300, 860 + i * 140, span(g, S(12) + 30, MID(12) + 40)) + 200 * gone} y={1820 + i * 20} s={0.6} dir={-1} rot={30 * gone} o={1 - gone}>
                <Figure look={i ? LOOKS.munda : LOOKS.chanda} t={t + i} far={{a: 60, b: 40, hand: 'fist'}} near={{a: 120, b: 20, hand: 'fist'}} blinkOff={i} />
              </At>
            ))}
            {strike > 0 && gone < 1 && <path d={`M ${kaliX + 300} ${1000} C ${kaliX + 500} 1200 ${kaliX + 500} 1500 ${kaliX + 360} 1700`} fill="none" stroke={WD} strokeWidth={18 * (1 - gone)} strokeLinecap="round" opacity={strike} />}
          </Layer>
        </g>
      )}
      {puja > 0 && (
        <g opacity={puja}>
          <Layer p={0.3} cam={cam}>
            {/* the puja: Kali under a decorated arch, lamps and hibiscus, conch */}
            <g transform="translate(540 1500)" stroke={PL} strokeWidth={4} strokeLinejoin="round">
              <path d="M -400 0 L -400 -900 C -400 -1150 400 -1150 400 -900 L 400 0 Z" fill="#7a1f16" />
              <path d="M -340 0 L -340 -880 C -340 -1080 340 -1080 340 -880 L 340 0 Z" fill="#1b2550" />
              <Dots d="M -370 -10 L -370 -900 C -370 -1120 370 -1120 370 -900 L 370 -10" n={60} r={3} />
            </g>
          </Layer>
          <Layer p={0.45} cam={cam}>
            <circle cx={540} cy={1000} r={340} fill={GOLD} opacity={0.15} />
            <At x={540} y={1480} s={0.82}>
              <Figure look={LOOKS.kali} t={t} far={{a: 40, b: 70, hand: 'abhaya'}} near={{a: 150, b: 10, hand: 'fist'}} breathe={false} />
              <InHand side="near" arm={{a: 150, b: 10, hand: 'fist'}}><Sword /></InHand>
            </At>
            <Ground y={1500} fill="#3a2418" />
            <DiyaRow y={1560} n={9} w={900} s={1.1} t={t} f={g} at={MID(13)} step={3} />
            {Array.from({length: 10}, (_, i) => <g key={i} transform={`translate(${130 + i * 92} ${1660 + (i % 2) * 30})`}>{[0, 72, 144, 216, 288].map((r) => <ellipse key={r} cx={0} cy={-12} rx={10} ry={15} fill="#c0392b" stroke={PL} strokeWidth={2} transform={`rotate(${r})`} />)}<circle r={5} fill={GOLD} stroke={PL} strokeWidth={1.4} /></g>)}
          </Layer>
          <Layer p={0.8} cam={cam}><DiyaRow y={1830} n={7} w={900} s={1.4} t={t} f={g} at={MID(13) + 10} step={3} /></Layer>
        </g>
      )}
      <Banner f={g} at={S(11) - 4} text="बंगाल · असम" y={260} until={E(11) + 10} w={480} />
    </g>
  );
};

// ------------------------------------------------------------------ G: Odisha; light for the ancestors (14)
export const Odisha: React.FC<SceneProps> = ({f, id}) => {
  const {S, E, MID, FRAMES} = useL();
  const t = f / 30;
  const g = f + S(14) - 10;
  const raise = span(g, S(14) + 30, S(14) + 70);
  const cam: Cam = {x: 0, y: -60 * span(g, S(14), E(14) + 20), z: 0.05 * span(g, S(14), E(14))};
  const arm: Arm = mixArm({a: 60, b: 50, hand: 'fist'}, {a: 160, b: 5, hand: 'fist'}, raise);
  const people: [Look, number, number, number][] = [[LOOKS.villager, 260, 1720, 0.62], [LOOKS.villagerW, 520, 1740, 0.58], [LOOKS.villager, 780, 1720, 0.5]];
  return (
    <g>
      <Layer p={0.06} cam={cam}><NightSky seed={61} /></Layer>
      <Layer p={0.15} cam={cam}>
        {/* sparks rising into stars: the way lit for the ancestors */}
        {Array.from({length: 26}, (_, i) => {
          const k = span(g, S(14) + 50 + i * 3, S(14) + 140 + i * 3);
          return k > 0 && <circle key={i} cx={260 + ((i * 97) % 560) + 40 * Math.sin(t + i)} cy={lerp(900, 120 + (i * 53) % 500, k)} r={lerp(6, 4, k)} fill={i % 3 ? GOLD : WD} opacity={k < 1 ? 1 : 0.8} />;
        })}
      </Layer>
      <Layer p={0.3} cam={cam}><Deul x={900} y={1360} s={0.8} t={t} /><River y={1360} h={180} t={t} id={`${id}-mah`} fill="#1b2550" /></Layer>
      <Layer p={0.5} cam={cam}>
        <Ground y={1520} fill="#3a2418" />
        {people.map(([look, x, y, s], i) => (
          <At key={i} x={x} y={y} s={s}>
            <Figure look={look} t={t + i} far={REST} near={arm} head={-14 * raise} gaze={-0.5 * raise} blinkOff={i} />
            <InHand side="near" arm={arm}><g transform={`rotate(${-30 * raise})`}><JuteTorch t={t} k={span(g, S(14) + 10 + i * 6, S(14) + 30 + i * 6)} ph={i} /></g></InHand>
          </At>
        ))}
      </Layer>
      <Banner f={g} at={S(14) - 4} text="ओडिशा" y={260} w={340} />
    </g>
  );
};

// ------------------------------------------------------------------ H: the West; Lakshmi (15-17)
export const West: React.FC<SceneProps> = ({f, id}) => {
  const {S, E, MID, FRAMES} = useL();
  const t = f / 30;
  const g = f + S(15) - 10;
  const ocean = span(g, S(16) - 14, S(16) + 14);
  const rise = span(g, S(16) + 10, MID(16) + 10);
  const choose = span(g, MID(16) + 20, E(16));
  const ledger = span(g, S(17) - 14, S(17) + 14);
  const sun = span(g, MID(17) + 10, E(17) + 20);
  const cam: Cam = {x: 0, y: 0, z: 0.03 + 0.05 * span(g, S(15), E(17))};
  const lArm: Arm = mixArm({a: 40, b: 60, hand: 'open'}, {a: 95, b: 0, hand: 'open'}, choose);
  return (
    <g>
      {/* 15: a door lit for Lakshmi, her small footprints walking in */}
      {ocean < 1 && (
        <g opacity={1 - ocean}>
          <Layer p={0.06} cam={cam}><NightSky seed={83} /></Layer>
          <Layer p={0.3} cam={cam}>
            <g transform="translate(540 1500)" stroke={PL} strokeWidth={4} strokeLinejoin="round">
              <rect x={-460} y={-760} width={920} height={760} fill="#e8b860" />
              <path d="M -500 -760 L 500 -760 L 440 -840 L -440 -840 Z" fill="#a8281f" />
              <path d="M -150 0 L -150 -440 C -150 -560 150 -560 150 -440 L 150 0 Z" fill="#f2c14e" />
              <path d="M -110 0 L -110 -420 C -110 -510 110 -510 110 -420 L 110 0 Z" fill="#7a3a1e" />
              <path d="M -200 -480 C -100 -440 100 -440 200 -480" fill="none" stroke="#2e7d4f" strokeWidth={12} />
              {Array.from({length: 11}, (_, i) => <path key={i} d={`M ${-190 + i * 38} -474 l 8 34 l 8 -34`} fill={i % 2 ? '#e8742a' : GOLD} strokeWidth={2} />)}
              {[-300, 300].map((x) => <rect key={x} x={x - 70} y={-560} width={140} height={160} fill="#3a2418" />)}
            </g>
          </Layer>
          <Layer p={0.5} cam={cam}>
            <Ground y={1500} fill="#8a3a1e" />
            <g transform="translate(540 1660)"><Kolam r={170} k={span(g, S(15), E(15))} /></g>
            {Array.from({length: 6}, (_, i) => {
              const k = span(g, S(15) + 20 + i * 10, S(15) + 30 + i * 10);
              return <g key={i} transform={`translate(${540 + (i % 2 ? 30 : -30)} ${1790 - i * 52}) scale(${1.3 - i * 0.1})`} opacity={k}><path d="M 0 -30 C 14 -30 18 -10 14 10 C 10 26 -10 26 -14 10 C -18 -10 -14 -30 0 -30 Z" fill="#c0392b" stroke={PL} strokeWidth={2} />{[-10, -3, 4, 11].map((x) => <circle key={x} cx={x} cy={-40} r={4} fill="#c0392b" />)}</g>;
            })}
            <DiyaRow y={1520} n={8} w={940} s={1.0} t={t} f={g} at={S(15)} step={3} />
          </Layer>
          <Banner f={g} at={S(15) - 4} text="गुजरात · महाराष्ट्र" y={260} w={560} />
        </g>
      )}
      {/* 16: the ocean of milk; Lakshmi rises on the lotus and chooses Vishnu */}
      {ocean > 0 && ledger < 1 && (
        <g opacity={ocean * (1 - ledger)}>
          <defs>{waterPattern(`${id}-milk`, (g * 1.4) % 80, 0, '#e8eef6')}</defs>
          <Layer p={0.06} cam={cam}><Sky fill={SKY} dots={30} seed={7} /></Layer>
          <Layer p={0.25} cam={cam}><PCloud x={-60} y={420} w={420} t={t} /><PCloud x={640} y={520} w={380} t={t + 1} /></Layer>
          <Layer p={0.4} cam={cam}>
            <path d={`M -300 1240 ${Array.from({length: 16}, (_, i) => `Q ${-240 + i * 110} ${1210 + 16 * Math.sin(t * 2 + i)} ${-190 + i * 110} 1240`).join(' ')} L 1380 2200 L -300 2200 Z`} fill={`url(#${id}-milk)`} stroke={PL} strokeWidth={4} />
            {Array.from({length: 6}, (_, i) => <path key={i} d={`M ${-100 + i * 220} ${1320 + (i % 2) * 80} c 30 -24 60 -24 90 0`} fill="none" stroke={PL} strokeWidth={3} />)}
          </Layer>
          <Layer p={0.55} cam={cam}>
            <g transform="translate(860 1620) scale(0.78)"><Glory x={10} y={-960} r={150} t={t} /></g>
            <At x={860} y={1620} s={0.78} dir={-1}>
              <Figure look={LOOKS.vishnu} t={t} far={{a: 40, b: 60, hand: 'open'}} near={mixArm(REST, {a: 60, b: 40, hand: 'open'}, choose)} gaze={0.4} />
              <InHand side="far" arm={{a: 40, b: 60}}><Conch /></InHand>
            </At>
            <g transform={`translate(360 ${lerp(1700, 1420, rise)})`}>
              <circle cy={-500} r={420 * rise} fill={GOLD} opacity={0.15} />
              <LotusSeat w={360} />
              <At x={0} y={-30} s={0.72}>
                <Figure look={LOOKS.lakshmi} t={t} far={{a: 40, b: 60, hand: 'open'}} near={lArm} gaze={0.5} />
                <InHand side="far" arm={{a: 40, b: 60}}><Lotus s={0.8} /></InHand>
                {/* the garland she holds out to Vishnu */}
                <InHand side="near" arm={lArm} dy={10}><path d="M -30 0 C -30 120 90 120 90 0" fill="none" stroke="#f08fa8" strokeWidth={14} opacity={choose} /><Dots d="M -30 0 C -30 120 90 120 90 0" n={10} r={4} /></InHand>
              </At>
            </g>
          </Layer>
          <Layer p={0.85} cam={cam}><Petals f={g} n={30} k={choose} /></Layer>
        </g>
      )}
      {/* 17: the ledger worshipped; the new year's sun */}
      {ledger > 0 && (
        <g opacity={ledger}>
          <Layer p={0.06} cam={cam}><rect x={-300} y={-300} width={W + 600} height={H + 600} fill={hexMix('#2a1a3a', DAWN, sun)} />
            <circle cx={540} cy={lerp(1100, 560, sun)} r={150} fill={GOLD} stroke={PL} strokeWidth={4} opacity={sun} />
            {sun > 0 && Array.from({length: 16}, (_, i) => <path key={i} d="M -8 -180 L 0 -230 L 8 -180 Z" fill={GOLD} stroke={PL} strokeWidth={2} transform={`translate(540 ${lerp(1100, 560, sun)}) rotate(${i * 22.5 + t * 6})`} opacity={sun} />)}</Layer>
          <Layer p={0.4} cam={cam}>
            <Ground y={1420} fill="#7a3a1e" />
            <path d="M 160 1500 L 920 1500 L 960 1560 L 120 1560 Z" fill="#b3261e" stroke={PL} strokeWidth={4} />
            <Dots d="M 140 1540 L 940 1540" n={30} r={2.6} />
            <g transform="translate(700 1420)"><Ledger s={0.9} open={1} /></g>
            <g transform="translate(470 1440)"><Lotus s={0.6} /></g>
            <Diya x={880} y={1500} s={1.4} t={t} lit={1} />
            <At x={300} y={1760} s={0.66}><Figure look={LOOKS.trader} t={t} stance="sit" far={NAMASTE} near={NAMASTE} head={6} /></At>
          </Layer>
          <Banner f={g} at={MID(17) + 10} text="नूतन वर्ष" y={300} w={380} />
        </g>
      )}
    </g>
  );
};

// ------------------------------------------------------------------ J: Bali and Vamana (18-21)
export const Bali: React.FC<SceneProps> = ({f}) => {
  const {S, E, MID, FRAMES} = useL();
  const t = f / 30;
  const g = f + S(18) - 10;
  const enter = span(g, S(19) + 20, MID(19) + 20);
  const pour = span(g, MID(19) + 20, E(19));
  const grow = span(g, S(20) + 10, MID(20) + 10);
  const steps = span(g, MID(20), E(20) - 10);
  const sutala = span(g, E(20) - 30, E(20) + 6);
  const ret = span(g, S(21) - 10, S(21) + 20);
  const cam: Cam = {x: 0, y: lerp(0, -260, grow) * (1 - ret), z: 0.03 + 0.04 * span(g, S(18), E(19)) - 0.04 * grow * (1 - ret)};
  const bArm: Arm = mixArm({a: 50, b: 60, hand: 'open'}, {a: 80, b: 40, hand: 'open'}, pour);
  const vs = lerp(0.42, 2.6, grow);
  return (
    <g>
      {ret < 1 && (
        <g opacity={1 - ret}>
          <Layer p={0.06} cam={cam}><Sky fill={hexMix('#7a2a8a', SKY, grow)} dots={40} seed={9} />
            {steps > 0 && Array.from({length: 3}, (_, i) => <circle key={i} cx={240 + i * 300} cy={260} r={60 * span(g, MID(20) + i * 20, MID(20) + 20 + i * 20)} fill={GOLD} stroke={PL} strokeWidth={3} />)}</Layer>
          <Layer p={0.3} cam={cam}><g transform="translate(540 1300) scale(0.9) translate(-540 -1300)"><Palace x={540} y={1300} s={1} t={t} /></g></Layer>
          <Layer p={0.45} cam={cam}>
            <Ground y={1300} fill={hexMix('#c98a52', '#e8b860', sutala)} />
            <FireAltar x={540} y={1560} s={0.9} t={t} k={1 - grow} />
            {/* Bali on his throne, then on his knees before the giant */}
            <g transform="translate(280 1720)">
              <path d="M -130 0 L -130 -320 C -130 -380 120 -380 120 -320 L 120 0 Z" fill={GOLD} stroke={PL} strokeWidth={4} opacity={1 - grow} />
              <At x={0} y={0} s={0.58}>
                <Figure look={LOOKS.bali} t={t} stance={grow > 0.3 ? 'kneel' : 'sit'} far={grow > 0.3 ? NAMASTE : REST} near={grow > 0.3 ? NAMASTE : bArm} head={10 * grow} lean={20 * grow} gaze={0.5} />
                {grow <= 0.3 && pour > 0 && <InHand side="near" arm={bArm} stance="sit"><Kamandalu s={0.9} />{Array.from({length: 6}, (_, i) => <circle key={i} cx={80} cy={50 + ((g * 8 + i * 30) % 180)} r={5} fill="#7fb0e0" />)}</InHand>}
              </At>
            </g>
          </Layer>
          <Layer p={0.55} cam={cam}>
            <At x={lerp(1250, 760, enter)} y={1760} s={vs} dir={-1}>
              <Figure look={LOOKS.vamana} t={t} far={REST} near={grow > 0 ? {a: 30, b: 30, hand: 'open'} : mixArm({a: 30, b: 30, hand: 'fist'}, {a: 70, b: 50, hand: 'open'}, pour)} gaze={0.3} />
              {grow < 0.5 && <g opacity={1 - 2 * grow}><InHand side="far" arm={REST} dy={20}><Umbrella s={0.9} /></InHand></g>}
            </At>
            {grow > 0 && <circle cx={760} cy={1760 - vs * 600} r={vs * 500} fill={GOLD} opacity={0.12 * grow} />}
          </Layer>
        </g>
      )}
      {ret > 0 && (
        <g opacity={ret}>
          <Layer p={0.06} cam={cam}><NightSky seed={97} /></Layer>
          <Layer p={0.3} cam={cam}><Skyline y={1320} t={t} lit={span(g, S(21), MID(21))} /></Layer>
          <Layer p={0.45} cam={cam}>
            <Ground y={1320} fill="#3a2418" />
            <DiyaRow y={1360} n={9} w={960} s={0.9} t={t} f={g} at={S(21)} step={3} />
            <At x={lerp(-100, 420, span(g, S(21), MID(21) + 10))} y={1760} s={0.7}>
              <Figure look={LOOKS.bali} t={t} far={REST} near={{a: 120, b: 10, hand: 'abhaya'}} gaze={0.5} />
            </At>
            {[0, 1, 2].map((i) => (
              <At key={i} x={720 + i * 120} y={1780 - (i % 2) * 30} s={0.5} dir={-1}>
                <Figure look={i % 2 ? LOOKS.villager : LOOKS.villagerW} t={t + i} far={NAMASTE} near={NAMASTE} head={6} blinkOff={i} />
              </At>
            ))}
          </Layer>
        </g>
      )}
      <Banner f={g} at={S(18) - 4} text="महाराष्ट्र · कर्नाटक" y={260} until={E(18) + 10} w={560} />
      <Banner f={g} at={MID(20) + 10} text="सुतल लोक" y={260} until={E(20) + 6} w={380} />
    </g>
  );
};

// ------------------------------------------------------------------ K: Braj; Govardhan (22-25)
export const Braj: React.FC<SceneProps> = ({f}) => {
  const {S, E, MID, FRAMES} = useL();
  const t = f / 30;
  const g = f + S(22) - 10;
  const angry = span(g, MID(23), MID(23) + 30);
  const rain = span(g, MID(23) + 10, MID(23) + 40) * (1 - span(g, MID(24), MID(24) + 30));
  const lift = span(g, S(24) - 10, S(24) + 30);
  const bow = span(g, MID(24) + 10, E(24));
  const annakut = span(g, S(25) - 10, S(25) + 20);
  const cam: Cam = {x: 0, y: 0, z: 0.03 + 0.04 * span(g, S(22), E(24))};
  const kArm: Arm = {a: 175, b: 0, hand: 'abhaya'};
  const hw = wristAt('near', kArm);
  const hillY = lerp(1500, 1720 + 0.62 * hw.y - 20, lift);
  return (
    <g>
      {annakut < 1 && (
        <g opacity={1 - annakut}>
          <Layer p={0.06} cam={cam}><Sky fill={hexMix('#3b8fb0', '#2a2a3a', Math.max(angry, rain))} dots={20} seed={11} /></Layer>
          <Layer p={0.15} cam={cam}>
            {/* Indra in the storm clouds, then coming down to bow */}
            <g opacity={angry}>
              <PCloud x={-100} y={lerp(380, 600, bow)} w={560} fill="#9aa4b8" t={t} />
              <PCloud x={560} y={lerp(420, 640, bow)} w={520} fill="#9aa4b8" t={t + 1} />
            </g>
          </Layer>
          <Layer p={0.3} cam={cam}>
            <Ground y={1500} fill="#4e8a3e" />
            <g transform={`translate(540 ${hillY}) scale(${lerp(1, 0.9, lift)})`}><Hill w={1000} h={440} t={t} /></g>
          </Layer>
          <Layer p={0.45} cam={cam}>
            {[[250, 1620, 0.42], [820, 1640, 0.4]].map(([x, y, s], i) => <g key={i} transform={`translate(${x} ${y}) scale(${i ? -1 : 1} 1)`}><Cow t={t + i} s={s} /></g>)}
            {[0, 1, 2, 3].map((i) => (
              <At key={i} x={[90, 330, 760, 990][i]} y={1840} s={0.45} dir={i < 2 ? 1 : -1}>
                <Figure look={i % 2 ? LOOKS.villager : LOOKS.villagerW} t={t + i} far={NAMASTE} near={NAMASTE} head={-10 * lift} gaze={-0.6 * lift} blinkOff={i} />
              </At>
            ))}
            {lift > 0 && (
              <At x={540} y={1720 + 120 * (1 - lift)} s={0.62} o={lift}>
                <Figure look={LOOKS.krishnaBoy} t={t} far={{a: 30, b: 60, hand: 'open'}} near={kArm} gaze={0.2} />
              </At>
            )}
          </Layer>
          <Layer p={0.6} cam={cam}>
            {angry > 0 && (
              <At x={lerp(780, 860, bow)} y={lerp(700, 1500, bow)} s={lerp(0.42, 0.55, bow)} dir={-1} o={angry}>
                <Figure look={LOOKS.indra} t={t} far={bow > 0.5 ? NAMASTE : {a: 40, b: 60, hand: 'fist'}} near={bow > 0.5 ? NAMASTE : {a: 140, b: 30, hand: 'fist'}} lean={24 * bow} head={14 * bow} />
              </At>
            )}
            <Rain f={g} k={rain} />
          </Layer>
          <Banner f={g} at={S(22) - 4} text="ब्रज · गोवर्धन" y={260} until={E(22) + 10} w={480} />
        </g>
      )}
      {annakut > 0 && (
        <g opacity={annakut}>
          <Layer p={0.06} cam={cam}><Sky fill={GOLD} dots={30} seed={13} /></Layer>
          <Layer p={0.3} cam={cam}>
            <g transform="translate(540 1180) scale(0.8)"><Hill w={1100} h={480} t={t} /></g>
            <g transform="translate(540 1500) scale(0.62)"><Glory x={10} y={-960} r={150} t={t} /></g>
            <At x={540} y={1500} s={0.62}><Figure look={LOOKS.krishnaBoy} t={t} far={REST} near={{a: 120, b: 10, hand: 'abhaya'}} /></At>
          </Layer>
          <Layer p={0.5} cam={cam}>
            <Ground y={1500} fill="#c98a52" />
            <g transform={`translate(540 1760)`}><FoodMountain w={620} k={span(g, S(25), MID(25) + 10)} /></g>
            <DiyaRow y={1820} n={9} w={980} s={1.1} t={t} f={g} at={S(25) + 10} step={3} />
          </Layer>
          <Banner f={g} at={S(25) + 4} text="अन्नकूट" y={300} w={320} />
        </g>
      )}
    </g>
  );
};

// ------------------------------------------------------------------ L: whose Diwali? Every home's (26-28)
export const Close: React.FC<SceneProps> = ({f, id}) => {
  const {S, E, MID, FRAMES} = useL();
  const t = f / 30;
  const g = f + S(26) - 10;
  const d26 = E(26) - S(26);
  const homes = span(g, S(28) - 20, S(28) + 30);
  const end = FRAMES;
  void end;
  const cam: Cam = {x: 0, y: 20 * homes, z: 0.04 * span(g, S(26), end)};
  const faces: [Look, string, boolean][] = [[LOOKS.rama, '#7a1f16', true], [LOOKS.krishna, '#2e7d4f', true], [LOOKS.lakshmi, '#7a2a8a', false], [LOOKS.bali, '#3b5fb0', false], [LOOKS.kali, '#1b2550', false]];
  const pos = [[540, 520], [250, 820], [830, 820], [330, 1180], [750, 1180]];
  return (
    <g>
      <Layer p={0.06} cam={cam}><NightSky seed={113} /></Layer>
      <Layer p={0.3} cam={cam}>
        <g opacity={1 - homes}>
          {faces.map(([look, bg, glory], i) => (
            <Medallion key={i} id={`${id}-f${i}`} x={pos[i][0]} y={pos[i][1]} r={i === 4 ? 160 : 140} k={span(g, S(26) + 20 + i * d26 * 0.16, S(26) + 40 + i * d26 * 0.16)} bg={bg}>
              <Bust look={look} t={t} glory={glory} blinkOff={i} />
            </Medallion>
          ))}
        </g>
        {homes > 0 && <g opacity={homes}><Skyline y={1340} t={t} lit={span(g, S(28), MID(28) + 20)} /></g>}
      </Layer>
      <Layer p={0.5} cam={cam}>
        <rect x={-300} y={1500} width={W + 600} height={700} fill="#2a1a12" stroke={PL} strokeWidth={4} />
        <circle cx={540} cy={1480} r={300 * span(g, S(27), MID(27))} fill={GOLD} opacity={0.12} />
        <Diya x={540} y={1480} s={3.2} t={t} lit={1} />
      </Layer>
      <Layer p={0.75} cam={cam}>
        {homes > 0 && <g opacity={homes}>{[0, 1].map((row) => <DiyaRow key={row} y={1700 + row * 110} n={9 + row * 2} w={940} s={1 + row * 0.25} t={t} f={g} at={S(28) + row * 12} step={4} />)}</g>}
      </Layer>
    </g>
  );
};

