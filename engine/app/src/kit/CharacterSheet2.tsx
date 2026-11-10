/** Character sheet for the episode 003 figures and props (Remotion composition "Sheet-People2"). */
import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {Figure, Glory, LOOKS, wristAt} from './people';
import {Handmade, Surface} from './pattachitra';
import {Chakra, Conch, Cow, FoodMountain, Garuda, JuteTorch, Ledger, Lotus, LotusSeat, Sword, Umbrella} from './props';

export const CharacterSheet2: React.FC = () => {
  const f = useCurrentFrame();
  const t = f / 30;
  const cell = (x: number, y: number, s: number, node: React.ReactNode) => <g transform={`translate(${x} ${y}) scale(${s})`}>{node}</g>;
  const up = {a: 150, b: 10, hand: 'open' as const}, out = {a: 60, b: 60, hand: 'open' as const};
  const wU = wristAt('near', up), wF = wristAt('far', {a: 40, b: 60});
  return (
    <AbsoluteFill style={{background: '#a8281f'}}>
      <svg viewBox="0 0 3000 2600" width="100%" height="100%">
        <Handmade id="cs2" wobble={2} paper={[0.55, 0.4, 0.3]} cloth />
        <g filter="url(#cs2-wob)">
          <rect width={3000} height={2600} fill="#a8281f" />
          {cell(250, 1200, 1, <><Glory x={10} y={-960} t={t} /><Figure look={LOOKS.vishnu} t={t} far={{a: 40, b: 60}} near={up} /><g transform={`translate(${wU.x} ${wU.y - 60})`}><Chakra t={t} /></g><g transform={`translate(${wF.x} ${wF.y})`}><Conch /></g></>)}
          {cell(700, 1200, 1, <Figure look={LOOKS.krishna} t={t} far={{a: 70, b: 70, hand: 'fist'}} near={{a: 60, b: 80, hand: 'abhaya'}} />)}
          {cell(1150, 1200, 1, <><Figure look={LOOKS.lakshmi} t={t} far={{a: 40, b: 60}} near={out} /><g transform={`translate(${wristAt('near', out).x} ${wristAt('near', out).y})`}><Lotus s={0.6} /></g></>)}
          {cell(1600, 1200, 1, <Figure look={LOOKS.satyabhama} t={t} far={{a: 10, b: 20}} near={{a: 40, b: 90, hand: 'joined'}} />)}
          {cell(2050, 1200, 1, <Figure look={LOOKS.devi} t={t} far={{a: 10, b: 20}} near={out} />)}
          {cell(2550, 1200, 1, <><Figure look={LOOKS.kali} t={t} far={{a: 40, b: 70, hand: 'abhaya'}} near={up} /><g transform={`translate(${wU.x} ${wU.y})`}><Sword /></g></>)}
          {cell(250, 2500, 1, <Figure look={LOOKS.bali} t={t} far={{a: 10, b: 20}} near={{a: 50, b: 60, hand: 'open'}} />)}
          {cell(650, 2500, 0.7, <><Figure look={LOOKS.vamana} t={t} far={{a: 10, b: 20}} near={{a: 30, b: 30, hand: 'fist'}} /><g transform={`translate(${wristAt('near', {a: 30, b: 30}).x} ${wristAt('near', {a: 30, b: 30}).y})`}><Umbrella /></g></>)}
          {cell(1000, 2500, 1, <Figure look={LOOKS.indra} t={t} far={{a: 40, b: 90, hand: 'joined'}} near={{a: 45, b: 85, hand: 'joined'}} lean={14} head={10} />)}
          {cell(1400, 2500, 1, <Figure look={LOOKS.naraka} t={t} far={{a: 30, b: 40, hand: 'fist'}} near={{a: 100, b: 20, hand: 'fist'}} />)}
          {cell(1780, 2500, 0.9, <Figure look={LOOKS.trader} t={t} stance="sit" far={{a: 40, b: 90, hand: 'joined'}} near={{a: 45, b: 85, hand: 'joined'}} />)}
          {cell(2150, 2500, 0.9, <><Figure look={LOOKS.villagerW} t={t} far={{a: 10, b: 20}} near={{a: 150, b: 10, hand: 'fist'}} /><g transform={`translate(${wU.x} ${wU.y})`}><JuteTorch t={t} /></g></>)}
          {cell(2600, 2500, 0.8, <><LotusSeat /><g transform="translate(0 -300)"><Ledger s={0.6} /></g></>)}
          {cell(2600, 1700, 0.5, <FoodMountain />)}
          {cell(1500, 1700, 0.45, <Garuda t={t}><g transform="scale(0.6)"><Figure look={LOOKS.krishna} t={t} stance="sit" far={{a: 40, b: 90}} near={{a: 120, b: 20, hand: 'fist'}} /></g></Garuda>)}
          {cell(400, 1600, 0.6, <Cow t={t} />)}
        </g>
        <Surface id="cs2" mottle={0.45} />
      </svg>
    </AbsoluteFill>
  );
};
