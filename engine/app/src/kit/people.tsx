/**
 * Articulated Pattachitra figures (Odisha idiom): profile face with a long frontal almond eye and sharp nose, frontal
 * torso with broad shoulders and a narrow waist, legs in profile, thick black outline, flat colour, white-dot jewellery.
 * Two arms per figure, each with a shoulder and an elbow angle, so poses animate. Stances: stand, kneel, sit.
 *
 * Local coordinates: feet at y = 0, figure ~1000 units tall, facing right (+x). Wrap in scale(-1 1) to face left.
 * Angles in degrees: arm 0 = hanging straight down, 90 = straight forward (towards the face), 180 = straight up.
 */
import React from 'react';
import {Dots, PL, WD} from './pattachitra';

export const GOLD = '#f2c14e';
export const RED = '#b3261e';
export type Arm = {a: number; b: number; hand?: 'open' | 'fist' | 'abhaya' | 'joined'};
export type Look = {
  skin: string; skinDark: string;
  head: 'jata' | 'crown' | 'monkey' | 'sita' | 'goddess' | 'kali' | 'shikha' | 'asura' | 'turban';
  dhoti: 'long' | 'knee' | 'short';
  cloth: string; clothBorder: string; clothStripe?: string;
  upper?: string;           // uttariya (shoulder cloth) colour
  thin?: boolean;           // ribs, narrow waist (Bharat)
  tail?: boolean;           // Hanuman
  quiver?: boolean;
  jewels?: boolean;         // necklace, armlets, earrings in gold
  beardless?: boolean;
  feather?: boolean;        // Krishna's peacock feather on the crown
  hair?: string;            // hair colour where it shows (default black-brown)
};
/** Female figures share the draped torso and the bindi. */
const isFem = (L: Look) => L.head === 'sita' || L.head === 'goddess' || L.head === 'kali';

export const LOOKS: Record<string, Look> = {
  // Rama returning from exile: dark-blue body, jata piled like a crown with gold bands, yellow cloth, bow and quiver
  rama: {skin: '#3b5fb0', skinDark: '#2a4588', head: 'jata', dhoti: 'long', cloth: '#f2c14e', clothBorder: RED, clothStripe: '#e0a83a', upper: '#e8742a', quiver: true, jewels: true},
  lakshmana: {skin: '#e0a85e', skinDark: '#c08a44', head: 'jata', dhoti: 'long', cloth: '#7fb069', clothBorder: RED, upper: '#f2c14e', quiver: true, jewels: true},
  sita: {skin: '#e8b77a', skinDark: '#c9955a', head: 'sita', dhoti: 'long', cloth: '#c0392b', clothBorder: GOLD, clothStripe: '#a52a1e', upper: '#c0392b', jewels: true},
  // Hanuman as in Odisha patta: mustard-gold body, crown, red loincloth, curled tail
  hanuman: {skin: '#e3a82b', skinDark: '#c08a1a', head: 'monkey', dhoti: 'short', cloth: RED, clothBorder: GOLD, tail: true, jewels: true},
  // Bharat at Nandigram: hermit's bark cloth, matted hair, worn thin
  bharat: {skin: '#c98f5a', skinDark: '#a8723f', head: 'jata', dhoti: 'knee', cloth: '#8a5a2b', clothBorder: '#5a3a1a', clothStripe: '#6e4520', thin: true},
  // E003. Vishnu and his forms: dark-blue body, tall Odisha crown, yellow pitambara
  vishnu: {skin: '#3b5fb0', skinDark: '#2a4588', head: 'crown', dhoti: 'long', cloth: '#f2c14e', clothBorder: RED, clothStripe: '#e0a83a', upper: '#e8742a', jewels: true},
  krishna: {skin: '#3b5fb0', skinDark: '#2a4588', head: 'crown', feather: true, dhoti: 'long', cloth: '#f2c14e', clothBorder: RED, clothStripe: '#e0a83a', upper: '#2e7d4f', jewels: true},
  krishnaBoy: {skin: '#3b5fb0', skinDark: '#2a4588', head: 'crown', feather: true, dhoti: 'knee', cloth: '#f2c14e', clothBorder: RED, upper: '#e8742a', jewels: true},
  vamana: {skin: '#3b5fb0', skinDark: '#2a4588', head: 'shikha', dhoti: 'knee', cloth: '#e8742a', clothBorder: '#a8281f', upper: '#f6efdc'},
  // goddesses: crowned, draped, gold
  lakshmi: {skin: '#f0b98a', skinDark: '#d09a6a', head: 'goddess', dhoti: 'long', cloth: '#c0392b', clothBorder: GOLD, clothStripe: '#a52a1e', upper: '#c0392b', jewels: true},
  satyabhama: {skin: '#e8b77a', skinDark: '#c9955a', head: 'goddess', dhoti: 'long', cloth: '#2e7d4f', clothBorder: GOLD, clothStripe: '#256a42', upper: '#2e7d4f', jewels: true},
  devi: {skin: '#f0a63a', skinDark: '#d08a22', head: 'goddess', dhoti: 'long', cloth: '#b3261e', clothBorder: GOLD, clothStripe: '#8f1d16', upper: '#b3261e', jewels: true},
  // Kali as in Bengal and Odisha patta: blue-black body, loose wild hair, red tongue, third eye, red hibiscus garland
  kali: {skin: '#24335c', skinDark: '#18223f', head: 'kali', dhoti: 'knee', cloth: '#b3261e', clothBorder: GOLD, upper: '#b3261e', jewels: true},
  // kings
  bali: {skin: '#c98f5a', skinDark: '#a8723f', head: 'crown', dhoti: 'long', cloth: '#7a2a8a', clothBorder: GOLD, clothStripe: '#5e1f6b', upper: '#f2c14e', jewels: true},
  indra: {skin: '#f0c08a', skinDark: '#d0a06a', head: 'crown', dhoti: 'long', cloth: '#3b8fb0', clothBorder: GOLD, clothStripe: '#2f7590', upper: '#f2c14e', jewels: true},
  // asuras: green or dark body, fangs and moustache, crowned
  naraka: {skin: '#5a7a3a', skinDark: '#465f2c', head: 'asura', dhoti: 'knee', cloth: '#2a1a12', clothBorder: RED, upper: '#b3261e', jewels: true},
  chanda: {skin: '#7a4a8a', skinDark: '#5e386b', head: 'asura', dhoti: 'knee', cloth: '#2e7d4f', clothBorder: GOLD, jewels: true},
  munda: {skin: '#8a5a2b', skinDark: '#6e4520', head: 'asura', dhoti: 'knee', cloth: '#3b5fb0', clothBorder: GOLD, jewels: true},
  // people
  villager: {skin: '#c98f5a', skinDark: '#a8723f', head: 'jata', dhoti: 'knee', cloth: '#f6efdc', clothBorder: RED, upper: '#e8742a'},
  villagerW: {skin: '#d9a06a', skinDark: '#b8824c', head: 'sita', dhoti: 'long', cloth: '#e8742a', clothBorder: '#2e7d4f', jewels: true},
  maiden: {skin: '#e8b77a', skinDark: '#c9955a', head: 'sita', dhoti: 'long', cloth: '#3b5fb0', clothBorder: GOLD, jewels: true},
  trader: {skin: '#d9a06a', skinDark: '#b8824c', head: 'turban', dhoti: 'long', cloth: '#f6efdc', clothBorder: RED, upper: '#b3261e'},
};

const rad = (d: number) => (d * Math.PI) / 180;
/** Arm joint positions from the shoulder: upper arm 200, forearm 180. Angle 0 = down, +90 = forward (+x). */
const armPts = (sx: number, sy: number, arm: Arm) => {
  const ex = sx + 200 * Math.sin(rad(arm.a)), ey = sy + 200 * Math.cos(rad(arm.a));
  const fa = arm.a + arm.b;
  const wx = ex + 180 * Math.sin(rad(fa)), wy = ey + 180 * Math.cos(rad(fa));
  return {ex, ey, wx, wy, fa};
};

const Limb: React.FC<{d: string; w: number; fill: string}> = ({d, w, fill}) => (
  <>
    <path d={d} fill="none" stroke={PL} strokeWidth={w + 8} strokeLinecap="round" strokeLinejoin="round" />
    <path d={d} fill="none" stroke={fill} strokeWidth={w} strokeLinecap="round" strokeLinejoin="round" />
  </>
);

/** A hand at the wrist, pointing along the forearm angle fa. */
const Hand: React.FC<{x: number; y: number; fa: number; kind: Arm['hand']; skin: string}> = ({x, y, fa, kind = 'open', skin}) => {
  if (kind === 'fist') return <circle cx={x} cy={y} r={26} fill={skin} stroke={PL} strokeWidth={3.5} />;
  if (kind === 'abhaya') {
    // palm raised and facing out, fingers up
    return (
      <g transform={`translate(${x} ${y})`} stroke={PL} strokeWidth={3.5} strokeLinejoin="round">
        <path d="M -20 10 C -24 -20 -22 -60 -14 -86 C -8 -92 0 -90 2 -82 L 6 -94 C 10 -100 18 -98 18 -90 L 20 -84 C 24 -90 32 -88 32 -80 L 30 -40 C 40 -50 52 -44 46 -32 C 36 -16 26 0 20 12 Z" fill={skin} />
        <circle cx={4} cy={-34} r={6} fill={RED} strokeWidth={1.5} />
      </g>
    );
  }
  // open / joined: a long palm with fingers together, continuing the forearm
  return (
    <g transform={`translate(${x} ${y}) rotate(${-fa})`} stroke={PL} strokeWidth={3.5} strokeLinejoin="round">
      <path d="M -22 -6 C -26 30 -18 62 -6 82 C 2 90 12 88 14 78 C 20 50 24 20 22 -6 Z" fill={skin} />
      <path d="M 14 10 C 30 16 36 30 30 40" fill="none" />
    </g>
  );
};

const Head: React.FC<{look: Look; t: number; eye: number; gaze: number; tears?: number}> = ({look, t, eye, gaze, tears = 0}) => {
  const L = look;
  const monkey = L.head === 'monkey';
  const sway = 1.2 * Math.sin(t * 1.3);
  return (
    <g strokeLinejoin="round" stroke={PL} strokeWidth={3.5}>
      {/* behind the head: halo glow for the divine is added by the caller; hair falling behind */}
      {L.head === 'jata' && (
        <g transform={`skewX(${sway})`}>
          <path d="M -58 -30 C -88 20 -86 110 -64 170 C -48 180 -36 176 -30 160 C -46 110 -48 40 -30 0 Z" fill="#2a1a12" />
          {[0, 1, 2].map((i) => <path key={i} d={`M ${-62 - i * 6} ${-10 + i * 10} C ${-74 - i * 4} 60 ${-70 - i * 3} 120 ${-52 - i * 4} 166`} fill="none" stroke={WD} strokeWidth={1.2} opacity={0.6} />)}
        </g>
      )}
      {L.head === 'sita' && (
        <path d="M -70 -60 C -100 0 -96 100 -60 190 L -20 200 C -40 120 -40 40 -20 -20 Z" fill={L.cloth} />
      )}
      {L.head === 'goddess' && (
        <path d={`M -64 -50 C -110 20 -100 140 -${70 + 4 * sway} 240 C -50 250 -30 240 -24 220 C -50 140 -44 40 -20 -20 Z`} fill={L.hair ?? '#1a120c'} />
      )}
      {L.head === 'kali' && (
        <g transform={`skewX(${sway * 2})`}>
          {Array.from({length: 11}, (_, i) => {
            const a = -150 + i * 22;
            const r = 190 + (i % 3) * 40;
            return <path key={i} d={`M -10 -40 Q ${r * 0.6 * Math.cos(((a + 12) * Math.PI) / 180)} ${-40 + r * 0.6 * Math.sin(((a + 12) * Math.PI) / 180)} ${r * Math.cos((a * Math.PI) / 180)} ${-40 + r * Math.sin((a * Math.PI) / 180) + 120} L ${r * 0.7 * Math.cos(((a + 10) * Math.PI) / 180)} ${-40 + r * 0.7 * Math.sin(((a + 10) * Math.PI) / 180) + 40} Z`} fill="#0e0a12" stroke={PL} strokeWidth={2} />;
          })}
        </g>
      )}
      {/* face */}
      {monkey ? (
        <>
          <path d="M -60 -10 C -66 -60 -34 -96 8 -94 C 34 -92 50 -78 54 -56 C 76 -50 92 -30 90 -6 C 88 16 74 30 54 34 C 40 50 10 56 -20 50 C -48 42 -62 20 -60 -10 Z" fill={L.skin} />
          <path d="M 34 -40 C 62 -40 84 -24 84 -4 C 82 14 66 26 46 26 C 30 26 22 12 24 -6 C 26 -24 28 -36 34 -40 Z" fill="#f6e3b0" />
          <path d="M 50 14 C 62 16 74 12 80 4" fill="none" strokeWidth={3} />
          <circle cx={74} cy={-14} r={3.5} fill={PL} stroke="none" />
          <path d="M -40 -30 C -50 -40 -60 -30 -54 -14 C -48 -6 -38 -10 -36 -20" fill="#f6e3b0" />
        </>
      ) : (
        <path d="M -58 -20 C -64 -70 -24 -98 12 -92 C 34 -88 46 -70 48 -44 L 68 -10 C 64 -6 56 -4 52 -2 L 54 8 C 50 12 52 16 54 18 C 50 26 46 34 38 40 C 22 54 -8 56 -30 46 C -50 34 -58 12 -58 -20 Z" fill={L.skin} />
      )}
      {/* the long frontal eye */}
      <g transform={`translate(0 ${monkey ? -40 : -38}) scale(1 ${eye}) translate(0 ${monkey ? 40 : 38})`}>
        <path d={monkey ? 'M -4 -40 C 10 -56 34 -54 46 -42 C 32 -32 10 -32 -4 -40 Z' : 'M -6 -38 C 10 -56 40 -54 58 -38 C 40 -26 12 -26 -6 -38 Z'} fill={WD} />
        <circle cx={(monkey ? 22 : 28) + 4 * gaze} cy={monkey ? -41 : -39} r={monkey ? 6.5 : 7.5} fill={PL} />
      </g>
      <path d={monkey ? 'M -2 -40 L -16 -36' : 'M -6 -38 L -24 -34'} strokeWidth={3} />
      <path d={monkey ? 'M -6 -58 C 10 -72 34 -70 48 -58' : 'M -4 -56 C 14 -70 42 -68 56 -54'} fill="none" strokeWidth={4.5} strokeLinecap="round" />
      {!monkey && L.head !== 'kali' && <path d="M 36 22 C 44 24 50 22 54 18" fill="none" strokeWidth={2.4} />}
      {L.head === 'asura' && (
        <g>
          <path d="M 30 12 C 44 4 60 6 70 0 C 66 14 52 22 34 22 Z" fill="#1a120c" strokeWidth={2} />
          <path d="M 40 22 L 44 36 L 48 22 Z" fill={WD} strokeWidth={1.6} />
          <path d="M -30 -66 C -10 -80 20 -80 40 -66" fill="none" strokeWidth={6} />
        </g>
      )}
      {L.head === 'kali' && (
        <g>
          <path d="M 36 18 C 46 22 56 20 60 16 L 58 26 C 54 30 50 30 48 28 C 50 46 46 58 42 60 C 38 56 38 40 40 28 Z" fill="#c0392b" strokeWidth={2.4} />
          <path d="M 32 18 C 42 14 54 14 62 14" fill="none" stroke={WD} strokeWidth={3} />
        </g>
      )}
      {tears > 0 && <path d={`M 42 -28 C 46 ${-10 + 20 * tears} 40 ${4 + 30 * tears} 44 ${10 + 36 * tears}`} fill="none" stroke={WD} strokeWidth={5} strokeLinecap="round" opacity={tears} />}
      {tears > 0 && <circle cx={44} cy={14 + 36 * tears} r={5} fill={WD} stroke="none" opacity={tears} />}
      {/* Vaishnava tilak; the bindi for women; Kali's third eye; ash lines for asuras */}
      {!monkey && !isFem(L) && L.head !== 'asura' && <path d="M 30 -60 L 30 -84 M 22 -62 C 22 -76 38 -76 38 -62" fill="none" stroke={WD} strokeWidth={3} />}
      {!monkey && !isFem(L) && L.head !== 'asura' && <path d="M 30 -62 L 30 -80" stroke={RED} strokeWidth={2.5} />}
      {(L.head === 'sita' || L.head === 'goddess') && <circle cx={34} cy={-66} r={6} fill={RED} strokeWidth={1.5} />}
      {L.head === 'kali' && <path d="M 30 -58 C 22 -66 22 -80 30 -88 C 38 -80 38 -66 30 -58 Z" fill={WD} strokeWidth={2} />}
      {L.head === 'kali' && <circle cx={30} cy={-73} r={4} fill={RED} stroke="none" />}
      {/* ear and earring */}
      {!monkey && <path d="M -18 -30 C -30 -30 -32 -6 -18 -4" fill={L.skinDark} strokeWidth={3} />}
      {L.jewels && <circle cx={-20} cy={16} r={11} fill={GOLD} strokeWidth={2.5} />}
      {L.jewels && (L.head === 'sita' || L.head === 'goddess') && <circle cx={58} cy={4} r={7} fill="none" stroke={GOLD} strokeWidth={3} />}
      {/* hair / headgear on top */}
      {L.head === 'jata' && (
        <g>
          <path d="M -60 -30 C -66 -74 -40 -100 -6 -96 C 20 -94 38 -84 44 -68 C 20 -82 -20 -82 -40 -60 Z" fill="#2a1a12" />
          <path d="M -46 -84 C -50 -140 -36 -200 -4 -226 C 26 -200 38 -140 32 -84 Z" fill="#2a1a12" />
          {L.jewels
            ? [-110, -140, -170].map((y, i) => <path key={i} d={`M ${-46 + i * 6} ${y} C -20 ${y - 8} 10 ${y - 8} ${34 - i * 6} ${y}`} fill="none" stroke={GOLD} strokeWidth={9} />)
            : [-110, -140, -170].map((y, i) => <path key={i} d={`M ${-46 + i * 6} ${y} C -20 ${y - 8} 10 ${y - 8} ${34 - i * 6} ${y}`} fill="none" stroke={WD} strokeWidth={1.6} />)}
          {L.jewels && <Dots d="M -44 -96 C -20 -104 10 -104 34 -96" n={9} r={2.6} />}
          {L.jewels && [[-36, -196, RED], [-2, -232, '#f08fa8'], [28, -190, RED]].map(([x, y, c], i) => (
            <g key={i} transform={`translate(${x} ${y})`}>{[0, 72, 144, 216, 288].map((r) => <ellipse key={r} cx={0} cy={-8} rx={5} ry={9} fill={c as string} strokeWidth={1.5} transform={`rotate(${r})`} />)}<circle r={4} fill={GOLD} strokeWidth={1.2} /></g>
          ))}
        </g>
      )}
      {L.head === 'monkey' && (
        <g>
          {/* Hanuman's tiered crown */}
          <path d="M -50 -80 L 40 -80 L 30 -120 L -40 -120 Z" fill={GOLD} />
          <path d="M -40 -120 L 30 -120 L 14 -176 L -24 -176 Z" fill={GOLD} />
          <path d="M -24 -176 L 14 -176 L -5 -222 Z" fill={GOLD} />
          <circle cx={-5} cy={-226} r={8} fill={RED} strokeWidth={2} />
          <Dots d="M -46 -90 C -20 -94 10 -94 36 -90" n={9} r={2.6} />
          {[-8, 18].map((x) => <circle key={x} cx={x} cy={-148} r={7} fill={RED} strokeWidth={2} />)}
          <path d="M -50 -80 C -64 -70 -70 -50 -64 -30" fill="none" stroke={GOLD} strokeWidth={8} />
        </g>
      )}
      {(L.head === 'crown' || L.head === 'asura') && (
        <g>
          {/* the tall Odisha mukuta: a band, three tiers and a finial, gems and dots */}
          <path d="M -60 -40 C -66 -74 -40 -100 -6 -96 C 20 -94 38 -84 44 -68 C 20 -80 -20 -80 -40 -56 Z" fill="#1a120c" />
          <path d="M -58 -72 L 44 -72 L 40 -104 L -54 -104 Z" fill={GOLD} />
          <path d="M -50 -104 L 36 -104 L 24 -160 L -38 -160 Z" fill={L.head === 'asura' ? '#c0392b' : GOLD} />
          <path d="M -38 -160 L 24 -160 L 12 -212 L -26 -212 Z" fill={GOLD} />
          <path d="M -26 -212 L 12 -212 L -7 -262 Z" fill={L.head === 'asura' ? '#c0392b' : GOLD} />
          <circle cx={-7} cy={-266} r={9} fill={RED} strokeWidth={2} />
          <Dots d="M -54 -88 C -20 -92 10 -92 40 -88" n={10} r={2.6} />
          {[-28, 0, 22].map((x) => <circle key={x} cx={x} cy={-132} r={7} fill={L.head === 'asura' ? GOLD : RED} strokeWidth={2} />)}
          <circle cx={-7} cy={-186} r={8} fill="#2e7d4f" strokeWidth={2} />
          {/* side flares (karnaphula) */}
          <path d="M -58 -96 C -96 -110 -110 -80 -92 -64 C -80 -74 -70 -80 -58 -80 Z" fill={GOLD} />
          {L.head === 'asura' && <path d="M -46 -104 C -70 -150 -64 -190 -40 -210 C -44 -170 -36 -136 -30 -106 Z" fill={WD} />}
          {L.head === 'asura' && <path d="M 26 -104 C 48 -150 46 -190 24 -214 C 28 -172 20 -136 14 -106 Z" fill={WD} />}
          {L.feather && (
            <g transform={`translate(18 -210) rotate(${28 + 3 * Math.sin(t * 1.5)})`}>
              <path d="M 0 0 C 30 -60 40 -150 10 -210 C -24 -150 -24 -60 0 0 Z" fill="#2e7d4f" />
              <ellipse cx={8} cy={-150} rx={20} ry={30} fill="#3b5fb0" />
              <ellipse cx={8} cy={-150} rx={10} ry={15} fill={GOLD} strokeWidth={2} />
              <path d="M 0 0 C 6 -70 10 -140 10 -200" fill="none" stroke={GOLD} strokeWidth={2.5} />
            </g>
          )}
        </g>
      )}
      {L.head === 'goddess' && (
        <g>
          <path d="M -64 -40 C -72 -96 -30 -118 10 -112 C 40 -106 56 -88 58 -64 C 30 -84 -20 -84 -50 -50 Z" fill={L.hair ?? '#1a120c'} />
          <path d="M -56 -88 L 46 -88 L 34 -130 L -44 -130 Z" fill={GOLD} />
          <path d="M -44 -130 L 34 -130 L 18 -180 L -28 -180 Z" fill={GOLD} />
          <path d="M -28 -180 L 18 -180 L -5 -222 Z" fill={GOLD} />
          <circle cx={-5} cy={-226} r={8} fill={RED} strokeWidth={2} />
          {[-24, 0, 16].map((x) => <circle key={x} cx={x} cy={-110} r={6} fill={RED} strokeWidth={1.6} />)}
          <Dots d="M -54 -96 C -20 -100 10 -100 44 -96" n={10} r={2.4} />
          <path d="M 50 -60 C 60 -40 62 -10 58 10" fill="none" stroke={GOLD} strokeWidth={5} />
        </g>
      )}
      {L.head === 'kali' && (
        <g>
          <path d="M -60 -30 C -66 -74 -40 -100 -6 -96 C 20 -94 38 -84 44 -68 C 20 -82 -20 -82 -40 -60 Z" fill="#0e0a12" />
          <path d="M -50 -84 L 40 -84 L 30 -116 L -40 -116 Z" fill={GOLD} />
          {[-36, -14, 8, 28].map((x) => <path key={x} d={`M ${x - 8} -116 L ${x} -142 L ${x + 8} -116 Z`} fill={GOLD} />)}
          <Dots d="M -48 -94 C -20 -98 10 -98 38 -94" n={9} r={2.4} />
        </g>
      )}
      {L.head === 'turban' && (
        <g>
          {/* a wrapped pagdi with a tail at the back */}
          <path d="M -60 -30 C -66 -74 -40 -100 -6 -96 C 20 -94 38 -84 44 -68 C 20 -78 -20 -78 -44 -54 Z" fill="#1a120c" />
          <path d="M -66 -56 C -70 -120 -30 -150 10 -146 C 46 -142 60 -110 54 -66 C 20 -80 -30 -80 -66 -56 Z" fill={L.upper ?? RED} />
          {[0, 1, 2].map((i) => <path key={i} d={`M ${-62 + i * 4} ${-76 - i * 20} C -20 ${-96 - i * 16} 20 ${-96 - i * 16} ${52 - i * 4} ${-80 - i * 18}`} fill="none" stroke={GOLD} strokeWidth={3} />)}
          <path d="M -64 -70 C -100 -50 -100 10 -86 40 L -70 34 C -80 6 -76 -30 -56 -56 Z" fill={L.upper ?? RED} />
          <circle cx={30} cy={-118} r={8} fill={GOLD} strokeWidth={2} />
        </g>
      )}
      {L.head === 'shikha' && (
        <g>
          {/* the young brahmachari: shaven head with a top-knot */}
          <path d="M -60 -30 C -66 -74 -40 -100 -6 -96 C 20 -94 38 -84 44 -68 C 20 -78 -20 -78 -44 -54 Z" fill={L.skinDark} />
          <path d={`M -30 -94 C -40 -130 -20 -150 ${-4 + 3 * sway} -170 C 0 -150 4 -120 -10 -96 Z`} fill="#1a120c" />
        </g>
      )}
      {L.head === 'sita' && (
        <g>
          <path d="M -64 -40 C -72 -96 -30 -118 10 -112 C 40 -106 56 -88 58 -64 C 30 -84 -20 -84 -50 -50 Z" fill={L.cloth} />
          <Dots d="M -62 -44 C -50 -90 0 -110 54 -68" n={14} r={2.4} />
          <circle cx={-6} cy={-118} r={9} fill={GOLD} strokeWidth={2} />
        </g>
      )}
    </g>
  );
};

/**
 * A full figure. stance: stand | kneel (near knee down) | sit (cross-legged). lean tips the upper body forward
 * about the hips (degrees); head tilts the head; eye 1 = open; props drawn by the caller via the hand slots.
 */
export const Figure: React.FC<{
  look: Look; t: number; stance?: 'stand' | 'kneel' | 'sit';
  far: Arm; near: Arm; lean?: number; head?: number; gaze?: number; breathe?: boolean;
  farProp?: React.ReactNode; nearProp?: React.ReactNode;   // drawn at the wrist, rotated with the forearm
  bow?: boolean;                                             // Rama's bow, held in the far hand
  mace?: boolean;                                            // Hanuman's gada, in the near hand
  blinkOff?: number; tears?: number; closed?: boolean;
}> = ({look: L, t, stance = 'stand', far, near, lean = 0, head = 0, gaze = 0, breathe = true, farProp, nearProp, bow, mace, blinkOff = 0, tears = 0, closed = false}) => {
  const drop = stance === 'stand' ? 0 : stance === 'kneel' ? 250 : 430;
  const br = breathe ? 1 + 0.008 * Math.sin(t * 2.1) : 1;
  const bt = (t + blinkOff) % 4.1;
  const eye = closed || bt < 0.12 ? 0.12 : 1;
  const sF = {x: -118, y: -842}, sN = {x: 118, y: -842};
  const fa = armPts(sF.x, sF.y, far), na = armPts(sN.x, sN.y, near);
  const waist = L.thin ? 44 : 54;
  const skin = L.skin;
  const legs = () => {
    if (stance === 'sit') {
      return (
        <g stroke={PL} strokeWidth={3.5} strokeLinejoin="round">
          <path d="M -170 -60 C -190 -150 -60 -170 40 -150 C 160 -130 230 -100 220 -40 C 200 0 -150 10 -170 -60 Z" fill={L.cloth} />
          {[0, 1, 2, 3].map((i) => <path key={i} d={`M ${-120 + i * 80} -150 C ${-110 + i * 80} -100 ${-120 + i * 80} -40 ${-110 + i * 80} 0`} fill="none" stroke={L.clothStripe ?? L.clothBorder} strokeWidth={3} />)}
          <path d="M 150 -40 C 190 -46 220 -36 226 -20 C 210 -10 180 -12 150 -20 Z" fill={skin} />
          <path d="M -170 -60 C -150 -10 120 0 220 -40" fill="none" stroke={L.clothBorder} strokeWidth={10} />
        </g>
      );
    }
    if (stance === 'kneel') {
      return (
        <g stroke={PL} strokeWidth={3.5} strokeLinejoin="round">
          {/* far leg: foot planted forward, knee up */}
          <Limb d="M 20 -300 L 150 -180 L 140 -20" w={58} fill={skin} />
          <path d="M 120 -20 C 150 -26 196 -20 204 0 L 116 0 Z" fill={skin} />
          {/* near leg: knee on the ground, shin back */}
          <Limb d="M -10 -300 L 40 -20 L -170 -20" w={62} fill={L.skinDark} />
          <path d="M -60 -320 C -90 -250 -70 -120 -20 -80 L 180 -150 C 160 -230 110 -290 70 -320 Z" fill={L.cloth} />
          <path d="M -20 -80 L 180 -150" fill="none" stroke={L.clothBorder} strokeWidth={10} />
        </g>
      );
    }
    return (
      <g stroke={PL} strokeWidth={3.5} strokeLinejoin="round">
        <Limb d="M -30 -560 L -40 -300 L -60 -40" w={64} fill={L.skinDark} />
        <Limb d="M 34 -560 L 46 -300 L 40 -40" w={66} fill={skin} />
        <path d="M -90 -40 C -60 -50 -10 -46 0 -10 L 0 0 L -90 0 Z" fill={L.skinDark} />
        <path d="M 10 -40 C 50 -50 100 -40 112 -10 L 112 0 L 10 0 Z" fill={skin} />
        {L.jewels && <path d="M -82 -46 L -24 -46 M 18 -46 L 76 -46" stroke={GOLD} strokeWidth={8} />}
      </g>
    );
  };
  const garment = () => {
    if (stance !== 'stand') return null;
    const hem = L.dhoti === 'long' ? -60 : L.dhoti === 'knee' ? -300 : -440;
    const flare = L.dhoti === 'long' ? 150 : L.dhoti === 'knee' ? 120 : 104;
    const sw = 6 * Math.sin(t * 1.6);
    return (
      <g stroke={PL} strokeWidth={3.5} strokeLinejoin="round">
        <path d={`M -92 -580 C -110 ${(-580 + hem) / 2} ${-flare} ${hem + 40} ${-flare + sw} ${hem} L ${flare + sw} ${hem} C ${flare} ${hem + 40} 110 ${(-580 + hem) / 2} 92 -580 Z`} fill={L.cloth} />
        {L.clothStripe && [-60, -20, 20, 60].map((x) => <path key={x} d={`M ${x * 0.8} -570 C ${x} ${(-570 + hem) / 2} ${x * 1.3} ${hem + 30} ${x * 1.4 + sw} ${hem}`} fill="none" stroke={L.clothStripe} strokeWidth={4} />)}
        <path d={`M ${-flare + sw} ${hem} L ${flare + sw} ${hem}`} stroke={L.clothBorder} strokeWidth={14} />
        <Dots d={`M ${-flare + 10 + sw} ${hem - 2} C ${-50 + sw} ${hem - 2} ${50 + sw} ${hem - 2} ${flare - 10 + sw} ${hem - 2}`} n={14} r={2.4} />
        {/* the front pleat (kachha) */}
        {L.dhoti !== 'short' && <path d={`M 10 -570 C 30 ${(-570 + hem) / 2} 24 ${hem + 60} ${40 + sw * 1.5} ${hem + 30} L ${70 + sw * 1.5} ${hem + 30} C 60 ${hem + 60} 56 ${(-570 + hem) / 2} 40 -570 Z`} fill={L.clothBorder} />}
        <path d="M -94 -580 C -40 -596 40 -596 94 -580" fill="none" stroke={L.clothBorder} strokeWidth={14} />
        <Dots d="M -90 -580 C -40 -594 40 -594 90 -580" n={12} r={2.4} />
      </g>
    );
  };
  const ArmG: React.FC<{s: {x: number; y: number}; p: ReturnType<typeof armPts>; arm: Arm; dark?: boolean; prop?: React.ReactNode}> = ({s, p, arm, dark, prop}) => (
    <g>
      <Limb d={`M ${s.x} ${s.y} L ${p.ex} ${p.ey} L ${p.wx} ${p.wy}`} w={dark ? 40 : 44} fill={dark ? L.skinDark : skin} />
      {L.jewels && <path d={`M ${s.x + (p.ex - s.x) * 0.28 - 22} ${s.y + (p.ey - s.y) * 0.28} l 44 0`} stroke={GOLD} strokeWidth={10} transform={`rotate(${-arm.a} ${s.x + (p.ex - s.x) * 0.28} ${s.y + (p.ey - s.y) * 0.28})`} />}
      <path d={`M ${p.wx - 20} ${p.wy} l 40 0`} stroke={L.jewels ? GOLD : '#5a3a1a'} strokeWidth={9} transform={`rotate(${-p.fa} ${p.wx} ${p.wy})`} />
      {prop && <g transform={`translate(${p.wx} ${p.wy}) rotate(${-p.fa})`}>{prop}</g>}
      <Hand x={p.wx} y={p.wy} fa={p.fa} kind={arm.hand} skin={dark ? L.skinDark : skin} />
    </g>
  );
  return (
    <g>
      {legs()}
      <g transform={`translate(0 ${drop}) rotate(${lean} 0 -560)`}>
        {/* the tail (behind everything above the hips) */}
        {L.tail && (
          <path d={`M -70 -600 C -260 -620 -300 -820 -220 -${980 + 20 * Math.sin(t * 1.7)} C -180 -1040 -120 -1030 -130 -${990 + 14 * Math.sin(t * 1.7 + 0.5)}`} fill="none" stroke={PL} strokeWidth={34} strokeLinecap="round" />
        )}
        {L.tail && (
          <path d={`M -70 -600 C -260 -620 -300 -820 -220 -${980 + 20 * Math.sin(t * 1.7)} C -180 -1040 -120 -1030 -130 -${990 + 14 * Math.sin(t * 1.7 + 0.5)}`} fill="none" stroke={L.skin} strokeWidth={26} strokeLinecap="round" />
        )}
        {/* quiver on the back, arrows over the shoulder */}
        {L.quiver && (
          <g transform="rotate(-24 -120 -760)" stroke={PL} strokeWidth={3}>
            {[-14, 0, 14].map((dx) => <path key={dx} d={`M ${-120 + dx} -960 L ${-120 + dx} -880`} strokeWidth={4} />)}
            {[-14, 0, 14].map((dx) => <path key={`f${dx}`} d={`M ${-120 + dx} -972 l -7 16 l 7 -4 l 7 4 Z`} fill={RED} strokeWidth={2} />)}
            <rect x={-150} y={-900} width={60} height={240} rx={14} fill="#8a3a1e" />
            <Dots d="M -140 -880 C -140 -820 -140 -760 -140 -680" n={8} r={2.4} />
          </g>
        )}
        {/* bow held upright in the far hand, behind the body */}
        {bow && (
          <g transform={`translate(${fa.wx} ${fa.wy})`} stroke={PL}>
            <path d="M 0 -380 C 70 -260 70 -120 0 0 C 70 120 70 260 0 380" fill="none" strokeWidth={14} />
            <path d="M 0 -380 C 70 -260 70 -120 0 0 C 70 120 70 260 0 380" fill="none" stroke="#8a3a1e" strokeWidth={8} />
            <path d="M 0 -380 L 0 380" strokeWidth={2} stroke={WD} />
            {[-300, 0, 300].map((y) => <path key={y} d={`M 30 ${y - 12} l 24 0`} stroke={GOLD} strokeWidth={7} />)}
          </g>
        )}
        <ArmG s={sF} p={fa} arm={far} dark prop={farProp} />
        {garment()}
        {/* torso */}
        <g transform={`translate(0 -600) scale(1 ${br}) translate(0 600)`} stroke={PL} strokeWidth={3.5} strokeLinejoin="round">
          <path d={`M -30 -884 C -84 -880 -128 -872 -134 -830 C -126 -760 -74 -700 ${-waist} -640 L -92 -572 L 92 -572 L ${waist} -640 C 74 -700 126 -760 134 -830 C 128 -872 84 -880 30 -884 Z`} fill={skin} />
          {L.thin && [0, 1, 2, 3].map((i) => <path key={i} d={`M ${-70 + i * 4} ${-780 + i * 26} C -20 ${-790 + i * 26} 20 ${-790 + i * 26} ${70 - i * 4} ${-780 + i * 26}`} fill="none" stroke={L.skinDark} strokeWidth={2.4} />)}
          {/* the sacred thread */}
          {!isFem(L) && L.head !== 'monkey' && <path d="M -96 -860 C -40 -760 20 -680 70 -590" fill="none" stroke={WD} strokeWidth={3.5} />}
          {/* shoulder cloth, a diagonal band */}
          {L.upper && <path d="M -134 -840 C -60 -780 20 -700 62 -600 L 90 -610 C 50 -720 -20 -800 -110 -868 Z" fill={L.upper} />}
          {L.upper && <Dots d="M -120 -846 C -50 -790 20 -710 70 -606" n={14} r={2.2} />}
          {isFem(L) && L.head !== 'kali' && <path d="M -134 -830 C -90 -700 -60 -640 -92 -572 L 92 -572 C 60 -660 90 -780 134 -830 C 60 -800 -60 -800 -134 -830 Z" fill={L.cloth} />}
          {L.thin && <path d="M -120 -850 C -60 -800 0 -760 50 -640 L 80 -650 C 40 -760 -20 -820 -90 -870 Z" fill="#6a5a4a" />}
          {/* necklace and garland */}
          {L.jewels && <path d="M -60 -872 C -40 -800 40 -800 60 -872" fill="none" stroke={GOLD} strokeWidth={9} />}
          {L.jewels && <circle cx={0} cy={-806} r={12} fill={RED} strokeWidth={2.5} />}
          {L.jewels && L.head !== 'monkey' && L.head !== 'sita' && L.head !== 'kali' && (
            <g>
              <path d="M -80 -876 C -96 -720 -40 -640 0 -624 C 40 -640 96 -720 80 -876" fill="none" stroke="#2e7d4f" strokeWidth={12} />
              {Array.from({length: 11}, (_, i) => { const u = i / 10; const x = -80 + 160 * u; const y = -876 + 250 * Math.sin(Math.PI * u); return <circle key={i} cx={x * (1 - 0.12 * Math.sin(Math.PI * u))} cy={y} r={7} fill={i % 2 ? RED : WD} strokeWidth={1.6} />; })}
            </g>
          )}
          {L.head === 'kali' && (
            <g>
              {/* a garland of red hibiscus to the knees */}
              <path d="M -90 -870 C -110 -640 -40 -520 0 -500 C 40 -520 110 -640 90 -870" fill="none" stroke="#2e7d4f" strokeWidth={6} />
              {Array.from({length: 13}, (_, i) => { const u = i / 12; const x = -90 + 180 * u; const y = -870 + 370 * Math.sin(Math.PI * u); return <g key={i} transform={`translate(${x * (1 - 0.1 * Math.sin(Math.PI * u))} ${y})`}>{[0, 72, 144, 216, 288].map((r) => <ellipse key={r} cx={0} cy={-9} rx={7} ry={10} fill="#c0392b" strokeWidth={1.4} transform={`rotate(${r})`} />)}<circle r={4} fill={GOLD} strokeWidth={1} /></g>; })}
            </g>
          )}
          {L.head === 'monkey' && <path d="M -92 -600 C -40 -612 40 -612 92 -600" fill="none" stroke={GOLD} strokeWidth={14} />}
        </g>
        <g transform={`translate(10 -930) rotate(${head}) translate(0 0)`}>
          <path d="M -26 40 L -24 80 L 30 80 L 28 34 Z" fill={skin} stroke={PL} strokeWidth={3.5} />
          <Head look={L} t={t} eye={eye} gaze={gaze} tears={tears} />
        </g>
        {/* Hanuman's mace in the near hand */}
        {mace && (
          <g transform={`translate(${na.wx} ${na.wy}) rotate(${-na.fa + 180})`} stroke={PL} strokeWidth={3.5}>
            <rect x={-9} y={-20} width={18} height={260} fill="#8a5a2b" />
            <circle cx={0} cy={250} r={62} fill={GOLD} />
            {[0, 45, 90, 135].map((r) => <path key={r} d="M -60 0 L 60 0" transform={`translate(0 250) rotate(${r})`} strokeWidth={2.5} />)}
            <circle cx={0} cy={250} r={20} fill={RED} />
          </g>
        )}
        <ArmG s={sN} p={na} arm={near} prop={nearProp} />
      </g>
    </g>
  );
};

/** The sun-like glory round the head (Valmiki): a red-gold-white disc with a rim of dots, placed behind a head. */
export const Glory: React.FC<{x: number; y: number; r?: number; t: number}> = ({x, y, r = 170, t}) => (
  <g transform={`translate(${x} ${y})`} stroke={PL} strokeWidth={3}>
    <circle r={r + 40 + 6 * Math.sin(t * 1.4)} fill={GOLD} opacity={0.25} stroke="none" />
    {Array.from({length: 24}, (_, i) => <path key={i} d={`M -9 ${-r - 6} L 0 ${-r - 34} L 9 ${-r - 6} Z`} fill={i % 2 ? GOLD : '#e8742a'} transform={`rotate(${i * 15 + t * 4})`} strokeWidth={2} />)}
    <circle r={r} fill={RED} />
    <circle r={r - 14} fill={GOLD} />
    <circle r={r - 30} fill={WD} />
  </g>
);

/** Where a hand ends up in the figure's own coordinates (lean 0), so callers can place props held upright. */
export const wristAt = (side: 'far' | 'near', arm: Arm, stance: 'stand' | 'kneel' | 'sit' = 'stand') => {
  const s = side === 'far' ? {x: -118, y: -842} : {x: 118, y: -842};
  const p = armPts(s.x, s.y, arm);
  const drop = stance === 'stand' ? 0 : stance === 'kneel' ? 250 : 430;
  return {x: p.wx, y: p.wy + drop, fa: p.fa};
};
