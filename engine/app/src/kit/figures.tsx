/**
 * Pattachitra figures and props beyond the sage, in the house idiom (thick black line, flat colour, white-dot
 * ornament, long frontal eye on a profile face). Coordinates are local: the figure's chest is near (0, 140) and the
 * waist-up body ends at y = 380, like PattaSage; place them with a transform.
 * Divine figures (DivineLight) are light and silhouette only: no faces, no features (project rule).
 */
import React from 'react';
import {Dots, PL, WD, almond, smooth} from './pattachitra';

const GOLD = '#f2c14e';
const RED = '#b3261e';
const SKIN = '#c98f5a';      // a darker, sun-worn skin for the ascetic prince
const SKIN_D = '#a8723f';
const BARK = '#8a5a2b';      // valkala: bark cloth

export type HermitPose = 'namaste' | 'hold' | 'offer' | 'rest';

/**
 * Bharat as a young ascetic: no beard, matted hair falling loose, bark cloth, a thin body.
 * look 0..1 lifts the gaze (towards the road / Rama); bow 0..1 lowers the head; tears 0..1 shows a tear line.
 * pose: namaste (palms joined), hold (both hands raised above the head, carrying), offer (hands forward, low), rest.
 */
export const PattaHermit: React.FC<{f: number; pose?: HermitPose; look?: number; bow?: number; tears?: number; thin?: number}> = ({
  f, pose = 'namaste', look = 0, bow = 0, tears = 0, thin = 1,
}) => {
  const t = f / 30;
  const headRot = -4 * look + 10 * bow + 0.3 * Math.sin(t * 1.2);
  const blink = (t % 4.3) < 0.12 ? 0.1 : 1;
  const breathe = 1 + 0.007 * Math.sin(t * 2.0);
  const hair = 1.2 * Math.sin(t * 1.4);
  const head = `rotate(${headRot} 0 60)`;
  const w = 1 - 0.12 * thin;   // narrower shoulders and chest when worn thin
  return (
    <g stroke={PL} strokeWidth={2.6} strokeLinejoin="round">
      {/* matted hair (jata): a knot on top and long locks down the back */}
      <g transform={head}>
        <g transform={`translate(-30 -20) skewX(${hair}) translate(30 20)`}>
          <path d="M -40 -40 C -78 -10 -84 70 -70 150 C -62 186 -46 200 -34 196 C -44 150 -46 80 -24 30 Z" fill="#3a2418" />
          {[0, 1, 2, 3].map((i) => <path key={i} d={`M ${-50 - i * 4} ${-10 + i * 6} C ${-64 - i * 3} 60 ${-60 - i * 2} 130 ${-46 - i * 4} 186`} fill="none" stroke={WD} strokeWidth={1} opacity={0.6} />)}
        </g>
        <path d="M -42 -50 C -48 -88 -26 -116 -4 -118 C 18 -116 26 -88 14 -52 Z" fill="#3a2418" />
        {[-64, -80, -96].map((y, i) => <path key={i} d={`M ${-38 + i * 3} ${y + 8} C -20 ${y} 0 ${y} ${10 - i * 2} ${y + 8}`} fill="none" stroke={WD} strokeWidth={1.4} />)}
        <circle cx={-14} cy={-122} r={9} fill="#3a2418" />
      </g>
      {/* body: bark cloth over one shoulder, ribs showing when thin */}
      <g transform={`translate(0 380) scale(${w} ${breathe}) translate(0 -380)`}>
        <path d="M -26 58 C -30 90 -60 110 -74 140 C -84 200 -82 300 -78 380 L 70 380 C 72 300 70 220 58 172 C 50 140 34 112 18 80 Z" fill={SKIN} />
        {thin > 0 && [0, 1, 2, 3].map((i) => <path key={i} d={`M ${-40 + i * 2} ${180 + i * 22} C -10 ${172 + i * 22} 20 ${174 + i * 22} 44 ${186 + i * 22}`} fill="none" stroke={SKIN_D} strokeWidth={2} opacity={0.8 * thin} />)}
        <path d="M -78 250 C -40 236 20 236 70 250 L 70 380 L -78 380 Z" fill={BARK} />
        <path d="M 18 82 C 40 120 60 180 70 250 L 50 250 C 40 190 26 130 6 92 Z" fill={BARK} />
        {[0, 1, 2, 3, 4].map((i) => <path key={i} d={`M ${-70 + i * 32} 258 C ${-66 + i * 32} 300 ${-70 + i * 32} 340 ${-66 + i * 32} 378`} fill="none" stroke="#5a3a1a" strokeWidth={2.4} />)}
        <path d="M -78 250 C -40 236 20 236 70 250" fill="none" stroke={RED} strokeWidth={8} />
        <Dots d="M -76 248 C -40 234 20 234 68 248" n={12} r={2} />
      </g>
      {/* head: young profile, no beard; long frontal eye */}
      <g transform={head}>
        <path d="M -26 60 C -54 32 -54 -28 -24 -48 C -4 -62 22 -56 38 -38 C 44 -30 46 -20 48 -12 L 68 8 C 64 12 56 14 52 16 L 50 28 C 46 40 40 48 30 52 C 18 58 -4 62 -26 60 Z" fill={SKIN} />
        <path d="M 30 52 C 24 44 26 36 34 34" fill="none" strokeWidth={1.6} />
        <g transform={`translate(0 -14) scale(1 ${blink}) translate(0 14)`}>
          <path d="M -8 -14 C 10 -30 40 -28 56 -12 C 38 -2 10 -2 -8 -14 Z" fill={WD} />
          <circle cx={30 + 3 * look} cy={-14 - 3 * look + 2 * bow} r={6.2} fill={PL} />
        </g>
        <path d="M -8 -14 L -24 -10" strokeWidth={2.4} />
        <path d={`M -2 ${-30 - 2 * look} C 16 ${-42 - 3 * look} 40 ${-40 - 3 * look} 54 ${-26 - 2 * look}`} fill="none" strokeWidth={3.4} strokeLinecap="round" />
        <path d="M 22 -46 L 42 -34" stroke={RED} strokeWidth={4} />
        <path d="M 40 30 C 46 32 50 30 52 28" fill="none" strokeWidth={2} />
        {tears > 0 && <path d={`M 40 -6 C 42 ${8 + 30 * tears} 38 ${20 + 40 * tears} 40 ${26 + 44 * tears}`} fill="none" stroke={WD} strokeWidth={3} opacity={tears} strokeLinecap="round" />}
        <circle cx={-6} cy={14} r={6} fill="#5a2416" />
      </g>
      {/* rudraksha mala */}
      {Array.from({length: 11}, (_, i) => { const u = i / 10; return <circle key={i} cx={-18 + u * 66 - 36 * u * (1 - u)} cy={66 + 160 * u * (1 - u) * 1.5 + u * 70} r={3.6} fill="#5a2416" strokeWidth={1} />; })}
      {pose === 'namaste' && (
        <g>
          <path d="M -36 150 C -28 190 0 212 30 208 C 50 204 66 190 76 178" fill="none" stroke={PL} strokeWidth={22} strokeLinecap="round" />
          <path d="M -36 150 C -28 190 0 212 30 208 C 50 204 66 190 76 178" fill="none" stroke={SKIN_D} strokeWidth={17} strokeLinecap="round" />
          <path d="M 0 140 C 4 180 16 208 36 212 C 56 210 70 194 82 176" fill="none" stroke={PL} strokeWidth={25} strokeLinecap="round" />
          <path d="M 0 140 C 4 180 16 208 36 212 C 56 210 70 194 82 176" fill="none" stroke={SKIN} strokeWidth={20} strokeLinecap="round" />
          <path d="M 74 186 C 76 158 84 124 100 92 C 106 88 110 92 108 100 C 104 130 98 160 92 190 Z" fill={SKIN} />
        </g>
      )}
      {pose === 'hold' && (
        <g>
          {/* both forearms raised, hands meeting above the head where the sandals rest */}
          <path d="M -40 150 C -70 110 -60 10 -30 -150" fill="none" stroke={PL} strokeWidth={22} strokeLinecap="round" />
          <path d="M -40 150 C -70 110 -60 10 -30 -150" fill="none" stroke={SKIN_D} strokeWidth={17} strokeLinecap="round" />
          <path d="M 20 140 C 70 100 70 0 40 -150" fill="none" stroke={PL} strokeWidth={25} strokeLinecap="round" />
          <path d="M 20 140 C 70 100 70 0 40 -150" fill="none" stroke={SKIN} strokeWidth={20} strokeLinecap="round" />
        </g>
      )}
      {pose === 'offer' && (
        <g>
          {/* both hands forward and low, palms up, holding something out */}
          <path d="M -36 150 C -20 220 60 250 140 236" fill="none" stroke={PL} strokeWidth={22} strokeLinecap="round" />
          <path d="M -36 150 C -20 220 60 250 140 236" fill="none" stroke={SKIN_D} strokeWidth={17} strokeLinecap="round" />
          <path d="M 0 140 C 10 210 80 236 160 224" fill="none" stroke={PL} strokeWidth={25} strokeLinecap="round" />
          <path d="M 0 140 C 10 210 80 236 160 224" fill="none" stroke={SKIN} strokeWidth={20} strokeLinecap="round" />
          <path d="M 150 214 C 176 210 196 218 198 228 C 182 238 164 238 150 234 Z" fill={SKIN} />
        </g>
      )}
      {pose === 'rest' && (
        <g>
          <path d="M -36 150 C -40 220 -30 300 -10 340" fill="none" stroke={PL} strokeWidth={22} strokeLinecap="round" />
          <path d="M -36 150 C -40 220 -30 300 -10 340" fill="none" stroke={SKIN_D} strokeWidth={17} strokeLinecap="round" />
          <path d="M 0 140 C 20 210 40 280 60 330" fill="none" stroke={PL} strokeWidth={25} strokeLinecap="round" />
          <path d="M 0 140 C 20 210 40 280 60 330" fill="none" stroke={SKIN} strokeWidth={20} strokeLinecap="round" />
        </g>
      )}
    </g>
  );
};

/** Wooden sandals (paduka) with gold inlay and a toe knob; one pair, seen from above at an angle. */
export const Paduka: React.FC<{x: number; y: number; s?: number; glow?: number; rot?: number}> = ({x, y, s = 1, glow = 0, rot = 0}) => (
  <g transform={`translate(${x} ${y}) rotate(${rot}) scale(${s})`} stroke={PL} strokeWidth={3}>
    {glow > 0 && <ellipse rx={150} ry={110} fill={GOLD} opacity={0.28 * glow} stroke="none" />}
    {[-46, 46].map((dx, i) => (
      <g key={i} transform={`translate(${dx} 0) rotate(${i ? 6 : -6})`}>
        <path d="M -30 -80 C -40 -40 -36 50 -26 80 C -14 96 14 96 26 80 C 36 50 40 -40 30 -80 C 20 -98 -20 -98 -30 -80 Z" fill="#a8723f" />
        <path d="M -20 -70 C -28 -36 -26 44 -18 70 C -8 82 8 82 18 70 C 26 44 28 -36 20 -70 C 12 -84 -12 -84 -20 -70 Z" fill={GOLD} strokeWidth={2} />
        <Dots d="M -14 -60 C -20 -20 -18 30 -12 64" n={8} r={2} />
        <Dots d="M 14 -60 C 20 -20 18 30 12 64" n={8} r={2} />
        <circle cy={-46} r={11} fill={RED} />
        <circle cy={-46} r={4} fill={GOLD} strokeWidth={1.4} />
      </g>
    ))}
  </g>
);

/** A fire altar (agni kund): stepped brick base and flat, layered Pattachitra flames. k 0..1 is the blaze. */
export const FireAltar: React.FC<{x: number; y: number; s?: number; t: number; k?: number}> = ({x, y, s = 1, t, k = 1}) => {
  const flame = (h: number, w: number, ph: number, fill: string) => {
    const sw = 10 * Math.sin(t * 7 + ph), sw2 = 8 * Math.sin(t * 9.3 + ph * 1.7);
    return <path d={`M ${-w} 0 C ${-w} ${-h * 0.4} ${-w * 0.3 + sw2} ${-h * 0.6} ${sw} ${-h} C ${w * 0.3 + sw2} ${-h * 0.6} ${w} ${-h * 0.4} ${w} 0 Z`} fill={fill} />;
  };
  const hk = 0.25 + 0.75 * k;
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`} stroke={PL} strokeWidth={3} strokeLinejoin="round">
      <g transform={`translate(0 -60) scale(1 ${hk})`}>
        {flame(260, 90, 0, '#b3261e')}
        <g transform="translate(-40 0)">{flame(170, 50, 1.3, '#e8742a')}</g>
        <g transform="translate(44 0)">{flame(190, 54, 2.1, '#e8742a')}</g>
        {flame(150, 46, 0.7, GOLD)}
        <g transform="translate(0 -10)">{flame(70, 20, 2.9, WD)}</g>
      </g>
      {[0, 1, 2].map((i) => <circle key={i} cx={-60 + i * 60 + 12 * Math.sin(t * 3 + i)} cy={-200 * hk - ((t * 80 + i * 70) % 200)} r={4} fill={GOLD} strokeWidth={1.4} opacity={k} />)}
      <path d="M -130 -60 L 130 -60 L 112 -20 L -112 -20 Z" fill="#b5542e" />
      <path d="M -150 -20 L 150 -20 L 150 30 L -150 30 Z" fill="#8a3a1e" />
      {[-110, -60, -10, 40, 90].map((bx) => <path key={bx} d={`M ${bx} -20 L ${bx} 30`} strokeWidth={2} />)}
      <path d="M -150 5 L 150 5" strokeWidth={2} />
      <Dots d="M -110 -40 C -40 -42 40 -42 110 -40" n={12} r={2} />
    </g>
  );
};

/**
 * A divine presence: light and silhouette only. A haloed, crowned standing outline filled with light, no features.
 * glow 0..1 brightens the halo; bow raises a bow silhouette over the shoulder (Rama).
 */
export const DivineLight: React.FC<{x: number; y: number; s?: number; t: number; glow?: number; bow?: boolean; tone?: string}> = ({
  x, y, s = 1, t, glow = 1, bow = false, tone = '#e8a92c',
}) => (
  <g transform={`translate(${x} ${y}) scale(${s})`} stroke={PL} strokeWidth={3}>
    <circle cy={-300} r={210 + 8 * Math.sin(t * 1.5)} fill={GOLD} opacity={0.22 * glow} stroke="none" />
    <circle cy={-300} r={150} fill={RED} />
    <circle cy={-300} r={136} fill={GOLD} />
    <circle cy={-300} r={120} fill={WD} />
    <g transform={`translate(0 -300) rotate(${t * 12})`}>
      {Array.from({length: 36}, (_, i) => <circle key={i} cx={Math.cos((i / 36) * Math.PI * 2) * 143} cy={Math.sin((i / 36) * Math.PI * 2) * 143} r={2.4} fill={WD} stroke="none" />)}
    </g>
    {bow && <path d="M 90 -470 C 170 -330 170 -110 90 30" fill="none" stroke={PL} strokeWidth={9} />}
    {bow && <path d="M 90 -470 L 90 30" fill="none" stroke={WD} strokeWidth={2} />}
    {/* crowned head, shoulders, long robe: one silhouette of light */}
    <path d="M -22 -400 L -14 -440 L 0 -420 L 14 -440 L 22 -400 Z" fill={GOLD} />
    <circle cy={-370} r={34} fill={tone} />
    <path d="M -34 -330 C -80 -320 -100 -280 -104 -220 L -96 0 L 96 0 L 104 -220 C 100 -280 80 -320 34 -330 Z" fill={tone} />
    <path d="M -96 0 L -120 140 L 120 140 L 96 0 Z" fill={tone} />
    <Dots d="M -100 -230 C -40 -250 40 -250 100 -230" n={14} r={2.4} />
    <path d="M -104 -220 C -40 -236 40 -236 104 -220" fill="none" stroke={RED} strokeWidth={6} />
  </g>
);

/** Divine feet of light (for the sandals being laid at them): two soft gold feet on a lotus. */
export const DivineFeet: React.FC<{x: number; y: number; s?: number; t: number}> = ({x, y, s = 1, t}) => (
  <g transform={`translate(${x} ${y}) scale(${s})`} stroke={PL} strokeWidth={3}>
    <ellipse cy={20} rx={260} ry={120} fill={GOLD} opacity={0.2 + 0.05 * Math.sin(t * 2)} stroke="none" />
    {Array.from({length: 10}, (_, i) => <path key={i} d="M 0 0 C -24 -30 -18 -80 0 -104 C 18 -80 24 -30 0 0 Z" fill={i % 2 ? '#f08fa8' : WD} transform={`translate(0 60) rotate(${-90 + i * 20}) scale(1.6)`} />)}
    {[-60, 60].map((dx, i) => (
      <g key={i} transform={`translate(${dx} 0) scale(${i ? -1 : 1} 1)`}>
        <path d="M -30 -110 C -46 -60 -40 10 -24 40 C -10 56 22 54 30 30 C 40 -10 34 -70 20 -110 C 8 -126 -20 -126 -30 -110 Z" fill="#e8a92c" />
        {[0, 1, 2, 3, 4].map((k) => <circle key={k} cx={-24 + k * 11} cy={-118 + Math.abs(k - 1.5) * 4} r={7 - k * 0.6} fill="#e8a92c" />)}
      </g>
    ))}
  </g>
);

/** A small flying light: Hanuman as a streak of gold with a faint silhouette at its head; dir 1 = to the right. */
export const FlyingLight: React.FC<{x: number; y: number; s?: number; t: number; dir?: number; trail?: number}> = ({x, y, s = 1, t, dir = 1, trail = 1}) => (
  <g transform={`translate(${x} ${y}) scale(${dir * s} ${s})`} stroke={PL} strokeWidth={2.6}>
    <path d={`M 0 -26 C ${-260 * trail} -40 ${-520 * trail} -6 ${-700 * trail} 0 C ${-520 * trail} 6 ${-260 * trail} 40 0 26 Z`} fill={GOLD} opacity={0.6} />
    <path d={`M 0 -12 C ${-200 * trail} -18 ${-380 * trail} -4 ${-480 * trail} 0 C ${-380 * trail} 4 ${-200 * trail} 18 0 12 Z`} fill={WD} opacity={0.8} stroke="none" />
    <circle r={46 + 3 * Math.sin(t * 6)} fill={GOLD} />
    <circle r={32} fill={WD} />
    {/* the silhouette: arm forward, body stretched, tail curling behind */}
    <path d="M 30 -6 C 10 -16 -20 -14 -40 -4 C -50 8 -40 16 -20 14 C 0 12 20 10 30 -6 Z" fill="#e8a92c" />
    <path d={`M -40 0 C -70 ${-30 + 8 * Math.sin(t * 5)} -100 ${-40 + 8 * Math.sin(t * 5)} -90 -70`} fill="none" stroke="#e8a92c" strokeWidth={6} strokeLinecap="round" />
  </g>
);

/** A diya (clay oil lamp) with a flickering flame; lit 0..1 grows the flame in. */
export const Diya: React.FC<{x: number; y: number; s?: number; t: number; lit?: number; ph?: number}> = ({x, y, s = 1, t, lit = 1, ph = 0}) => {
  const fl = 1 + 0.08 * Math.sin(t * 11 + ph) + 0.05 * Math.sin(t * 17 + ph * 2);
  const l = smooth(lit);
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`} stroke={PL} strokeWidth={2.4}>
      {l > 0 && <circle cy={-30} r={46 * l} fill={GOLD} opacity={0.25 * l} stroke="none" />}
      {l > 0 && <path d={almond(44 * l * fl, 12 * l)} transform={`translate(${2 * Math.sin(t * 7 + ph)} -20) rotate(-90)`} fill={GOLD} />}
      {l > 0 && <path d={almond(22 * l * fl, 6 * l)} transform="translate(0 -18) rotate(-90)" fill={WD} strokeWidth={1.2} />}
      <path d="M -34 -8 C -30 14 30 14 34 -8 C 44 -10 46 -14 40 -16 L -40 -16 C -46 -14 -44 -10 -34 -8 Z" fill="#b5542e" />
      <Dots d="M -28 -6 C -14 4 14 4 28 -6" n={6} r={1.6} />
    </g>
  );
};

/** Ayodhya skyline: palace domes, towers and flags, flat colour, white-dot ornament. lit 0..1 lights the windows. */
export const Skyline: React.FC<{y: number; t: number; lit?: number; fill?: string}> = ({y, t, lit = 0, fill = '#d9a25a'}) => {
  const tower = (x: number, w: number, h: number, k: number) => (
    <g key={k}>
      <rect x={x - w / 2} y={y - h} width={w} height={h} fill={fill} />
      <path d={`M ${x - w / 2 - 8} ${y - h} C ${x - w / 2} ${y - h - w * 0.9} ${x + w / 2} ${y - h - w * 0.9} ${x + w / 2 + 8} ${y - h} Z`} fill="#e8b860" />
      <circle cx={x} cy={y - h - w * 0.72} r={6} fill={GOLD} />
      <path d={`M ${x} ${y - h - w * 0.72} L ${x} ${y - h - w * 0.72 - 50} L ${x + 30} ${y - h - w * 0.72 - 40 + 4 * Math.sin(t * 3 + k)} L ${x} ${y - h - w * 0.72 - 30}`} fill={RED} strokeWidth={1.8} />
      {[0.3, 0.6].map((u) => <path key={u} d={`M ${x - w / 2} ${y - h * u} L ${x + w / 2} ${y - h * u}`} strokeWidth={1.6} />)}
      {Array.from({length: Math.max(1, Math.floor(w / 40))}, (_, i) => (
        <path key={i} d={`M ${x - w / 2 + 20 + i * 40} ${y - h * 0.15} l 0 -30 c 0 -14 18 -14 18 0 l 0 30 Z`} fill={lit > 0 ? (i + k) % 3 === 0 ? GOLD : '#e8742a' : PL} opacity={lit > 0 ? 0.4 + 0.6 * lit : 1} />
      ))}
    </g>
  );
  return (
    <g stroke={PL} strokeWidth={2.6} strokeLinejoin="round">
      {[[120, 120, 300], [300, 160, 420], [540, 220, 560], [780, 160, 420], [960, 120, 320], [420, 90, 260], [660, 90, 260]].map(([x, w, h], k) => tower(x, w, h, k))}
      <rect x={-300} y={y} width={1680} height={40} fill="#b5542e" />
      <Dots d={`M -200 ${y + 20} C 300 ${y + 20} 800 ${y + 20} 1280 ${y + 20}`} n={60} r={2.4} />
    </g>
  );
};
