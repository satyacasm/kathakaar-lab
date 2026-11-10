/**
 * Episode 002, Bharat's vow ("Why Rama sent a spy to his own brother"), in Odisha Pattachitra, English timeline.
 * Scene starts and cues follow the narration lines in lines.ts (generated from timing.json).
 * Figures are articulated (kit/people): Rama in exile dress (jata, yellow cloth, bow, sun-like glory: he refused
 * royal attire until he met Bharat, Yuddha 123/130), Hanuman crowned with mace and tail, Bharat in hermit's dress.
 * Places from Valmiki (kit/places): the jewelled golden Pushpaka, Ayodhya's ramparts and gate on the Sarayu, the
 * sandals on the royal seat under the king's canopy at Nandigram. Diwali night is amavasya: no moon in the last scene.
 *
 *  A  1     Pushpaka over the clouds, Ayodhya below on the Sarayu; Rama raises his hand, Hanuman leaps      (open)
 *  B  2-3   Chitrakoot, fourteen years ago: the sandals lowered onto Bharat's head; the fire of the vow      (scroll)
 *  C  4a    fourteen suns, the last one lighting: "that day"                                               (lotus iris)
 *  D  4b-6  the Pushpaka halts; Rama speaks to Hanuman, who kneels with joined palms                       (cut)
 *  E  6>7   Hanuman's flight over the meeting rivers                                                       (cut)
 *  F  7-10  Nandigram: Bharat thin and waiting, the sandals on the throne, the fire; Hanuman lands; he swoons (scroll)
 *  G  11    Bharat sets the sandals on Rama's feet; flowers fall                                            (lotus iris)
 *  H  12    Bharat's face: no greed, only waiting                                                          (scroll)
 *  J  13    Ayodhya tonight: lamps along the ramparts and on the Sarayu; fade                               (lotus iris)
 */
import React from 'react';
import {Cam, Dots, Layer, PL, WD, waterPattern} from '../../kit/pattachitra';
import {ClothStory, GOLD, H, NightSky, RED, Scene, SceneProps, W, hexMix, lerp, span} from '../../kit/cloth';
import {Diya, FireAltar, Paduka} from '../../kit/figures';
import {Arm, Figure, Glory, LOOKS} from '../../kit/people';
import {Ayodhya, Kutir, PCloud, Pushpaka, River, SalTree, ThroneOfSandals} from '../../kit/places';
import {FRAMES, LINES} from './lines';

const S = (n: number) => LINES[n - 1].s;
const E = (n: number) => LINES[n - 1].e;
const MID4 = Math.round((S(4) + E(4)) / 2);
const SKY = '#2d4a8a';
const DUSK = '#e8742a';
const mixArm = (p: Arm, q: Arm, k: number): Arm => ({a: lerp(p.a, q.a, k), b: lerp(p.b, q.b, k), hand: k < 0.5 ? p.hand : q.hand});
const NAMASTE: Arm = {a: 18, b: 148, hand: 'open'};
const REST: Arm = {a: 8, b: 14, hand: 'open'};

/** Place a figure: feet at (x, y), scale s, facing left when dir = -1. */
const At: React.FC<{x: number; y: number; s: number; dir?: number; rot?: number; children: React.ReactNode}> = ({x, y, s, dir = 1, rot = 0, children}) => (
  <g transform={`translate(${x} ${y}) rotate(${rot}) scale(${dir * s} ${s})`}>{children}</g>
);

/** Hanuman in flight: body near horizontal, mace forward, tail streaming. */
const FlyingHanuman: React.FC<{x: number; y: number; s: number; t: number; dir?: number}> = ({x, y, s, t, dir = 1}) => (
  <g transform={`translate(${x} ${y}) scale(${dir * s} ${s}) rotate(72) translate(0 500)`}>
    <path d={`M 0 0 C -40 300 0 600 ${20 * Math.sin(t * 5)} 900`} fill="none" stroke={GOLD} strokeWidth={60} opacity={0.35} strokeLinecap="round" />
    <Figure look={LOOKS.hanuman} t={t} far={{a: 172, b: 4, hand: 'open'}} near={{a: 168, b: 8, hand: 'fist'}} mace head={-60} breathe={false} />
  </g>
);

// ------------------------------------------------------------------ A: the Pushpaka over the clouds
const Crew: React.FC<{t: number; raise: number; hanuman: boolean}> = ({t, raise, hanuman}) => (
  <g>
    <At x={-150} y={-30} s={0.27}><Figure look={LOOKS.sita} t={t} far={REST} near={{a: 20, b: 60, hand: 'open'}} blinkOff={1} /></At>
    <g transform="translate(20 -30) scale(0.29)"><Glory x={10} y={-960} r={150} t={t} /></g>
    <At x={20} y={-30} s={0.29}><Figure look={LOOKS.rama} t={t} far={{a: 10, b: 20, hand: 'fist'}} near={mixArm({a: 20, b: 30, hand: 'open'}, {a: 120, b: 10, hand: 'abhaya'}, raise)} bow /></At>
    <At x={190} y={-30} s={0.27}><Figure look={LOOKS.lakshmana} t={t} far={REST} near={NAMASTE} blinkOff={2} /></At>
    {hanuman && <At x={310} y={-30} s={0.25} dir={-1}><Figure look={LOOKS.hanuman} t={t} stance="kneel" far={NAMASTE} near={NAMASTE} head={8} blinkOff={0.5} /></At>}
  </g>
);

const Approach: React.FC<SceneProps> = ({f, id}) => {
  const t = f / 30;
  const cam: Cam = {x: 0, y: -30 * span(f, 0, E(1)), z: 0.08 * span(f, 0, E(1))};
  const raise = span(f, E(1) - 90, E(1) - 60);
  const leap = span(f, E(1) - 60, E(1) + 20);
  return (
    <g>
      <Layer p={0.06} cam={cam}>
        <rect x={-300} y={-300} width={W + 600} height={H + 600} fill={SKY} />
        <rect x={-300} y={900} width={W + 600} height={1400} fill={hexMix(SKY, DUSK, 0.55)} />
        <circle cx={860} cy={1080} r={110} fill={GOLD} stroke={PL} strokeWidth={3} />
        {Array.from({length: 40}, (_, i) => <circle key={i} cx={(i * 211) % W} cy={120 + ((i * 97) % 600)} r={2.2} fill={WD} opacity={0.7} />)}
      </Layer>
      <Layer p={0.2} cam={cam}>
        <PCloud x={-60} y={360} w={420} t={t} />
        <PCloud x={660} y={520} w={380} t={t + 1} />
      </Layer>
      <Layer p={0.35} cam={cam}>
        <g transform="translate(540 1500) scale(0.62) translate(-540 -1500)">
          <Ayodhya y={1500} t={t} />
          <River y={1500} h={260} t={t} id={`${id}-sar`} />
          {[60, 980].map((x, i) => <SalTree key={x} x={x} y={1500} s={0.8} t={t + i} />)}
        </g>
      </Layer>
      <Layer p={0.6} cam={cam}>
        <Pushpaka x={lerp(470, 560, span(f, 0, E(1)))} y={900} s={0.62} t={t}>
          <Crew t={t} raise={raise} hanuman={leap <= 0} />
        </Pushpaka>
      </Layer>
      <Layer p={0.7} cam={cam}><PCloud x={-120} y={1160} w={520} t={t + 2} /><PCloud x={700} y={1240} w={420} t={t + 3} /></Layer>
      {leap > 0 && leap < 1 && <Layer p={0.75} cam={cam}><FlyingHanuman x={lerp(700, 220, leap)} y={lerp(860, 1480, leap)} s={0.2} t={t} dir={-1} /></Layer>}
    </g>
  );
};

// ------------------------------------------------------------------ B: Chitrakoot, the sandals and the vow
const Vow: React.FC<SceneProps> = ({f}) => {
  const t = f / 30;
  const g0 = S(2) - 10, g = f + g0;
  const give = span(g, S(2) + 10, S(2) + 70);         // Rama holds the sandals out over Bharat's head
  const place = span(g, S(2) + 70, S(2) + 120);       // lowered onto his head; Bharat raises his hands to them
  const fire = span(g, S(3) + 30, E(3));
  const cam: Cam = {x: -70 * span(g, S(3), E(3) + 20), y: 0, z: 0.04 + 0.1 * span(g, S(3), E(3) + 20)};
  const ramaArm = mixArm({a: 20, b: 30, hand: 'open'}, {a: 95, b: 30, hand: 'open'}, give);
  const bharatArm = mixArm({a: 40, b: 100, hand: 'open'}, {a: 150, b: 30, hand: 'open'}, place);
  const sx = lerp(lerp(470, 600, give), 668, place), sy = lerp(lerp(1060, 820, give), 900, place);
  return (
    <g>
      <Layer p={0.08} cam={cam}><rect x={-300} y={-300} width={W + 600} height={H + 600} fill={RED} />
        {Array.from({length: 26}, (_, i) => <circle key={i} cx={(i * 157) % 1000 + 40} cy={140 + (i * 241) % 760} r={3} fill={WD} opacity={0.8} />)}</Layer>
      <Layer p={0.2} cam={cam}>
        {/* Chitrakoot: hills */}
        <path d="M -300 1100 C -100 860 120 800 300 960 C 460 760 700 760 860 940 C 980 840 1200 860 1380 1000 L 1380 1300 L -300 1300 Z" fill="#5b6aa8" stroke={PL} strokeWidth={4} />
        <Dots d="M -200 1040 C 0 880 160 840 300 960" n={20} r={2.6} />
        <Dots d="M 300 960 C 460 780 700 780 860 940" n={20} r={2.6} />
        {[100, 880, 1000].map((x, i) => <SalTree key={x} x={x} y={1180} s={1.1} t={t + i} />)}
      </Layer>
      <Layer p={0.4} cam={cam}>
        <rect x={-300} y={1180} width={W + 600} height={800} fill="#3f7a3a" stroke={PL} strokeWidth={4} />
        {Array.from({length: 8}, (_, i) => <path key={i} d={`M -300 ${1220 + i * 46} L ${W + 300} ${1220 + i * 46}`} stroke="#2a5a2a" strokeWidth={3} strokeDasharray="30 14" />)}
      </Layer>
      <Layer p={0.55} cam={cam}>
        <g transform="translate(330 1560) scale(0.95)"><Glory x={10} y={-960} t={t} /></g>
        <At x={330} y={1560} s={0.95}><Figure look={LOOKS.rama} t={t} far={{a: 4, b: 6, hand: 'fist'}} near={ramaArm} bow head={4 * give} /></At>
        <At x={760} y={1560} s={0.92} dir={-1}><Figure look={LOOKS.bharat} t={t} stance="kneel" far={bharatArm} near={bharatArm} head={-6 * place + 8 * span(g, S(3), S(3) + 30)} tears={span(g, S(2) + 60, S(2) + 120)} blinkOff={1.3} /></At>
        <Paduka x={sx} y={sy} s={0.5} glow={0.4 + 0.6 * place} rot={90} />
      </Layer>
      <Layer p={0.85} cam={cam}>
        <rect x={-300} y={1660} width={W + 600} height={400} fill="#2e5d2a" stroke={PL} strokeWidth={4} />
        {fire > 0 && <FireAltar x={560} y={1780} s={1.1} t={t} k={fire} />}
      </Layer>
    </g>
  );
};

// ------------------------------------------------------------------ C: fourteen suns, the last one lights
const SunFace: React.FC<{x: number; y: number; r: number; on: number; rot: number}> = ({x, y, r, on, rot}) => (
  <g transform={`translate(${x} ${y})`} stroke={PL} strokeWidth={2.4}>
    {Array.from({length: 12}, (_, k) => <path key={k} d={`M -6 ${-r - 4} L 0 ${-r - 20} L 6 ${-r - 4} Z`} fill={on > 0.5 ? (k % 2 ? GOLD : DUSK) : '#6a3b1e'} transform={`rotate(${k * 30 + rot})`} />)}
    <circle r={r} fill={hexMix('#6a3b1e', GOLD, on)} />
    <path d={`M ${-r * 0.45} ${-r * 0.1} C ${-r * 0.3} ${-r * 0.3} ${-r * 0.1} ${-r * 0.3} 0 ${-r * 0.1}`} fill="none" strokeWidth={2} />
    <path d={`M ${r * 0.1} ${-r * 0.1} C ${r * 0.2} ${-r * 0.3} ${r * 0.4} ${-r * 0.3} ${r * 0.5} ${-r * 0.1}`} fill="none" strokeWidth={2} />
    <path d={`M ${-r * 0.3} ${r * 0.35} C 0 ${r * 0.5} ${r * 0.2} ${r * 0.45} ${r * 0.35} ${r * 0.3}`} fill="none" strokeWidth={2} />
    {on > 0 && <circle r={r * 1.8 * on} fill={GOLD} opacity={0.2 * on} stroke="none" />}
  </g>
);
const TheDay: React.FC<SceneProps> = ({f}) => {
  const t = f / 30;
  const last = span(f, 14, 40);
  const dawn = span(f, 0, MID4 - S(4) + 10);
  const cam: Cam = {x: 0, y: 0, z: 0.04 * dawn};
  return (
    <g>
      <Layer p={0.08} cam={cam}><rect x={-300} y={-300} width={W + 600} height={H + 600} fill={hexMix('#2a1a3a', DUSK, dawn)} /></Layer>
      <Layer p={0.15} cam={cam}>
        {Array.from({length: 14}, (_, i) => <SunFace key={i} x={200 + (i % 7) * 113} y={300 + Math.floor(i / 7) * 150} r={36} on={i < 13 ? 1 : last} rot={i === 13 ? f * 1.2 : 0} />)}
      </Layer>
      <Layer p={0.35} cam={cam}>
        <circle cx={540} cy={lerp(1420, 1180, dawn)} r={150} fill={GOLD} stroke={PL} strokeWidth={4} />
        <rect x={-300} y={1300} width={W + 600} height={800} fill="#3a2418" stroke={PL} strokeWidth={4} />
      </Layer>
      <Layer p={0.6} cam={cam}>
        <Kutir x={280} y={1440} s={1.1} />
        <ThroneOfSandals x={700} y={1440} s={0.55} t={t} glow={dawn} />
        <rect x={-300} y={1440} width={W + 600} height={700} fill="#2a1a12" stroke={PL} strokeWidth={4} />
      </Layer>
    </g>
  );
};

// ------------------------------------------------------------------ D: the Pushpaka halts; Rama's order
const Order: React.FC<SceneProps> = ({f, id}) => {
  const t = f / 30;
  const g = f + MID4;
  const close = span(g, S(5) - 24, S(5) + 12);
  const point = span(g, S(5), S(5) + 30);              // "go": Rama points the way
  const bless = span(g, S(6) + 20, S(6) + 50);         // "let him be king": the open, blessing hand
  const rise = span(g, E(6) - 24, E(6) + 6);           // Hanuman rises to leap
  const cam: Cam = {x: 0, y: 0, z: 0.05 * span(g, S(5), E(6))};
  const ramaNear = bless === 0 ? mixArm({a: 20, b: 30, hand: 'open'}, {a: 95, b: 0, hand: 'open'}, point) : mixArm({a: 95, b: 0, hand: 'open'}, {a: 120, b: 10, hand: 'abhaya'}, bless);
  return (
    <g>
      {close < 1 && (
        <g opacity={1 - close}>
          <Layer p={0.06} cam={cam}><rect x={-300} y={-300} width={W + 600} height={H + 600} fill={SKY} />
            <rect x={-300} y={900} width={W + 600} height={1400} fill={hexMix(SKY, DUSK, 0.55)} /></Layer>
          <Layer p={0.2} cam={cam}><PCloud x={-60} y={380} w={420} /><PCloud x={660} y={540} w={380} /></Layer>
          <Layer p={0.35} cam={cam}><g transform="translate(540 1500) scale(0.62) translate(-540 -1500)"><Ayodhya y={1500} t={t} /><River y={1500} h={260} t={t} id={`${id}-sar`} /></g></Layer>
          <Layer p={0.6} cam={cam}><Pushpaka x={560} y={900} s={0.62} t={0.4}><Crew t={t} raise={0} hanuman /></Pushpaka></Layer>
        </g>
      )}
      {close > 0 && (
        <g opacity={close}>
          <Layer p={0.06} cam={cam}><rect x={-300} y={-300} width={W + 600} height={H + 600} fill={hexMix(SKY, '#7a1f16', 0.5)} />
            {Array.from({length: 30}, (_, i) => <circle key={i} cx={(i * 173) % W} cy={160 + (i * 89) % 700} r={2.4} fill={WD} opacity={0.7} />)}</Layer>
          <Layer p={0.2} cam={cam}><PCloud x={-100} y={1180} w={560} t={t} /><PCloud x={560} y={1260} w={520} t={t + 1} /></Layer>
          <Layer p={0.5} cam={cam}>
            {/* inside the Pushpaka's golden hall */}
            <rect x={-300} y={1440} width={W + 600} height={600} fill={GOLD} stroke={PL} strokeWidth={4} />
            {Array.from({length: 22}, (_, i) => <circle key={i} cx={-280 + i * 72} cy={1470} r={9} fill={i % 3 === 0 ? RED : i % 3 === 1 ? '#2e7d4f' : '#3b5fb0'} stroke={PL} strokeWidth={2} />)}
            <g transform="translate(330 1460) scale(1.05)"><Glory x={10} y={-960} t={t} /></g>
            <At x={330} y={1460} s={1.05}><Figure look={LOOKS.rama} t={t} far={{a: 4, b: 6, hand: 'fist'}} near={ramaNear} bow /></At>
            <At x={790} y={lerp(1460, 1380, rise)} s={0.95} dir={-1}>
              <Figure look={LOOKS.hanuman} t={t} stance={rise > 0.5 ? 'stand' : 'kneel'} far={NAMASTE} near={NAMASTE} head={10 * (1 - rise) - 4} lean={8 * (1 - rise)} gaze={0.6} />
            </At>
          </Layer>
        </g>
      )}
    </g>
  );
};

// ------------------------------------------------------------------ E: the flight over the meeting rivers
const Flight: React.FC<SceneProps> = ({f, id}) => {
  const t = f / 30;
  const len = Math.max(20, S(7) - 8 - (E(6) + 6));
  const k = span(f, 0, len);
  const cam: Cam = {x: 60 * k, y: 0, z: 0};
  return (
    <g>
      <defs>
        {waterPattern(`${id}-g`, (f * 1.6) % 80, 0, '#2d5aa8')}
        {waterPattern(`${id}-y`, (f * 1.2) % 80, 0, '#1b2550')}
      </defs>
      <Layer p={0.2} cam={cam}><rect x={-300} y={-300} width={W + 600} height={H + 600} fill="#3f7a3a" />
        {Array.from({length: 20}, (_, i) => <path key={i} d={`M -300 ${i * 100} L ${W + 300} ${i * 100 + 140}`} stroke="#2a5a2a" strokeWidth={4} strokeDasharray="40 18" />)}</Layer>
      <Layer p={0.4} cam={cam}>
        <path d="M -300 500 C 200 600 400 900 560 1100 L 700 1100 C 520 860 300 520 -300 380 Z" fill={`url(#${id}-g)`} stroke={PL} strokeWidth={4} />
        <path d="M 1400 420 C 1000 560 760 900 620 1100 L 720 1100 C 860 920 1060 640 1400 560 Z" fill={`url(#${id}-y)`} stroke={PL} strokeWidth={4} />
        <path d="M 560 1100 C 500 1400 700 1700 600 2200 L 840 2200 C 900 1700 720 1400 720 1100 Z" fill={`url(#${id}-g)`} stroke={PL} strokeWidth={4} />
        {[[200, 700], [900, 1500], [300, 1600]].map(([x, y], i) => <SalTree key={i} x={x} y={y} s={0.6} t={t + i} />)}
      </Layer>
      <Layer p={0.6} cam={cam}><PCloud x={-60} y={300} w={420} t={t} /><PCloud x={640} y={1500} w={460} t={t + 1} /></Layer>
      <Layer p={0.9} cam={cam}><FlyingHanuman x={lerp(-260, 1250, k)} y={lerp(1300, 760, k)} s={0.42} t={t} /></Layer>
    </g>
  );
};

// ------------------------------------------------------------------ F: Nandigram; Hanuman lands; Bharat swoons
const Nandigram: React.FC<SceneProps> = ({f}) => {
  const t = f / 30;
  const g = f + S(7) - 10;
  const toThrone = span(g, S(8) - 6, S(8) + 50);
  const back = span(g, S(9) - 30, S(9) + 10);
  const land = span(g, S(9) - 40, S(9) + 6);
  const swoon = span(g, S(10) + 10, S(10) + 40);
  const burst = span(g, S(10) + 30, S(10) + 90);
  const cam: Cam = {
    x: lerp(lerp(70, -170, toThrone), 0, back),
    y: lerp(lerp(-60, -140, toThrone), 0, back),
    z: lerp(lerp(0.14, 0.26, toThrone), 0.04, back),
  };
  const hx = lerp(1250, 860, land), hy = lerp(700, 1500, land);
  return (
    <g>
      <Layer p={0.08} cam={cam}><rect x={-300} y={-300} width={W + 600} height={H + 600} fill={RED} />
        {Array.from({length: 20}, (_, i) => <circle key={i} cx={(i * 157) % 1000 + 40} cy={140 + (i * 241) % 560} r={3} fill={WD} opacity={0.8} />)}</Layer>
      <Layer p={0.15} cam={cam}><circle cx={860} cy={340} r={66} fill={GOLD} stroke={PL} strokeWidth={3} />
        {Array.from({length: 14}, (_, i) => <path key={i} d="M -5 -84 L 0 -100 L 5 -84 Z" fill={GOLD} stroke={PL} strokeWidth={2} transform={`translate(860 340) rotate(${i * 25.7})`} />)}</Layer>
      <Layer p={0.25} cam={cam}>
        {[90, 1000].map((x, i) => <SalTree key={x} x={x} y={1000} s={1.0} t={t + i} />)}
        <rect x={-300} y={960} width={W + 600} height={1200} fill="#c98a52" stroke={PL} strokeWidth={4} />
        <path d="M 1300 960 C 1060 1000 940 1060 900 1140 C 860 1220 960 1300 1300 1360 Z" fill="#e8b860" stroke={PL} strokeWidth={3} />
        <Dots d="M 1300 960 C 1060 1000 940 1060 900 1140" n={14} r={2.6} />
      </Layer>
      <Layer p={0.4} cam={cam}><Kutir x={220} y={1260} s={1.5} /></Layer>
      <Layer p={0.5} cam={cam}><ThroneOfSandals x={700} y={1420} s={0.9} t={t} glow={0.5 + 0.5 * toThrone} /></Layer>
      <Layer p={0.6} cam={cam}>
        {/* darbha mat, and Bharat seated on it facing the throne and the road */}
        <path d="M 160 1560 L 560 1560 L 600 1610 L 120 1610 Z" fill="#b5893e" stroke={PL} strokeWidth={3} />
        {Array.from({length: 12}, (_, i) => <path key={i} d={`M ${140 + i * 38} 1608 L ${170 + i * 34} 1562`} stroke="#6a4a1e" strokeWidth={2} />)}
        <At x={380} y={1580} s={0.78}>
          <Figure look={LOOKS.bharat} t={t} stance="sit" far={mixArm(NAMASTE, {a: 40, b: 10, hand: 'open'}, swoon)} near={mixArm(NAMASTE, {a: 70, b: 10, hand: 'open'}, swoon)}
            lean={-38 * swoon} head={-6 * land + 10 * (1 - span(g, S(7), S(7) + 40)) - 22 * swoon} closed={swoon > 0.5}
            gaze={Math.max(0.4, land)} tears={span(g, S(9) + 10, S(9) + 40)} blinkOff={0.7} />
        </At>
        <rect x={-300} y={1640} width={W + 600} height={600} fill="#a8723f" stroke={PL} strokeWidth={4} />
        {Array.from({length: 4}, (_, i) => <path key={i} d={`M -300 ${1680 + i * 50} L ${W + 300} ${1680 + i * 50}`} stroke="#8a5a2b" strokeWidth={3} strokeDasharray="30 14" />)}
      </Layer>
      <Layer p={0.75} cam={cam}><FireAltar x={120} y={1760} s={1.0} t={t} k={1 - 0.5 * burst} /></Layer>
      {land > 0 && (
        <Layer p={0.62} cam={cam}>
          {land < 1
            ? <FlyingHanuman x={hx} y={hy - 300} s={0.3} t={t} dir={-1} />
            : <At x={880} y={1640} s={0.7} dir={-1}><Figure look={LOOKS.hanuman} t={t} far={NAMASTE} near={NAMASTE} head={6} gaze={0.3} blinkOff={2.2} /></At>}
        </Layer>
      )}
      {burst > 0 && burst < 1 && (
        <Layer p={0.65} cam={cam}>
          {[0, 1, 2].map((k) => <circle key={k} cx={380} cy={1300} r={80 + 900 * Math.max(0, burst - k * 0.15)} fill="none" stroke={GOLD} strokeWidth={10} opacity={(1 - burst) * 0.8} />)}
        </Layer>
      )}
    </g>
  );
};

// ------------------------------------------------------------------ G: the sandals set on Rama's feet
const Petals: React.FC<{f: number; n?: number}> = ({f, n = 40}) => (
  <g stroke={PL} strokeWidth={1.6}>
    {Array.from({length: n}, (_, i) => {
      const x = (i * 263) % W, v = 3 + (i % 5);
      const y = ((i * 431 + f * v) % (H + 200)) - 100;
      return <ellipse key={i} cx={x + 20 * Math.sin(f / 20 + i)} cy={y} rx={7} ry={12} fill={i % 3 ? '#f08fa8' : i % 2 ? GOLD : WD} transform={`rotate(${(f * 3 + i * 40) % 360} ${x} ${y})`} />;
    })}
  </g>
);
const Return: React.FC<SceneProps> = ({f}) => {
  const t = f / 30;
  const dur = E(11) - S(11);
  const lower = span(f, 6, Math.max(30, dur * 0.55));     // Bharat lowers the sandals to Rama's feet
  const lift = span(f, dur * 0.7, dur + 20);               // Rama reaches to raise him
  const cam: Cam = {x: 0, y: 0, z: 0.05 * span(f, 0, dur)};
  const bArm = mixArm({a: 70, b: 60, hand: 'open'}, {a: 40, b: 10, hand: 'open'}, lower);
  return (
    <g>
      <Layer p={0.06} cam={cam}><rect x={-300} y={-300} width={W + 600} height={H + 600} fill={GOLD} />
        {Array.from({length: 26}, (_, i) => <circle key={i} cx={(i * 197) % W} cy={120 + (i * 311) % 900} r={3} fill={WD} />)}</Layer>
      <Layer p={0.2} cam={cam}><g transform="translate(540 1260) scale(0.6) translate(-540 -1260)"><Ayodhya y={1260} t={t} /></g></Layer>
      <Layer p={0.4} cam={cam}><rect x={-300} y={1260} width={W + 600} height={900} fill="#c98a52" stroke={PL} strokeWidth={4} />
        <Dots d="M -300 1290 C 200 1290 800 1290 1380 1290" n={60} r={2.4} /></Layer>
      <Layer p={0.6} cam={cam}>
        <g transform="translate(700 1700) scale(1.05)"><Glory x={-10} y={-960} t={t} /></g>
        <At x={700} y={1700} s={1.05} dir={-1}><Figure look={LOOKS.rama} t={t} far={{a: 4, b: 6, hand: 'fist'}} near={mixArm(REST, {a: 50, b: 30, hand: 'open'}, lift)} bow head={6} gaze={0.5} /></At>
        <Paduka x={lerp(470, 640, lower)} y={lerp(1520, 1690, lower)} s={0.42} glow={lower} rot={90} />
        <At x={300} y={1700} s={0.9}><Figure look={LOOKS.bharat} t={t} stance="kneel" far={bArm} near={bArm} lean={18 * lower} head={10 - 14 * lift} tears={1} gaze={0.6 * lift} blinkOff={0.9} /></At>
      </Layer>
      <Layer p={0.9} cam={cam}><Petals f={f} /></Layer>
    </g>
  );
};

// ------------------------------------------------------------------ H: his face
const Face: React.FC<SceneProps> = ({f}) => {
  const t = f / 30;
  const cam: Cam = {x: 0, y: 0, z: 0.05 * span(f, 0, E(12) - S(12) + 20)};
  return (
    <g>
      <Layer p={0.08} cam={cam}><rect x={-300} y={-300} width={W + 600} height={H + 600} fill={RED} /></Layer>
      <Layer p={0.2} cam={cam}>
        <circle cx={540} cy={820} r={470} fill="none" stroke={GOLD} strokeWidth={4} strokeDasharray="3 14" />
        <circle cx={540} cy={820} r={400} fill="#8a1f16" />
        <g opacity={0.35}><ThroneOfSandals x={880} y={1500} s={1.1} t={t} glow={1} /></g>
      </Layer>
      <Layer p={0.5} cam={cam}>
        <At x={470} y={2300} s={2.9}><Figure look={LOOKS.bharat} t={t} stance="sit" far={NAMASTE} near={NAMASTE} gaze={0.8} head={-6} tears={1} /></At>
      </Layer>
    </g>
  );
};

// ------------------------------------------------------------------ J: Ayodhya tonight (amavasya: no moon)
const Lamps: React.FC<SceneProps> = ({f, id}) => {
  const t = f / 30;
  const end = FRAMES - S(13) + 10;
  const cam: Cam = {x: 0, y: 30 * span(f, 0, end), z: 0.05 * span(f, 0, end)};
  const lit = span(f, 6, 70);
  return (
    <g>
      <Layer p={0.08} cam={cam}><NightSky seed={71} /></Layer>
      <Layer p={0.2} cam={cam}><Pushpaka x={540} y={lerp(420, 560, span(f, 0, end))} s={0.3} t={t} glow={1} /></Layer>
      <Layer p={0.35} cam={cam}>
        <Ayodhya y={1260} t={t} lit={lit} night />
        {[40, 1040].map((x, i) => <SalTree key={x} x={x} y={1260} s={0.9} t={t + i} />)}
      </Layer>
      <Layer p={0.5} cam={cam}>
        <River y={1260} h={420} t={t} id={`${id}-sar`} fill="#1b2550" />
        {Array.from({length: 9}, (_, i) => (
          <Diya key={i} x={(i * 131 + f * (0.6 + (i % 3) * 0.2)) % (W + 200) - 100} y={1360 + (i % 3) * 110} s={0.9} t={t} lit={span(f, 20 + i * 4, 40 + i * 4)} ph={i * 1.3} />
        ))}
      </Layer>
      <Layer p={0.7} cam={cam}>
        <rect x={-300} y={1680} width={W + 600} height={500} fill="#2a1a12" stroke={PL} strokeWidth={4} />
        {[0, 1].map((row) => {
          const n = 9 + row * 2, y = 1740 + row * 90, s = 1.0 + row * 0.25;
          return Array.from({length: n}, (_, i) => (
            <Diya key={`${row}-${i}`} x={540 + (i - (n - 1) / 2) * (920 / (n - 1))} y={y} s={s} t={t} lit={span(f, 10 + row * 14 + Math.abs(i - (n - 1) / 2) * 5, 26 + row * 14 + Math.abs(i - (n - 1) / 2) * 5)} ph={i * 1.7 + row} />
          ));
        })}
      </Layer>
      {f > end - 60 && <rect x={-300} y={-300} width={W + 600} height={H + 600} fill="#000" opacity={span(f, end - 60, end - 10)} />}
    </g>
  );
};

const SCENES: Scene[] = [
  {start: 0, C: Approach, id: 'A'},
  {start: S(2) - 10, C: Vow, id: 'B', tin: {type: 'scroll', d: 18}},
  {start: S(4), C: TheDay, id: 'C', tin: {type: 'iris', d: 20, cx: 540, cy: 1000}},
  {start: MID4, C: Order, id: 'D', tin: {type: 'cut', d: 1}},
  {start: E(6) + 6, C: Flight, id: 'E', tin: {type: 'cut', d: 1}},
  {start: S(7) - 10, C: Nandigram, id: 'F', tin: {type: 'scroll', d: 16}},
  {start: S(11), C: Return, id: 'G', tin: {type: 'iris', d: 20, cx: 540, cy: 1300}},
  {start: S(12), C: Face, id: 'H', tin: {type: 'scroll', d: 16}},
  {start: S(13), C: Lamps, id: 'J', tin: {type: 'iris', d: 22, cx: 540, cy: 1400}},
];

export const STORY_FRAMES = FRAMES;
export const BharatStory: React.FC<{audio?: string; warp?: {hi: number[]; en: number[]}}> = ({audio = 'episodes/002-bharat-vow/mix.wav', warp}) => (
  <ClothStory audio={audio} frames={FRAMES} scenes={SCENES} warp={warp} />
);
