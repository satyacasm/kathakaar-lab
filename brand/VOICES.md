# Narrators and sound (final, 7 Nov 2026)

| Language | Voice | Model | File |
|---|---|---|---|
| Hindi (main) | "D", rich bass, designed synthetic voice | Chatterbox Multilingual v3 (MIT, outputs carry the PerTh watermark) | `voices/narrator_hi_D_ref.wav` (clone reference) |
| English (extra YouTube track, reference cut) | "A2", warm documentary, designed synthetic voice | Qwen3-TTS 1.7B Base (Apache 2.0) cloning the reference | `voices/narrator_en_A2.wav` + `narrator_en_A2.txt` (exact words) |

Both voices were designed from quality-only descriptions with Qwen3 VoiceDesign; they imitate no real person. **Never clone anyone except Satyam.** No celebrity voices.

## Sound theme
- Original drone score in D (tanpura plucks, pads, sub-drone, bells on stressed words), synthetic SFX (thunder, wave roar, splash, rain, wind, whoosh); all made in code by `engine/audio/build_sound.py`, seeded and reproducible.
- Voice chain: high-pass, de-box, presence, air, de-ess, gentle compression, small room.
- Loudness: −14 LUFS integrated, true peak ≤ −2 dBTP before AAC; the voice stays ≥ 9 LU above music and SFX on every line.
- Hindi runs about 25% longer than English: retime the picture (warp), never speed up the voice.
