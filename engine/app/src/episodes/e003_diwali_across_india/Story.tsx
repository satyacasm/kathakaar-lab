/**
 * Episode 003, "Is Diwali only Rama's?" part 1: the North, the South and the East (script lines 1-14), then the
 * teaser for part 2 and the call to follow (local lines 15-17). Scenes live in scenes.tsx (shared with part 2,
 * episode 004); this file maps the script's line numbers onto this part's lines.ts.
 *
 *  A  1-3    "भाग 1"; a single diya; Kali and the ledger; the ring of five emblems
 *  B  4-5    Ayodhya                                  C  6      Rama is Vishnu; the discus turns south
 *  D  7-9    the South: Narakasura, Garuda, the discus    E  10   the women free; dawn lamps and kolam
 *  F  11-13  the East: Kali                           G  14     Odisha: torches for the ancestors
 *  P  15-17  "the story isn't over": Lakshmi, Bali, Govardhan; like / comment / follow / subscribe; "भाग 2"
 */
import React from 'react';
import {ClothStory, Scene} from '../../kit/cloth';
import {Part1End, HookPart1} from './cards';
import {AyodhyaScene, Bridge, East, LinesCtx, Odisha, South, SouthDawn, makeLines} from './scenes';
import {FRAMES, LINES} from './lines';

const L = makeLines(LINES, (n) => n, FRAMES);
const {S, SL} = L;

const SCENES: Scene[] = [
  {start: 0, C: HookPart1, id: 'A'},
  {start: S(4) - 10, C: AyodhyaScene, id: 'B', tin: {type: 'scroll', d: 18}},
  {start: S(6) - 10, C: Bridge, id: 'C', tin: {type: 'iris', d: 20, cx: 540, cy: 900}},
  {start: S(7) - 10, C: South, id: 'D', tin: {type: 'scroll', d: 18}},
  {start: S(10), C: SouthDawn, id: 'E', tin: {type: 'iris', d: 20, cx: 540, cy: 1300}},
  {start: S(11) - 10, C: East, id: 'F', tin: {type: 'scroll', d: 18}},
  {start: S(14) - 10, C: Odisha, id: 'G', tin: {type: 'iris', d: 20, cx: 540, cy: 1500}},
  {start: SL(15) - 10, C: Part1End, id: 'P', tin: {type: 'iris', d: 22, cx: 540, cy: 1580}},
];

export const STORY_FRAMES = FRAMES;
export const DiwaliStory: React.FC<{audio?: string; warp?: {hi: number[]; en: number[]}}> = ({audio = 'episodes/003-diwali-across-india/mix.wav', warp}) => (
  <LinesCtx.Provider value={L}><ClothStory audio={audio} frames={FRAMES} scenes={SCENES} warp={warp} /></LinesCtx.Provider>
);
