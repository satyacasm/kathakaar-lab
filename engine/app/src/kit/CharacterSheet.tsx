/** Character sheet for the articulated figures: a quick visual check (Remotion composition "Sheet-People"). */
import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {Figure, Glory, LOOKS} from './people';
import {Handmade, Surface} from './pattachitra';

export const CharacterSheet: React.FC = () => {
  const f = useCurrentFrame();
  const t = f / 30;
  const cell = (x: number, y: number, s: number, node: React.ReactNode) => <g transform={`translate(${x} ${y}) scale(${s})`}>{node}</g>;
  return (
    <AbsoluteFill style={{background: '#a8281f'}}>
      <svg viewBox="0 0 2400 1400" width="100%" height="100%">
        <Handmade id="cs" wobble={2} paper={[0.55, 0.4, 0.3]} cloth />
        <g filter="url(#cs-wob)">
          <rect width={2400} height={1400} fill="#a8281f" />
          {cell(300, 1250, 1, <><Glory x={10} y={-960} t={t} /><Figure look={LOOKS.rama} t={t} far={{a: 20, b: 40, hand: 'fist'}} near={{a: 60, b: 80, hand: 'abhaya'}} bow /></>)}
          {cell(760, 1250, 1, <Figure look={LOOKS.hanuman} t={t} stance="kneel" far={{a: 70, b: 50}} near={{a: 75, b: 45, hand: 'joined'}} head={6} />)}
          {cell(1180, 1250, 1, <Figure look={LOOKS.bharat} t={t} stance="sit" far={{a: 40, b: 80}} near={{a: 45, b: 75, hand: 'joined'}} gaze={0.5} />)}
          {cell(1600, 1250, 1, <Figure look={LOOKS.bharat} t={t} stance="kneel" far={{a: 160, b: 20, hand: 'open'}} near={{a: 165, b: 15, hand: 'open'}} head={10} />)}
          {cell(2000, 1250, 0.9, <Figure look={LOOKS.sita} t={t} far={{a: 10, b: 20}} near={{a: 30, b: 70, hand: 'open'}} />)}
          {cell(2250, 1250, 0.9, <Figure look={LOOKS.lakshmana} t={t} far={{a: 10, b: 10, hand: 'fist'}} near={{a: 40, b: 90, hand: 'joined'}} bow />)}
        </g>
        <Surface id="cs" mottle={0.45} />
      </svg>
    </AbsoluteFill>
  );
};
