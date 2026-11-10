import React from 'react';
import {Composition} from 'remotion';
import {EPISODES} from './episodes';
import {PATTA_FRAMES, StyleMadhubani, StylePattachitra} from './kit/pattachitra';
import {CharacterSheet} from './kit/CharacterSheet';
import {CharacterSheet2} from './kit/CharacterSheet2';
import {FBCover, Highlight, Profile, ProfileNamed, YTBanner} from './brand/BrandAssets';
import {EvidenceCover, EvidenceStory, EvidenceThumb} from './episodes/e005_ramayana_evidence/Story';
import E005_TEXTS from '../../../episodes/005-ramayana-evidence/tools/texts.json';
import {CHAPTERS as E005_CH} from './episodes/e005_ramayana_evidence/shots';
import {CUTS as E005_CUTS} from './episodes/e005_ramayana_evidence/timing';
const E005_TITLES: Record<string, string> = Object.fromEntries(Object.entries(E005_TEXTS.chapters).map(([c, t]) => [c, t.cover.title]));

const FPS = 30;

export const Root: React.FC = () => (
  <>
    {EPISODES.map((e) => {
      const en = {audio: `episodes/${e.slug}/mix.wav`};
      const hi = {audio: `episodes/${e.slug}/mix_hi.wav`, warp: e.hiWarp};
      return (
        <React.Fragment key={e.id}>
          <Composition id={`${e.id}-long-hi`} component={e.Story} durationInFrames={e.hiFrames} fps={FPS} width={1920} height={1080} defaultProps={hi} />
          <Composition id={`${e.id}-long-en`} component={e.Story} durationInFrames={e.frames} fps={FPS} width={1920} height={1080} defaultProps={en} />
          <Composition id={`${e.id}-short-hi`} component={e.Story} durationInFrames={e.hiFrames} fps={FPS} width={1080} height={1920} defaultProps={hi} />
          <Composition id={`${e.id}-short-en`} component={e.Story} durationInFrames={e.frames} fps={FPS} width={1080} height={1920} defaultProps={en} />
        </React.Fragment>
      );
    })}
    {/* house style references: Pattachitra (final) and Madhubani (fallback) */}
    {Object.keys(E005_CH).filter((c) => E005_CUTS[c]).map((c) => (
      <Composition key={c} id={`E005-${c}-short-hi`} component={EvidenceStory} durationInFrames={E005_CUTS[c].frames} fps={FPS}
        width={1080} height={1920} defaultProps={{cut: c, chapters: [c], audio: `episodes/005-ramayana-evidence/${c}/mix.wav`}} />
    ))}
    {Object.entries(E005_TEXTS.chapters).map(([c, t]) => (
      <Composition key={`cov-${c}`} id={`E005-${c}-cover`} component={EvidenceCover} durationInFrames={1} fps={FPS} width={1080} height={1920}
        defaultProps={{bg: t.cover.bg, title: t.cover.title, sub: t.cover.sub, n: +c.slice(2), focus: t.cover.focus as [number, number, number]}} />
    ))}
    {E005_CUTS.long && (
      <>
        <Composition id="E005-long-thumb" component={EvidenceThumb} durationInFrames={1} fps={FPS} width={1920} height={1080} />
        <Composition id="E005-long-hi" component={EvidenceStory} durationInFrames={E005_CUTS.long.frames} fps={FPS} width={1920} height={1080}
          defaultProps={{cut: 'long', chapters: Object.keys(E005_CH), audio: 'episodes/005-ramayana-evidence/long/mix.wav', titles: E005_TITLES}} />
        <Composition id="E005-long-en" component={EvidenceStory} durationInFrames={E005_CUTS.long.frames} fps={FPS} width={1920} height={1080}
          defaultProps={{cut: 'long', chapters: Object.keys(E005_CH), audio: 'episodes/005-ramayana-evidence/long_en/mix.wav', titles: E005_TITLES}} />
      </>
    )}
    <Composition id="Style-Pattachitra" component={StylePattachitra} durationInFrames={PATTA_FRAMES} fps={FPS} width={1080} height={1920} />
    <Composition id="Sheet-People" component={CharacterSheet} durationInFrames={90} fps={FPS} width={2400} height={1400} />
    <Composition id="Sheet-People2" component={CharacterSheet2} durationInFrames={90} fps={FPS} width={3000} height={2600} />
    <Composition id="Brand-YTBanner" component={YTBanner} durationInFrames={1} fps={FPS} width={2560} height={1440} />
    <Composition id="Brand-FBCover" component={FBCover} durationInFrames={1} fps={FPS} width={1640} height={624} />
    <Composition id="Brand-Profile" component={Profile} durationInFrames={1} fps={FPS} width={1080} height={1080} />
    <Composition id="Brand-ProfileNamed" component={ProfileNamed} durationInFrames={1} fps={FPS} width={1080} height={1080} />
    {['ramayana', 'mahabharata', 'puranas', 'festivals'].map((k) => (
      <Composition key={k} id={`Brand-Highlight-${k}`} component={() => <Highlight k={k} />} durationInFrames={1} fps={FPS} width={1080} height={1080} />
    ))}
    <Composition id="Style-Madhubani" component={StyleMadhubani} durationInFrames={1} fps={FPS} width={1080} height={1920} />
  </>
);
