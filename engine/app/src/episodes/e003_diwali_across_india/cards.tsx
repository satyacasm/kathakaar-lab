/**
 * The part cards for "Is Diwali only Rama's?": the part tag on the opening, part 1's teaser and call to action,
 * part 2's opening recap and its closing question. Local line numbers (SL/EL) are each part's own lines.
 */
import React from 'react';
import {Cam, Layer, PL, WD} from '../../kit/pattachitra';
import {GOLD, H, NightSky, RED, SceneProps, W, lerp, span} from '../../kit/cloth';
import {Diya} from '../../kit/figures';
import {Figure, LOOKS} from '../../kit/people';
import {Chakra, Hill, JuteTorch, RegionBanner} from '../../kit/props';
import {Banner, Bust, Hook, Medallion, useL} from './scenes';

const FONT = 'Kohinoor Devanagari, Devanagari Sangam MN, Noto Sans Devanagari, sans-serif';

/** Social icons drawn in the house style: a gold disc, a dark glyph, a Devanagari label under it. */
const Icon: React.FC<{x: number; y: number; k: number; kind: 'like' | 'comment' | 'follow' | 'bell'; label: string; pulse?: number}> = ({x, y, k, kind, label, pulse = 0}) => (
  <g transform={`translate(${x} ${y}) scale(${0.78 * (0.5 + 0.5 * k) * (1 + 0.08 * pulse)})`} opacity={k} stroke={PL} strokeWidth={4} strokeLinejoin="round">
    <circle r={92} fill={GOLD} />
    <circle r={78} fill="none" stroke={RED} strokeWidth={5} />
    {kind === 'like' && <path d="M 0 40 C -70 -6 -60 -62 -26 -62 C -8 -62 0 -46 0 -40 C 0 -46 8 -62 26 -62 C 60 -62 70 -6 0 40 Z" fill={RED} />}
    {kind === 'comment' && <g><path d="M -54 -44 L 54 -44 C 64 -44 70 -38 70 -28 L 70 18 C 70 28 64 34 54 34 L -6 34 L -34 58 L -30 34 L -54 34 C -64 34 -70 28 -70 18 L -70 -28 C -70 -38 -64 -44 -54 -44 Z" fill={WD} />{[-30, 0, 30].map((cx) => <circle key={cx} cx={cx} cy={-5} r={8} fill={PL} stroke="none" />)}</g>}
    {kind === 'follow' && <g><circle cx={-14} cy={-28} r={24} fill={WD} /><path d="M -60 44 C -60 4 32 4 32 44 Z" fill={WD} /><path d="M 44 -24 L 44 20 M 22 -2 L 66 -2" stroke={RED} strokeWidth={12} strokeLinecap="round" /></g>}
    {kind === 'bell' && <g><path d="M -44 30 C -40 10 -40 -20 -30 -36 C -20 -52 20 -52 30 -36 C 40 -20 40 10 44 30 Z" fill={WD} /><path d="M -56 30 L 56 30" strokeWidth={8} strokeLinecap="round" /><circle cy={44} r={11} fill={WD} /><path d="M 64 -40 C 74 -30 74 -10 66 0 M -64 -40 C -74 -30 -74 -10 -66 0" fill="none" strokeWidth={5} /></g>}
    <text x={0} y={150} textAnchor="middle" fontSize={40} fontWeight={700} fill={WD} stroke="none" fontFamily={FONT}>{label}</text>
  </g>
);

const Night: React.FC<{cam: Cam; seed: number; f: number; children?: React.ReactNode}> = ({cam, seed, children}) => (
  <>
    <Layer p={0.06} cam={cam}><NightSky seed={seed} /></Layer>
    <Layer p={0.3} cam={cam}>
      <rect x={-300} y={1600} width={W + 600} height={600} fill="#2a1a12" stroke={PL} strokeWidth={4} />
      {children}
    </Layer>
  </>
);
const fadeOut = (g: number, end: number) => g > end - 60 && <rect x={-300} y={-300} width={W + 600} height={H + 600} fill="#000" opacity={span(g, end - 60, end - 10)} />;

/** The krishna-lifts-the-hill emblem for a medallion. */
const Govardhan: React.FC<{t: number}> = ({t}) => (
  <g transform="translate(0 190) scale(0.22)">
    <g transform="translate(0 -1232)"><Hill w={700} h={240} t={t} /></g>
    <Figure look={LOOKS.krishnaBoy} t={t} far={{a: 30, b: 60, hand: 'open'}} near={{a: 175, b: 0, hand: 'abhaya'}} />
  </g>
);

// ------------------------------------------------------------------ part 1: the opening carries a "भाग 1" tag
export const HookPart1: React.FC<SceneProps> = (p) => {
  const {E} = useL();
  return (
    <g>
      <Hook {...p} />
      <RegionBanner x={540} y={250} text="भाग 1" k={span(p.f, 0, 16) * (1 - span(p.f, E(3), E(3) + 14))} w={260} />
    </g>
  );
};

// ------------------------------------------------------------------ part 1: "the story isn't over"; teaser; follow
export const Part1End: React.FC<SceneProps> = ({f, id}) => {
  const {SL, EL, FRAMES} = useL();
  const t = f / 30;
  const g = f + SL(15) - 10;
  const d16 = EL(16) - SL(16);
  const q = (i: number) => span(g, SL(16) + 6 + i * d16 * 0.33, SL(16) + 26 + i * d16 * 0.33);
  const cta = span(g, SL(17) - 10, SL(17) + 16);
  const cam: Cam = {x: 0, y: 0, z: 0.04 * span(g, SL(15), FRAMES)};
  const shrink = lerp(1, 0.72, cta), lift = lerp(0, -200, cta);
  return (
    <g>
      <Night cam={cam} seed={131} f={g}>
        <circle cx={540} cy={1580} r={260} fill={GOLD} opacity={0.12} />
        <Diya x={540} y={1580} s={3} t={t} lit={1} />
      </Night>
      <Layer p={0.45} cam={cam}>
        <g transform={`translate(0 ${lift}) translate(540 900) scale(${shrink}) translate(-540 -900)`}>
          <Medallion id={`${id}-q1`} x={300} y={760} r={140} k={q(0)} bg="#7a2a8a"><Bust look={LOOKS.lakshmi} t={t} /></Medallion>
          <Medallion id={`${id}-q2`} x={780} y={760} r={140} k={q(1)} bg="#3b5fb0"><Bust look={LOOKS.bali} t={t} blinkOff={1} /></Medallion>
          <Medallion id={`${id}-q3`} x={540} y={1080} r={140} k={q(2)} bg="#2e7d4f"><Govardhan t={t} /></Medallion>
        </g>
        {cta > 0 && (
          <g>
            {(['like', 'comment', 'follow', 'bell'] as const).map((kind, i) => (
              <Icon key={kind} x={210 + i * 220} y={1180} kind={kind} label={['लाइक', 'कमेंट', 'फ़ॉलो', 'सब्सक्राइब'][i]}
                k={span(g, SL(17) + 10 + i * 10, SL(17) + 26 + i * 10)} pulse={Math.max(0, Math.sin((g - SL(17) - 40 - i * 8) / 5)) * span(g, SL(17) + 40, SL(17) + 50)} />
            ))}
          </g>
        )}
      </Layer>
      <Banner f={g} at={SL(15)} text="भाग 1" y={260} w={260} until={SL(17) - 6} />
      <RegionBanner x={540} y={260} text="भाग 2 जल्द →" k={span(g, SL(17) + 50, SL(17) + 66)} w={440} />
      {fadeOut(g, FRAMES)}
    </g>
  );
};

// ------------------------------------------------------------------ part 2: "this is part 2"; the recap ring
export const Part2Open: React.FC<SceneProps> = ({f, id}) => {
  const {SL, EL} = useL();
  const t = f / 30;
  const lamp = span(f, SL(1) - 6, SL(1) + 20);
  const d2 = EL(2) - SL(2);
  const k = (i: number) => span(f, SL(2) + 4 + i * d2 * 0.16, SL(2) + 22 + i * d2 * 0.16) * (1 - span(f, SL(2) + d2 * 0.78, SL(2) + d2 * 0.9));
  const cam: Cam = {x: 0, y: 0, z: 0.05 * span(f, 0, EL(2))};
  const items: [string, string, React.ReactNode][] = [
    ['अयोध्या', RED, <Bust look={LOOKS.rama} t={t} glory />],
    ['दक्षिण', '#4a2a5a', <Chakra r={80} t={t * 0.4} />],
    ['बंगाल', '#1b2550', <Bust look={LOOKS.kali} t={t} blinkOff={1} />],
    ['ओडिशा', '#2a1a12', <g transform="translate(0 120) scale(0.7)"><JuteTorch t={t} /></g>],
  ];
  const pos = [[290, 700], [790, 700], [290, 1150], [790, 1150]];
  return (
    <g>
      <Night cam={cam} seed={139} f={f}>
        <circle cx={540} cy={1580} r={280 * lamp} fill={GOLD} opacity={0.12} />
        <Diya x={540} y={1580} s={3.2} t={t} lit={lamp} />
      </Night>
      <Layer p={0.45} cam={cam}>
        {items.map(([label, bg, node], i) => (
          <g key={label}>
            <Medallion id={`${id}-r${i}`} x={pos[i][0]} y={pos[i][1]} r={150} k={k(i)} bg={bg}>{node}</Medallion>
            <RegionBanner x={pos[i][0]} y={pos[i][1] + 200} text={label} k={k(i)} w={240} />
          </g>
        ))}
      </Layer>
      <Banner f={f} at={SL(1)} text="भाग 2" y={260} w={260} />
    </g>
  );
};

// ------------------------------------------------------------------ part 2: "how is Diwali kept in your home?"
export const Part2End: React.FC<SceneProps> = ({f}) => {
  const {SL, EL, FRAMES} = useL();
  const t = f / 30;
  const g = f + SL(17) - 10;
  const d = EL(17) - SL(17);
  const ask = span(g, SL(17), SL(17) + 20);
  const icons = span(g, SL(17) + d * 0.5, SL(17) + d * 0.5 + 16);
  const cam: Cam = {x: 0, y: 0, z: 0.04 * span(g, SL(17), FRAMES)};
  return (
    <g>
      <Night cam={cam} seed={151} f={g}>
        <circle cx={540} cy={1580} r={260} fill={GOLD} opacity={0.12} />
        <Diya x={540} y={1580} s={3} t={t} lit={1} />
      </Night>
      <Layer p={0.45} cam={cam}>
        <g transform={`translate(540 760) scale(${0.85 * (0.6 + 0.4 * ask)})`} opacity={ask} stroke={PL} strokeWidth={5} strokeLinejoin="round">
          <path d="M -400 -200 L 400 -200 C 440 -200 460 -180 460 -140 L 460 120 C 460 160 440 180 400 180 L 0 180 L -120 290 L -100 180 L -400 180 C -440 180 -460 160 -460 120 L -460 -140 C -460 -180 -440 -200 -400 -200 Z" fill={WD} />
          <path d="M -420 -170 L 420 -170" stroke={RED} strokeWidth={8} />
          <text x={0} y={-40} textAnchor="middle" fontSize={78} fontWeight={700} fill={RED} stroke="none" fontFamily={FONT}>आपके घर की दिवाली</text>
          <text x={0} y={80} textAnchor="middle" fontSize={78} fontWeight={700} fill={PL} stroke="none" fontFamily={FONT}>कैसी होती है?</text>
        </g>
        {(['comment', 'like', 'follow', 'bell'] as const).map((kind, i) => (
          <Icon key={kind} x={210 + i * 220} y={1220} kind={kind} label={['कमेंट', 'लाइक', 'फ़ॉलो', 'सब्सक्राइब'][i]} k={icons * span(g, SL(17) + d * 0.5 + i * 8, SL(17) + d * 0.5 + 16 + i * 8)} />
        ))}
      </Layer>
      {fadeOut(g, FRAMES)}
    </g>
  );
};
