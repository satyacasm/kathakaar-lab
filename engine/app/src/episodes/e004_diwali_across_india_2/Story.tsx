/**
 * Episode 004, "Is Diwali only Rama's?" part 2: "this is part 2" and the recap (local lines 1-2), then the West,
 * Bali, Braj and the answer (script lines 15-28 = local 3-16), then the closing question and follow (local 17).
 * Scenes are shared with part 1 (episode 003, scenes.tsx); script line n plays as local line n - 12.
 *
 *  O  1-2    "भाग 2"; the diya; recap medallions: Ayodhya, the South, Bengal, Odisha
 *  H  15-17  the West: Lakshmi's door, the milk ocean, the ledger and the new year's sun
 *  J  18-21  Bali and Vamana                          K  22-25  Braj: Govardhan, Indra bows, Annakut
 *  L  26-28  the five faces of the answer; every home lit
 *  Z  17     "how is Diwali kept in your home?"; comment / like / follow / subscribe; fade
 */
import React from 'react';
import {ClothStory, Scene} from '../../kit/cloth';
import {Part2End, Part2Open} from '../e003_diwali_across_india/cards';
import {Bali, Braj, Close, LinesCtx, West, makeLines} from '../e003_diwali_across_india/scenes';
import {FRAMES, LINES} from './lines';

const L = makeLines(LINES, (n) => n - 12, FRAMES);
const {S, SL} = L;

const SCENES: Scene[] = [
  {start: 0, C: Part2Open, id: 'O'},
  {start: S(15) - 10, C: West, id: 'H', tin: {type: 'scroll', d: 18}},
  {start: S(18) - 10, C: Bali, id: 'J', tin: {type: 'scroll', d: 18}},
  {start: S(22) - 10, C: Braj, id: 'K', tin: {type: 'scroll', d: 18}},
  {start: S(26) - 10, C: Close, id: 'L', tin: {type: 'iris', d: 22, cx: 540, cy: 1480}},
  {start: SL(17) - 10, C: Part2End, id: 'Z', tin: {type: 'iris', d: 22, cx: 540, cy: 1580}},
];

export const STORY_FRAMES = FRAMES;
export const DiwaliStory2: React.FC<{audio?: string; warp?: {hi: number[]; en: number[]}}> = ({audio = 'episodes/004-diwali-across-india-2/mix.wav', warp}) => (
  <LinesCtx.Provider value={L}><ClothStory audio={audio} frames={FRAMES} scenes={SCENES} warp={warp} /></LinesCtx.Provider>
);
