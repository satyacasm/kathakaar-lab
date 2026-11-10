# Kathakaar house style (final, 7 Nov 2026)

## Look: Pattachitra (Odisha); fallback Madhubani
Reference frames: `archive/2026-11-story-test/out/style-frames/Pattachitra.png`; live reference composition `Style-Pattachitra` (and `Style-Madhubani`).
Code kit: `engine/app/src/kit/pattachitra.tsx` (characters, motifs, texture, layers) and `kit/geometry.tsx` (shared shapes).

- **Figures:** profile faces with a long, tapering eye drawn frontally, sharp nose, rounded chin, thick black outline (`PL #120c0a`), flat fills, conch-white (`WD #f6efdc`) dot ornament along garment edges, armlets and beads.
- **Palette:** red ground `#a8281f`, yellow `#f2c14e`, indigo water `#1f2a55`, green `#2e7d4f`, black, conch white. Night scenes use a black ground with white dot stars.
- **Motifs:** fan-leaf tree clumps edged in white dots; patterned water (curl rows); scalloped clouds; lotuses; fish; huts, temples, palms.
- **Frame:** the fixed layered border (black with white dots, red creeper band, yellow rule) surrounds every frame.
- **Hand-made, never AI-looking:** no gradients, glows or perfect geometry; slight line wobble (`feDisplacementMap`); uneven pigment; cloth grain; a slow line "boil" every 8 frames.
- **The divine:** Deities (Rama, Hanuman, Sita, Lakshmana…) are drawn as full traditional Pattachitra figures, faces in the long-eyed profile, iconography per Odisha patta and the text (Satyam, 7 Nov 2026); cosmic or formless manifestations (e.g. the divine child of the pralaya) stay light and silhouette. Mythology gets no humour.
- **Figures:** `kit/people.tsx` (articulated: shoulder/elbow angles, stand/kneel/sit, props, `LOOKS` per character), places in `kit/places.tsx` (Pushpaka, Ayodhya, river, temples, throne, hut), drawn from the text's own descriptions.

## Motion
- Every scene is a **multiplane**: each element on its own depth layer (`<Layer p=0..1>`; sky, moon, sprays, far/mid/near waves, back and front tree clumps, characters, foreground water, lotuses), with a slow camera drift or push. The border never moves.
- Small, slow, devotional movements: breathing, blinking, beard sway, leaf sway, wave drift, halo rotation. Nothing bouncy.
- **Transitions** (in `SCENES`): `scroll` (a creeper band sweeps across like a cloth scroll unrolling), `iris` (a lotus ring opens from a point of light), `irisOut` (the old scene shrinks into a sphere), whiteout into or out of divine light, and hard cuts only on stressed words.

## Formats
- **Short / Reel:** 1080×1920, the cloth fills the frame.
- **Long (YouTube):** 1920×1080. For now the portrait cloth hangs centred on a patterned wall; proper widescreen scenes are planned for long-form episodes.

## Public copy (rule of 8 Nov 2026)
The art style is internal. Never name it (Pattachitra, Odisha patta or similar) in anything published: captions, hashtags, titles, descriptions, tags, bios, channel and Page texts, or on-screen text. Use "animated stories" / "एनिमेटेड कथाएँ", or nothing.
