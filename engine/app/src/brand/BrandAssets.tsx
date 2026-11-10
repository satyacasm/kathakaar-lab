/**
 * Social profile assets for Kathakaar: profile picture, YouTube banner, Facebook cover, YouTube watermark and
 * Instagram highlight covers. The painted art is AI-generated (Higgsfield, Z Image; see brand/social/ASSETS note);
 * the name, tagline and borders are drawn here so the Devanagari is exact and the platform safe zones are respected.
 * Render: npx remotion still src/index.ts Brand-<name> <out.png>
 */
import React from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import {Dots, PL, WD} from '../kit/pattachitra';

const GOLD = '#f2c14e';
const RED = '#a8281f';
const DEV = 'Kohinoor Devanagari, Devanagari Sangam MN, Noto Sans Devanagari, sans-serif';
const LAT = 'Georgia, "Times New Roman", serif';

/**
 * The AI paintings aren't centred on their canvases, so they're placed by measured anchors (in source pixels, 2048
 * wide): the emblem medallion's centre and diameter, and the panorama's diya. See brand/social/SETUP.md.
 */
const EMBLEM = {src: 'brand/emblem_b.png', size: 2048, cx: 852, cy: 948, d: 1550, bg: '#9e3334'};
const PANO = {src: 'brand/panorama_b.png', w: 2048, h: 1152, cx: 960, cy: 759};
/** Draw the emblem with its medallion centred at (x, y) and diameter d (output pixels). */
const Emblem: React.FC<{x: number; y: number; d: number}> = ({x, y, d}) => {
  const k = d / EMBLEM.d;
  return <Img src={staticFile(EMBLEM.src)} style={{position: 'absolute', left: x - EMBLEM.cx * k, top: y - EMBLEM.cy * k, width: EMBLEM.size * k, height: EMBLEM.size * k}} />;
};
/** Draw the panorama scaled by k with its diya at x and the top edge at top. */
const Pano: React.FC<{k: number; x: number; top: number}> = ({k, x, top}) => (
  <Img src={staticFile(PANO.src)} style={{position: 'absolute', left: x - PANO.cx * k, top, width: PANO.w * k, height: PANO.h * k}} />
);

/** A red cloth name plate with gold rules and white dots (the house banner), centred at (x, y). */
const Plate: React.FC<{x: number; y: number; w: number; h: number; children: React.ReactNode}> = ({x, y, w, h, children}) => (
  <g transform={`translate(${x} ${y})`}>
    <path d={`M ${-w / 2 - 50} ${-h / 2} L ${w / 2 + 50} ${-h / 2} L ${w / 2 + 14} 0 L ${w / 2 + 50} ${h / 2} L ${-w / 2 - 50} ${h / 2} L ${-w / 2 - 14} 0 Z`} fill={RED} stroke={PL} strokeWidth={6} strokeLinejoin="round" />
    <rect x={-w / 2} y={-h / 2 + 14} width={w} height={h - 28} fill="none" stroke={GOLD} strokeWidth={5} />
    {[-h / 2 + 30, h / 2 - 30].map((y) => <Dots key={y} d={`M ${-w / 2 + 14} ${y} C ${-w / 6} ${y} ${w / 6} ${y} ${w / 2 - 14} ${y}`} n={Math.floor(w / 26)} r={3} />)}
    {children}
  </g>
);
const Name: React.FC<{y: number; size: number; latin?: number}> = ({y, size, latin = 0.42}) => (
  <g>
    <text x={0} y={y} textAnchor="middle" fontFamily={DEV} fontWeight={700} fontSize={size} fill={WD} stroke={PL} strokeWidth={size * 0.035} paintOrder="stroke">कथाकार</text>
    {latin > 0 && <text x={0} y={y + size * 0.62} textAnchor="middle" fontFamily={LAT} fontWeight={700} fontSize={size * latin} letterSpacing={size * 0.08} fill={GOLD}>KATHAKAAR</text>}
  </g>
);

// ------------------------------------------------------------------ YouTube banner 2560x1440 (safe 1546x423 centre)
export const YTBanner: React.FC = () => (
  <AbsoluteFill style={{background: RED}}>
    <Pano k={1.45} x={1280} top={-230} />
    <svg viewBox="0 0 2560 1440" width={2560} height={1440} style={{position: 'absolute', inset: 0}}>
      {/* the safe zone (visible on every device) is x 507-2053, y 508-931; the diya sits at its centre */}
      <Plate x={810} y={700} w={520} h={250}><Name y={40} size={150} latin={0} /></Plate>
      <Plate x={1750} y={700} w={520} h={250}>
        <text x={0} y={-8} textAnchor="middle" fontFamily={LAT} fontWeight={700} fontSize={66} letterSpacing={5} fill={GOLD}>KATHAKAAR</text>
        <text x={0} y={70} textAnchor="middle" fontFamily={DEV} fontWeight={700} fontSize={50} fill={WD}>शास्त्रों से सच्ची कथाएँ</text>
      </Plate>
    </svg>
  </AbsoluteFill>
);

// ------------------------------------------------------------------ Facebook cover 1640x624 (mobile shows the centre ~1230x624)
export const FBCover: React.FC = () => (
  <AbsoluteFill style={{background: RED}}>
    <Pano k={0.9} x={820} top={-400} />
    <svg viewBox="0 0 1640 624" width={1640} height={624} style={{position: 'absolute', inset: 0}}>
      <Plate x={440} y={360} w={380} h={190}><Name y={34} size={110} latin={0} /></Plate>
      <Plate x={1200} y={360} w={380} h={190}>
        <text x={0} y={-8} textAnchor="middle" fontFamily={LAT} fontWeight={700} fontSize={50} letterSpacing={4} fill={GOLD}>KATHAKAAR</text>
        <text x={0} y={50} textAnchor="middle" fontFamily={DEV} fontWeight={700} fontSize={38} fill={WD}>शास्त्रों से सच्ची कथाएँ</text>
      </Plate>
    </svg>
  </AbsoluteFill>
);

// ------------------------------------------------------------------ profile picture 1080x1080 (shown as a circle)
export const Profile: React.FC = () => (
  <AbsoluteFill style={{background: EMBLEM.bg}}>
    <Emblem x={540} y={540} d={1000} />
  </AbsoluteFill>
);
/** The same emblem with the name under it: for places that show a square (Facebook posts, thumbnails' corner). */
export const ProfileNamed: React.FC = () => (
  <AbsoluteFill style={{background: EMBLEM.bg}}>
    <Emblem x={540} y={450} d={760} />
    <svg viewBox="0 0 1080 1080" width={1080} height={1080} style={{position: 'absolute', inset: 0}}>
      <Plate x={540} y={930} w={600} h={190}><Name y={40} size={120} latin={0} /></Plate>
    </svg>
  </AbsoluteFill>
);

// ------------------------------------------------------------------ Instagram highlight covers 1080x1080 (circle crop)
const HIGHLIGHTS: Record<string, [string, string]> = {
  ramayana: ['रामायण', '#1b2550'],
  mahabharata: ['महाभारत', '#2e7d4f'],
  puranas: ['पुराण', '#7a2a8a'],
  festivals: ['त्योहार', '#b3261e'],
};
export const Highlight: React.FC<{k: string}> = ({k}) => {
  const [label, bg] = HIGHLIGHTS[k] ?? HIGHLIGHTS.ramayana;
  return (
    <AbsoluteFill style={{background: bg}}>
      <svg viewBox="0 0 1080 1080" width={1080} height={1080}>
        <circle cx={540} cy={540} r={470} fill="none" stroke={GOLD} strokeWidth={14} />
        {Array.from({length: 72}, (_, i) => <circle key={i} cx={540 + 420 * Math.cos((i * Math.PI) / 36)} cy={540 + 420 * Math.sin((i * Math.PI) / 36)} r={7} fill={WD} />)}
        <text x={540} y={600} textAnchor="middle" fontFamily={DEV} fontWeight={700} fontSize={190} fill={WD}>{label}</text>
      </svg>
    </AbsoluteFill>
  );
};
